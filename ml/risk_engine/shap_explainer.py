"""
SHAP explainability for XGBoost flight-risk model.

Returns the top-3 features and their SHAP values for every scored employee.
Uses TreeExplainer (fast, exact for tree models).
"""

import numpy as np
import pandas as pd
import shap
import mlflow
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from ml.risk_engine.features import FEATURE_COLS


def build_explainer(model):
    return shap.TreeExplainer(model)


def top3_shap(explainer, X: pd.DataFrame) -> pd.DataFrame:
    """
    Returns DataFrame with columns:
        shap_top_feature_1/2/3  (feature name)
        shap_value_1/2/3        (SHAP value, can be negative)
    """
    shap_values = explainer.shap_values(X[FEATURE_COLS])   # shape (n, p)
    abs_vals = np.abs(shap_values)

    top3_idx = np.argsort(-abs_vals, axis=1)[:, :3]
    feature_names = np.array(FEATURE_COLS)

    rows = []
    for i, (idxs, vals) in enumerate(zip(top3_idx, shap_values)):
        rows.append({
            "shap_top_feature_1": feature_names[idxs[0]],
            "shap_top_feature_2": feature_names[idxs[1]],
            "shap_top_feature_3": feature_names[idxs[2]],
            "shap_value_1": round(float(vals[idxs[0]]), 4),
            "shap_value_2": round(float(vals[idxs[1]]), 4),
            "shap_value_3": round(float(vals[idxs[2]]), 4),
        })
    return pd.DataFrame(rows)


def log_summary_plot(explainer, X: pd.DataFrame, n_sample: int = 500):
    """Log SHAP summary beeswarm plot to MLflow (sampled for speed)."""
    X_sample = X[FEATURE_COLS].sample(min(n_sample, len(X)), random_state=42)
    shap_vals = explainer.shap_values(X_sample)

    fig, ax = plt.subplots(figsize=(10, 8))
    shap.summary_plot(shap_vals, X_sample, feature_names=FEATURE_COLS,
                      show=False, plot_size=None)
    plt.tight_layout()
    mlflow.log_figure(fig, "shap_summary.png")
    plt.close(fig)
