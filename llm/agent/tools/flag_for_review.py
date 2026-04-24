"""
LangChain tool: flag_for_review

Flags an employee for human review by writing to the audit.hitl_overrides
table via the existing HITL workflow, without correcting the model's label.
The override_label is set to 0 and the reason is prefixed with "[AGENT FLAG]".
"""

import os

import psycopg2
from langchain_core.tools import tool

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://talentlens:talentlens@localhost:5434/talentlens",
)

_AGENT_REVIEWER_ID = "llm-agent"


@tool
def flag_for_review(employee_id: str, reason: str) -> str:
    """
    Flag an employee for human HR review without correcting the model's risk label.

    Writes a record to audit.hitl_overrides with override_label=0 and the
    reason prefixed with "[AGENT FLAG]". An HR manager will then review and
    decide whether further action is needed.

    Args:
        employee_id: The employee's unique identifier string.
        reason:      Plain-English explanation of why this employee needs review.

    Returns a confirmation string with the employee_id and flag reason.
    """
    prefixed_reason = f"[AGENT FLAG] {reason}"

    try:
        # Write directly so we don't require an original_risk_index lookup
        conn = psycopg2.connect(DATABASE_URL)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO audit.hitl_overrides
                        (employee_id, reviewer_id, original_risk_index,
                         override_label, reason, notes)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        employee_id,
                        _AGENT_REVIEWER_ID,
                        None,          # original_risk_index unknown at flag time
                        0,             # override_label=0 per spec (flags for review)
                        prefixed_reason,
                        "Flagged by LLM agent for human review",
                    ),
                )
            conn.commit()
        finally:
            conn.close()

        return (
            f"Employee {employee_id} successfully flagged for human review. "
            f"Reason recorded: {prefixed_reason}"
        )

    except Exception as exc:
        # Graceful degradation: log what would have been written
        return (
            f"[DB unavailable — would have flagged employee {employee_id} "
            f"with reason: {prefixed_reason}. Error: {exc}]"
        )
