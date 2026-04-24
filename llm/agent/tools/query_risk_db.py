"""
LangChain tool: query_risk_db

Accepts natural language strings with recognized keywords and runs
pre-built, read-only PostgreSQL queries against the TalentLens mart schema.
"""

import os
from textwrap import dedent

import psycopg2
import psycopg2.extras
from langchain_core.tools import tool

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://talentlens:talentlens@localhost:5434/talentlens",
)

# ─────────────────────────────────────────────────────────────────────────────
# Pre-built queries (read-only)
# ─────────────────────────────────────────────────────────────────────────────

_QUERIES = {
    "top critical": dedent("""
        SELECT employee_id, department, latest_risk_index, latest_risk_band
        FROM mart.mart_risk_index
        WHERE latest_risk_band IN ('High', 'Critical')
        ORDER BY latest_risk_index DESC
        LIMIT 10
    """).strip(),

    "risk summary": dedent("""
        SELECT latest_risk_band AS risk_band, COUNT(*) AS employee_count
        FROM mart.mart_risk_index
        GROUP BY latest_risk_band
        ORDER BY employee_count DESC
    """).strip(),

    "department risk": dedent("""
        SELECT department,
               ROUND(AVG(latest_risk_index)::numeric, 2) AS avg_risk_index,
               COUNT(*) AS employee_count
        FROM mart.mart_risk_index
        GROUP BY department
        ORDER BY avg_risk_index DESC
    """).strip(),

    "recent scores": dedent("""
        SELECT employee_id, scored_at, risk_index, risk_band
        FROM mart.fact_risk_scores
        ORDER BY scored_at DESC, risk_index DESC
        LIMIT 10
    """).strip(),
}

_KEYWORD_ORDER = ["top critical", "risk summary", "department risk", "recent scores"]


def _detect_query(natural_language: str) -> tuple[str | None, str | None]:
    """Return (keyword, sql) for the first keyword found in the input, or (None, None)."""
    lower = natural_language.lower()
    for keyword in _KEYWORD_ORDER:
        if keyword in lower:
            return keyword, _QUERIES[keyword]
    return None, None


def _run_query(sql: str) -> str:
    """Execute *sql* and return a formatted plain-text result table."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql)
                rows = cur.fetchall()
        finally:
            conn.close()
    except Exception as exc:
        return f"[DB error: {exc}]"

    if not rows:
        return "(no rows returned)"

    # Format as a simple text table
    cols = list(rows[0].keys())
    header = " | ".join(cols)
    separator = "-" * len(header)
    lines = [header, separator]
    for row in rows:
        lines.append(" | ".join(str(row[c]) for c in cols))
    return "\n".join(lines)


@tool
def query_risk_db(query: str) -> str:
    """
    Query the TalentLens risk database using natural language.

    Recognized keywords (case-insensitive):
      - "top critical"    → Top 10 High/Critical risk employees by risk index
      - "risk summary"    → Employee count aggregated by risk band
      - "department risk" → Average risk index per department
      - "recent scores"   → Latest 10 fact_risk_scores rows

    Returns a formatted text table with the query results, or a helpful
    message if no keyword is matched.

    Args:
        query: Natural language string describing what data you need.
    """
    keyword, sql = _detect_query(query)
    if sql is None:
        available = ", ".join(f'"{k}"' for k in _KEYWORD_ORDER)
        return (
            f"No matching query found for: '{query}'. "
            f"Available keywords: {available}. "
            "Try rephrasing with one of those keywords."
        )

    result = _run_query(sql)
    return f"[Query: {keyword}]\n{result}"
