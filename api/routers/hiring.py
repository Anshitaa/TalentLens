"""
Hiring router — funnel conversion rates and overall hiring summary
from mart.fact_hiring_funnel.
"""

import psycopg2
from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import get_db

router = APIRouter(prefix="/hiring", tags=["hiring"])


@router.get("/funnel")
def get_hiring_funnel(db=Depends(get_db)):
    """
    Return funnel conversion rates by department.
    Computes: total applicants, screened, interviewed, offered, hired counts
    and conversion rates at each stage, grouped by department.
    """
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT
                    department,
                    COUNT(*) AS total_candidates,
                    COUNT(*) FILTER (WHERE days_to_screen IS NOT NULL)    AS reached_screen,
                    COUNT(*) FILTER (WHERE days_to_interview IS NOT NULL) AS reached_interview,
                    COUNT(*) FILTER (WHERE days_to_offer IS NOT NULL)     AS reached_offer,
                    COUNT(*) FILTER (WHERE outcome = 'Hired')             AS hired,
                    ROUND(AVG(days_to_screen)::numeric, 1)    AS avg_days_to_screen,
                    ROUND(AVG(days_to_interview)::numeric, 1) AS avg_days_to_interview,
                    ROUND(AVG(days_to_offer)::numeric, 1)     AS avg_days_to_offer,
                    ROUND(AVG(days_to_close)::numeric, 1)     AS avg_days_to_close
                FROM mart.fact_hiring_funnel
                GROUP BY department
                ORDER BY total_candidates DESC
                """
            )
            rows = cur.fetchall()
    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    result = []
    for row in rows:
        d = dict(row)
        total = d["total_candidates"] or 0
        hired = d["hired"] or 0
        reached_screen = d["reached_screen"] or 0
        reached_interview = d["reached_interview"] or 0
        reached_offer = d["reached_offer"] or 0

        result.append(
            {
                "department": d["department"],
                "total_candidates": total,
                "reached_screen": reached_screen,
                "reached_interview": reached_interview,
                "reached_offer": reached_offer,
                "hired": hired,
                "conversion_rates": {
                    "application_to_screen": round(reached_screen / total * 100, 1) if total else 0,
                    "screen_to_interview": round(reached_interview / reached_screen * 100, 1) if reached_screen else 0,
                    "interview_to_offer": round(reached_offer / reached_interview * 100, 1) if reached_interview else 0,
                    "offer_to_hire": round(hired / reached_offer * 100, 1) if reached_offer else 0,
                    "overall_hire_rate": round(hired / total * 100, 1) if total else 0,
                },
                "avg_days": {
                    "to_screen": d["avg_days_to_screen"],
                    "to_interview": d["avg_days_to_interview"],
                    "to_offer": d["avg_days_to_offer"],
                    "to_close": d["avg_days_to_close"],
                },
            }
        )

    return result


@router.get("/summary")
def get_hiring_summary(db=Depends(get_db)):
    """
    Return overall hiring summary: total candidates, overall hire rate,
    and average days to close across all departments.
    """
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*)                                          AS total_candidates,
                    COUNT(*) FILTER (WHERE outcome = 'Hired')        AS total_hired,
                    ROUND(AVG(days_to_close)::numeric, 1)            AS avg_days_to_close,
                    ROUND(AVG(days_to_screen)::numeric, 1)           AS avg_days_to_screen,
                    ROUND(AVG(days_to_interview)::numeric, 1)        AS avg_days_to_interview,
                    ROUND(AVG(days_to_offer)::numeric, 1)            AS avg_days_to_offer,
                    COUNT(DISTINCT department)                        AS departments_hiring
                FROM mart.fact_hiring_funnel
                """
            )
            row = cur.fetchone()
    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    if not row:
        return {"message": "No hiring data available"}

    d = dict(row)
    total = d["total_candidates"] or 0
    hired = d["total_hired"] or 0

    return {
        "total_candidates": total,
        "total_hired": hired,
        "hire_rate_pct": round(hired / total * 100, 2) if total else 0.0,
        "avg_days_to_close": d["avg_days_to_close"],
        "avg_days_to_screen": d["avg_days_to_screen"],
        "avg_days_to_interview": d["avg_days_to_interview"],
        "avg_days_to_offer": d["avg_days_to_offer"],
        "departments_hiring": d["departments_hiring"],
    }
