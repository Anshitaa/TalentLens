"""
WebSocket endpoint — streams live risk summary stats to the dashboard.
"""

import asyncio
import json
import os
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras
from fastapi import WebSocket, WebSocketDisconnect

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://talentlens:talentlens@localhost:5434/talentlens",
)


def _fetch_band_counts() -> dict[str, int]:
    """Synchronous helper: query band counts from the DB."""
    conn = psycopg2.connect(
        DATABASE_URL,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT latest_risk_band, COUNT(*) AS cnt
                FROM mart.mart_risk_index
                GROUP BY latest_risk_band
                """
            )
            rows = cur.fetchall()
        return {(row["latest_risk_band"] or "Unknown"): int(row["cnt"]) for row in rows}
    finally:
        conn.close()


async def risk_feed_endpoint(websocket: WebSocket):
    """
    WebSocket /ws/dashboard

    Sends a JSON message every 5 seconds with current risk summary stats.
    Format: {"type": "risk_update", "data": {band_counts: {...}, timestamp: "..."}}

    Clients disconnect gracefully; DB errors are sent as an error message type
    without terminating the connection.
    """
    await websocket.accept()

    try:
        while True:
            try:
                loop = asyncio.get_event_loop()
                band_counts = await loop.run_in_executor(None, _fetch_band_counts)

                payload = {
                    "type": "risk_update",
                    "data": {
                        "band_counts": band_counts,
                        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                    },
                }
                await websocket.send_text(json.dumps(payload))

            except psycopg2.Error as db_err:
                error_payload = {
                    "type": "error",
                    "detail": f"DB error: {db_err}",
                    "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                }
                await websocket.send_text(json.dumps(error_payload))

            await asyncio.sleep(5)

    except WebSocketDisconnect:
        # Client disconnected cleanly — no action needed.
        pass
