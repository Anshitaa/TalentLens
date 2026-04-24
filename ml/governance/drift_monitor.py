"""
PSI (Population Stability Index) drift monitor.

Compares reference distribution (training data) vs current scoring population.
PSI interpretation:
  < 0.10 → no significant change
  0.10–0.20 → moderate change, monitor
  > 0.20 → significant shift, retrain triggered

Writes report to audit.drift_reports.
"""

import os
import json
import uuid
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd
import psycopg2

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://talentlens:talentlens@localhost:5434/talentlens",
)

PSI_RETRAIN_THRESHOLD = 0.20
PSI_MONITOR_THRESHOLD = 0.10

MONITOR_FEATURES = [
    "monthly_income", "job_satisfaction", "performance_rating",
    "years_since_last_promotion", "absence_rate_90d",
    "overtime_rate_180d", "income_peer_percentile",
    "performance_rating_delta",
]


def psi(reference: np.ndarray, current: np.ndarray, bins: int = 10) -> float:
    """Compute PSI between reference and current distributions."""
    ref_clean = reference[~np.isnan(reference)]
    cur_clean = current[~np.isnan(current)]
    if len(ref_clean) == 0 or len(cur_clean) == 0:
        return 0.0

    breakpoints = np.percentile(ref_clean, np.linspace(0, 100, bins + 1))
    breakpoints[0] -= 1e-6
    breakpoints[-1] += 1e-6

    ref_counts, _ = np.histogram(ref_clean, bins=breakpoints)
    cur_counts, _ = np.histogram(cur_clean, bins=breakpoints)

    ref_pct = (ref_counts / len(ref_clean)).clip(1e-6)
    cur_pct = (cur_counts / len(cur_clean)).clip(1e-6)

    return float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))


def run(
    X_reference: pd.DataFrame,
    X_current: pd.DataFrame,
    model_version: str,
) -> dict:
    """
    Compute per-feature PSI. Write to audit.drift_reports. Return report dict.
    """
    feature_psi = {}
    for col in MONITOR_FEATURES:
        if col in X_reference.columns and col in X_current.columns:
            feature_psi[col] = round(psi(
                X_reference[col].values.astype(float),
                X_current[col].values.astype(float),
            ), 4)

    overall_psi = round(float(np.mean(list(feature_psi.values()))), 4)
    retrain = overall_psi > PSI_RETRAIN_THRESHOLD

    report = {
        "run_date": date.today().isoformat(),
        "model_version": model_version,
        "overall_psi": overall_psi,
        "feature_psi": feature_psi,
        "retrain_triggered": retrain,
        "interpretation": (
            "significant shift — retrain recommended" if overall_psi > PSI_RETRAIN_THRESHOLD
            else "moderate shift — monitor" if overall_psi > PSI_MONITOR_THRESHOLD
            else "stable"
        ),
    }

    _write_report(report)

    print(f"\n  PSI Drift Report — overall PSI: {overall_psi:.4f} "
          f"({'RETRAIN' if retrain else 'stable'})")
    for feat, score in sorted(feature_psi.items(), key=lambda x: -x[1]):
        flag = " ⚠" if score > PSI_RETRAIN_THRESHOLD else ""
        print(f"    {feat:35s}: {score:.4f}{flag}")

    return report


def _write_report(report: dict):
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO audit.drift_reports
                    (run_date, model_version, psi_score, feature_psi_detail, retrain_triggered)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    report["run_date"],
                    report["model_version"],
                    report["overall_psi"],
                    json.dumps(report["feature_psi"]),
                    report["retrain_triggered"],
                ),
            )
        conn.commit()
    finally:
        conn.close()
