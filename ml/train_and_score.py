"""
Phase 3 entry point — Train + Score + Govern.

Usage:
    python ml/train_and_score.py           # train + score + governance
    python ml/train_and_score.py --score-only  # skip training, load latest model

Output:
    mlruns/                  MLflow experiment artifacts
    mart.fact_risk_scores    one row per employee per run
    mart.mart_risk_index     upserted latest score per employee
    audit.model_decisions    immutable decision log
    audit.drift_reports      PSI drift report
"""

import argparse
import sys
import os

import mlflow
import mlflow.xgboost

# Ensure project root is on the path when running from subdirectories
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml.risk_engine.features import load_features, FEATURE_COLS, TARGET_COL, SENSITIVE_COLS
from ml.risk_engine import train_attrition, train_anomaly, inference
from ml.governance import mlflow_registry, drift_monitor, bias_audit, model_risk_card


MODEL_VERSION = "1.0.0"


def main(score_only: bool = False):
    mlflow_registry.setup()

    print("=" * 60)
    print("TalentLens Phase 3 — Risk ML Engine")
    print("=" * 60)

    # ── Load features ────────────────────────────────────────────────────────
    print("\n[1/5] Loading features ...")
    df_all = load_features()

    # Training population: all employees (active + attrited) with valid labels
    df_train = df_all.dropna(subset=[TARGET_COL]).copy()
    X_all = df_train[FEATURE_COLS].fillna(0)
    y_all = df_train[TARGET_COL].astype(int)

    # Active-only population: inference target
    df_active = df_all[df_all["is_active"]].copy()
    X_active = df_active[FEATURE_COLS].fillna(0)

    print(f"  Total employees:   {len(df_all):,}")
    print(f"  Training set:      {len(df_train):,}  (attrition rate: {y_all.mean():.1%})")
    print(f"  Active / scoring:  {len(df_active):,}")

    # ── Train or load models ─────────────────────────────────────────────────
    with mlflow_registry.start_run(run_name=f"risk-engine-v{MODEL_VERSION}") as run:
        mlflow.log_param("model_version", MODEL_VERSION)

        if not score_only:
            print("\n[2/5] Training XGBoost flight-risk model ...")
            xgb_model, xgb_metrics = train_attrition.train(X_all, y_all, mlflow_run=run)

            print("\n[3/5] Training Isolation Forest anomaly detector ...")
            if_model, if_scaler, if_metrics = train_anomaly.train(X_active, mlflow_run=run)
        else:
            print("\n[2/5] Loading latest registered models ...")
            xgb_model = mlflow.xgboost.load_model("models:/talentlens-flight-risk/latest")
            # IsolationForest scaler is not persisted between runs in score-only mode
            raise RuntimeError(
                "--score-only requires a pre-serialised IsolationForest scaler. "
                "Run without --score-only first."
            )

        # ── Inference ────────────────────────────────────────────────────────
        print(f"\n[4/5] Scoring active employees ...")
        summary = inference.run(xgb_model, if_model, if_scaler, model_version=MODEL_VERSION)
        mlflow.log_metrics({
            "n_scored":        summary["n_scored"],
            "pct_low":         summary["Low"]["pct"],
            "pct_medium":      summary["Medium"]["pct"],
            "pct_high":        summary["High"]["pct"],
            "pct_critical":    summary["Critical"]["pct"],
        })

        # ── Governance ───────────────────────────────────────────────────────
        print("\n[5/5] Governance checks ...")

        # PSI drift (reference = training data, current = active population)
        drift_report = drift_monitor.run(
            X_reference=X_all,
            X_current=X_active,
            model_version=MODEL_VERSION,
        )
        mlflow.log_metric("psi_overall", drift_report["overall_psi"])
        mlflow.log_param("psi_retrain_triggered", drift_report["retrain_triggered"])

        # Fairlearn bias audit (on training population with ground truth)
        y_prob_train = xgb_model.predict_proba(X_all)[:, 1]
        y_pred_train = (y_prob_train >= 0.40).astype(int)
        sensitive = df_train[SENSITIVE_COLS]
        bias_results = bias_audit.run(
            y_true=y_all.values,
            y_pred=y_pred_train,
            y_prob=y_prob_train,
            sensitive_df=sensitive,
            mlflow_run=run,
        )

        # SHAP summary plot
        from ml.risk_engine import shap_explainer as shap_mod
        print("  Logging SHAP summary plot ...")
        explainer = shap_mod.build_explainer(xgb_model)
        shap_mod.log_summary_plot(explainer, df_active)

        # Model risk card (Phase 4)
        print("  Generating model risk card ...")
        card_path = model_risk_card.generate(
            model_version=MODEL_VERSION,
            xgb_metrics=xgb_metrics if not score_only else {},
            bias_results=bias_results,
            drift_report={**drift_report, **summary},
            hitl_count=0,
            n_scored=summary["n_scored"],
        )
        print(f"  Risk card → {card_path}")

        run_id = run.info.run_id

    print("\n" + "=" * 60)
    print(f"  Phase 3+4 complete!")
    print(f"  MLflow run ID:  {run_id}")
    print(f"  Scoring run ID: {summary['scoring_run_id']}")
    print(f"  Rows written:   {summary['n_scored']:,} → mart.fact_risk_scores")
    print(f"  PSI:            {drift_report['overall_psi']:.4f} ({drift_report['interpretation']})")
    print(f"  Risk card:      {card_path}")
    print(f"\n  View MLflow UI:  mlflow ui --port 5001 --backend-store-uri mlruns")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--score-only", action="store_true",
                        help="Skip training; load latest model from registry")
    args = parser.parse_args()
    main(score_only=args.score_only)
