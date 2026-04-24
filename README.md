# TalentLens — AI-Powered Workforce Intelligence Platform

> End-to-end ML + Data Engineering portfolio project.  
> Predicts employee flight risk, explains decisions with SHAP, and answers HR policy questions via an LLM ReAct agent — all running in Docker Compose with a live React dashboard.

---

## What It Does

TalentLens ingests a stream of HR events, scores 85,000 employees for attrition risk using XGBoost + Isolation Forest, explains predictions with SHAP, monitors model drift, and surfaces insights through a FastAPI backend and React dashboard with an AI agent powered by Gemini.

```
Synthetic HRIS (85K employees, 2M events)
        ↓
  Kafka (4 topics)  →  Airflow DAGs  →  PostgreSQL (raw / staging / mart / audit)
        ↓
  PySpark feature engineering (rolling windows, peer percentiles)
        ↓
  XGBoost + Isolation Forest  →  SHAP  →  Composite Risk Index (0–100)
        ↓
  MLflow governance  +  Fairlearn bias audit  +  HITL active-learning loop
        ↓
  LangChain ReAct Agent (Gemini Flash)  +  FAISS RAG (HR policy docs)
        ↓
  FastAPI (22 routes + WebSocket)  →  React Dashboard (5 pages)
        ↓
  Docker Compose (dev)  /  Kubernetes minikube (demo)  /  AWS EKS (target)
```

---

## Tech Stack

| Layer | Technologies |
|---|---|
| **Data generation** | Python synthetic generator — 85K employees, 2M+ HR events, 24 months |
| **Event streaming** | Apache Kafka (4 topics, 3 consumer groups, idempotent producer) |
| **Orchestration** | Apache Airflow (5 DAGs — ingestion, features, scoring, drift, HITL) |
| **Warehouse** | PostgreSQL + dbt (raw / staging / mart / audit schema separation) |
| **Feature engineering** | PySpark — rolling 30/90/180-day windows, peer percentiles via `percent_rank()` |
| **ML models** | XGBoost (flight risk), Isolation Forest (anomaly), SHAP explainability |
| **Model governance** | MLflow tracking + Fairlearn bias audit + PSI drift monitoring + Optuna HPO |
| **HITL** | Active learning loop with uncertainty sampling, override audit trail |
| **LLM / Agent** | LangChain ReAct agent, FAISS semantic search, multi-provider (Gemini / Claude / GPT-4o) |
| **API** | FastAPI — async, JWT auth, WebSocket live feed, 22 routes |
| **Frontend** | React + Recharts — risk heatmap, SHAP charts, hiring funnel, AI chatbot |
| **Infrastructure** | Docker Compose (dev), Kubernetes + KEDA HPA (demo), architected for AWS EKS |

---

## Key Numbers

| Metric | Value |
|---|---|
| Employees scored | 30,824 |
| HR events processed | 2M+ |
| XGBoost AUC | tracked in MLflow |
| SHAP features per prediction | top 3 surfaced to dashboard |
| RAG corpus | 28 chunks, 384-dim embeddings (all-MiniLM-L6-v2) |
| HITL overrides | 180 seeded |
| API routes | 22 (risk, employees, audit, models, hiring, agent) |
| Kafka topics | 4 (employee-events, risk-scores, audit-log, dashboard-feed) |
| dbt models | staging + mart + audit layers |
| Docker services | 7 (postgres, kafka, zookeeper, airflow-web, airflow-scheduler, api, mlflow) |

---

## Project Structure

