"""
Composite Risk Index (0–100) and band assignment.

Formula (from CLAUDE.md):
    risk_index = 0.50 × flight_risk_prob × 100
               + 0.35 × anomaly_score_norm × 100
               + 0.15 × compliance_flag × 100

Bands:
    0–25   → Low
    26–50  → Medium
    51–75  → High
    76–100 → Critical

Compliance flag: high performer (rating ≥ 4) paid below peer median.
These employees represent a pay-equity / retention compliance risk.
"""

import numpy as np
import pandas as pd


def compute_compliance_flag(df: pd.DataFrame) -> np.ndarray:
    return (
        (df["flag_high_performer"] == 1) & (df["flag_below_peer_pay"] == 1)
    ).astype(int).values


def compute_risk_index(
    flight_risk_prob: np.ndarray,
    anomaly_score_norm: np.ndarray,
    compliance_flag: np.ndarray,
) -> np.ndarray:
    raw = (
        0.50 * flight_risk_prob * 100
        + 0.35 * anomaly_score_norm * 100
        + 0.15 * compliance_flag * 100
    )
    return np.clip(raw, 0, 100).round(2)


def assign_band(risk_index: np.ndarray) -> list[str]:
    bands = []
    for v in risk_index:
        if v <= 25:
            bands.append("Low")
        elif v <= 50:
            bands.append("Medium")
        elif v <= 75:
            bands.append("High")
        else:
            bands.append("Critical")
    return bands


def band_summary(risk_index: np.ndarray) -> dict:
    bands = assign_band(risk_index)
    counts = {b: bands.count(b) for b in ["Low", "Medium", "High", "Critical"]}
    total = len(bands)
    return {k: {"count": v, "pct": round(v / total * 100, 1)} for k, v in counts.items()}
