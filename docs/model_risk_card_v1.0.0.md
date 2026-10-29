# TalentLens Flight-Risk Model — Risk Card

**Model:** `talentlens-flight-risk`
**Version:** 1.0.0
**Generated:** 2026-10-29
**Scored population:** 30,824 active employees

---

## 1. Model Overview

| Field | Value |
|---|---|
| Algorithm | XGBoost (gradient boosted trees) |
| Target | Binary attrition risk (0 = active, 1 = attrited) |
| Composite Risk Index | 0.50 × flight_prob + 0.35 × anomaly_score + 0.15 × compliance_flag |
| Training data | Synthetic HR dataset — 32,883 employees, 578K events |
| Feature sources | mart.dim_employee (HR attributes) + mart.feature_store (PySpark rolling features) |
| Explainability | SHAP TreeExplainer — top-3 features per employee |

---

## 2. Performance Metrics (Validation Set, 20% holdout)

| Metric | Value |
|---|---|
| ROC-AUC | 0.9967 |
| PR-AUC | 0.9936 |
| F1 Score | 0.9513 |
| Precision | 0.9287 |
| Recall | 0.975 |
| Threshold | 0.40 (optimised for recall on attrition minority class) |

> **Note on synthetic data:** The model achieves near-perfect AUC because the
> synthetic generator derived attrition labels from the same features used for
> training. In a real deployment, expect AUC in the 0.75–0.88 range based on
> comparable published HR attrition literature.

---

## 3. Risk Band Distribution (Latest Scoring Run)

| Band | Count | % |
|---|---|---|
| Low | 26700 | 86.6% |
| Medium | 4092 | 13.3% |
| High | 32 | 0.1% |
| Critical | 0 | 0.0% |

---

## 4. Fairness Audit (Fairlearn)

Threshold: demographic parity difference > 0.10 flagged.

| Sensitive Feature | Demographic Parity Diff | Equalized Odds Diff | Status |
|---|---|---|---|
| gender | 0.0296 | 0.0069 | ✓ Pass |
| department | 0.2793 | 0.0428 | ⚠ Flag |
| age_band | 0.0256 | 0.0073 | ✓ Pass |


**Actionable:** Department shows demographic parity gap (0.26).
Recommend reviewing whether Engineering/Sales over-representation in High/Critical
bands reflects genuine risk signal or department-level data artefacts.

---

## 5. Drift Monitoring (PSI)

| Metric | Value |
|---|---|
| Overall PSI | 0.0249 |
| Interpretation | stable |
| Retrain triggered | False |

**Highest-drift features:**
- `performance_rating_delta` — PSI high because training set includes all employees
  (active + terminated) while scoring is active-only. Expected structural difference.
- `income_peer_percentile` — slight distribution shift between historical and current cohort.

---

## 6. HITL Active Learning

| Metric | Value |
|---|---|
| Human override labels (total) | 0 |
| Retrain threshold | 50 new labels OR PSI > 0.20 |
| Uncertainty sampling band | 0.35 – 0.65 predicted probability |
| Uncertainty sample size | 200 per retraining run |

---

## 7. Known Limitations

1. **Synthetic training data** — all performance metrics are inflated vs real-world data.
2. **Static snapshot** — model trained on point-in-time data; does not capture intra-week events.
3. **No causal inference** — high risk score indicates correlation with attrition patterns, not causation.
4. **Department parity gap** — Department demographic parity difference exceeds 0.10 threshold. Do not use as sole basis for HR decisions.
5. **Cold-start** — new employees (<90 days) have no rolling features; COALESCE defaults apply.

---

## 8. Recommended Review Schedule

| Trigger | Action |
|---|---|
| Weekly | PSI drift report automated via Airflow `drift_monitor_dag` |
| ≥50 HITL labels | Automatic retraining with Optuna tuning |
| PSI > 0.20 | Retrain regardless of label count |
| Quarterly | Full bias audit re-run with updated demographic composition |
| Model promoted | Update this risk card, notify model risk committee |

---

*Generated automatically by `ml/governance/model_risk_card.py`*
