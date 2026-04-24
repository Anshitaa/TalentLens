import math
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


def _sanitize_float(v):
    """Convert NaN/Inf (legal in PostgreSQL but not in JSON) to None."""
    if v is None:
        return None
    try:
        f = float(v)
        return None if not math.isfinite(f) else f
    except (TypeError, ValueError):
        return None


class RiskScore(BaseModel):
    """Represents a row from mart.mart_risk_index."""

    employee_id: UUID
    full_name: Optional[str] = None
    department: Optional[str] = None
    job_level: Optional[str] = None
    latest_risk_index: Optional[float] = None
    latest_risk_band: Optional[str] = None
    prev_risk_index: Optional[float] = None
    risk_delta: Optional[float] = None
    flight_risk_prob: Optional[float] = None
    anomaly_score: Optional[float] = None
    shap_top_feature_1: Optional[str] = None
    shap_top_feature_2: Optional[str] = None
    shap_top_feature_3: Optional[str] = None
    last_scored_at: Optional[datetime] = None
    _updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

    @field_validator("prev_risk_index", "risk_delta", "flight_risk_prob",
                     "anomaly_score", "latest_risk_index", mode="before")
    @classmethod
    def sanitize_float(cls, v):
        return _sanitize_float(v)


class RiskSummary(BaseModel):
    """Aggregate risk statistics across all employees."""

    band_counts: dict[str, int] = Field(
        description="Count of employees per risk band, e.g. {'Low': 120, 'High': 30}"
    )
    total: int = Field(description="Total number of scored employees")
    avg_risk_index: float = Field(description="Mean risk index across all employees")
    pct_high_critical: float = Field(
        description="Percentage of employees in High or Critical risk bands"
    )


class RiskScoreDetail(BaseModel):
    """Represents a row from mart.fact_risk_scores (score history for an employee)."""

    score_id: UUID
    employee_id: UUID
    scoring_run_id: Optional[str] = None
    scored_at: Optional[datetime] = None
    flight_risk_prob: Optional[float] = None
    anomaly_score: Optional[float] = None
    compliance_flag: Optional[bool] = None
    risk_index: Optional[float] = None
    risk_band: Optional[str] = None
    shap_top_feature_1: Optional[str] = None
    shap_top_feature_2: Optional[str] = None
    shap_top_feature_3: Optional[str] = None
    shap_value_1: Optional[float] = None
    shap_value_2: Optional[float] = None
    shap_value_3: Optional[float] = None
    model_version: Optional[str] = None
    _loaded_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class OverrideRequest(BaseModel):
    """Request body for submitting a HITL override."""

    employee_id: str = Field(description="UUID of the employee being overridden")
    reviewer_id: str = Field(description="ID of the HR manager submitting the override")
    override_label: int = Field(
        ge=0, le=1, description="0 = not at risk, 1 = at risk (model disagreement)"
    )
    reason: str = Field(description="Reason for the override decision")
    notes: Optional[str] = Field(default=None, description="Optional additional notes")


class DriftReport(BaseModel):
    """Represents a drift detection report from audit.drift_reports."""

    run_date: Optional[datetime] = None
    model_version: Optional[str] = None
    psi_score: Optional[float] = None
    feature_psi_detail: Optional[dict] = Field(
        default=None, description="Per-feature PSI scores as a JSON dict"
    )
    retrain_triggered: Optional[bool] = None

    model_config = {"from_attributes": True}


class DepartmentRisk(BaseModel):
    """Average risk index per department."""

    department: str
    avg_risk_index: float
    employee_count: int
