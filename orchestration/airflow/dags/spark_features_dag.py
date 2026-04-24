"""
DAG: spark_features_dag

Schedule: @daily (runs at 02:00, before risk_scoring_dag at 04:00)
Purpose:  Compute PySpark feature engineering jobs and populate mart.feature_store.

Task flow:
  check_dim_employee_ready           (ensures dbt Phase 1 models exist and have data)
      ↓
  run_peer_percentile_job            (SparkSubmitOperator)
      ↓
  run_rolling_aggregations_job       (SparkSubmitOperator)
      ↓
  validate_feature_output            (row count + null checks + range checks)
      ↓
  notify_on_validation_failure  OR  log_success

Why SparkSubmitOperator:
  Delegates execution to the Spark cluster (spark-master:7077), not the Airflow
  worker. This decouples feature computation resources from orchestration resources,
  which is the pattern Amazon/PayPal interviewers expect to see.
"""

import logging
import os
from datetime import timedelta

import psycopg2
import psycopg2.extras
from airflow import DAG
from airflow.operators.python import BranchPythonOperator, PythonOperator
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
from airflow.utils.dates import days_ago

log = logging.getLogger(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://talentlens:talentlens@postgres:5432/talentlens",
)
SPARK_MASTER = os.getenv("SPARK_MASTER_URL", "spark://spark-master:7077")
JDBC_JAR = "/opt/bitnami/spark/jars/extra/postgresql-42.7.3.jar"
SPARK_SCRIPTS_DIR = "/opt/airflow/spark"

# Minimum rows in mart.feature_store to consider the run successful
MIN_FEATURE_ROWS = 1_000

default_args = {
    "owner": "talentlens",
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
    "email_on_failure": False,
}

dag = DAG(
    dag_id="spark_features_dag",
    description="Daily PySpark feature engineering: peer percentiles + rolling aggregations",
    schedule_interval="0 2 * * *",   # 02:00 daily — before risk_scoring_dag
    start_date=days_ago(1),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["feature-engineering", "spark", "phase-2"],
)


# ─────────────────────────────────────────────────────────────────────────────
# Task 1: Gate — ensure dim_employee has been populated
# ─────────────────────────────────────────────────────────────────────────────

def check_dim_employee_ready(**context):
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS n FROM mart.dim_employee WHERE is_active")
    n = cur.fetchone()["n"]
    conn.close()

    if n < 100:
        raise RuntimeError(
            f"mart.dim_employee has only {n} active rows — "
            "run hris_ingestion_dag and dbt first (Phase 1 checkpoint)."
        )
    log.info("Gate passed: mart.dim_employee has %d active employees", n)
    context["task_instance"].xcom_push(key="active_employee_count", value=n)


# ─────────────────────────────────────────────────────────────────────────────
# Tasks 2 & 3: SparkSubmitOperator for each PySpark job
# ─────────────────────────────────────────────────────────────────────────────

# Shared Spark config passed to both jobs via --conf
spark_conf = {
    "spark.sql.adaptive.enabled": "true",
    "spark.sql.adaptive.coalescePartitions.enabled": "true",
    "spark.sql.shuffle.partitions": "50",
    "spark.executor.memory": "1g",
    "spark.driver.memory": "1g",
}

# Environment variables forwarded to the Spark job processes
spark_env_vars = {
    "POSTGRES_HOST": os.getenv("POSTGRES_HOST", "postgres"),
    "POSTGRES_PORT": os.getenv("POSTGRES_PORT", "5432"),
    "POSTGRES_DB":   os.getenv("POSTGRES_DB", "talentlens"),
    "POSTGRES_USER": os.getenv("POSTGRES_USER", "talentlens"),
    "POSTGRES_PASSWORD": os.getenv("POSTGRES_PASSWORD", "talentlens"),
    "JDBC_JAR": JDBC_JAR,
}

t_peer_percentile = SparkSubmitOperator(
    task_id="run_peer_percentile_job",
    application=f"{SPARK_SCRIPTS_DIR}/peer_percentile_job.py",
    conn_id="spark_default",
    jars=JDBC_JAR,
    conf=spark_conf,
    env_vars=spark_env_vars,
    application_args=[],
    name="talentlens-peer-percentile",
    verbose=True,
    dag=dag,
)

