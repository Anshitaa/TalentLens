"""
Feature spec for the TalentLens flight-risk model.

Joins mart.dim_employee (labels + HR attributes) with mart.feature_store
(PySpark-computed rolling behavioural features).
"""

import os
import pandas as pd
import psycopg2

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://talentlens:talentlens@localhost:5434/talentlens",
)

JOB_LEVEL_ORDER = {"IC1": 1, "IC2": 2, "IC3": 3, "IC4": 4, "IC5": 5,
                   "M1": 6, "M2": 7, "M3": 8, "M4": 9}

FEATURE_COLS = [
    # HR attributes
    "monthly_income", "job_satisfaction", "environment_satisfaction",
    "work_life_balance", "performance_rating", "years_since_last_promotion",
    "years_with_current_manager", "years_at_company", "distance_from_home",
    "num_companies_worked", "training_times_last_year", "overtime_flag",
    "education", "age", "department_enc", "job_level_enc",
    "marital_status_enc", "gender_enc",
    # Peer-enrichment flags (from dim_employee)
    "is_below_peer_median", "income_vs_peer_median_pct",
    "flag_low_satisfaction", "flag_stagnant_career",
    "flag_below_peer_pay", "flag_high_performer",
    # Rolling behavioural features (from feature_store)
    "manager_changes_30d", "manager_changes_90d",
    "absence_rate_90d", "overtime_rate_180d",
    "monthly_income_vs_peer_median", "income_peer_percentile",
    "performance_rating_delta", "training_count_90d",
]

TARGET_COL = "has_attrited"

# Sensitive attributes kept for fairness auditing (not in FEATURE_COLS)
SENSITIVE_COLS = ["gender", "department", "age_band"]


_QUERY = """
SELECT
    e.employee_id,
    e.has_attrited,
    e.is_active,
    -- sensitive cols for fairness audit
    e.gender,
    e.department,
    e.age_band,
    -- numeric HR features
    COALESCE(e.monthly_income, 0)                       AS monthly_income,
    COALESCE(e.job_satisfaction, 2)                     AS job_satisfaction,
    COALESCE(e.environment_satisfaction, 2)             AS environment_satisfaction,
    COALESCE(e.work_life_balance, 2)                    AS work_life_balance,
    COALESCE(e.performance_rating, 2)                   AS performance_rating,
    COALESCE(e.years_since_last_promotion, 0)           AS years_since_last_promotion,
    COALESCE(e.years_with_current_manager, 0)           AS years_with_current_manager,
    COALESCE(e.years_at_company, 0)                     AS years_at_company,
    COALESCE(e.distance_from_home, 10)                  AS distance_from_home,
    COALESCE(e.num_companies_worked, 1)                 AS num_companies_worked,
    COALESCE(e.training_times_last_year, 0)             AS training_times_last_year,
    e.overtime_flag::int                                AS overtime_flag,
    COALESCE(e.education, 3)                            AS education,
    COALESCE(e.age, 35)                                 AS age,
    -- categorical (raw, encoded in Python)
    e.job_level                                         AS job_level_raw,
    COALESCE(e.marital_status, 'Single')                AS marital_status_raw,
    COALESCE(e.gender, 'Male')                          AS gender_raw,
    -- peer enrichment flags
    e.is_below_peer_median::int                         AS is_below_peer_median,
    COALESCE(e.income_vs_peer_median_pct, 0)            AS income_vs_peer_median_pct,
    e.flag_low_satisfaction::int                        AS flag_low_satisfaction,
    e.flag_stagnant_career::int                         AS flag_stagnant_career,
    e.flag_below_peer_pay::int                          AS flag_below_peer_pay,
    e.flag_high_performer::int                          AS flag_high_performer,
    -- rolling behavioural (feature_store)
    COALESCE(f.manager_changes_30d, 0)                  AS manager_changes_30d,
    COALESCE(f.manager_changes_90d, 0)                  AS manager_changes_90d,
    COALESCE(f.absence_rate_90d, 0)                     AS absence_rate_90d,
    COALESCE(f.overtime_rate_180d, 0)                   AS overtime_rate_180d,
    COALESCE(f.monthly_income_vs_peer_median, 0)        AS monthly_income_vs_peer_median,
    COALESCE(f.income_peer_percentile, 2)               AS income_peer_percentile,
    COALESCE(f.performance_rating_delta, 0)             AS performance_rating_delta,
    COALESCE(f.training_count_90d, 0)                   AS training_count_90d
FROM mart.dim_employee e
LEFT JOIN mart.feature_store f ON e.employee_id::uuid = f.employee_id
"""

# Encoding maps built from the full dataset and stored here for inference consistency
_DEPT_MAP: dict = {}
_MARITAL_MAP: dict = {}
_GENDER_MAP: dict = {}


def load_features() -> pd.DataFrame:
    """Return full feature DataFrame (train + inference populations)."""
    conn = psycopg2.connect(DATABASE_URL)
    df = pd.read_sql(_QUERY, conn)
    conn.close()
    return _encode(df)


def _encode(df: pd.DataFrame) -> pd.DataFrame:
    global _DEPT_MAP, _MARITAL_MAP, _GENDER_MAP

    # Job level — ordinal encoding matches seniority
    df["job_level_enc"] = df["job_level_raw"].map(JOB_LEVEL_ORDER).fillna(1).astype(int)

    # Department — label encode (stable across calls via global map)
    if not _DEPT_MAP:
        _DEPT_MAP = {v: i for i, v in enumerate(sorted(df["department"].unique()))}
    df["department_enc"] = df["department"].map(_DEPT_MAP).fillna(0).astype(int)

    if not _MARITAL_MAP:
        _MARITAL_MAP = {v: i for i, v in enumerate(sorted(df["marital_status_raw"].unique()))}
    df["marital_status_enc"] = df["marital_status_raw"].map(_MARITAL_MAP).fillna(0).astype(int)

    if not _GENDER_MAP:
        _GENDER_MAP = {v: i for i, v in enumerate(sorted(df["gender_raw"].unique()))}
    df["gender_enc"] = df["gender_raw"].map(_GENDER_MAP).fillna(0).astype(int)

    return df


def get_encoding_maps() -> dict:
    return {
        "department": _DEPT_MAP,
        "job_level": JOB_LEVEL_ORDER,
        "marital_status": _MARITAL_MAP,
        "gender": _GENDER_MAP,
    }
