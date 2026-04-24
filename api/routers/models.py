"""
Models router — MLflow run summaries and fairness metrics.
"""

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/models", tags=["models"])

# Attempt to import MLflow; degrade gracefully if unavailable.
try:
    import mlflow
    from mlflow.tracking import MlflowClient

    _MLFLOW_AVAILABLE = True
except ImportError:
    _MLFLOW_AVAILABLE = False


def _get_mlflow_client():
    """Return a MlflowClient pointed at the local mlruns directory."""
    mlflow.set_tracking_uri("mlruns")
    return MlflowClient()


@router.get("/runs")
def get_model_runs():
    """
    Return a summary of the last 10 MLflow runs across all experiments,
    reading the local mlruns/ directory directly via MlflowClient.
    """
    if not _MLFLOW_AVAILABLE:
        return {
            "error": "module not available",
            "detail": "mlflow is not installed. Install it via pip install mlflow.",
        }

    try:
        client = _get_mlflow_client()
        experiments = client.search_experiments()

        runs = []
        for exp in experiments:
            try:
                exp_runs = client.search_runs(
                    experiment_ids=[exp.experiment_id],
                    order_by=["start_time DESC"],
                    max_results=10,
                )
            except Exception:
                continue
            for run in exp_runs:
                try:
                    runs.append(
                        {
                            "run_id": run.info.run_id,
                            "experiment_id": run.info.experiment_id,
                            "experiment_name": exp.name,
                            "status": run.info.status,
                            "start_time": run.info.start_time,
                            "end_time": run.info.end_time,
                            "metrics": dict(run.data.metrics),
                            "params": dict(run.data.params),
                            "tags": {
                                k: v
                                for k, v in run.data.tags.items()
                                if not k.startswith("mlflow.")
                            },
                        }
                    )
                except Exception:
                    continue

        # Sort globally by start_time desc and return top 10
        runs.sort(key=lambda r: r["start_time"] or 0, reverse=True)
        return runs[:10]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MLflow error: {e}")


@router.get("/fairness")
def get_fairness_metrics():
    """
    Return the latest fairness metrics stored as MLflow tags/metrics.
    Looks for runs tagged with 'fairness' in their tags or experiment name.
    """
    if not _MLFLOW_AVAILABLE:
        return {
            "error": "module not available",
            "detail": "mlflow is not installed. Install it via pip install mlflow.",
        }

    try:
        client = _get_mlflow_client()
        experiments = client.search_experiments()

        fairness_runs = []
        for exp in experiments:
            runs = client.search_runs(
                experiment_ids=[exp.experiment_id],
                order_by=["start_time DESC"],
                max_results=50,
            )
            for run in runs:
                tags = run.data.tags
                metrics = run.data.metrics

                # Include runs that have any fairness-related metric or tag
                fairness_metrics = {
                    k: v
                    for k, v in metrics.items()
                    if any(
                        kw in k.lower()
                        for kw in ("fairness", "demographic", "equalized", "disparate", "bias")
                    )
                }
                is_fairness_tagged = any(
                    "fairness" in str(v).lower() or "bias" in str(v).lower()
                    for v in tags.values()
                )

                if fairness_metrics or is_fairness_tagged:
                    fairness_runs.append(
                        {
                            "run_id": run.info.run_id,
                            "experiment_name": exp.name,
                            "start_time": run.info.start_time,
                            "fairness_metrics": fairness_metrics,
                            "tags": {
                                k: v
                                for k, v in tags.items()
                                if not k.startswith("mlflow.")
                            },
                        }
                    )

        fairness_runs.sort(key=lambda r: r["start_time"] or 0, reverse=True)
        latest = fairness_runs[:1]

        if not latest:
            return {"message": "No fairness metrics found in MLflow runs", "data": []}

        return {"data": latest}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MLflow error: {e}")