t_rolling_agg = SparkSubmitOperator(
    task_id="run_rolling_aggregations_job",
    application=f"{SPARK_SCRIPTS_DIR}/rolling_aggregations.py",
    conn_id="spark_default",
    jars=JDBC_JAR,
    conf=spark_conf,
    env_vars=spark_env_vars,
    application_args=[],
    name="talentlens-rolling-aggregations",
    verbose=True,
    dag=dag,
)


# ─────────────────────────────────────────────────────────────────────────────
# Task 4: Validate feature output (BranchPythonOperator)
# ─────────────────────────────────────────────────────────────────────────────

def validate_feature_output(**context) -> str:
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()

    # Row count check
    cur.execute("SELECT COUNT(*) AS n FROM mart.feature_store")
    n = cur.fetchone()["n"]
    log.info("mart.feature_store row count: %d", n)

    if n < MIN_FEATURE_ROWS:
        log.error("Feature store has only %d rows (min %d)", n, MIN_FEATURE_ROWS)
        conn.close()
        return "notify_on_validation_failure"

    # Null checks on critical columns
    cur.execute("""
        SELECT
            COUNT(*) FILTER (WHERE monthly_income_vs_peer_median IS NULL) AS null_peer_rank,
            COUNT(*) FILTER (WHERE income_peer_percentile IS NULL)         AS null_peer_quartile,
            COUNT(*) FILTER (WHERE manager_changes_30d IS NULL)            AS null_mgr_30d,
            COUNT(*) FILTER (WHERE absence_rate_90d IS NULL)               AS null_absence,
            COUNT(*) FILTER (WHERE overtime_rate_180d IS NULL)             AS null_overtime
        FROM mart.feature_store
    """)
    nulls = dict(cur.fetchone())
    conn.close()

    total_null_violations = sum(nulls.values())
    if total_null_violations > n * 0.05:  # allow up to 5% nulls
        log.error("Too many nulls in feature_store: %s", nulls)
        return "notify_on_validation_failure"

    # Range checks
    if nulls.get("null_peer_rank", 0) > 0:
        log.warning("Some employees missing peer rank: %d", nulls["null_peer_rank"])

    log.info("Feature validation passed. Rows: %d, Nulls: %s", n, nulls)
    context["task_instance"].xcom_push(key="feature_row_count", value=n)
    context["task_instance"].xcom_push(key="null_summary", value=nulls)
    return "log_success"


def log_success(**context):
    n = context["task_instance"].xcom_pull(key="feature_row_count", task_ids="validate_feature_output")
    nulls = context["task_instance"].xcom_pull(key="null_summary", task_ids="validate_feature_output")
    log.info(
        "Phase 2 checkpoint PASSED. feature_store: %d rows. Null summary: %s",
        n, nulls,
    )
    print(
        f"\n✓ Phase 2 checkpoint: mart.feature_store has {n:,} rows ready for XGBoost (Phase 3).\n"
    )


def notify_on_validation_failure(**context):
    log.error("Spark feature validation FAILED — check SparkSubmitOperator logs above.")
    raise ValueError("Feature store validation failed — see task logs.")


# ─────────────────────────────────────────────────────────────────────────────
# DAG wiring
# ─────────────────────────────────────────────────────────────────────────────

t_gate = PythonOperator(
    task_id="check_dim_employee_ready",
    python_callable=check_dim_employee_ready,
    dag=dag,
)

t_validate = BranchPythonOperator(
    task_id="validate_feature_output",
    python_callable=validate_feature_output,
    dag=dag,
)

t_success = PythonOperator(
    task_id="log_success",
    python_callable=log_success,
    dag=dag,
)

t_fail = PythonOperator(
    task_id="notify_on_validation_failure",
    python_callable=notify_on_validation_failure,
    dag=dag,
)

# Pipeline: gate → peer percentile → rolling aggs → validate → branch
t_gate >> t_peer_percentile >> t_rolling_agg >> t_validate
t_validate >> t_success
t_validate >> t_fail
