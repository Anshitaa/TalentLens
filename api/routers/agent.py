"""
Agent router — LLM chat and risk narration endpoints.
"""

import os

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import get_db
from api.schemas.agent import ChatRequest, ChatResponse

router = APIRouter(prefix="/agent", tags=["agent"])

# Conditionally import LLM modules; degrade gracefully if missing.
try:
    from llm.agent import react_agent as _react_agent_module

    _AGENT_AVAILABLE = True
except ImportError:
    _AGENT_AVAILABLE = False

try:
    from llm import risk_narrator as _risk_narrator_module

    _NARRATOR_AVAILABLE = True
except ImportError:
    _NARRATOR_AVAILABLE = False

_NO_KEY_MESSAGES = {
    "gemini": (
        "GEMINI_API_KEY is not set. "
        "Get a free key at aistudio.google.com, then: export GEMINI_API_KEY=AIza..."
    ),
    "anthropic": (
        "ANTHROPIC_API_KEY is not set. "
        "Example: export ANTHROPIC_API_KEY=sk-ant-..."
    ),
    "openai": (
        "OPENAI_API_KEY is not set. "
        "Example: export OPENAI_API_KEY=sk-..."
    ),
}

_KEY_ENV_VARS = {
    "gemini": "GEMINI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
}


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest):
    """
    Send a message to the ReAct agent and receive a response.
    Default provider is 'gemini' (free tier). Also supports 'anthropic', 'openai', 'local'.
    """
    provider = body.provider.lower()

    env_var = _KEY_ENV_VARS.get(provider)
    if env_var and not os.getenv(env_var):
        return ChatResponse(
            response=_NO_KEY_MESSAGES.get(provider, f"{env_var} is not set."),
            tool_calls_used=[],
        )

    if not _AGENT_AVAILABLE:
        return ChatResponse(
            response="The agent module (llm.agent.react_agent) is not available. "
                     "Ensure Phase 5 LLM dependencies are installed.",
            tool_calls_used=[],
        )

    try:
        result = _react_agent_module.chat(message=body.message, provider=provider)

        # Normalise the return value: accept str or dict with 'response' / 'tool_calls_used'
        if isinstance(result, str):
            return ChatResponse(response=result, tool_calls_used=[])

        return ChatResponse(
            response=result.get("response", str(result)),
            tool_calls_used=result.get("tool_calls_used", []),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {e}")


@router.get("/narrate/{employee_id}")
def narrate_risk(employee_id: str, db=Depends(get_db)):
    """
    Generate a plain-English risk narration for a single employee.
    Calls llm.risk_narrator.narrate_risk() if available.
    Requires ANTHROPIC_API_KEY to be set.
    """
    if not os.getenv("GEMINI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"):
        return {
            "employee_id": employee_id,
            "narration": _NO_KEY_MESSAGES["gemini"],
        }

    if not _NARRATOR_AVAILABLE:
        return {
            "employee_id": employee_id,
            "narration": "The risk narrator module (llm.risk_narrator) is not available. "
                         "Ensure Phase 5 LLM dependencies are installed.",
        }

    # Fetch the employee's latest risk context from the DB
    import psycopg2

    try:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT
                    e.full_name, e.department, e.job_level,
                    e.age, e.gender, e.performance_rating, e.job_satisfaction,
                    r.latest_risk_index, r.latest_risk_band,
                    r.flight_risk_prob, r.anomaly_score, r.risk_delta,
                    r.shap_top_feature_1, r.shap_top_feature_2, r.shap_top_feature_3
                FROM mart.dim_employee e
                LEFT JOIN mart.mart_risk_index r
                    ON e.employee_id::text = r.employee_id::text
                WHERE e.employee_id = %s
                """,
                (employee_id,),
            )
            row = cur.fetchone()
    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    if row is None:
        raise HTTPException(
            status_code=404, detail=f"Employee {employee_id} not found"
        )

    employee_context = dict(row)

    try:
        narration = _risk_narrator_module.narrate_risk(employee_context)
        return {"employee_id": employee_id, "narration": narration}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Narration error: {e}")
