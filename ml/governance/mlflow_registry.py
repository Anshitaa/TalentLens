"""
MLflow model registry helpers.

Uses local file-based tracking (mlruns/) — no server required.
Run `mlflow ui --port 5001` to browse experiments.
"""

import os
import mlflow

MLFLOW_TRACKING_URI = os.getenv(
    "MLFLOW_TRACKING_URI",
    "file:///Users/anshita/Desktop/TalentLens/mlruns",
)
EXPERIMENT_NAME = "talentlens-risk-engine"


def setup():
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(EXPERIMENT_NAME)


def start_run(run_name: str):
    return mlflow.start_run(run_name=run_name)


def get_latest_model_version(model_name: str) -> str | None:
    """Return version string of the latest registered model, or None."""
    client = mlflow.tracking.MlflowClient(tracking_uri=MLFLOW_TRACKING_URI)
    try:
        versions = client.search_model_versions(f"name='{model_name}'")
        if not versions:
            return None
        latest = max(versions, key=lambda v: int(v.version))
        return latest.version
    except Exception:
        return None


def promote_to_production(model_name: str, version: str):
    client = mlflow.tracking.MlflowClient(tracking_uri=MLFLOW_TRACKING_URI)
    client.set_model_version_tag(model_name, version, "stage", "Production")
    print(f"  Promoted {model_name} v{version} → Production")
