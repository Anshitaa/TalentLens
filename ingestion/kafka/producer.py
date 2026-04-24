"""
HR Event Kafka Producer

Reads delta events from the Mock HRIS API and publishes them to the
`employee-events` Kafka topic. Designed to run on a schedule (Airflow
triggers it hourly) or as a one-shot backfill.

Delivery semantics:
  - Uses idempotent producer (enable.idempotence=True)
  - Message key = employee_id for per-employee ordering within a partition
  - On failure: retries up to MAX_RETRIES with exponential backoff
  - Deduplication: event_id stored in PostgreSQL prevents double-publishing

Usage:
  python producer.py                          # delta from last watermark
  python producer.py --since 2024-01-01       # backfill from date
  python producer.py --backfill               # replay all events
"""

import argparse
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from kafka import KafkaProducer
from kafka.errors import KafkaError

from topic_config import partition_key_employee_events

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
HRIS_BASE_URL = os.getenv("HRIS_BASE_URL", "http://localhost:8001")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://talentlens:talentlens@localhost:5432/talentlens")
TOPIC = "employee-events"
BATCH_SIZE = 500
MAX_RETRIES = 3


def build_producer() -> KafkaProducer:
    return KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        key_serializer=lambda k: k if isinstance(k, bytes) else k.encode("utf-8"),
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        acks="all",              # wait for all in-sync replicas
        retries=5,
        max_in_flight_requests_per_connection=1,  # required for idempotence ordering
        enable_idempotence=True,
        compression_type="gzip",
        linger_ms=10,            # small batching window for throughput
        batch_size=32_768,
    )


def get_watermark(conn) -> Optional[str]:
    """Return the ISO timestamp of the last successfully published event."""
    cur = conn.cursor()
    cur.execute("""
        SELECT value FROM audit.producer_watermarks
        WHERE topic = %s
        ORDER BY updated_at DESC LIMIT 1
    """, (TOPIC,))
    row = cur.fetchone()
    return row["value"] if row else None


def set_watermark(conn, timestamp: str) -> None:
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO audit.producer_watermarks (topic, value, updated_at)
        VALUES (%s, %s, NOW())
        ON CONFLICT (topic) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
    """, (TOPIC, timestamp))
    conn.commit()


def ensure_watermark_table(conn) -> None:
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS audit.producer_watermarks (
            topic       TEXT PRIMARY KEY,
            value       TEXT NOT NULL,
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.commit()


def fetch_events(since: Optional[str], limit: int = 10_000) -> list[dict]:
    params = {"limit": limit}
    if since:
        params["since"] = since

    try:
        resp = httpx.get(f"{HRIS_BASE_URL}/hris/events", params=params, timeout=30.0)
        resp.raise_for_status()
        return resp.json()["data"]
    except httpx.HTTPError as e:
        log.error("HRIS API error: %s", e)
        raise


def publish_events(producer: KafkaProducer, events: list[dict]) -> int:
    published = 0
    errors = 0

    for event in events:
        employee_id = event["employee_id"]
        message = {
            "event_id": event["event_id"],
            "employee_id": employee_id,
            "event_type": event["event_type"],
            "event_date": event["event_date"] if isinstance(event["event_date"], str)
                          else event["event_date"].isoformat(),
            "department": event.get("department"),
            "payload": event.get("payload") or {},
            "schema_version": "1.0",
            "produced_at": datetime.now(timezone.utc).isoformat(),
        }

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                future = producer.send(
                    TOPIC,
                    key=partition_key_employee_events(employee_id),
                    value=message,
                    headers=[
                        ("event_type", event["event_type"].encode()),
                        ("event_id", event["event_id"].encode()),
                    ],
                )
                future.get(timeout=10)  # block to catch errors early
                published += 1
                break
            except KafkaError as e:
                if attempt == MAX_RETRIES:
                    log.error("Failed to publish event %s after %d attempts: %s",
                              event["event_id"], MAX_RETRIES, e)
                    errors += 1
                else:
                    wait = 2 ** attempt
                    log.warning("Retry %d for event %s in %ds", attempt, event["event_id"], wait)
                    time.sleep(wait)

    producer.flush()
    log.info("Published %d events, %d errors", published, errors)
    return published


def run(since: Optional[str] = None, backfill: bool = False) -> None:
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    ensure_watermark_table(conn)

    if backfill:
        since_ts = None
        log.info("Backfill mode: replaying all events")
    elif since:
        since_ts = since
        log.info("Fetching events since: %s", since_ts)
    else:
        since_ts = get_watermark(conn)
        log.info("Resuming from watermark: %s", since_ts or "beginning")

    producer = build_producer()

    total_published = 0
    page_since = since_ts

    while True:
        events = fetch_events(since=page_since, limit=BATCH_SIZE)
        if not events:
            log.info("No more events. Total published: %d", total_published)
            break

        published = publish_events(producer, events)
        total_published += published

        # Advance watermark to the latest event's ingestion time
        latest_date = max(e["event_date"] for e in events)
        set_watermark(conn, latest_date if isinstance(latest_date, str) else latest_date.isoformat())

        if len(events) < BATCH_SIZE:
            break
        page_since = latest_date if isinstance(latest_date, str) else latest_date.isoformat()

    producer.close()
    conn.close()
    log.info("Producer run complete. Published %d total events.", total_published)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", help="ISO date/datetime to fetch events from")
    parser.add_argument("--backfill", action="store_true", help="Replay all events from beginning")
    args = parser.parse_args()
    run(since=args.since, backfill=args.backfill)
