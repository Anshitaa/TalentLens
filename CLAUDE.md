# CLAUDE.md — TalentLens

Auto-loaded by Claude Code on every session. Keep this up to date as phases complete.

**Owner:** Anshita Bhardwaj — MS Data Science ASU May 2026  
**Target roles:** AmEx (AI/ML Platform), Tesla (Data Eng People Analytics), Amazon (Data Eng CDP), PayPal (MLE)  
**Full spec:** `TalentLens_Project_Spec.md`  
**Run guide:** `RUNNING.md`

---

## Build Status

| Phase | Status | Checkpoint |
|---|---|---|
| 1 — Data Foundation | ✅ Built | `mart.dim_employee` 43,844 rows populated |
| 2 — PySpark Features | ✅ Built | `mart.feature_store` 43,844 rows (peer pcts + rolling aggs) |
| 3 — Risk ML (XGBoost + SHAP) | ✅ Built | 30,824 rows → `mart.fact_risk_scores` + `mart.mart_risk_index` |
| 4 — Model Governance + HITL | ✅ Built | 180 HITL overrides, Optuna retrain, risk card generated |
| 5 — LLM & Agent | ✅ Built | LangChain ReAct agent + FAISS RAG (28 chunks, dim=384) + 4 tools; default LLM: Gemini Flash (free, GEMINI_API_KEY in .env) |
| 6 — API + Frontend | ✅ Built | FastAPI 22 routes + React 5-page dashboard (port 5173); frontend base URL: http://127.0.0.1:8000 (not localhost — macOS IPv6 issue) |
| 7 — Infrastructure | ✅ Built | Dockerfiles + docker-compose.override.yml + k8s/ + KEDA ScaledObject |

---

## Stack

| Layer | Technology |
|---|---|
| Event streaming | Kafka (4 topics, 3 consumer groups) |
| Orchestration | Airflow (5 DAGs) |
| Warehouse | PostgreSQL (port **5434** on Mac) + dbt (raw/staging/mart/audit) |
| Batch features | PySpark (SparkSubmitOperator via Airflow) |
| ML | XGBoost (flight risk) + Isolation Forest (anomaly) + SHAP |
| Governance | MLflow (port **5001**) + Fairlearn + PSI drift monitoring |
| HITL | Active learning loop with uncertainty sampling |
| LLM/Agent | LangChain ReAct agent, FAISS RAG, multi-provider abstraction |
| API | FastAPI (async, JWT, WebSocket) |
| Frontend | React (risk heatmap, SHAP charts, chatbot) |
| Infra | Docker Compose (dev), Kubernetes minikube (demo), AWS EKS (target) |

---

## Critical Environment Facts

- **Mac has 3 Postgres instances**: local Homebrew (5432), Anaconda (5433), Docker TalentLens (**5434**)
- **Always use port 5434** for TalentLens postgres — never 5432 or 5433
- **MLflow runs on port 5001** — port 5000 is permanently taken by macOS AirPlay Receiver
- `DATABASE_URL=postgresql://talentlens:talentlens@localhost:5434/talentlens`
- User uses **Anaconda** (not venv) — conda env name: `talentlens`
- Spark profile is separate: `docker-compose --profile spark up -d` — never starts with base `up -d`
- Spark image: `apache/spark:3.5.5` (bitnami removed from Docker Hub)
- **Java for PySpark**: `export JAVA_HOME=/opt/anaconda3` (Anaconda OpenJDK 17, not in /Library/Java/)
- **dbt version**: 1.9.0 (upgraded from 1.7.4 — protobuf compatibility)
- **protobuf**: must be `>=4.0.0,<5.0.0` after all installs (mlflow <5, dbt >=4)
- **`mart.fact_risk_scores`** is a physical TABLE (written by inference.py) — dbt creates a VIEW on top of it; if DB volume is new, run the CREATE TABLE from `warehouse/migrations/01_schemas.sql` manually

---

## Quick Start Commands

