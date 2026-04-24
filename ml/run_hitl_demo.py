"""
Phase 4 HITL demo.

Simulates 60 HR manager overrides on high-risk employees,
then triggers active learning retraining with Optuna tuning.

Usage:
    python ml/run_hitl_demo.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random
import psycopg2
import pandas as pd
import mlflow.xgboost

from ml.governance.hitl_workflow import (
    submit_override,
    get_pending_label_count,
    trigger_retrain,
    get_uncertainty_samples,
    retrain,
)
from ml.governance import mlflow_registry
from ml.risk_engine.features import load_features, FEATURE_COLS

random.seed(42)

REVIEWERS = ["hr_manager_alice", "hr_manager_bob", "hr_director_carol"]
REASONS = [
    "Employee recently received a competing offer and declined — not a flight risk",
    "Known high performer — score driven by peer pay gap, not intent to leave",
    "Employee is on a planned sabbatical, not attrition",
    "Recent promotion resolves the stagnation flag — score is stale",
    "Employee confirmed planning to stay for upcoming vesting cliff",
    "Performance drop was due to medical leave, now resolved",
]

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://talentlens:talentlens@localhost:5434/talentlens",
)


def _get_high_risk_employees(n: int = 80) -> list[dict]:
    """Pull highest risk-index employees from mart.mart_risk_index."""
    conn = psycopg2.connect(DATABASE_URL)
    try:
        df = pd.read_sql(
            f"""
            SELECT employee_id::text, latest_risk_index, latest_risk_band
            FROM mart.mart_risk_index
            ORDER BY latest_risk_index DESC
            LIMIT {n}
            """,
            conn,
        )
    finally:
        conn.close()
    return df.to_dict("records")


def _load_current_model():
    mlflow_registry.setup()
    client = mlflow.tracking.MlflowClient()
    versions = client.search_model_versions("name='talentlens-flight-risk'")
    latest = max(versions, key=lambda v: int(v.version))
    model_uri = f"models:/talentlens-flight-risk/{latest.version}"
    print(f"  Loaded champion model: talentlens-flight-risk v{latest.version}")
    return mlflow.xgboost.load_model(model_uri), latest.version


def main():
    print("=" * 60)
    print("TalentLens Phase 4 — HITL Active Learning Demo")
    print("=" * 60)

    # ── Step 1: Load current champion model ──────────────────────────────────
    print("\n[1/4] Loading champion model ...")
    current_model, champion_version = _load_current_model()

    # ── Step 2: Simulate 60 HR overrides ─────────────────────────────────────
    print("\n[2/4] Simulating HR manager overrides ...")
    employees = _get_high_risk_employees(n=80)

    if not employees:
        print("  No scored employees found. Run ml/train_and_score.py first.")
        return

    overridden = 0
    for emp in employees[:60]:
        # Simulate: 70% of high-risk flags disputed as false positives
        override_label = 0 if random.random() < 0.70 else 1
        reviewer = random.choice(REVIEWERS)
        reason = random.choice(REASONS)

        submit_override(
            employee_id=emp["employee_id"],
            reviewer_id=reviewer,
            override_label=override_label,
            reason=reason,
            original_risk_index=float(emp["latest_risk_index"]),
            notes=f"Batch demo override — simulated {reviewer}",
            feature_snapshot={"demo": True, "risk_index": float(emp["latest_risk_index"])},
        )
        overridden += 1

    pending = get_pending_label_count()
    print(f"  Submitted {overridden} overrides → {pending} pending labels in active learning queue")

    # ── Step 3: Check retrain trigger ────────────────────────────────────────
    print("\n[3/4] Checking retrain trigger ...")
    should_retrain = trigger_retrain(psi_score=0.527)
    print(f"  Retrain triggered: {should_retrain} "
          f"(pending labels: {pending}, PSI: 0.527)")

    if not should_retrain:
        print("  Threshold not met — skipping retraining.")
        return

    # ── Step 4: Show uncertainty samples ────────────────────────────────────
    print("\n[4/4] Active learning retraining ...")
    df_all = load_features()
    df_active = df_all[df_all["is_active"]].copy()
    uncertain = get_uncertainty_samples(current_model, df_active)
    print(f"  Employees near decision boundary (0.35–0.65 prob): {len(uncertain)}")

    # Retrain with Optuna
    result = retrain(current_model, model_version_base="1.0.0")

    print("\n" + "=" * 60)
    print("  Phase 4 HITL Demo Complete!")
    print(f"  Champion version:   v{champion_version}")
    print(f"  Challenger version: v{result['new_version']}")
    print(f"  Champion AUC:       {result['old_auc']:.4f}")
    print(f"  Challenger AUC:     {result['new_auc']:.4f}")
    print(f"  Promoted:           {result['promoted']}")
    print(f"  HITL labels used:   {result['hitl_labels']}")
    print(f"  Uncertainty samples:{result['uncertainty_n']}")
    print(f"  MLflow run:         {result['mlflow_run_id']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
