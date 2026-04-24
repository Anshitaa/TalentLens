from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


class EmployeeOut(BaseModel):
    employee_id: str
    first_name: str
    last_name: str
    email: str
    department: str
    job_level: str
    job_role: str
    hire_date: date
    termination_date: Optional[date] = None
    is_active: bool
    monthly_income: float
    job_satisfaction: Optional[int] = Field(None, ge=1, le=4)
    environment_satisfaction: Optional[int] = Field(None, ge=1, le=4)
    work_life_balance: Optional[int] = Field(None, ge=1, le=4)
    performance_rating: Optional[int] = Field(None, ge=1, le=4)
    years_since_last_promotion: Optional[float] = None
    years_with_current_manager: Optional[float] = None
    years_at_company: Optional[float] = None
    distance_from_home: Optional[int] = None
    num_companies_worked: Optional[int] = None
    training_times_last_year: Optional[int] = None
    overtime_flag: bool = False
    education: Optional[int] = None
    education_field: Optional[str] = None
    marital_status: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = None
    age_band: Optional[str] = None
    manager_id: Optional[str] = None

    class Config:
        from_attributes = True


class EmployeeListOut(BaseModel):
    data: list[EmployeeOut]
    total: int
    page: int
    page_size: int
    has_next: bool


class HREventOut(BaseModel):
    event_id: str
    employee_id: str
    event_type: str
    event_date: date
    department: Optional[str] = None
    payload: Optional[dict] = None

    class Config:
        from_attributes = True


class EventsOut(BaseModel):
    data: list[HREventOut]
    total: int
    since: Optional[str] = None


class EmployeeUpdateIn(BaseModel):
    job_satisfaction: Optional[int] = Field(None, ge=1, le=4)
    environment_satisfaction: Optional[int] = Field(None, ge=1, le=4)
    work_life_balance: Optional[int] = Field(None, ge=1, le=4)
    performance_rating: Optional[int] = Field(None, ge=1, le=4)
    monthly_income: Optional[float] = None
    job_level: Optional[str] = None
    manager_id: Optional[str] = None
    overtime_flag: Optional[bool] = None
    termination_date: Optional[date] = None
    is_active: Optional[bool] = None


class EmployeeUpdateOut(BaseModel):
    employee_id: str
    updated_fields: list[str]
    updated_at: datetime
