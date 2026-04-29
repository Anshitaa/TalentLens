"""
Seed the k8s MLflow instance with experiment runs and registered models.
Bypasses artifact logging (artifact root is inside the k8s pod, not locally writable).

Usage:
    MLFLOW_TRACKING_URI=http://localhost:5001 python scripts/seed_k8s_mlflow.py
"""
import os
import mlflow
from mlflow.tracking import MlflowClient
import time

TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5001")
mlflow.set_tracking_uri(TRACKING_URI)
client = MlflowClient()

print(f"Seeding MLflow at {TRACKING_URI}...")

# ── Experiment ────────────────────────────────────────────────────────────────
exp_name = "talentlens-risk-engine"
exp = client.get_experiment_by_name(exp_name)
if exp is None:
    exp_id = client.create_experiment(
        exp_name,
        artifact_location="/tmp/mlflow-artifacts"   # local-writable for demo
    )
    print(f"Created experiment '{exp_name}' (id={exp_id})")
else:
    exp_id = exp.experiment_id
    print(f"Experiment '{exp_name}' already exists (id={exp_id})")

# ── XGBoost flight-risk run ───────────────────────────────────────────────────
with mlflow.start_run(experiment_id=exp_id, run_name="xgboost-flight-risk-v10"):
    mlflow.log_params({
        "model_type": "XGBoost",
        "n_estimators": 300,
        "max_depth": 6,
        "learning_rate": 0.05,
        "scale_pos_weight": 2.4,
        "objective": "binary:logistic",
        "n_employees_train": 10961,
        "attrition_rate": 0.297,
        "seed": 42,
    })
    mlflow.log_metrics({
        "roc_auc":   0.980,
        "pr_auc":    0.971,
        "f1_score":  0.887,
        "precision": 0.901,
        "recall":    0.874,
        "accuracy":  0.923,
    })
    run_id_xgb = mlflow.active_run().info.run_id
    print(f"  Logged XGBoost run: {run_id_xgb}")

# ── Isolation Forest anomaly run ──────────────────────────────────────────────
with mlflow.start_run(experiment_id=exp_id, run_name="isolation-forest-anomaly-v10"):
    mlflow.log_params({
        "model_type": "IsolationForest",
        "n_estimators": 200,
        "contamination": 0.05,
        "max_samples": "auto",
        "n_employees_scored": 7706,
    })
    mlflow.log_metrics({
        "anomaly_rate":   0.052,
        "mean_score":     0.031,
        "std_score":      0.089,
    })
    run_id_iso = mlflow.active_run().info.run_id
    print(f"  Logged IsolationForest run: {run_id_iso}")

# ── Composite risk scoring run ────────────────────────────────────────────────
with mlflow.start_run(experiment_id=exp_id, run_name="composite-risk-index-v10"):
    mlflow.log_params({
        "weight_flight_risk":  0.50,
        "weight_anomaly":      0.35,
        "weight_compliance":   0.15,
        "n_employees_scored":  7706,
        "risk_bands": "Low:0-25 | Medium:26-50 | High:51-75 | Critical:76-100",
    })
    mlflow.log_metrics({
        "avg_risk_index":     14.4,
        "pct_low":            0.912,
        "pct_medium":         0.074,
        "pct_high":           0.013,
        "pct_critical":       0.001,
        "high_critical_count": 11,
        "rows_written":       7706,
    })
    print(f"  Logged composite risk run")

# ── Register models ───────────────────────────────────────────────────────────
for model_name, run_id, uri_suffix in [
    ("talentlens-flight-risk",    run_id_xgb, "flight_risk_model"),
    ("talentlens-anomaly-detector", run_id_iso, "anomaly_model"),
]:
    try:
        client.create_registered_model(
            model_name,
            description=f"TalentLens {model_name} — trained on 10,961 employees"
        )
    except Exception:
        pass  # already exists

    client.create_model_version(
        name=model_name,
        source=f"runs:/{run_id}/{uri_suffix}",
        run_id=run_id,
    )
    print(f"  Registered model: {model_name}")

print("\nDone! Refresh http://localhost:5001 → Experiments + Models tabs.")
