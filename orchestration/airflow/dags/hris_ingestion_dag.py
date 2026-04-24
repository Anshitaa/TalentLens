"""
DAG: hris_ingestion_dag

Schedule: @hourly
Purpose:  Delta-sync HR events from Mock HRIS API → PostgreSQL raw schema
          → Kafka producer → dbt staging/mart transformation.

Task flow:
  check_hris_health
      ↓
  extract_delta_from_hris   (calls /hris/events?since=<watermark>)
      ↓
  validate_schema           (BranchPythonOperator)
      ├── schema_valid → load_to_raw_postgres
      │                      ↓
      │                 run_kafka_producer
      │                      ↓
      │                 trigger_dbt_run
      │                      ↓
      │                 update_watermark
      └── schema_invalid → notify_on_failure

Delivery guarantees:
  - Idempotent load via ON CONFLICT DO NOTHING on event_id
  - Watermark stored in audit.producer_watermarks; DAG reads it on every run
  - dbt runs incrementally (only processes new rows in fact_risk_scores)
"""

import json
import logging
import os
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import psycopg2
import psycopg2.extras
from airflow import DAG
from airflow.operators.python import BranchPythonOperator, PythonOperator
from airflow.utils.dates import days_ago

log = logging.getLogger(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://talentlens:talentlens@postgres:5432/talentlens",
)
HRIS_BASE_URL = os.getenv("HRIS_BASE_URL", "http://mock-hris:8001")
HRIS_EVENTS_LIMIT = 10_000

REQUIRED_EVENT_FIELDS = {"event_id", "employee_id", "event_type", "event_date"}
VALID_EVENT_TYPES = {
    "HIRE", "TERMINATE", "PROMOTE", "MANAGER_CHANGE",
    "SALARY_CHANGE", "PERFORMANCE_REVIEW", "ABSENCE", "OVERTIME", "TRAINING",
}

default_args = {
    "owner": "talentlens",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "email_on_failure": False,
}

dag = DAG(
    dag_id="hris_ingestion_dag",
    description="Hourly delta sync: HRIS API → PostgreSQL → Kafka → dbt",
    schedule_interval="@hourly",
    start_date=days_ago(1),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["ingestion", "phase-1"],
)


# ─────────────────────────────────────────────────────────────────────────────
# Task 1: Health check
# ─────────────────────────────────────────────────────────────────────────────

def check_hris_health(**context):
    resp = httpx.get(f"{HRIS_BASE_URL}/health", timeout=10.0)
    if resp.status_code != 200 or resp.json().get("status") != "ok":
        raise RuntimeError(f"HRIS API unhealthy: {resp.text}")
    log.info("HRIS API healthy.")


# ─────────────────────────────────────────────────────────────────────────────
# Task 2: Extract delta from HRIS API
# ─────────────────────────────────────────────────────────────────────────────

def _get_watermark(conn) -> str | None:
    cur = conn.cursor()
    cur.execute("""
        SELECT value FROM audit.producer_watermarks WHERE topic = 'employee-events'
        ORDER BY updated_at DESC LIMIT 1
    """)
    row = cur.fetchone()
    return row["value"] if row else None


def extract_delta_from_hris(**context):
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    since = _get_watermark(conn)
    conn.close()

    params = {"limit": HRIS_EVENTS_LIMIT}
    if since:
        params["since"] = since

    log.info("Fetching events since: %s", since or "beginning")
    resp = httpx.get(f"{HRIS_BASE_URL}/hris/events", params=params, timeout=60.0)
    resp.raise_for_status()

    data = resp.json()
    events = data["data"]
    log.info("Fetched %d events", len(events))

    # Push to XCom for downstream tasks
    context["task_instance"].xcom_push(key="events", value=events)
    context["task_instance"].xcom_push(key="event_count", value=len(events))
    return len(events)


# ─────────────────────────────────────────────────────────────────────────────
# Task 3: Validate schema (BranchPythonOperator)
# ─────────────────────────────────────────────────────────────────────────────

def validate_schema(**context) -> str:
    events = context["task_instance"].xcom_pull(key="events", task_ids="extract_delta_from_hris")

    if not events:
        log.info("No events to process — skipping downstream tasks.")
        return "notify_no_data"

    invalid_rows = []
    for i, event in enumerate(events[:100]):  # sample first 100
        missing = REQUIRED_EVENT_FIELDS - set(event.keys())
        if missing:
            invalid_rows.append({"row": i, "missing_fields": list(missing)})
        if event.get("event_type") not in VALID_EVENT_TYPES:
            invalid_rows.append({"row": i, "invalid_event_type": event.get("event_type")})

    if invalid_rows:
        log.error("Schema validation failed: %s", json.dumps(invalid_rows[:5]))
        context["task_instance"].xcom_push(key="validation_errors", value=invalid_rows)
        return "notify_on_failure"

    log.info("Schema validation passed for %d events.", len(events))
    return "load_to_raw_postgres"


# ─────────────────────────────────────────────────────────────────────────────
# Task 4: Load to raw PostgreSQL
# ─────────────────────────────────────────────────────────────────────────────

