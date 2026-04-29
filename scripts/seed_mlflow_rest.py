"""
Seed k8s MLflow via raw HTTP REST calls (no SDK — avoids connection lifecycle bugs).
Usage:
    MLFLOW_TRACKING_URI=http://localhost:5001 python scripts/seed_mlflow_rest.py
"""
import os, json, time, requests

BASE = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5001")
S = requests.Session()
S.headers.update({"Content-Type": "application/json"})

def post(path, body):
    r = S.post(f"{BASE}{path}", json=body, timeout=30)
    return r.json()

def get(path, params=None):
    r = S.get(f"{BASE}{path}", params=params, timeout=30)
    return r.json()

def ts():
    return int(time.time() * 1000)

print(f"Seeding MLflow at {BASE} ...")

# ── Experiment ────────────────────────────────────────────────────────────────
try:
    d = post("/api/2.0/mlflow/experiments/create",
             {"name": "talentlens-risk-engine",
              "artifact_location": "/tmp/mlflow-artifacts"})
    exp_id = d["experiment_id"]
    print(f"Created experiment (id={exp_id})")
except Exception:
    d = get("/api/2.0/mlflow/experiments/get-by-name",
            {"experiment_name": "talentlens-risk-engine"})
    exp_id = d["experiment"]["experiment_id"]
    print(f"Experiment already exists (id={exp_id})")

# ── Helper ────────────────────────────────────────────────────────────────────
def make_run(name, params, metrics):
    r = post("/api/2.0/mlflow/runs/create",
             {"experiment_id": exp_id, "run_name": name, "start_time": ts()})
    run_id = r["run"]["info"]["run_id"]

    post("/api/2.0/mlflow/runs/log-batch", {
        "run_id": run_id,
        "params": [{"key": k, "value": str(v)} for k, v in params.items()],
        "metrics": [{"key": k, "value": float(v), "timestamp": ts(), "step": 0}
                    for k, v in metrics.items()],
    })

    post("/api/2.0/mlflow/runs/update",
         {"run_id": run_id, "status": "FINISHED", "end_time": ts()})

    print(f"  Run logged: {name}  (run_id={run_id})")
    return run_id

# ── XGBoost flight-risk ───────────────────────────────────────────────────────
run_id_xgb = make_run(
    "xgboost-flight-risk-v10",
    params={
        "model_type": "XGBoost", "n_estimators": 300, "max_depth": 6,
        "learning_rate": 0.05, "scale_pos_weight": 2.4,
        "objective": "binary:logistic", "n_employees_train": 10961,
        "attrition_rate": 0.297, "seed": 42,
    },
    metrics={
        "roc_auc": 0.980, "pr_auc": 0.971, "f1_score": 0.887,
        "precision": 0.901, "recall": 0.874, "accuracy": 0.923,
    },
)

# ── Isolation Forest anomaly ──────────────────────────────────────────────────
run_id_iso = make_run(
    "isolation-forest-anomaly-v10",
    params={
        "model_type": "IsolationForest", "n_estimators": 200,
        "contamination": 0.05, "max_samples": "auto",
        "n_employees_scored": 7706,
    },
    metrics={"anomaly_rate": 0.052, "mean_score": 0.031, "std_score": 0.089},
)

# ── Composite risk scoring ────────────────────────────────────────────────────
make_run(
    "composite-risk-index-v10",
    params={
        "weight_flight_risk": 0.50, "weight_anomaly": 0.35,
        "weight_compliance": 0.15, "n_employees_scored": 7706,
        "risk_bands": "Low:0-25 | Medium:26-50 | High:51-75 | Critical:76-100",
    },
    metrics={
        "avg_risk_index": 14.4, "pct_low": 0.912, "pct_medium": 0.074,
        "pct_high": 0.013, "pct_critical": 0.001,
        "high_critical_count": 11, "rows_written": 7706,
    },
)

# ── Register models ───────────────────────────────────────────────────────────
for model_name, run_id, uri_suffix in [
    ("talentlens-flight-risk",      run_id_xgb, "flight_risk_model"),
    ("talentlens-anomaly-detector", run_id_iso, "anomaly_model"),
]:
    # Create registered model (ignore if already exists)
    post("/api/2.0/mlflow/registered-models/create",
         {"name": model_name,
          "description": f"TalentLens {model_name} — trained on 10,961 employees"})

    # Create model version
    mv = post("/api/2.0/mlflow/model-versions/create", {
        "name": model_name,
        "source": f"runs:/{run_id}/{uri_suffix}",
        "run_id": run_id,
    })
    version = mv.get("model_version", {}).get("version", "?")

    # Transition to Production
    post("/api/2.0/mlflow/model-versions/transition-stage", {
        "name": model_name,
        "version": version,
        "stage": "Production",
        "archive_existing_versions": False,
    })
    print(f"  Registered model: {model_name}  v{version}  → Production")

print("\nDone! Refresh http://localhost:5001 → Experiments + Models tabs.")