```bash
cd /Users/anshita/Desktop/TalentLens

# ── One-time setup ──────────────────────────────────────────
pip install -r requirements.txt
pip install "dbt-postgres==1.9.0"
pip install "protobuf>=4.0.0,<5.0.0"   # must run LAST — locks the sweet-spot
pip install sentence-transformers==2.7.0
cd frontend && npm install && cd ..
mkdir -p spark/jars && curl -sL https://jdbc.postgresql.org/download/postgresql-42.7.3.jar \
  -o spark/jars/postgresql-42.7.3.jar
# Persist JAVA_HOME for PySpark (run once):
mkdir -p /opt/anaconda3/envs/talentlens/etc/conda/activate.d
echo 'export JAVA_HOME=/opt/anaconda3' \
  > /opt/anaconda3/envs/talentlens/etc/conda/activate.d/java_home.sh

# ── Phase 1 — Data Foundation ───────────────────────────────
docker-compose up -d                          # start Postgres, Kafka, Airflow
python data/synthetic_generator.py --fast --load-db
cd warehouse/dbt_project
dbt deps --profiles-dir . --project-dir .
dbt run --profiles-dir . --project-dir .
dbt test --profiles-dir . --project-dir .    # expect PASS=52 WARN=1 ERROR=0
cd ../..

# ── Phase 2 — Spark Features ────────────────────────────────
docker-compose --profile spark up -d
export JAVA_HOME=/opt/anaconda3
export JDBC_JAR=/Users/anshita/Desktop/TalentLens/spark/jars/postgresql-42.7.3.jar
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5434
python spark/peer_percentile_job.py --local
python spark/rolling_aggregations.py --local

# ── Phase 3 — Risk ML ───────────────────────────────────────
python ml/train_and_score.py
# Checkpoint: mart.mart_risk_index should have ~30K rows with avg latest_risk_index
docker exec -it talentlens-postgres psql -U talentlens -d talentlens \
  -c "SELECT COUNT(*), ROUND(AVG(latest_risk_index),2) FROM mart.mart_risk_index;"

# ── Phase 4 — Governance + HITL ─────────────────────────────
python ml/run_hitl_demo.py

# ── Phase 5 — LLM & Agent ───────────────────────────────────
export ANTHROPIC_API_KEY=sk-ant-...          # or OPENAI_API_KEY=sk-...
python -c "from llm.rag.indexer import build_index; build_index()"
python llm/run_agent_demo.py                  # smoke-test 3 queries

# ── Phase 6 — API + Frontend ────────────────────────────────
uvicorn api.main:app --reload --port 8000 &  # Terminal 1
cd frontend && npm run dev                    # Terminal 2 → http://localhost:5173

# ── Phase 7 — Docker Compose (production-like) ──────────────
docker-compose build api frontend
docker-compose up -d
# Dashboard → http://localhost:5173  |  API docs → http://localhost:8000/docs
# MLflow   → http://localhost:5001

# ── Phase 7 — minikube (K8s demo) ──────────────────────────
./scripts/minikube-up.sh
echo "$(minikube ip) talentlens.local" | sudo tee -a /etc/hosts
# Dashboard → http://talentlens.local  |  MLflow → http://$(minikube ip):30500
```

---

## Known Port Conflicts (Mac-specific)

| Port | Taken by | TalentLens service | Resolution |
|---|---|---|---|
| 5000 | macOS AirPlay Receiver | MLflow UI | Use port **5001** |
| 5432 | Homebrew Postgres | TalentLens Postgres | Use port **5434** |
| 5433 | Anaconda Postgres | TalentLens Postgres | Use port **5434** |

---

## Dependency Compatibility Matrix

| Package | Version | Why pinned |
|---|---|---|
| dbt-postgres | 1.9.0 | protobuf compat; 1.7.4 broke with protobuf 6.x |
| protobuf | >=4,<5 | mlflow 2.12.1 needs `google.protobuf.service` (removed in 5.x) |
| mlflow | 2.12.1 | matches mlruns/ artifact format on disk |
| pyspark | 3.5.1 | matches Spark docker image 3.5.5 |
| sentence-transformers | 2.7.0 | needed for FAISS RAG; not in original requirements.txt |

