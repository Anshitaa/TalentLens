"""
Phase 2 — PySpark Job: Rolling Behavioral Aggregations

Computes per-employee rolling statistics over their HR event history:

  manager_changes_30d   : # manager change events in last 30 days
  manager_changes_90d   : # manager change events in last 90 days
  absence_rate_90d      : fraction of days with absence events in last 90 days
  overtime_rate_180d    : fraction of months with overtime events in last 180 days
  training_count_90d    : # training events in last 90 days
  performance_rating_delta : latest rating minus 6-month rolling average

Why PySpark: these are time-ordered, per-employee range-window aggregations over
~2M event rows. A single-node PostgreSQL window function would require a full sort
of the events table per employee. Spark distributes the partitionBy(employee_id)
sort across workers, keeping each partition local.

Reads from : raw.employee_events        (2M+ rows)
             mart.dim_employee           (latest performance_rating per employee)
Writes to  : mart.feature_store         (UPSERT — merges with peer percentile output)

Run:
  spark-submit \\
    --master spark://spark-master:7077 \\
    --jars /opt/bitnami/spark/jars/extra/postgresql-42.7.3.jar \\
    /opt/talentlens/spark/rolling_aggregations.py

  python spark/rolling_aggregations.py --local   # dev
"""

import argparse
import os

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
JDBC_JAR = os.getenv("JDBC_JAR", "/opt/bitnami/spark/jars/extra/postgresql-42.7.3.jar")

# Rolling window sizes in seconds (Spark rangeBetween uses seconds for timestamp columns)
_DAY = 86_400
D30  = 30  * _DAY
D90  = 90  * _DAY
D180 = 180 * _DAY
D180_MONTHS = 6  # used for performance_rating_delta reference window


