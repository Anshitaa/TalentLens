"""
Risk narrator: generates plain-English explanations of why an employee
has been flagged as an attrition risk, based on their risk index and
top SHAP feature attributions.
"""

from __future__ import annotations


_SYSTEM_PROMPT = """\
You are an HR analytics assistant. Your role is to explain employee \
attrition risk assessments in clear, empathetic, non-jargon language \
for HR Business Partners and managers.

Given an employee's risk profile and the top factors driving their risk score, \
write a concise 2-3 sentence explanation suitable for an internal HR dashboard. \
Do not reveal technical model internals. Focus on what the data suggests about \
the employee's situation and why HR attention may be warranted. \
Never speculate beyond what the data shows.\
"""


def _build_prompt(
    employee_id: str,
    risk_index: float,
    risk_band: str,
    shap_top_feature_1: str,
    shap_top_feature_2: str,
    shap_top_feature_3: str,
    shap_value_1: float,
    shap_value_2: float,
    shap_value_3: float,
) -> str:
    """Construct the user-facing prompt for the LLM."""
    direction = lambda v: "increases" if v > 0 else "decreases"
    return (
        f"Employee ID: {employee_id}\n"
        f"Risk Band: {risk_band}  (Risk Index: {risk_index:.1f} / 100)\n\n"
        f"Top factors contributing to this risk score:\n"
        f"  1. {shap_top_feature_1} (contribution: {shap_value_1:+.3f} — "
        f"this factor {direction(shap_value_1)} attrition risk)\n"
        f"  2. {shap_top_feature_2} (contribution: {shap_value_2:+.3f} — "
        f"this factor {direction(shap_value_2)} attrition risk)\n"
        f"  3. {shap_top_feature_3} (contribution: {shap_value_3:+.3f} — "
        f"this factor {direction(shap_value_3)} attrition risk)\n\n"
        "Please write a 2-3 sentence plain-English explanation for the HR team."
    )


def _template_fallback(
    employee_id: str,
    risk_index: float,
    risk_band: str,
    shap_top_feature_1: str,
    shap_top_feature_2: str,
    shap_top_feature_3: str,
    shap_value_1: float,
    shap_value_2: float,
    shap_value_3: float,
) -> str:
    """Rule-based fallback used when the LLM is unavailable."""
    top = shap_top_feature_1.replace("_", " ")
    second = shap_top_feature_2.replace("_", " ")
    return (
        f"Employee {employee_id} has been assigned a {risk_band} attrition risk "
        f"(Risk Index: {risk_index:.1f}/100). "
        f"The primary driver is {top}, with {second} as a secondary contributing factor. "
        f"HR review is recommended to assess whether targeted retention actions are appropriate."
    )


def narrate_risk(
    employee_id: str,
    risk_index: float,
    risk_band: str,
    shap_top_feature_1: str,
    shap_top_feature_2: str,
    shap_top_feature_3: str,
    shap_value_1: float,
    shap_value_2: float,
    shap_value_3: float,
    provider_tier: str = "anthropic",
) -> str:
    """
    Generate a 2-3 sentence plain-English explanation of why an employee is
    flagged as an attrition risk, suitable for display in the HR dashboard.

    Uses the configured LLM provider with a structured prompt. Falls back to
    a rule-based template if the LLM is unavailable (missing API key, network
    error, or local Ollama offline).

    Args:
        employee_id:         Unique employee identifier.
        risk_index:          Numeric risk score (0–100).
        risk_band:           Risk tier label ("Low" / "Medium" / "High" / "Critical").
        shap_top_feature_1:  Name of the most influential model feature.
        shap_top_feature_2:  Name of the second most influential feature.
        shap_top_feature_3:  Name of the third most influential feature.
        shap_value_1:        SHAP contribution value for feature 1.
        shap_value_2:        SHAP contribution value for feature 2.
        shap_value_3:        SHAP contribution value for feature 3.
        provider_tier:       LLM provider to use: "anthropic" | "openai" | "local".

    Returns:
        A plain-English narrative string (2-3 sentences).
    """
    user_prompt = _build_prompt(
        employee_id, risk_index, risk_band,
        shap_top_feature_1, shap_top_feature_2, shap_top_feature_3,
        shap_value_1, shap_value_2, shap_value_3,
    )

    try:
        from llm.providers import get_provider
        provider = get_provider(provider_tier)
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt},
        ]
        return provider.complete(messages, max_tokens=256)

    except EnvironmentError:
        # API key not configured — use template
        return _template_fallback(
            employee_id, risk_index, risk_band,
            shap_top_feature_1, shap_top_feature_2, shap_top_feature_3,
            shap_value_1, shap_value_2, shap_value_3,
        )
    except Exception:
        # Network error, model unavailable, etc. — use template
        return _template_fallback(
            employee_id, risk_index, risk_band,
            shap_top_feature_1, shap_top_feature_2, shap_top_feature_3,
            shap_value_1, shap_value_2, shap_value_3,
        )
