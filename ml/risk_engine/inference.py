"""
Batch inference: score all active employees and write results to:
  - mart.fact_risk_scores      (append one row per scoring run per employee)
  - mart.mart_risk_index       (upsert — latest score per employee for dashboards)
  - audit.model_decisions      (immutable append-only log)
"""

import os
import uuid
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import psycopg2
import psycopg2.extras

from ml.risk_engine.features import FEATURE_COLS, load_features
from ml.risk_engine.risk_index import (
    compute_compliance_flag, compute_risk_index, assign_band, band_summary
)
from ml.risk_engine import shap_explainer as shap_mod
from ml.risk_engine import train_anomaly as anomaly_mod

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://talentlens:talentlens@localhost:5434/talentlens",
)


def run(
    xgb_model,
    if_model,
    if_scaler,
    model_version: str = "1.0.0",
) -> dict:
    """
    Score all active employees. Returns summary stats dict.
    """
    print("Loading features for inference ...")
    df_all = load_features()
    df = df_all[df_all["is_active"]].copy().reset_index(drop=True)
    print(f"  Scoring {len(df):,} active employees")

    X = df[FEATURE_COLS].fillna(0)

    # ── XGBoost flight risk ──────────────────────────────────────────────────
    flight_risk_prob = xgb_model.predict_proba(X)[:, 1]

    # ── Isolation Forest anomaly ─────────────────────────────────────────────
    anomaly_score_norm = anomaly_mod.score(if_model, if_scaler, df)

    # ── Compliance flag ──────────────────────────────────────────────────────
    compliance_flag = compute_compliance_flag(df)

    # ── Composite Risk Index ─────────────────────────────────────────────────
    risk_index = compute_risk_index(flight_risk_prob, anomaly_score_norm, compliance_flag)
    risk_bands = assign_band(risk_index)

    # ── SHAP top-3 per employee ──────────────────────────────────────────────
    print("  Computing SHAP values ...")
    explainer = shap_mod.build_explainer(xgb_model)
    shap_df = shap_mod.top3_shap(explainer, df)

    scoring_run_id = str(uuid.uuid4())
    scored_at = datetime.now(timezone.utc)

    results = pd.DataFrame({
        "employee_id":       df["employee_id"].values,
        "scoring_run_id":    scoring_run_id,
        "scored_at":         scored_at,
        "flight_risk_prob":  np.round(flight_risk_prob, 4),
        "anomaly_score":     np.round(anomaly_score_norm, 4),
        "compliance_flag":   compliance_flag.astype(bool),
        "risk_index":        risk_index,
        "risk_band":         risk_bands,
        "model_version":     model_version,
    }).join(shap_df)

    print(f"  Writing {len(results):,} rows to mart.fact_risk_scores ...")
    _write_fact_risk_scores(results)
    _upsert_mart_risk_index(results, df)
    _write_audit_decisions(results, df, X)

    summary = band_summary(risk_index)
    summary["scoring_run_id"] = scoring_run_id
    summary["scored_at"] = scored_at.isoformat()
    summary["n_scored"] = len(results)
    summary["model_version"] = model_version

    print(f"\n  Risk band distribution:")
    for band, stat in summary.items():
        if isinstance(stat, dict):
            print(f"    {band:8s}: {stat['count']:5d}  ({stat['pct']}%)")

    return summary


