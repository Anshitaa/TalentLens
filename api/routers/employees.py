"""
Employees router — paginated employee list and individual detail endpoint.
Joins dim_employee with mart_risk_index for latest risk data.
"""

from typing import Optional

import psycopg2
from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import get_db
from api.schemas.employee import Employee, EmployeeListItem

router = APIRouter(prefix="/employees", tags=["employees"])

_EMPLOYEE_LIST_SELECT = """
    SELECT
        e.employee_id,
        e.full_name,
        e.department,
        e.job_level,
        e.is_active,
        r.latest_risk_index,
        r.latest_risk_band,
        r.flight_risk_prob,
        r.last_scored_at
    FROM mart.dim_employee e
    LEFT JOIN mart.mart_risk_index r
        ON e.employee_id::text = r.employee_id::text
"""

_EMPLOYEE_DETAIL_SELECT = """
    SELECT
        e.employee_id,
        e.full_name,
        e.department,
        e.job_level,
        e.monthly_income,
        e.job_satisfaction,
        e.performance_rating,
        e.is_active,
        e.has_attrited,
        e.age,
        e.gender,
        e.age_band,
        e.hire_date,
        r.latest_risk_index,
        r.latest_risk_band,
        r.prev_risk_index,
        r.risk_delta,
        r.flight_risk_prob,
        r.anomaly_score,
        r.shap_top_feature_1,
        r.shap_top_feature_2,
        r.shap_top_feature_3,
        r.last_scored_at
    FROM mart.dim_employee e
    LEFT JOIN mart.mart_risk_index r
        ON e.employee_id::text = r.employee_id::text
"""


@router.get("", response_model=list[EmployeeListItem])
def list_employees(
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    size: int = Query(default=50, ge=1, le=200, description="Records per page"),
    dept: Optional[str] = Query(default=None, description="Filter by department name"),
    active: Optional[bool] = Query(default=None, description="Filter by is_active status"),
    db=Depends(get_db),
):
    """
    Return a paginated list of employees with their latest risk snapshot.
    Supports ?dept= and ?active= filters.
    """
    filters = []
    params: list = []

    if dept:
        filters.append("e.department = %s")
        params.append(dept)
    if active is not None:
        filters.append("e.is_active = %s")
        params.append(active)

    where_clause = ("WHERE " + " AND ".join(filters)) if filters else ""
    offset = (page - 1) * size
    params.extend([size, offset])

    sql = f"""
        {_EMPLOYEE_LIST_SELECT}
        {where_clause}
        ORDER BY e.full_name ASC
        LIMIT %s OFFSET %s
    """

    try:
        with db.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    return [EmployeeListItem(**dict(row)) for row in rows]


@router.get("/{employee_id}", response_model=Employee)
def get_employee(employee_id: str, db=Depends(get_db)):
    """
    Return full employee detail joined with their latest risk score.
    Returns 404 if the employee_id does not exist in dim_employee.
    """
    try:
        with db.cursor() as cur:
            cur.execute(
                f"{_EMPLOYEE_DETAIL_SELECT} WHERE e.employee_id = %s",
                (employee_id,),
            )
            row = cur.fetchone()
    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    if row is None:
        raise HTTPException(
            status_code=404, detail=f"Employee {employee_id} not found"
        )

    return Employee(**dict(row))
