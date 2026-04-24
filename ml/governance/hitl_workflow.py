"""
HITL (Human-in-the-Loop) active learning workflow.

Flow:
  1. HR manager disputes a prediction via API
  2. submit_override() → writes audit.hitl_overrides + audit.active_learning_labels
  3. Weekly drift_monitor_dag checks trigger_retrain()
  4. retrain() pulls HITL labels + uncertainty samples, retrains XGBoost with Optuna
  5. New model registered as "challenger"; auto-promoted to champion if better

Uncertainty sampling: pull employees near the decision boundary (0.35–0.65
predicted probability) — these are the cases the model is least confident
about and most likely to benefit from human correction.
"""

import os
import json
import uuid
from datetime import datetime, timezone
from typing import Literal

import numpy as np
import pandas as pd
import psycopg2
import psycopg2.extras
import optuna
import mlflow
import mlflow.xgboost
import xgboost as xgb
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.metrics import roc_auc_score, average_precision_score, f1_score

from ml.risk_engine.features import FEATURE_COLS, TARGET_COL, load_features
from ml.governance import mlflow_registry

optuna.logging.set_verbosity(optuna.logging.WARNING)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://talentlens:talentlens@localhost:5434/talentlens",
)

HITL_RETRAIN_THRESHOLD = 50      # retrain if ≥ 50 new labels since last run
UNCERTAINTY_BAND = (0.35, 0.65)  # model confidence zone for uncertainty sampling
N_UNCERTAINTY_SAMPLES = 200
N_OPTUNA_TRIALS = 30


# ─────────────────────────────────────────────────────────────────────────────
# Step 1-2: Submit override
# ─────────────────────────────────────────────────────────────────────────────