```
data/synthetic_generator.py      # Primary dataset — no Kaggle downloads needed
ingestion/                        # Kafka producer + mock HRIS API (FastAPI, port 8001)
orchestration/airflow/dags/       # 5 DAGs — ingestion, Spark features, scoring, drift, HITL
warehouse/
  migrations/01_schemas.sql       # Full schema — raw/staging/mart/audit
  dbt_project/models/             # stg_employees, dim_employee (SCD-2), fact_risk_scores, etc.
spark/
  peer_percentile_job.py          # percent_rank() + ntile(4) peer benchmarking
  rolling_aggregations.py         # 30/90/180-day rolling feature windows
ml/
  train_and_score.py              # XGBoost + Isolation Forest + SHAP + MLflow
  governance/hitl_workflow.py     # Active learning + uncertainty sampling
  governance/drift_monitor.py     # PSI population stability index
llm/
  providers/                      # Gemini / Anthropic / OpenAI / Ollama abstraction
  agent/react_agent.py            # LangGraph ReAct agent + 4 tools
  rag/                            # FAISS indexer + retriever (sentence-transformers)
api/
  main.py                         # FastAPI app — CORS, routers, WebSocket
  routers/                        # risk, employees, audit, models, hiring, agent
frontend/src/
  pages/                          # Dashboard, RiskExplorer, ModelGovernance, HiringFunnel, AgentChatbot
k8s/                              # Kubernetes manifests + KEDA ScaledObject (HPA on Kafka lag)
```

---

## Architecture Decisions

| ADR | Decision | Rationale |
|---|---|---|
| ADR-001 | Kafka over direct DB writes | Fan-out to 3 consumers, replay on failure, decoupling |
| ADR-002 | XGBoost over neural nets | Tabular HR data + SHAP explainability required for HR compliance |
| ADR-003 | Separate RAG microservice | LLM latency (1–10s) must not block risk scoring (< 100ms) |
| ADR-004 | HPA on Kafka consumer lag | Lag is a leading indicator; CPU is a lagging indicator |
| ADR-005 | PySpark for batch features | Rolling windows over 70M rows too slow in single-node PostgreSQL |

---

## Running Locally

**Prerequisites:** Docker Desktop, conda, Node.js 18+

```bash
# Clone and set up environment
git clone <repo-url>
cd TalentLens
conda activate talentlens
pip install -r requirements.txt
cd frontend && npm install && cd ..

# Add your Gemini API key (free at aistudio.google.com)
echo "GEMINI_API_KEY=your-key-here" >> .env

# Start all services
docker compose up --build
# API docs  → http://127.0.0.1:8000/docs
# Airflow   → http://localhost:8080  (admin/admin)
# MLflow    → http://localhost:5001

# Start frontend (separate terminal)
cd frontend && npm run dev
# Dashboard → http://localhost:5173
```

**Kubernetes demo (minikube):**
```bash
minikube start --cpus=4 --memory=8g
eval $(minikube docker-env)
docker compose build
kubectl apply -f k8s/
kubectl get pods
minikube service api --url
```

---

## Resume Bullets

```
• Built end-to-end ML workforce intelligence platform: Kafka → Airflow → PySpark →
  XGBoost/Isolation Forest → FastAPI → React; scored 85K employees for flight risk

• Engineered 30/90/180-day rolling feature windows and peer percentile benchmarks
  in PySpark over 2M+ HR events; features written to PostgreSQL mart layer via dbt

• Trained XGBoost attrition classifier with SHAP explainability, MLflow experiment
  tracking, Fairlearn bias audit, PSI drift monitoring, and Optuna hyperparameter tuning

• Deployed LangChain ReAct agent backed by FAISS RAG (HR policy corpus, 384-dim
  embeddings); agent answers natural-language HR queries using 4 live database tools

• Containerized full stack in Docker Compose (7 services); architected Kubernetes
  manifests with KEDA HPA scaling on Kafka consumer lag for AWS EKS deployment
```

---

## Design Principles

- **No Kaggle**: dataset is fully synthetic (85K employees, 24 months of events) — built to demonstrate data engineering, not data download
- **Explainability first**: every risk score surfaced with top-3 SHAP features
- **Production patterns**: schema separation (raw/staging/mart/audit), idempotent ingestion, HITL audit trail, model versioning
- **Honest deployment**: demo runs on minikube; EKS deployment is architected but not claimed unless actually deployed

---

*Anshita Bhardwaj — MS Data Science, Arizona State University (May 2026)*  
*Target: ML Engineering / Data Engineering roles — AmEx · Tesla · Amazon · PayPal*
