"""
Risk router — exposes scored risk data from mart_risk_index and fact_risk_scores.
"""

from typing import Optional

import psycopg2
from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import get_db
from api.schemas.risk import DepartmentRisk, RiskScore, RiskScoreDetail, RiskSummary

router = APIRouter(prefix="/risk", tags=["risk"])


@router.get("/summary", response_model=RiskSummary)
def get_risk_summary(db=Depends(get_db)):
    """
    Return aggregate risk statistics: band counts, total employees scored,
    average risk index, and percentage in High/Critical bands.
    """
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT
                    latest_risk_band,
                    COUNT(*) AS cnt
                FROM mart.mart_risk_index
                GROUP BY latest_risk_band
                """
            )
            rows = cur.fetchall()

            cur.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    AVG(latest_risk_index) AS avg_risk_index
                FROM mart.mart_risk_index
                """
            )
            agg = cur.fetchone()

    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    band_counts: dict[str, int] = {}
    for row in rows:
        band = row["latest_risk_band"] or "Unknown"
        band_counts[band] = int(row["cnt"])

    total = int(agg["total"]) if agg["total"] else 0
    avg_risk_index = float(agg["avg_risk_index"]) if agg["avg_risk_index"] else 0.0

    high_critical = sum(
        v for k, v in band_counts.items() if k in ("High", "Critical")
    )
    pct_high_critical = (high_critical / total * 100) if total > 0 else 0.0

    return RiskSummary(
        band_counts=band_counts,
        total=total,
        avg_risk_index=round(avg_risk_index, 4),
        pct_high_critical=round(pct_high_critical, 2),
    )


@router.get("/scores", response_model=list[RiskScore])
def get_risk_scores(
    band: Optional[str] = Query(default=None, description="Filter by risk band (e.g. High)"),
    dept: Optional[str] = Query(default=None, description="Filter by department"),
    limit: int = Query(default=50, ge=1, le=500),
    db=Depends(get_db),
):
    """
    Return risk scores from mart_risk_index.
    Supports optional ?band= and ?dept= filters and a ?limit= cap.
    """
    filters = []
    params: list = []

    if band:
        filters.append("latest_risk_band = %s")
        params.append(band)
    if dept:
        filters.append("department = %s")
        params.append(dept)

    where_clause = ("WHERE " + " AND ".join(filters)) if filters else ""
    params.append(limit)

    sql = f"""
        SELECT
            employee_id, full_name, department, job_level,
            latest_risk_index, latest_risk_band,
            prev_risk_index, risk_delta,
            flight_risk_prob, anomaly_score,
            shap_top_feature_1, shap_top_feature_2, shap_top_feature_3,
            last_scored_at, _updated_at
        FROM mart.mart_risk_index
        {where_clause}
        ORDER BY latest_risk_index DESC NULLS LAST
        LIMIT %s
    """

    try:
        with db.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    return [RiskScore(**dict(row)) for row in rows]


@router.get("/top", response_model=list[RiskScore])
def get_top_risk(db=Depends(get_db)):
    """Return the top 20 employees by risk_index from mart_risk_index."""
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT
                    employee_id, full_name, department, job_level,
                    latest_risk_index, latest_risk_band,
                    prev_risk_index, risk_delta,
                    flight_risk_prob, anomaly_score,
                    shap_top_feature_1, shap_top_feature_2, shap_top_feature_3,
                    last_scored_at, _updated_at
                FROM mart.mart_risk_index
                ORDER BY latest_risk_index DESC NULLS LAST
                LIMIT 20
                """
            )
            rows = cur.fetchall()
    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    return [RiskScore(**dict(row)) for row in rows]


@router.get("/scores/{employee_id}", response_model=list[RiskScoreDetail])
def get_employee_score_history(employee_id: str, db=Depends(get_db)):
    """
    Return all scoring history for a single employee from fact_risk_scores,
    ordered newest-first.
    """
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT
                    score_id, employee_id, scoring_run_id, scored_at,
                    flight_risk_prob, anomaly_score, compliance_flag,
                    risk_index, risk_band,
                    shap_top_feature_1, shap_top_feature_2, shap_top_feature_3,
                    shap_value_1, shap_value_2, shap_value_3,
                    model_version, _loaded_at
                FROM mart.fact_risk_scores
                WHERE employee_id = %s
                ORDER BY scored_at DESC
                """,
                (employee_id,),
            )
            rows = cur.fetchall()
    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    if not rows:
        raise HTTPException(
            status_code=404, detail=f"No score history found for employee {employee_id}"
        )

    return [RiskScoreDetail(**dict(row)) for row in rows]


@router.get("/department", response_model=list[DepartmentRisk])
def get_department_risk(db=Depends(get_db)):
    """Return average risk_index and employee count grouped by department."""
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT
                    department,
                    ROUND(AVG(latest_risk_index)::numeric, 4) AS avg_risk_index,
                    COUNT(*) AS employee_count
                FROM mart.mart_risk_index
                WHERE department IS NOT NULL
                GROUP BY department
                ORDER BY avg_risk_index DESC
                """
            )
            rows = cur.fetchall()
    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    return [
        DepartmentRisk(
            department=row["department"],
            avg_risk_index=float(row["avg_risk_index"]),
            employee_count=int(row["employee_count"]),
        )
        for row in rows
    ]