def submit_override(
    employee_id: str,
    reviewer_id: str,
    override_label: Literal[0, 1],
    reason: str,
    original_risk_index: float,
    notes: str = "",
    feature_snapshot: dict | None = None,
):
    """
    Write an HR manager override to audit tables.
    override_label: 0 = not at risk, 1 = at risk (different reason than model)
    """
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            # Immutable override log
            cur.execute(
                """
                INSERT INTO audit.hitl_overrides
                    (employee_id, reviewer_id, original_risk_index,
                     override_label, reason, notes)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (employee_id, reviewer_id, original_risk_index,
                 override_label, reason, notes),
            )

            # Active learning queue
            cur.execute(
                """
                INSERT INTO audit.active_learning_labels
                    (employee_id, feature_snapshot, corrected_label,
                     confidence, used_in_training)
                VALUES (%s, %s, %s, 'human_verified', FALSE)
                """,
                (
                    employee_id,
                    json.dumps(feature_snapshot or {}),
                    override_label,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def get_pending_label_count() -> int:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM audit.active_learning_labels WHERE used_in_training = FALSE"
            )
            return cur.fetchone()[0]
    finally:
        conn.close()


def trigger_retrain(psi_score: float = 0.0) -> bool:
    """Return True if retraining should fire."""
    pending = get_pending_label_count()
    return pending >= HITL_RETRAIN_THRESHOLD or psi_score > 0.20


# ─────────────────────────────────────────────────────────────────────────────
# Step 3: Uncertainty sampling
# ─────────────────────────────────────────────────────────────────────────────

def get_uncertainty_samples(model, df_active: pd.DataFrame, n: int = N_UNCERTAINTY_SAMPLES) -> pd.DataFrame:
    """
    Return employees near the model decision boundary.
    These are the cases the model is least confident about.
    """
    X = df_active[FEATURE_COLS].fillna(0)
    probs = model.predict_proba(X)[:, 1]
    lo, hi = UNCERTAINTY_BAND
    mask = (probs >= lo) & (probs <= hi)
    uncertain = df_active[mask].copy()
    uncertain["predicted_prob"] = probs[mask]
    return uncertain.sample(min(n, len(uncertain)), random_state=42)


# ─────────────────────────────────────────────────────────────────────────────
# Step 4: Retrain with HITL labels + Optuna tuning
# ─────────────────────────────────────────────────────────────────────────────

def _load_hitl_labels() -> pd.DataFrame:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        df = pd.read_sql(
            """
            SELECT DISTINCT ON (employee_id)
                employee_id::text, corrected_label, feature_snapshot
            FROM audit.active_learning_labels
            WHERE used_in_training = FALSE
            ORDER BY employee_id, labeled_at DESC
            """,
            conn,
        )
    finally:
        conn.close()
    return df


def _mark_labels_used(label_ids: list | None = None):
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE audit.active_learning_labels SET used_in_training = TRUE "
                "WHERE used_in_training = FALSE"
            )
        conn.commit()
    finally:
        conn.close()


def _optuna_objective(trial, X_tr, y_tr, X_val, y_val):
    params = {
        "n_estimators": trial.suggest_int("n_estimators", 200, 600),
        "max_depth": trial.suggest_int("max_depth", 3, 7),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.15, log=True),
        "subsample": trial.suggest_float("subsample", 0.6, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
        "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
        "reg_alpha": trial.suggest_float("reg_alpha", 1e-4, 1.0, log=True),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-4, 1.0, log=True),
        "scale_pos_weight": round((y_tr == 0).sum() / max((y_tr == 1).sum(), 1), 2),
        "eval_metric": "aucpr",
        "random_state": 42,
        "n_jobs": -1,
    }
    model = xgb.XGBClassifier(**params, enable_categorical=False)
    model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=False)
    prob = model.predict_proba(X_val)[:, 1]
    return roc_auc_score(y_val, prob)


def retrain(current_model, model_version_base: str = "1.0.0") -> dict:
    """
    Full retraining pipeline:
      1. Load base features
      2. Merge HITL labels (corrected)
      3. Add uncertainty samples (soft signal)
      4. Optuna-tune XGBoost
      5. Register challenger; promote if better
    """
    mlflow_registry.setup()

    print("  Loading base features ...")
    df_all = load_features()
    X_base = df_all[FEATURE_COLS].fillna(0)
    y_base = df_all[TARGET_COL].astype(int)

    # ── Uncertainty samples ──────────────────────────────────────────────────
    df_active = df_all[df_all["is_active"]].copy()
    uncertain = get_uncertainty_samples(current_model, df_active)
    print(f"  Uncertainty samples near boundary: {len(uncertain)}")

    # ── HITL labels ──────────────────────────────────────────────────────────
    hitl_df = _load_hitl_labels()
    print(f"  HITL override labels to incorporate: {len(hitl_df)}")

    # Merge HITL corrections into training set (override any existing label)
    X_combined = X_base.copy()
    y_combined = y_base.copy()

    if not hitl_df.empty:
        # Replace base label with human-verified label for overridden employees
        hitl_map = hitl_df.set_index("employee_id")["corrected_label"].to_dict()
        y_combined = df_all["employee_id"].map(hitl_map).combine_first(y_base).astype(int)
        X_combined = X_base.copy()

    # Add uncertainty samples (use current model label as soft signal)
    if len(uncertain) > 0:
        X_unc = uncertain[FEATURE_COLS].fillna(0)
        y_unc_prob = current_model.predict_proba(X_unc)[:, 1]
        y_unc = (y_unc_prob >= 0.5).astype(int)
        X_combined = pd.concat([X_combined, X_unc], ignore_index=True)
        y_combined = pd.concat([y_combined, pd.Series(y_unc)], ignore_index=True)

    print(f"  Final training set: {len(X_combined):,} rows "
          f"(attrition rate: {y_combined.mean():.1%})")

    X_tr, X_val, y_tr, y_val = train_test_split(
        X_combined, y_combined, test_size=0.20, stratify=y_combined, random_state=42
    )

    # ── Optuna tuning ────────────────────────────────────────────────────────
    print(f"  Optuna tuning ({N_OPTUNA_TRIALS} trials) ...")
    study = optuna.create_study(direction="maximize", study_name="talentlens-retrain")
    study.optimize(
        lambda trial: _optuna_objective(trial, X_tr, y_tr, X_val, y_val),
        n_trials=N_OPTUNA_TRIALS,
        show_progress_bar=False,
    )
    best_params = study.best_params
    best_params.update({
        "scale_pos_weight": round((y_tr == 0).sum() / max((y_tr == 1).sum(), 1), 2),
        "eval_metric": "aucpr",
        "random_state": 42,
        "n_jobs": -1,
    })
    print(f"  Best trial AUC: {study.best_value:.4f}")

    # ── Train final challenger ───────────────────────────────────────────────
    challenger = xgb.XGBClassifier(**best_params, enable_categorical=False)
    challenger.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=False)

    y_prob_new = challenger.predict_proba(X_val)[:, 1]
    y_prob_old = current_model.predict_proba(X_val)[:, 1]

    new_auc = roc_auc_score(y_val, y_prob_new)
    old_auc = roc_auc_score(y_val, y_prob_old)
    new_pr  = average_precision_score(y_val, y_prob_new)

    # ── MLflow logging ───────────────────────────────────────────────────────
    app_version = _bump_version(model_version_base)
    mlflow_version = None
    with mlflow_registry.start_run(run_name=f"retrain-challenger-{app_version}") as run:
        mlflow.log_params(best_params)
        mlflow.log_metrics({
            "val_roc_auc":        round(new_auc, 4),
            "val_pr_auc":         round(new_pr, 4),
            "champion_auc":       round(old_auc, 4),
            "hitl_labels_used":   len(hitl_df),
            "uncertainty_samples": len(uncertain),
            "training_size":      len(X_tr),
        })
        mlflow.set_tag("stage", "challenger")
        mlflow.set_tag("app_version", app_version)
        model_info = mlflow.xgboost.log_model(
            challenger,
            artifact_path="attrition_model",
            registered_model_name="talentlens-flight-risk",
        )
        # Retrieve the MLflow integer version that was just assigned
        client = mlflow.tracking.MlflowClient()
        versions = client.search_model_versions("name='talentlens-flight-risk'")
        mlflow_version = str(max(int(v.version) for v in versions))
        run_id = run.info.run_id

    # ── Champion promotion ───────────────────────────────────────────────────
    promoted = new_auc > old_auc
    result = {
        "new_version":    app_version,
        "mlflow_version": mlflow_version,
        "new_auc":        round(new_auc, 4),
        "old_auc":        round(old_auc, 4),
        "promoted":       promoted,
        "hitl_labels":    len(hitl_df),
        "uncertainty_n":  len(uncertain),
        "mlflow_run_id":  run_id,
    }

    if promoted:
        mlflow_registry.promote_to_production("talentlens-flight-risk", mlflow_version)
        _mark_labels_used()
        print(f"  Challenger {app_version} (MLflow v{mlflow_version}) promoted to champion "
              f"(AUC {old_auc:.4f} → {new_auc:.4f})")
    else:
        print(f"  Challenger {app_version} NOT promoted "
              f"(challenger AUC {new_auc:.4f} ≤ champion {old_auc:.4f})")

    return result


def _bump_version(version: str) -> str:
    parts = version.split(".")
    parts[-1] = str(int(parts[-1]) + 1)
    return ".".join(parts)
