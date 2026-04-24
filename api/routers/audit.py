"""
Audit router — HITL overrides and drift reports.
"""

import psycopg2
from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import get_db
from api.schemas.risk import DriftReport, OverrideRequest

router = APIRouter(prefix="/audit", tags=["audit"])

# Attempt to import the HITL module; degrade gracefully if unavailable.
try:
    from ml.governance.hitl_workflow import submit_override as _submit_override

    _HITL_AVAILABLE = True
except ImportError:
    _HITL_AVAILABLE = False


@router.post("/override")
def submit_hitl_override(body: OverrideRequest, db=Depends(get_db)):
    """
    Submit a Human-in-the-Loop override for an employee risk prediction.
    Calls ml.governance.hitl_workflow.submit_override() which writes to
    audit.hitl_overrides and audit.active_learning_labels.
    """
    if not _HITL_AVAILABLE:
        return {
            "error": "module not available",
            "detail": "ml.governance.hitl_workflow could not be imported. "
                      "Ensure Phase 3 ML dependencies are installed.",
        }

    # Fetch the employee's current risk index to pass through to the audit log.
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT latest_risk_index FROM mart.mart_risk_index WHERE employee_id = %s",
                (body.employee_id,),
            )
            row = cur.fetchone()
    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"DB error fetching risk index: {e}")

    original_risk_index = float(row["latest_risk_index"]) if row else 0.0

    try:
        _submit_override(
            employee_id=body.employee_id,
            reviewer_id=body.reviewer_id,
            override_label=body.override_label,
            reason=body.reason,
            original_risk_index=original_risk_index,
            notes=body.notes or "",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Override submission failed: {e}")

    return {
        "status": "accepted",
        "employee_id": body.employee_id,
        "reviewer_id": body.reviewer_id,
        "override_label": body.override_label,
    }


@router.get("/overrides")
def list_overrides(db=Depends(get_db)):
    """Return the last 100 HITL overrides from audit.hitl_overrides."""
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM audit.hitl_overrides
                ORDER BY override_at DESC
                LIMIT 100
                """
            )
            rows = cur.fetchall()
    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    return [dict(row) for row in rows]


@router.get("/drift", response_model=list[DriftReport])
def list_drift_reports(db=Depends(get_db)):
    """Return all drift reports from audit.drift_reports, newest first."""
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT
                    run_date,
                    model_version,
                    psi_score,
                    feature_psi_detail,
                    retrain_triggered
                FROM audit.drift_reports
                ORDER BY run_date DESC
                """
            )
            rows = cur.fetchall()
    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    return [DriftReport(**dict(row)) for row in rows]
