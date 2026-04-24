"""
XGBoost flight-risk (attrition) model.

Trained on the full historical population (active + terminated employees).
~15% positive rate → uses scale_pos_weight to handle imbalance.
Evaluated with ROC-AUC + PR-AUC since classes are imbalanced.
"""

import numpy as np
import mlflow
import mlflow.xgboost
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    roc_auc_score, average_precision_score,
    f1_score, precision_score, recall_score,
    classification_report,
)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from ml.risk_engine.features import FEATURE_COLS, TARGET_COL


def train(X, y, mlflow_run=None):
    """
    Train XGBoost classifier. Logs params + metrics + model to active MLflow run.
    Returns fitted model.
    """
    X_tr, X_val, y_tr, y_val = train_test_split(
        X, y, test_size=0.20, stratify=y, random_state=42
    )

    neg, pos = (y_tr == 0).sum(), (y_tr == 1).sum()
    scale_pos_weight = neg / max(pos, 1)

    params = {
        "n_estimators": 400,
        "max_depth": 5,
        "learning_rate": 0.05,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "min_child_weight": 5,
        "scale_pos_weight": round(float(scale_pos_weight), 2),
        "eval_metric": "aucpr",
        "random_state": 42,
        "n_jobs": -1,
    }

    model = xgb.XGBClassifier(**params, enable_categorical=False)
    model.fit(
        X_tr, y_tr,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )

    y_prob = model.predict_proba(X_val)[:, 1]
    y_pred = (y_prob >= 0.40).astype(int)

    metrics = {
        "val_roc_auc":  round(roc_auc_score(y_val, y_prob), 4),
        "val_pr_auc":   round(average_precision_score(y_val, y_prob), 4),
        "val_f1":       round(f1_score(y_val, y_pred), 4),
        "val_precision": round(precision_score(y_val, y_pred, zero_division=0), 4),
        "val_recall":   round(recall_score(y_val, y_pred, zero_division=0), 4),
        "train_size":   len(X_tr),
        "val_size":     len(X_val),
        "pos_rate":     round(float(y_tr.mean()), 4),
    }

    if mlflow_run:
        mlflow.log_params(params)
        mlflow.log_metrics(metrics)
        _log_feature_importance(model, X_tr.columns.tolist())
        mlflow.xgboost.log_model(model, artifact_path="attrition_model",
                                 registered_model_name="talentlens-flight-risk")

    print(f"  XGBoost — ROC-AUC: {metrics['val_roc_auc']:.3f} | "
          f"PR-AUC: {metrics['val_pr_auc']:.3f} | "
          f"F1: {metrics['val_f1']:.3f}")
    print(classification_report(y_val, y_pred, target_names=["Active", "Attrited"]))

    return model, metrics


def _log_feature_importance(model, feature_names):
    fig, ax = plt.subplots(figsize=(8, 10))
    xgb.plot_importance(model, ax=ax, max_num_features=20,
                        importance_type="gain", title="XGBoost Feature Importance (Gain)")
    plt.tight_layout()
    mlflow.log_figure(fig, "feature_importance.png")
    plt.close(fig)