---

## Repository Structure

```
data/synthetic_generator.py          # 100K employees, 2M events — PRIMARY dataset
ingestion/kafka/producer.py          # Idempotent Kafka producer, watermark in audit.*
ingestion/mock_hris_api/main.py      # FastAPI mock Workday (port 8001)
orchestration/airflow/dags/
  hris_ingestion_dag.py              # @hourly: extract → validate → load → dbt → kafka
  spark_features_dag.py              # daily 02:00: peer percentiles + rolling aggs
warehouse/
  migrations/01_schemas.sql          # raw/staging/mart/audit schemas + all tables
  migrations/02_airflow_db.sh        # creates airflow DB inside same postgres
  dbt_project/models/
    staging/stg_employees.sql
    staging/stg_hiring_events.sql
    mart/dim_employee.sql            # SCD Type 2 + peer enrichment + risk flags
    mart/fact_risk_scores.sql        # VIEW on top of physical table (written by inference.py)
    mart/fact_hiring_funnel.sql
spark/
  peer_percentile_job.py             # percent_rank() + ntile(4) by job_level+dept
  rolling_aggregations.py            # 30/90/180-day rolling windows
ml/                                  # Phase 3+4 — risk engine, HITL, governance
llm/                                 # Phase 5 — providers, FAISS RAG, ReAct agent
api/                                 # Phase 6 — FastAPI 22 routes + WebSocket
frontend/                            # Phase 6 — React 5-page dashboard (Vite + Recharts)
k8s/                                 # Phase 7 — minikube manifests (postgres/kafka/api/frontend/mlflow/keda)
scripts/minikube-up.sh               # Phase 7 — one-shot K8s deploy script
```

---

## Data Strategy

- **Primary:** `data/synthetic_generator.py` — ~10K employees (fast) or 85K (full), ~300K–2M HR events
- **Do NOT use IBM HR Attrition Kaggle** — 1,470 rows, overused in every portfolio
- **Supplementary:** BLS OES salary bands, O*NET job attributes (CC BY 4.0), BLS OOH for RAG
- **Attrition target:** ~15%; generator uses additive risk scoring (not multiplicative) to avoid attrition blowup

---

## Key Architecture Decisions

- **ADR-001 Kafka over direct DB writes** — fan-out to 3 consumers, replay on failure
- **ADR-002 XGBoost over neural nets** — SHAP explainability required for HR; fast weekly retraining
- **ADR-003 Separate RAG microservice** — LLM calls (1–10s) must not block risk scoring (< 100ms)
- **ADR-004 HPA on Kafka consumer lag** — lag is leading indicator; requires KEDA
- **ADR-005 PySpark for batch features** — rolling windows over 70M rows too slow in single-node PG

---

## Risk Scoring Formula (Phase 3)

```
Risk Index (0–100) =
    0.50 × XGBoost flight_risk_prob × 100
  + 0.35 × normalized_anomaly_score × 100
  + 0.15 × compliance_flag × 100

Bands: 0–25 Low | 26–50 Medium | 51–75 High | 76–100 Critical
Slack alert: risk_index > 85 AND previous_risk_index < 75 (spike)
```

---

## PostgreSQL Schema Layers

```
raw.*     — exact source copy, never modified
staging.* — cleaned, typed, deduped
mart.*    — dim_employee, fact_risk_scores (TABLE), fact_hiring_funnel, feature_store, mart_risk_index
audit.*   — append-only: model_decisions, hitl_overrides, drift_reports, active_learning_labels
```

---

## Deployment Honesty Rule

Only claim EKS deployment on resume if actually deployed there.  
For portfolio demo: deploy to minikube → state *"architected for AWS EKS; local demo runs on minikube."*  
Amazon interviewers ask detailed EKS/IAM/node-group questions.