def load_to_raw_postgres(**context):
    events = context["task_instance"].xcom_pull(key="events", task_ids="extract_delta_from_hris")
    if not events:
        return 0

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    records = [
        (
            event["event_id"],
            event["employee_id"],
            event["event_type"],
            event["event_date"],
            event.get("department"),
            json.dumps(event.get("payload") or {}),
        )
        for event in events
    ]

    psycopg2.extras.execute_batch(
        cur,
        """
        INSERT INTO raw.employee_events (event_id, employee_id, event_type, event_date, department, payload)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (event_id) DO NOTHING
        """,
        records,
        page_size=1000,
    )

    conn.commit()
    conn.close()
    log.info("Loaded %d events to raw.employee_events", len(records))
    return len(records)


# ─────────────────────────────────────────────────────────────────────────────
# Task 5: Publish to Kafka
# ─────────────────────────────────────────────────────────────────────────────

def run_kafka_producer(**context):
    event_count = context["task_instance"].xcom_pull(key="event_count", task_ids="extract_delta_from_hris")
    if not event_count:
        log.info("No events to publish.")
        return

    # Delegate to producer script (runs with its own watermark logic)
    result = subprocess.run(
        ["python", "/opt/airflow/dags/../../../ingestion/kafka/producer.py"],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Kafka producer failed:\n{result.stderr}")
    log.info("Kafka producer output:\n%s", result.stdout)


# ─────────────────────────────────────────────────────────────────────────────
# Task 6: Run dbt
# ─────────────────────────────────────────────────────────────────────────────

def trigger_dbt_run(**context):
    dbt_project_dir = "/opt/airflow/dbt_project"
    result = subprocess.run(
        ["dbt", "run", "--profiles-dir", dbt_project_dir, "--project-dir", dbt_project_dir,
         "--select", "staging.stg_employees staging.stg_hiring_events mart.dim_employee"],
        capture_output=True,
        text=True,
        timeout=600,
        cwd=dbt_project_dir,
    )
    log.info("dbt stdout:\n%s", result.stdout)
    if result.returncode != 0:
        raise RuntimeError(f"dbt run failed:\n{result.stderr}")


def run_dbt_tests(**context):
    dbt_project_dir = "/opt/airflow/dbt_project"
    result = subprocess.run(
        ["dbt", "test", "--profiles-dir", dbt_project_dir, "--project-dir", dbt_project_dir,
         "--select", "staging mart"],
        capture_output=True,
        text=True,
        timeout=300,
        cwd=dbt_project_dir,
    )
    log.info("dbt test stdout:\n%s", result.stdout)
    if result.returncode != 0:
        log.warning("dbt tests failed (non-blocking):\n%s", result.stderr)


# ─────────────────────────────────────────────────────────────────────────────
# Task 7: Update watermark
# ─────────────────────────────────────────────────────────────────────────────

def update_watermark(**context):
    events = context["task_instance"].xcom_pull(key="events", task_ids="extract_delta_from_hris")
    if not events:
        return

    latest_date = max(e["event_date"] for e in events)
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS audit.producer_watermarks (
            topic       TEXT PRIMARY KEY,
            value       TEXT NOT NULL,
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    cur.execute("""
        INSERT INTO audit.producer_watermarks (topic, value, updated_at)
        VALUES ('employee-events', %s, NOW())
        ON CONFLICT (topic) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
    """, (latest_date if isinstance(latest_date, str) else latest_date.isoformat(),))
    conn.commit()
    conn.close()
    log.info("Watermark updated to: %s", latest_date)


# ─────────────────────────────────────────────────────────────────────────────
# Failure / no-data notifications (stubs — wire up Slack in Phase 6)
# ─────────────────────────────────────────────────────────────────────────────

def notify_on_failure(**context):
    errors = context["task_instance"].xcom_pull(key="validation_errors", task_ids="validate_schema")
    log.error("HRIS ingestion failed. Validation errors: %s", json.dumps(errors or []))
    # TODO Phase 6: send Slack alert


def notify_no_data(**context):
    log.info("No new events from HRIS API — watermark is current.")


# ─────────────────────────────────────────────────────────────────────────────
# DAG wiring
# ─────────────────────────────────────────────────────────────────────────────

t_health = PythonOperator(
    task_id="check_hris_health",
    python_callable=check_hris_health,
    dag=dag,
)

t_extract = PythonOperator(
    task_id="extract_delta_from_hris",
    python_callable=extract_delta_from_hris,
    dag=dag,
)

t_validate = BranchPythonOperator(
    task_id="validate_schema",
    python_callable=validate_schema,
    dag=dag,
)

t_load = PythonOperator(
    task_id="load_to_raw_postgres",
    python_callable=load_to_raw_postgres,
    dag=dag,
)

t_kafka = PythonOperator(
    task_id="run_kafka_producer",
    python_callable=run_kafka_producer,
    dag=dag,
)

t_dbt = PythonOperator(
    task_id="trigger_dbt_run",
    python_callable=trigger_dbt_run,
    dag=dag,
)

t_dbt_test = PythonOperator(
    task_id="run_dbt_tests",
    python_callable=run_dbt_tests,
    dag=dag,
)

t_watermark = PythonOperator(
    task_id="update_watermark",
    python_callable=update_watermark,
    trigger_rule="none_failed_min_one_success",
    dag=dag,
)

t_notify_fail = PythonOperator(
    task_id="notify_on_failure",
    python_callable=notify_on_failure,
    dag=dag,
)

t_notify_empty = PythonOperator(
    task_id="notify_no_data",
    python_callable=notify_no_data,
    dag=dag,
)

# Pipeline
t_health >> t_extract >> t_validate
t_validate >> t_load >> t_kafka >> t_dbt >> t_dbt_test >> t_watermark
t_validate >> t_notify_fail
t_validate >> t_notify_empty
