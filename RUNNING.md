# TalentLens — Complete Run Guide (Phases 1–7)

All commands run from `/Users/anshita/Desktop/TalentLens` unless noted.  
Conda env: `talentlens` (activate before every session).

---

## Prerequisites (do once, ever)

```bash
conda activate talentlens
cd /Users/anshita/Desktop/TalentLens

# Python dependencies
pip install -r requirements.txt
pip install "dbt-postgres==1.9.0"
pip install "protobuf>=4.0.0,<5.0.0"   # MUST run last — see Dependency Notes below
pip install sentence-transformers==2.7.0

# Frontend
cd frontend && npm install && cd ..

# JDBC driver for PySpark
mkdir -p spark/jars
curl -sL https://jdbc.postgresql.org/download/postgresql-42.7.3.jar \
     -o spark/jars/postgresql-42.7.3.jar

# Persist JAVA_HOME for PySpark (Anaconda OpenJDK lives at /opt/anaconda3, not /Library/Java)
mkdir -p /opt/anaconda3/envs/talentlens/etc/conda/activate.d
echo 'export JAVA_HOME=/opt/anaconda3' \
  > /opt/anaconda3/envs/talentlens/etc/conda/activate.d/java_home.sh

# Copy env file
cp .env.example .env
# Edit .env → fill in ANTHROPIC_API_KEY or OPENAI_API_KEY for Phase 5
```

---

## Phase 1 — Data Foundation

```bash
conda activate talentlens
cd /Users/anshita/Desktop/TalentLens

# 1a. Start core Docker services (Postgres:5434, Kafka:9092, Airflow:8080, Mock HRIS:8001)
docker-compose up -d
# Wait ~60 seconds, then verify:
docker-compose ps   # all services should show "Up" or "healthy"

# 1b. Generate synthetic data
# Fast (~1 min, ~8K employees, ~200K events):
python data/synthetic_generator.py --fast --load-db
# Full (~15 min, ~85K employees, ~2M events):
# python data/synthetic_generator.py --load-db

# 1c. Run dbt
cd warehouse/dbt_project
dbt deps --profiles-dir . --project-dir .
dbt run  --profiles-dir . --project-dir .
dbt test --profiles-dir . --project-dir .   # expect PASS=52 WARN=1 ERROR=0
cd ../..
```

**Checkpoint:**
```bash
docker exec -it talentlens-postgres psql -U talentlens -d talentlens \
  -c "SELECT COUNT(*) FROM mart.dim_employee;"
# Should return ~8K (fast) or ~43K (full)
```

---

## Phase 2 — PySpark Feature Engineering

```bash
conda activate talentlens
cd /Users/anshita/Desktop/TalentLens

# 2a. Start Spark cluster
docker-compose --profile spark up -d
# Wait ~90s, then verify at http://localhost:8090

# 2b. Set environment variables (required every terminal session unless JAVA_HOME persisted)
export JAVA_HOME=/opt/anaconda3
export JDBC_JAR=/Users/anshita/Desktop/TalentLens/spark/jars/postgresql-42.7.3.jar
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5434

# 2c. Run PySpark jobs
python spark/peer_percentile_job.py --local    # ~2-5 min
python spark/rolling_aggregations.py --local   # ~5-10 min
```

**Checkpoint:**
```bash
docker exec -it talentlens-postgres psql -U talentlens -d talentlens \
  -c "SELECT COUNT(*) FROM mart.feature_store;"
# Should match mart.dim_employee row count
```

---

## Phase 3 — Risk ML (XGBoost + SHAP + MLflow)

```bash
conda activate talentlens
cd /Users/anshita/Desktop/TalentLens

python ml/train_and_score.py
# Trains XGBoost + IsolationForest, scores all active employees,
# writes to mart.fact_risk_scores + mart.mart_risk_index, logs to mlruns/
```

**Checkpoint:**
```bash
docker exec -it talentlens-postgres psql -U talentlens -d talentlens -c \
  "SELECT COUNT(*), ROUND(AVG(latest_risk_index),2) AS avg_risk,
          COUNT(*) FILTER (WHERE latest_risk_band = 'Critical') AS critical
   FROM mart.mart_risk_index;"
```

**MLflow UI:**
```bash
# In a separate terminal (port 5001 — port 5000 is taken by macOS AirPlay):
mlflow ui --port 5001 --backend-store-uri mlruns
# → http://localhost:5001  (click "talentlens-risk-engine" experiment)
```

---

## Phase 4 — Model Governance + HITL

```bash
conda activate talentlens
cd /Users/anshita/Desktop/TalentLens

python ml/run_hitl_demo.py
# Simulates 60 HR overrides, runs active learning, Optuna retrain, promotes challenger
```

**Checkpoint:**
```bash
docker exec -it talentlens-postgres psql -U talentlens -d talentlens \
  -c "SELECT COUNT(*) FROM audit.hitl_overrides;"
# Should show 60+ rows
```

---

## Phase 5 — LLM & Agent (FAISS RAG)

```bash
conda activate talentlens
cd /Users/anshita/Desktop/TalentLens

# Set your LLM key (add to .env to persist)
export ANTHROPIC_API_KEY=sk-ant-...   # recommended
# OR:
export OPENAI_API_KEY=sk-...

# Build FAISS index (one-time, ~30 sec) — skip if llm/rag/faiss_index.index already exists
python -c "from llm.rag.indexer import build_index; build_index()"
# Output: [indexer] 3 docs → 28 chunks ... Index saved (28 vectors, dim=384)

# Smoke-test the ReAct agent (3 sample queries)
python llm/run_agent_demo.py
```

---

