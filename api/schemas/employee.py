from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class Employee(BaseModel):
    """
    Full employee record — join of dim_employee with latest risk data
    from mart_risk_index.
    """

    # dim_employee fields
    employee_id: str
    full_name: Optional[str] = None
    department: Optional[str] = None
    job_level: Optional[str] = None
    monthly_income: Optional[float] = None
    job_satisfaction: Optional[int] = None
    performance_rating: Optional[int] = None
    is_active: Optional[bool] = None
    has_attrited: Optional[bool] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    age_band: Optional[str] = None
    hire_date: Optional[date] = None

    # mart_risk_index fields (latest risk snapshot)
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

    model_config = {"from_attributes": True}


class EmployeeListItem(BaseModel):
    """
    Lighter employee record for list/paginated endpoints — avoids sending
    all dim_employee columns when only a summary is needed.
    """

    employee_id: str
    full_name: Optional[str] = None
    department: Optional[str] = None
    job_level: Optional[str] = None
    is_active: Optional[bool] = None
    latest_risk_index: Optional[float] = None
    latest_risk_band: Optional[str] = None
    flight_risk_prob: Optional[float] = None
    last_scored_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
