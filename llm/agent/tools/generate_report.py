"""
LangChain tool: generate_report

Queries mart.mart_risk_index for a given department and returns a
formatted plain-text risk report.
"""

import os
from collections import Counter

import psycopg2
import psycopg2.extras
from langchain_core.tools import tool

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://talentlens:talentlens@localhost:5434/talentlens",
)

_BAND_ORDER = ["Critical", "High", "Medium", "Low"]


@tool
def generate_report(department: str) -> str:
    """
    Generate a risk summary report for a specific department.

    Queries mart.mart_risk_index for all employees in the given department
    and returns:
      - Total employee count
      - Distribution of employees by risk band
      - Top 3 highest-risk employees (employee_id + risk index + band)
      - Average risk score for the department

    Args:
        department: Exact department name (case-insensitive match attempted).

    Returns a formatted plain-text report string.
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT employee_id,
                           latest_risk_index,
                           latest_risk_band
                    FROM mart.mart_risk_index
                    WHERE LOWER(department) = LOWER(%s)
                    ORDER BY latest_risk_index DESC
                    """,
                    (department,),
                )
                rows = cur.fetchall()
        finally:
            conn.close()
    except Exception as exc:
        return f"[DB error while generating report for '{department}': {exc}]"

    if not rows:
        return (
            f"No employees found in department '{department}'. "
            "Check the spelling or try a different department name."
        )

    n = len(rows)
    avg_risk = sum(r["latest_risk_index"] for r in rows) / n

    # Band distribution
    band_counts: Counter = Counter(r["latest_risk_band"] for r in rows)
    band_lines = []
    for band in _BAND_ORDER:
        count = band_counts.get(band, 0)
        pct = (count / n * 100) if n else 0
        band_lines.append(f"  {band:<10} {count:>4} employees  ({pct:.1f}%)")

    # Top 3 at-risk
    top3 = rows[:3]
    top3_lines = []
    for i, emp in enumerate(top3, 1):
        top3_lines.append(
            f"  {i}. Employee {emp['employee_id']:>10}  "
            f"Risk Index: {emp['latest_risk_index']:.2f}  "
            f"Band: {emp['latest_risk_band']}"
        )

    report = "\n".join([
        f"=" * 55,
        f"  ATTRITION RISK REPORT — {department.upper()}",
        f"=" * 55,
        f"  Total employees:   {n}",
        f"  Average risk score: {avg_risk:.2f} / 100",
        "",
        "  Risk Band Distribution:",
        *band_lines,
        "",
        "  Top 3 At-Risk Employees:",
        *top3_lines,
        "=" * 55,
    ])

    return report
