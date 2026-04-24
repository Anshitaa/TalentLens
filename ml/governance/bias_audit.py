"""
Fairlearn bias audit for the flight-risk model.

Checks demographic parity and equalized odds across:
  - gender
  - department
  - age_band

Logs metrics to MLflow. Prints a readable summary.
"""

import numpy as np
import pandas as pd
import mlflow
from fairlearn.metrics import (
    MetricFrame,
    demographic_parity_difference,
    equalized_odds_difference,
    selection_rate,
)
from sklearn.metrics import accuracy_score, recall_score, precision_score


SENSITIVE_FEATURES = ["gender", "department", "age_band"]

FAIRNESS_THRESHOLDS = {
    "demographic_parity_diff": 0.10,
    "equalized_odds_diff": 0.10,
}


def run(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_prob: np.ndarray,
    sensitive_df: pd.DataFrame,
    mlflow_run=None,
) -> dict:
    """
    Run Fairlearn audit. Returns dict of metric results per sensitive feature.
    """
    threshold = 0.40
    y_pred_bin = (y_prob >= threshold).astype(int) if y_pred is None else y_pred

    results = {}
    all_metrics = {}

    for feat in SENSITIVE_FEATURES:
        if feat not in sensitive_df.columns:
            continue

        groups = sensitive_df[feat]

        dp_diff = demographic_parity_difference(
            y_true, y_pred_bin, sensitive_features=groups
        )
        eo_diff = equalized_odds_difference(
            y_true, y_pred_bin, sensitive_features=groups
        )

        mf = MetricFrame(
            metrics={
                "selection_rate": selection_rate,
                "recall": lambda y, yp: recall_score(y, yp, zero_division=0),
                "precision": lambda y, yp: precision_score(y, yp, zero_division=0),
            },
            y_true=y_true,
            y_pred=y_pred_bin,
            sensitive_features=groups,
        )

        dp_flag = abs(dp_diff) > FAIRNESS_THRESHOLDS["demographic_parity_diff"]
        eo_flag = abs(eo_diff) > FAIRNESS_THRESHOLDS["equalized_odds_diff"]

        results[feat] = {
            "demographic_parity_diff": round(float(dp_diff), 4),
            "equalized_odds_diff":     round(float(eo_diff), 4),
            "dp_flag":                 dp_flag,
            "eo_flag":                 eo_flag,
            "by_group":                mf.by_group.round(4).to_dict(),
        }

        all_metrics[f"{feat}_dp_diff"] = round(float(dp_diff), 4)
        all_metrics[f"{feat}_eo_diff"] = round(float(eo_diff), 4)

    if mlflow_run:
        mlflow.log_metrics({f"fairness_{k}": v for k, v in all_metrics.items()})

    _print_report(results)
    return results


def _print_report(results: dict):
    print("\n  Fairlearn Bias Audit")
    print(f"  {'Feature':<15} {'DemParity':>10} {'EqualOdds':>10} {'Flags'}")
    print("  " + "-" * 55)
    for feat, r in results.items():
        flags = []
        if r["dp_flag"]:
            flags.append("DP⚠")
        if r["eo_flag"]:
            flags.append("EO⚠")
        flag_str = " ".join(flags) if flags else "✓"
        print(f"  {feat:<15} {r['demographic_parity_diff']:>10.4f} "
              f"{r['equalized_odds_diff']:>10.4f}  {flag_str}")
