"""
TalentLens FastAPI application — Phase 6 backend.

Entry point: uvicorn api.main:app --reload --port 8000
"""

import logging
import os
import sys

# Ensure the project root is on sys.path so that sibling packages
# (ml, llm, etc.) are importable when running from any working directory.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import psycopg2
import psycopg2.extras
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import agent, audit, employees, hiring, models, risk
from api.websocket import risk_feed_endpoint

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# App initialisation
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="TalentLens API",
    version="1.0.0",
    description=(
        "Phase 6 backend for TalentLens — an HR analytics platform combining "
        "ML-driven flight-risk scoring, HITL governance, and LLM narration."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─────────────────────────────────────────────────────────────────────────────
# Middleware
# ─────────────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # Open for local React dev; tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────────────────
# Routers
# ─────────────────────────────────────────────────────────────────────────────

app.include_router(risk.router,      prefix="/api/v1")
app.include_router(employees.router, prefix="/api/v1")
app.include_router(audit.router,     prefix="/api/v1")
app.include_router(models.router,    prefix="/api/v1")
app.include_router(hiring.router,    prefix="/api/v1")
app.include_router(agent.router,     prefix="/api/v1")

# ─────────────────────────────────────────────────────────────────────────────
# WebSocket
# ─────────────────────────────────────────────────────────────────────────────

app.add_api_websocket_route("/ws/dashboard", risk_feed_endpoint)

# ─────────────────────────────────────────────────────────────────────────────
# Health check
# ─────────────────────────────────────────────────────────────────────────────

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://talentlens:talentlens@localhost:5434/talentlens",
)


@app.get("/health", tags=["health"])
def health_check():
    """
    Liveness / readiness probe.
    Returns {"status": "ok", "db": "connected"} when the DB is reachable,
    or {"status": "degraded", "db": "unreachable"} if not.
    """
    db_status = "connected"
    try:
        conn = psycopg2.connect(
            DATABASE_URL,
            cursor_factory=psycopg2.extras.RealDictCursor,
            connect_timeout=3,
        )
        conn.close()
    except psycopg2.OperationalError:
        db_status = "unreachable"

    return {"status": "ok" if db_status == "connected" else "degraded", "db": db_status}


# ─────────────────────────────────────────────────────────────────────────────
# Startup event
# ─────────────────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def on_startup():
    logger.info("TalentLens API started")
    logger.info("Docs available at http://localhost:8000/docs")