## Phase 6 — API + Frontend

Open two terminal tabs:

```bash
# Terminal 1 — FastAPI backend
conda activate talentlens
cd /Users/anshita/Desktop/TalentLens
uvicorn api.main:app --reload --port 8000
# API docs → http://localhost:8000/docs
```

```bash
# Terminal 2 — React frontend
cd /Users/anshita/Desktop/TalentLens/frontend
npm run dev
# Dashboard → http://localhost:5173
```

**5 pages to verify:**

| Page | URL | What to check |
|---|---|---|
| Workforce Risk Dashboard | http://localhost:5173/ | Heatmap loads, live feed ticks |
| Risk Explorer | http://localhost:5173/risk | Filters work, SHAP chart renders |
| Model Governance | http://localhost:5173/governance | MLflow runs table, PSI drift chart |
| Hiring Funnel | http://localhost:5173/hiring | Funnel chart + KPI cards |
| AI Risk Agent | http://localhost:5173/agent | Type a question, agent responds |

---

## Phase 7 — Infrastructure

### Option A — Docker Compose (production-like, recommended for demo)

```bash
cd /Users/anshita/Desktop/TalentLens
docker-compose build api frontend
docker-compose up -d

# Dashboard  → http://localhost:5173
# API docs   → http://localhost:8000/docs
# MLflow     → http://localhost:5001
# Airflow    → http://localhost:8080  (admin / admin)
```

### Option B — minikube (Kubernetes demo)

```bash
# Prerequisites (once)
brew install minikube kubectl helm
minikube start --cpus 4 --memory 8192

# One-shot deploy
cd /Users/anshita/Desktop/TalentLens
./scripts/minikube-up.sh

# Add to /etc/hosts (once)
echo "$(minikube ip) talentlens.local" | sudo tee -a /etc/hosts

# Dashboard  → http://talentlens.local
# MLflow     → http://$(minikube ip):30500
```

---

## Full Status Check (any time)

```bash
# Docker services
docker-compose ps

# Kafka topics
docker exec talentlens-kafka kafka-topics --bootstrap-server localhost:9092 --list

# Row counts across all mart tables
docker exec -it talentlens-postgres psql -U talentlens -d talentlens -c "
  SELECT 'dim_employee'     AS table_name, COUNT(*) FROM mart.dim_employee    UNION ALL
  SELECT 'feature_store'    AS table_name, COUNT(*) FROM mart.feature_store   UNION ALL
  SELECT 'fact_risk_scores' AS table_name, COUNT(*) FROM mart.fact_risk_scores UNION ALL
  SELECT 'mart_risk_index'  AS table_name, COUNT(*) FROM mart.mart_risk_index  UNION ALL
  SELECT 'hitl_overrides'   AS table_name, COUNT(*) FROM audit.hitl_overrides;"
```

---

## Dependency Notes

**protobuf must be `>=4.0.0,<5.0.0`** — run this after any pip install that might bump it:
```bash
pip install "protobuf>=4.0.0,<5.0.0"
```
Why: mlflow 2.12.1 uses `google.protobuf.service` which was removed in protobuf 5.x. dbt 1.9 requires >=4. The 4.x range satisfies both.

**dbt must be 1.9.x** (not 1.7.4 from requirements.txt):
```bash
pip install "dbt-postgres==1.9.0"
```
Why: dbt 1.7.4 writes a `package-lock.yml` format incompatible with dbt 1.8+ and has a `MessageToJson` crash with protobuf 6.x.

**JAVA_HOME must be set for PySpark:**
```bash
export JAVA_HOME=/opt/anaconda3
```
Why: Anaconda installs OpenJDK 17 at `/opt/anaconda3`, not at the standard macOS path `/Library/Java/JavaVirtualMachines/`, so PySpark's auto-detection fails. Set this once permanently using the activate.d script in Prerequisites.

---

## Common Problems

| Problem | Fix |
|---|---|
| `docker-compose: command not found` | Open Docker Desktop first |
| Kafka `NodeExistsException` on restart | `docker-compose restart zookeeper && sleep 8 && docker-compose up -d` |
| Port 5000 already in use (MLflow) | Always use `--port 5001` — AirPlay owns 5000 on Mac |
| `role "talentlens" does not exist` (Spark) | Set `POSTGRES_PORT=5434` — Spark defaulting to 5432 (wrong postgres) |
| `JAVA_GATEWAY_EXITED` (PySpark) | `export JAVA_HOME=/opt/anaconda3` |
| `google.protobuf.service` ImportError (mlflow) | `pip install "protobuf>=4.0.0,<5.0.0"` |
| `No module named 'dbt.adapters.factory'` | `pip install "dbt-postgres==1.9.0"` (cleans broken upgrade) |
| `packages.yml malformed` (dbt) | Delete `warehouse/dbt_project/package-lock.yml`, re-run `dbt deps` |
| `mart.fact_risk_scores does not exist` | Table missing from DB — run CREATE TABLE from `warehouse/migrations/01_schemas.sql` lines 99–121 |
| `uuid = text` join error in dbt | Already fixed in `fact_risk_scores.sql` (cast to `::text`) |
| `unique_stg_employees_email` test fails | Expected — Faker emails collide at 40K+ rows; test severity set to `warn` |
| `ModuleNotFoundError: No module named 'llm'` | Already fixed in `run_agent_demo.py` (sys.path insert) |
| dbt `connection refused` | Set `POSTGRES_HOST=localhost` and `POSTGRES_PORT=5434` in `.env` |
| Airflow shows no DAGs | `docker-compose restart airflow-scheduler` |
| Spark worker not registering | Wait 30s, check http://localhost:8090 |