def _write_fact_risk_scores(df: pd.DataFrame):
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            rows = [
                (
                    row.employee_id,
                    row.scoring_run_id,
                    row.scored_at,
                    float(row.flight_risk_prob),
                    float(row.anomaly_score),
                    bool(row.compliance_flag),
                    float(row.risk_index),
                    row.risk_band,
                    row.shap_top_feature_1,
                    row.shap_top_feature_2,
                    row.shap_top_feature_3,
                    float(row.shap_value_1),
                    float(row.shap_value_2),
                    float(row.shap_value_3),
                    row.model_version,
                )
                for row in df.itertuples(index=False)
            ]
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO mart.fact_risk_scores (
                    employee_id, scoring_run_id, scored_at,
                    flight_risk_prob, anomaly_score, compliance_flag,
                    risk_index, risk_band,
                    shap_top_feature_1, shap_top_feature_2, shap_top_feature_3,
                    shap_value_1, shap_value_2, shap_value_3,
                    model_version
                ) VALUES %s
                """,
                rows,
                page_size=500,
            )
        conn.commit()
    finally:
        conn.close()


def _upsert_mart_risk_index(scores: pd.DataFrame, emp: pd.DataFrame):
    """Upsert per-employee latest score into mart.mart_risk_index."""
    merged = scores.join(
        emp[["employee_id", "department", "job_level_raw", "gender", "age_band"]].rename(columns={"job_level_raw": "job_level"}).set_index("employee_id"),
        on="employee_id",
    )

    # Pull previous risk index to compute delta
    conn = psycopg2.connect(DATABASE_URL)
    try:
        prev = pd.read_sql(
            "SELECT employee_id::text, latest_risk_index AS prev_risk_index FROM mart.mart_risk_index",
            conn,
        )
        if not prev.empty:
            merged = merged.merge(prev, on="employee_id", how="left")
        else:
            merged["prev_risk_index"] = None

        with conn.cursor() as cur:
            rows = []
            for row in merged.itertuples(index=False):
                prev_ri = row.prev_risk_index if hasattr(row, "prev_risk_index") and row.prev_risk_index is not None else None
                delta = round(float(row.risk_index) - float(prev_ri), 2) if prev_ri is not None else None
                rows.append((
                    row.employee_id,
                    getattr(row, "department", None),
                    getattr(row, "job_level", None),
                    float(row.risk_index),
                    row.risk_band,
                    prev_ri,
                    delta,
                    float(row.flight_risk_prob),
                    float(row.anomaly_score),
                    row.shap_top_feature_1,
                    row.shap_top_feature_2,
                    row.shap_top_feature_3,
                    row.scored_at,
                ))
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO mart.mart_risk_index (
                    employee_id, department, job_level,
                    latest_risk_index, latest_risk_band,
                    prev_risk_index, risk_delta,
                    flight_risk_prob, anomaly_score,
                    shap_top_feature_1, shap_top_feature_2, shap_top_feature_3,
                    last_scored_at, _updated_at
                ) VALUES %s
                ON CONFLICT (employee_id) DO UPDATE SET
                    department          = EXCLUDED.department,
                    job_level           = EXCLUDED.job_level,
                    latest_risk_index   = EXCLUDED.latest_risk_index,
                    latest_risk_band    = EXCLUDED.latest_risk_band,
                    prev_risk_index     = EXCLUDED.prev_risk_index,
                    risk_delta          = EXCLUDED.risk_delta,
                    flight_risk_prob    = EXCLUDED.flight_risk_prob,
                    anomaly_score       = EXCLUDED.anomaly_score,
                    shap_top_feature_1  = EXCLUDED.shap_top_feature_1,
                    shap_top_feature_2  = EXCLUDED.shap_top_feature_2,
                    shap_top_feature_3  = EXCLUDED.shap_top_feature_3,
                    last_scored_at      = EXCLUDED.last_scored_at,
                    _updated_at         = NOW()
                """,
                [(
                    r[0], r[1], r[2], r[3], r[4], r[5], r[6],
                    r[7], r[8], r[9], r[10], r[11], r[12], datetime.now(timezone.utc)
                ) for r in rows],
                page_size=500,
            )
        conn.commit()
    finally:
        conn.close()


def _write_audit_decisions(scores: pd.DataFrame, emp: pd.DataFrame, X: pd.DataFrame):
    """Append immutable decision log to audit.model_decisions."""
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            rows = []
            feature_cols_sample = X.columns.tolist()[:10]
            for i, row in enumerate(scores.itertuples(index=False)):
                feat_snap = {col: float(X.iloc[i][col]) for col in feature_cols_sample}
                rows.append((
                    row.employee_id,
                    row.model_version,
                    row.scored_at,
                    json.dumps(feat_snap),
                    float(row.flight_risk_prob),
                    float(row.anomaly_score),
                    float(row.risk_index),
                    row.risk_band,
                ))
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO audit.model_decisions (
                    employee_id, model_version, decision_at,
                    input_features, flight_risk_prob, anomaly_score,
                    risk_index, risk_band
                ) VALUES %s
                """,
                rows,
                page_size=500,
            )
        conn.commit()
    finally:
        conn.close()
