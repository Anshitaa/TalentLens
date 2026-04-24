"""
Phase 2 — PySpark Job: Peer Income Percentiles

Computes, for every active employee:
  - monthly_income_vs_peer_median : percent_rank() within (job_level, department)
    → 0.0 = lowest earner in peer group, 1.0 = highest
  - income_peer_percentile        : quartile (1–4) within (job_level, department)
    → 1 = bottom 25%, 4 = top 25%

Why PySpark here: a full-table partition scan across 100K employees grouped by
job_level × department (72 groups) requires shuffling the full income column per
group. At this scale, single-node PostgreSQL is slow; Spark distributes the sort
and rank computation across workers.

Reads from : mart.dim_employee  (built by dbt in Phase 1)
Writes to  : mart.feature_store (UPSERT on employee_id)

Run via spark-submit:
  spark-submit \\
    --master spark://spark-master:7077 \\
    --jars /opt/bitnami/spark/jars/extra/postgresql-42.7.3.jar \\
    /opt/talentlens/spark/peer_percentile_job.py

Or locally (dev):
  python spark/peer_percentile_job.py --local
"""

import argparse
import os
import sys

from dotenv import load_dotenv

load_dotenv()

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB   = os.getenv("POSTGRES_DB", "talentlens")
POSTGRES_USER = os.getenv("POSTGRES_USER", "talentlens")
POSTGRES_PASS = os.getenv("POSTGRES_PASSWORD", "talentlens")

JDBC_URL = f"jdbc:postgresql://{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
JDBC_PROPS = {
    "user": POSTGRES_USER,
    "password": POSTGRES_PASS,
    "driver": "org.postgresql.Driver",
}

JDBC_JAR = os.getenv(
    "JDBC_JAR",
    "/opt/bitnami/spark/jars/extra/postgresql-42.7.3.jar",
)


def build_spark(local: bool):
    from pyspark.sql import SparkSession

    builder = (
        SparkSession.builder
        .appName("TalentLens-PeerPercentiles")
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
    )

    if local:
        builder = builder.master("local[*]").config("spark.jars", JDBC_JAR)
    else:
        builder = builder.config("spark.jars", JDBC_JAR)

    return builder.getOrCreate()


def run(local: bool = False) -> None:
    from pyspark.sql import functions as F
    from pyspark.sql.window import Window

    spark = build_spark(local)
    spark.sparkContext.setLogLevel("WARN")

    print("Reading mart.dim_employee ...")
    employees = (
        spark.read
        .jdbc(url=JDBC_URL, table="mart.dim_employee", properties=JDBC_PROPS)
        .filter(F.col("is_active") == True)  # noqa: E712
        .select(
            "employee_id",
            "department",
            "job_level",
            "monthly_income",
        )
    )

    n = employees.count()
    print(f"  Loaded {n:,} active employees")

    # ── Peer-group window: partition by job_level + department ────────────────
    peer_window = (
        Window
        .partitionBy("job_level", "department")
        .orderBy("monthly_income")
    )

    features = (
        employees
        .withColumn(
            "monthly_income_vs_peer_median",
            F.percent_rank().over(peer_window),
        )
        .withColumn(
            "income_peer_percentile",
            F.ntile(4).over(peer_window),   # quartile 1–4
        )
        .select(
            "employee_id",
            F.round("monthly_income_vs_peer_median", 4).alias("monthly_income_vs_peer_median"),
            F.col("income_peer_percentile").cast("integer").alias("income_peer_percentile"),
        )
    )

    # ── Validate: every quartile should be populated ─────────────────────────
    quartile_counts = features.groupBy("income_peer_percentile").count().orderBy("income_peer_percentile")
    print("Quartile distribution:")
    quartile_counts.show()

    feature_count = features.count()
    print(f"Computed peer percentiles for {feature_count:,} employees")

    # ── Upsert into mart.feature_store ───────────────────────────────────────
    # Write to a temp table then UPSERT — Spark JDBC doesn't support ON CONFLICT,
    # so we write to a staging table and run a merge via JDBC execute.
    print("Writing to mart.feature_store ...")
    (
        features
        .write
        .jdbc(
            url=JDBC_URL,
            table="mart._spark_peer_percentile_tmp",
            mode="overwrite",
            properties=JDBC_PROPS,
        )
    )

    # Merge temp → feature_store
    merge_sql = """
        INSERT INTO mart.feature_store (
            employee_id,
            monthly_income_vs_peer_median,
            income_peer_percentile,
            computed_at
        )
        SELECT
            employee_id::uuid,
            monthly_income_vs_peer_median,
            income_peer_percentile,
            NOW()
        FROM mart._spark_peer_percentile_tmp
        ON CONFLICT (employee_id) DO UPDATE SET
            monthly_income_vs_peer_median = EXCLUDED.monthly_income_vs_peer_median,
            income_peer_percentile        = EXCLUDED.income_peer_percentile,
            computed_at                   = EXCLUDED.computed_at
    """
    _execute_sql(merge_sql)

    # Cleanup temp table
    _execute_sql("DROP TABLE IF EXISTS mart._spark_peer_percentile_tmp")

    print(f"Peer percentile job complete — {feature_count:,} rows upserted into mart.feature_store")
    spark.stop()


def _execute_sql(sql: str) -> None:
    """Run a SQL statement directly via psycopg2 (Spark JDBC can't do DDL/DML outside writes)."""
    import psycopg2
    conn = psycopg2.connect(
        host=POSTGRES_HOST, port=POSTGRES_PORT, dbname=POSTGRES_DB,
        user=POSTGRES_USER, password=POSTGRES_PASS,
    )
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(sql)
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--local", action="store_true", help="Run in Spark local mode (dev)")
    args = parser.parse_args()
    run(local=args.local)