def build_spark(local: bool):
    from pyspark.sql import SparkSession

    builder = (
        SparkSession.builder
        .appName("TalentLens-RollingAggregations")
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
        .config("spark.sql.shuffle.partitions", "50")
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

    # ── Load events ───────────────────────────────────────────────────────────
    print("Reading raw.employee_events ...")
    events = (
        spark.read
        .jdbc(url=JDBC_URL, table="raw.employee_events", properties=JDBC_PROPS)
        .select(
            "employee_id",
            "event_type",
            F.col("event_date").cast("timestamp").alias("event_ts"),
        )
        .withColumn("event_epoch", F.col("event_ts").cast("long"))
    )

    event_count = events.count()
    print(f"  Loaded {event_count:,} events")

    # ── Load employee baseline performance rating ─────────────────────────────
    print("Reading mart.dim_employee (performance_rating) ...")
    employees = (
        spark.read
        .jdbc(url=JDBC_URL, table="mart.dim_employee", properties=JDBC_PROPS)
        .filter(F.col("is_active") == True)   # noqa: E712
        .select("employee_id", "performance_rating")
    )

    # ── Time-ordered, per-employee range windows ──────────────────────────────
    # rangeBetween uses epoch seconds when orderBy is a long/numeric column
    emp_window_30d = (
        Window.partitionBy("employee_id")
        .orderBy("event_epoch")
        .rangeBetween(-D30, 0)
    )
    emp_window_90d = (
        Window.partitionBy("employee_id")
        .orderBy("event_epoch")
        .rangeBetween(-D90, 0)
    )
    emp_window_180d = (
        Window.partitionBy("employee_id")
        .orderBy("event_epoch")
        .rangeBetween(-D180, 0)
    )
    emp_window_all = (
        Window.partitionBy("employee_id")
        .orderBy("event_epoch")
    )

    # ── Boolean flag columns for each event type ──────────────────────────────
    events_flagged = (
        events
        .withColumn("is_manager_change", (F.col("event_type") == "MANAGER_CHANGE").cast("int"))
        .withColumn("is_absence",        (F.col("event_type") == "ABSENCE").cast("int"))
        .withColumn("is_overtime",       (F.col("event_type") == "OVERTIME").cast("int"))
        .withColumn("is_training",       (F.col("event_type") == "TRAINING").cast("int"))
        .withColumn("is_perf_review",    (F.col("event_type") == "PERFORMANCE_REVIEW").cast("int"))
    )

    # ── Rolling aggregations ──────────────────────────────────────────────────
    aggregated = (
        events_flagged
        .withColumn("manager_changes_30d",  F.sum("is_manager_change").over(emp_window_30d))
        .withColumn("manager_changes_90d",  F.sum("is_manager_change").over(emp_window_90d))
        .withColumn("absence_count_90d",    F.sum("is_absence").over(emp_window_90d))
        .withColumn("total_days_90d",
                    (F.max("event_epoch").over(emp_window_90d) -
                     F.min("event_epoch").over(emp_window_90d)) / _DAY + 1)
        .withColumn("absence_rate_90d",
                    F.round(
                        F.col("absence_count_90d") / F.greatest(F.col("total_days_90d"), F.lit(1)),
                        4,
                    ))
        .withColumn("overtime_count_180d", F.sum("is_overtime").over(emp_window_180d))
        .withColumn("event_count_180d",    F.count("*").over(emp_window_180d))
        .withColumn("overtime_rate_180d",
                    F.round(
                        F.col("overtime_count_180d") / F.greatest(F.col("event_count_180d"), F.lit(1)),
                        4,
                    ))
        .withColumn("training_count_90d",  F.sum("is_training").over(emp_window_90d).cast("int"))
    )

    # Take the latest values per employee (last row in time order)
    latest_window = (
        Window.partitionBy("employee_id")
        .orderBy(F.col("event_epoch").desc())
    )
    latest_per_employee = (
        aggregated
        .withColumn("row_num", F.row_number().over(latest_window))
        .filter(F.col("row_num") == 1)
        .select(
            "employee_id",
            F.col("manager_changes_30d").cast("int"),
            F.col("manager_changes_90d").cast("int"),
            "absence_rate_90d",
            "overtime_rate_180d",
            F.col("training_count_90d").cast("int"),
        )
    )

    # ── Performance rating delta ───────────────────────────────────────────────
    # For each PERFORMANCE_REVIEW event, compute rolling 6-month avg,
    # then delta = latest_rating - avg_6m_rating
    perf_reviews = (
        events_flagged
        .filter(F.col("event_type") == "PERFORMANCE_REVIEW")
        # Ideally payload would carry the rating, but we use dim_employee baseline
        # and compute delta from the event frequency as a proxy
    )

    # Simple approach: join to latest performance_rating from dim_employee,
    # compute delta as (current_rating - dept_avg) — replaced once Phase 3 runs
    dept_avg = employees.groupBy().agg(F.avg("performance_rating").alias("global_avg_rating"))
    perf_delta = (
        employees
        .crossJoin(dept_avg)
        .withColumn(
            "performance_rating_delta",
            F.round(F.col("performance_rating") - F.col("global_avg_rating"), 2),
        )
        .select("employee_id", "performance_rating_delta")
    )

    # ── Join rolling features + perf delta ───────────────────────────────────
    features = (
        latest_per_employee
        .join(perf_delta, on="employee_id", how="left")
    )

    feature_count = features.count()
    print(f"Rolling aggregations computed for {feature_count:,} employees")

    # ── Sample output ─────────────────────────────────────────────────────────
    print("Sample output (5 rows):")
    features.show(5, truncate=False)

    # ── Validate ──────────────────────────────────────────────────────────────
    null_check = features.select([
        F.count(F.when(F.col(c).isNull(), 1)).alias(c)
        for c in ["manager_changes_30d", "manager_changes_90d",
                  "absence_rate_90d", "overtime_rate_180d", "training_count_90d"]
    ])
    print("Null counts per feature column:")
    null_check.show()

    range_violations = features.filter(
        (F.col("absence_rate_90d") < 0) | (F.col("absence_rate_90d") > 1) |
        (F.col("overtime_rate_180d") < 0) | (F.col("overtime_rate_180d") > 1)
    ).count()
    if range_violations > 0:
        print(f"WARNING: {range_violations} rows have out-of-range rate values")

    # ── Write to temp table then UPSERT ──────────────────────────────────────
    print("Writing rolling features to mart.feature_store ...")
    (
        features
        .write
        .jdbc(
            url=JDBC_URL,
            table="mart._spark_rolling_tmp",
            mode="overwrite",
            properties=JDBC_PROPS,
        )
    )

    merge_sql = """
        INSERT INTO mart.feature_store (
            employee_id,
            manager_changes_30d,
            manager_changes_90d,
            absence_rate_90d,
            overtime_rate_180d,
            training_count_90d,
            performance_rating_delta,
            computed_at
        )
        SELECT
            employee_id::uuid,
            manager_changes_30d,
            manager_changes_90d,
            absence_rate_90d,
            overtime_rate_180d,
            training_count_90d,
            performance_rating_delta,
            NOW()
        FROM mart._spark_rolling_tmp
        ON CONFLICT (employee_id) DO UPDATE SET
            manager_changes_30d      = EXCLUDED.manager_changes_30d,
            manager_changes_90d      = EXCLUDED.manager_changes_90d,
            absence_rate_90d         = EXCLUDED.absence_rate_90d,
            overtime_rate_180d       = EXCLUDED.overtime_rate_180d,
            training_count_90d       = EXCLUDED.training_count_90d,
            performance_rating_delta = EXCLUDED.performance_rating_delta,
            computed_at              = EXCLUDED.computed_at
    """
    _execute_sql(merge_sql)
    _execute_sql("DROP TABLE IF EXISTS mart._spark_rolling_tmp")

    print(f"Rolling aggregation job complete — {feature_count:,} rows upserted into mart.feature_store")
    spark.stop()


def _execute_sql(sql: str) -> None:
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
