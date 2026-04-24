"""
Isolation Forest anomaly detector.

Trained on ACTIVE employees only (no label needed).
Detects behavioural outliers: unusual absence patterns, manager churn,
overtime spikes, performance drops.

Returns normalised anomaly scores in [0, 1] where 1 = most anomalous.
"""

import numpy as np
import mlflow
import mlflow.sklearn
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import MinMaxScaler


ANOMALY_FEATURES = [
    "absence_rate_90d", "overtime_rate_180d",
    "manager_changes_30d", "manager_changes_90d",
    "performance_rating_delta", "training_count_90d",
    "years_since_last_promotion", "income_vs_peer_median_pct",
]

_scaler: MinMaxScaler | None = None


def train(X_active, mlflow_run=None):
    """
    Train IsolationForest on active employees.
    Returns (model, scaler, metrics).
    """
    global _scaler

    X_sub = X_active[ANOMALY_FEATURES].fillna(0)
    _scaler = MinMaxScaler()
    X_scaled = _scaler.fit_transform(X_sub)

    contamination = 0.05  # expect ~5% behavioural outliers
    params = {
        "n_estimators": 200,
        "contamination": contamination,
        "max_samples": "auto",
        "random_state": 42,
        "n_jobs": -1,
    }
    model = IsolationForest(**params)
    model.fit(X_scaled)

    raw_scores = model.score_samples(X_scaled)           # negative → more anomalous
    normalised = _normalise(-raw_scores)
    outlier_pct = round(float((normalised > 0.7).mean() * 100), 2)

    metrics = {
        "anomaly_contamination": contamination,
        "anomaly_outlier_pct_threshold_0.7": outlier_pct,
        "anomaly_score_mean": round(float(normalised.mean()), 4),
        "anomaly_score_p95":  round(float(np.percentile(normalised, 95)), 4),
    }

    if mlflow_run:
        mlflow.log_params({f"if_{k}": v for k, v in params.items()})
        mlflow.log_metrics({f"if_{k}": v for k, v in metrics.items()})
        mlflow.sklearn.log_model(model, artifact_path="anomaly_model",
                                 registered_model_name="talentlens-anomaly-detector")

    print(f"  IsolationForest — outliers (>0.7): {outlier_pct}% | "
          f"mean score: {metrics['anomaly_score_mean']:.3f} | "
          f"p95: {metrics['anomaly_score_p95']:.3f}")

    return model, _scaler, metrics


def score(model, scaler, X) -> np.ndarray:
    """Score new data. Returns normalised anomaly scores in [0,1]."""
    X_sub = X[ANOMALY_FEATURES].fillna(0)
    X_scaled = scaler.transform(X_sub)
    raw = model.score_samples(X_scaled)
    return _normalise(-raw)


def _normalise(scores: np.ndarray) -> np.ndarray:
    lo, hi = scores.min(), scores.max()
    if hi == lo:
        return np.zeros_like(scores)
    return (scores - lo) / (hi - lo)
