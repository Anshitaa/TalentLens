# TalentLens — AI-Powered Workforce Intelligence Platform
## Complete Project Specification & Skills Showcase Guide

> **Target Roles:** ML Engineer (AmEx), Data Engineer People Analytics (Tesla), Data Engineer CDP (Amazon), Machine Learning Engineer (PayPal)
> **Author:** Anshita Bhardwaj | M.S. Data Science, Analytics & Engineering, ASU (May 2026)
> **Stack:** Python · Spark · Kafka · Airflow · PostgreSQL · dbt · XGBoost · LangChain · FastAPI · React · Docker · Kubernetes · AWS · MLflow

---

## Table of Contents
1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Repository Structure](#3-repository-structure)
4. [Component Deep-Dives](#4-component-deep-dives)
   - 4.1 Data Ingestion Layer (Kafka)
   - 4.2 Orchestration Layer (Airflow)
   - 4.3 Data Warehouse Layer (PostgreSQL + dbt)
   - 4.4 Batch Feature Engineering (PySpark)
   - 4.5 Risk ML Layer (XGBoost + Isolation Forest)
   - 4.6 Model Governance Layer (MLflow + Fairlearn)
   - 4.7 HITL Active Learning Loop
   - 4.8 LLM & Agentic Layer (LangChain)
   - 4.9 API Layer (FastAPI)
   - 4.10 External API Integrations
   - 4.11 Frontend Dashboard (React)
   - 4.12 Infrastructure (Docker + Kubernetes + AWS)
5. [Data Sources & Schema](#5-data-sources--schema)
6. [Architecture Decision Records](#6-architecture-decision-records)
7. [System Design Document](#7-system-design-document)
8. [Skills Coverage Matrix](#8-skills-coverage-matrix)
9. [Resume Bullet Points](#9-resume-bullet-points)
10. [Build Phases & Timeline](#10-build-phases--timeline)
11. [Interview Talking Points](#11-interview-talking-points)
12. [MVP Scope — Must-Ship Baseline](#12-mvp-scope--must-ship-baseline)

---

## 1. Project Overview

### What is TalentLens?
TalentLens is a **production-grade, end-to-end workforce intelligence platform** that ingests real-time HR event streams, computes multi-dimensional employee risk scores, governs ML models with drift monitoring and bias audits, and surfaces AI-powered insights through a LangChain ReAct agent and interactive React dashboard.

The platform is designed to answer three core business questions:
- **Who is at risk of leaving?** (Attrition/Flight Risk)
- **Which models can we trust?** (Model Risk Governance)
- **What does the data actually mean?** (LLM-powered natural language insights)

### Why This Project?
This project is deliberately engineered to showcase skills that map 1:1 to the following job descriptions:

| Company | Role | Primary Skills Targeted |
|---|---|---|
| American Express | AI Engineer – ML Platform | RAG, GenAI, model governance, responsible AI, Docker/K8s, Airflow |
| Tesla | Data Engineer, People Analytics | ETL Python+SQL, full-stack analytics, dbt, visualization |
| Amazon | Data Engineer, Content & Data Platform | Kafka, AWS, Spark, distributed ETL, data modeling |
| PayPal | Machine Learning Engineer | XGBoost, fraud/risk scoring, model validation, Spark/SQL |

> **Note:** NVIDIA Deep Learning Engineer is intentionally out of scope. That role requires PyTorch, GPU workloads, and model serving infrastructure (vLLM, TensorRT) that do not fit naturally into a workforce analytics platform. Targeting it with this project would be a credibility risk in interviews. Focus is on AmEx, Tesla, Amazon, and PayPal where every component maps directly.

### Elevator Pitch
> *"TalentLens is a production-grade workforce intelligence platform. The primary dataset is a synthetic generator I built that produces 100,000+ employee records and 2M+ HR events, designed to simulate enterprise-scale people analytics data realistically — with seasonal hiring spikes, department-specific attrition curves, manager change cascades, and performance drift patterns. I designed a multi-topic Kafka event streaming architecture feeding Airflow-orchestrated ETL pipelines into PostgreSQL, with PySpark handling batch feature engineering at scale. I deployed a multi-factor risk scoring engine (XGBoost + Isolation Forest) with MLflow model governance, PSI drift monitoring, and Fairlearn bias audits. The HITL override workflow feeds back into active learning retraining using uncertainty sampling. I built a LangChain ReAct agent with tool-calling over live risk data and HR policy RAG, evaluated with RAGAS. Eight microservices are deployed on Kubernetes with HPA on Kafka consumer lag — full architecture documented with ADRs."*

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                                 │
│  Synthetic Generator (primary: 100K employees, 2M events)           │
│  Mock HRIS API (Workday sim)  │  Public BLS / O*NET datasets        │
└──────────────┬──────────────────────────┬────────────────────────────┘
               │                          │
               ▼                          ▼
┌──────────────────────────┐   ┌─────────────────────────┐
│   KAFKA EVENT BROKER     │   │   AIRFLOW SCHEDULER     │
│  Topics:                 │   │  DAGs:                  │
│  · employee-events       │◄──│  · hris_ingestion_dag   │
│  · risk-score-updates    │   │  · spark_features_dag   │
│  · audit-log             │   │  · risk_scoring_dag     │
│  · hiring-funnel-events  │   │  · drift_monitor_dag    │
└──────────┬───────────────┘   │  · report_gen_dag       │
           │                   └────────────┬────────────┘
           ▼                                │
┌──────────────────────────────────────────────────────┐
│              POSTGRESQL DATA WAREHOUSE                │
│  Schemas: raw · staging · mart · audit               │
│  dbt models: dim_employee · fact_risk · fact_hiring  │
│  AWS S3 backup via Lambda trigger                    │
└──────────────────────┬───────────────────────────────┘
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
┌──────────────────────┐  ┌────────────────────────────────┐
│  PYSPARK FEATURE     │  │    RISK ML ENGINE              │
│  ENGINEERING         │  │  · XGBoost (flight risk)       │
│  · Batch aggregations│─►│  · Isolation Forest (anomaly)  │
│  · Window functions  │  │  · Composite Risk Index 0–100  │
│  · Rolling stats     │  │  · SHAP explainability         │
│  · Peer percentiles  │  └────────────┬───────────────────┘
└──────────────────────┘               │
                                       ▼
                         ┌──────────────────────────────┐
                         │    MODEL GOVERNANCE LAYER    │
                         │  · MLflow Registry           │
                         │  · PSI Drift Monitoring      │
                         │  · Fairlearn Bias Audit      │
                         │  · HITL Active Learning Loop │
                         │  · Model Risk Cards          │
                         └──────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────┐
│              LLM & AGENTIC LAYER                    │
│  LangChain ReAct Agent                              │
│  Tools: query_risk_db · search_hr_policy            │
│         flag_for_review · generate_report           │
│  RAG: FAISS vector store over HR policy docs        │
│  LLM Abstraction: OpenAI / Anthropic / Ollama       │
│  Evaluation: RAGAS (faithfulness, relevance, recall)│
└────────────────────────┬────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│                  FASTAPI BACKEND                    │
│  /api/v1/employees     /api/v1/risk                 │
│  /api/v1/agent/chat    /api/v1/models               │
│  /api/v1/audit         /api/v1/alerts               │
│  WebSocket: /ws/dashboard (real-time risk feed)     │
└────────────────────────┬────────────────────────────┘
                         │
          ┌──────────────┴───────────────┐
          ▼                               ▼
┌──────────────────┐          ┌────────────────────────┐
│  REACT DASHBOARD │          │   EXTERNAL INTEGRATIONS│
│  · Risk heatmap  │          │   · Slack Alerts API   │
│  · SHAP charts   │          │   · Mock HRIS API      │
│  · Hiring funnel │          │   · LLM Provider APIs  │
│  · Model cards   │          └────────────────────────┘
│  · Agent chatbot │
└──────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│           KUBERNETES CLUSTER (AWS EKS)              │
│  Namespaces: talentlens-prod · talentlens-dev       │
│  Services: api · worker · risk-engine · rag         │
│            frontend · kafka · postgres · mlflow     │
│  HPA on risk-engine (Kafka consumer lag metric)     │
│  ConfigMaps + Secrets for all env management        │
└─────────────────────────────────────────────────────┘
```

---

## 3. Repository Structure

```
talentlens/
│
├── README.md                          # Project overview + architecture diagram
├── SYSTEM_DESIGN.md                   # Full system design document
├── docker-compose.yml                 # Local dev: all services
├── .env.example                       # Environment variables template
│
├── docs/
│   ├── adr/                           # Architecture Decision Records
│   │   ├── ADR-001-kafka-vs-direct-db.md
│   │   ├── ADR-002-xgboost-vs-neural-net.md
│   │   ├── ADR-003-rag-service-separation.md
│   │   ├── ADR-004-kubernetes-hpa-strategy.md
│   │   └── ADR-005-spark-for-feature-engineering.md
│   ├── architecture_diagram.png
│   └── model_risk_card_template.md
│
├── data/
│   ├── raw/                           # Synthetic data output, BLS/O*NET reference files
│   ├── seeds/                         # dbt seed files
│   └── synthetic_generator.py         # PRIMARY dataset: generates 100K+ employees, 2M+ events
│
├── ingestion/
│   ├── kafka/
│   │   ├── producer.py                # HR event producer (simulates HRIS events)
│   │   ├── consumers/
│   │   │   ├── risk_engine_consumer.py
│   │   │   ├── dashboard_consumer.py  # WebSocket push
│   │   │   └── audit_consumer.py      # Immutable S3 audit trail
│   │   └── topic_config.py            # Topic definitions, partitions, retention
│   └── mock_hris_api/
│       ├── main.py                    # FastAPI mock of Workday HRIS
│       └── schemas.py
│
├── orchestration/
│   └── airflow/
│       ├── dags/
│       │   ├── hris_ingestion_dag.py
│       │   ├── spark_features_dag.py  # NEW: triggers PySpark feature job
│       │   ├── risk_scoring_dag.py
│       │   ├── drift_monitor_dag.py
│       │   └── report_generation_dag.py
│       └── plugins/
│           └── talentlens_hooks.py
│
├── warehouse/
│   ├── migrations/                    # Alembic SQL migrations
│   │   └── versions/
│   └── dbt_project/
│       ├── dbt_project.yml
│       ├── models/
│       │   ├── raw/                   # Raw source models
│       │   ├── staging/               # Cleaned, typed models
│       │   └── mart/                  # Business-facing models
│       │       ├── dim_employee.sql
│       │       ├── fact_risk_scores.sql
│       │       ├── fact_hiring_funnel.sql
│       │       └── mart_risk_index.sql
│       └── tests/
│           └── data_quality_tests.yml
│
├── spark/
│   ├── feature_engineering.py         # PySpark batch feature job (run via spark-submit)
│   ├── peer_percentile_job.py         # Computes income percentile within job level/dept
│   └── rolling_aggregations.py        # 30/90/180-day rolling stats per employee
│
├── ml/
│   ├── risk_engine/
│   │   ├── features.py                # Feature spec: which columns, sources, types
│   │   ├── train_attrition.py         # XGBoost flight risk model
│   │   ├── train_anomaly.py           # Isolation Forest performance risk
│   │   ├── risk_index.py              # Composite Risk Index (0-100)
│   │   ├── shap_explainer.py          # SHAP value computation
│   │   └── inference.py              # Real-time scoring endpoint logic
│   ├── governance/
│   │   ├── mlflow_registry.py         # Champion/challenger model management
│   │   ├── drift_monitor.py           # PSI computation, drift alerts
│   │   ├── bias_audit.py              # Fairlearn: demographic parity, equalized odds
│   │   ├── model_risk_card.py         # Auto-generate model risk card as PDF
│   │   └── hitl_workflow.py           # Human-in-the-loop override + active learning
│   └── evaluation/
│       └── ragas_eval.py              # RAG pipeline evaluation (faithfulness etc.)
│
├── llm/
│   ├── providers/
│   │   ├── base.py                    # Abstract LLMProvider class
│   │   ├── openai_provider.py
│   │   ├── anthropic_provider.py
│   │   └── ollama_provider.py         # Local fallback
│   ├── rag/
│   │   ├── indexer.py                 # Document ingestion → FAISS
│   │   ├── retriever.py               # Similarity search
│   │   └── docs/                      # HR policy PDFs, BLS occupational handbooks
│   ├── agent/
│   │   ├── tools/
│   │   │   ├── query_risk_db.py       # Live DB tool
│   │   │   ├── search_hr_policy.py    # RAG tool
│   │   │   ├── flag_for_review.py     # HITL write-back tool
│   │   │   └── generate_report.py     # PDF report tool
│   │   └── react_agent.py             # LangChain ReAct agent orchestration
│   └── risk_narrator.py               # LLM-as-Judge risk explanation generator
│
├── api/
│   ├── main.py                        # FastAPI app entrypoint
│   ├── routers/
│   │   ├── employees.py
│   │   ├── risk.py
│   │   ├── agent.py
│   │   ├── models.py
│   │   └── audit.py
│   ├── schemas/                       # Pydantic models
│   ├── dependencies.py                # DB sessions, auth
│   └── websocket.py                   # Real-time dashboard feed
│
├── integrations/
│   ├── slack_alerts.py                # Slack webhook for high-risk notifications
│   └── aws/
│       ├── s3_backup.py
│       └── lambda_trigger.py
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── RiskHeatmap.jsx
│   │   │   ├── ShapChart.jsx
│   │   │   ├── HiringFunnel.jsx
│   │   │   ├── ModelCard.jsx
│   │   │   └── AgentChatbot.jsx
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx
│   │   │   ├── RiskExplorer.jsx
│   │   │   └── ModelGovernance.jsx
│   │   └── App.jsx
│   └── package.json
│
├── infrastructure/
│   ├── docker/
│   │   ├── Dockerfile.api
│   │   ├── Dockerfile.worker
│   │   ├── Dockerfile.risk-engine
│   │   └── Dockerfile.rag
│   └── kubernetes/
│       ├── namespaces.yaml
│       ├── configmaps/
│       │   ├── api-config.yaml
│       │   └── risk-engine-config.yaml
│       ├── secrets/                   # Sealed secrets (no plaintext)
│       ├── deployments/
│       │   ├── api-deployment.yaml
│       │   ├── risk-engine-deployment.yaml
│       │   ├── rag-deployment.yaml
│       │   └── frontend-deployment.yaml
│       ├── services/
│       ├── hpa/
│       │   └── risk-engine-hpa.yaml   # Scale on Kafka consumer lag
│       └── statefulsets/
│           ├── postgres-statefulset.yaml
│           └── kafka-statefulset.yaml
│
└── tests/
    ├── unit/
    ├── integration/
    └── load/
        └── locustfile.py              # Load testing the risk scoring API
```

---

## 4. Component Deep-Dives

### 4.1 Data Ingestion Layer — Kafka

**What you build:** A multi-topic Kafka event streaming architecture that simulates real-time HR system events.

**Topics and their purpose:**

| Topic | Partitions | Retention | Purpose |
|---|---|---|---|
| `employee-events` | 6 | 7 days | Raw HR events: hires, terminations, promotions, manager changes |
| `risk-score-updates` | 3 | 3 days | Computed risk deltas emitted after each model inference run |
| `audit-log` | 3 | 30 days | Immutable log of every model decision and HITL override |
| `hiring-funnel-events` | 3 | 7 days | Application, screen, interview, offer, hire/reject transitions |

**Consumer Groups:**

```python
# risk-engine-consumer
# Triggers model inference on every new employee-events message
# Uses manual offset commits for exactly-once semantics

# dashboard-consumer  
# Pushes real-time risk score deltas to React frontend via WebSocket
# Low-latency, at-most-once acceptable here

# audit-consumer
# Writes every message to S3 as immutable audit trail
# At-least-once with idempotent S3 writes (object key = message UUID)
```

**Key interview talking points this enables:**
- *"How do you handle backpressure?"* → Consumer lag monitoring with Prometheus, HPA scales risk-engine pods when lag exceeds threshold
- *"What if the risk engine crashes?"* → Kafka retention means events replay from last committed offset on restart
- *"How do you guarantee no duplicate scoring?"* → Idempotent inference with message UUID deduplication table in PostgreSQL
- *"Why Kafka over direct DB writes?"* → See ADR-001: decouples ingestion rate from processing rate, enables fan-out to multiple consumers, provides durable event log

---

### 4.2 Orchestration Layer — Airflow

**What you build:** Five production DAGs managing the full data lifecycle.

**DAG: `hris_ingestion_dag`**
- Schedule: `@hourly`
- Tasks: `extract_from_hris_api` → `validate_schema` → `load_to_raw_postgres` → `trigger_dbt_run` → `notify_on_failure`
- Uses: Custom `HRISHook` (extends `BaseHook`), `BranchPythonOperator` for schema validation failures

**DAG: `spark_features_dag`** *(new — Amazon/PayPal signal)*
- Schedule: `@daily` (runs before risk_scoring_dag)
- Tasks: `submit_peer_percentile_job` → `submit_rolling_aggregations_job` → `validate_feature_output` → `write_feature_table`
- Uses: `SparkSubmitOperator`, reads from PostgreSQL mart, writes feature table back to mart schema
- Why: Batch feature engineering at 100K employee scale is where Spark earns its keep — window functions and peer-group aggregations that would be slow in pure SQL

**DAG: `risk_scoring_dag`**
- Schedule: `@daily` + triggered by Kafka consumer lag threshold
- Tasks: `pull_features_from_mart` → `run_xgboost_inference` → `run_isolation_forest` → `compute_risk_index` → `write_scores_to_db` → `publish_to_kafka`
- Uses: `PythonOperator` with XCom for passing feature dataframes between tasks

**DAG: `drift_monitor_dag`**
- Schedule: `@weekly`
- Tasks: `load_reference_distribution` → `load_current_distribution` → `compute_psi` → `flag_if_drift_detected` → `trigger_retraining_if_needed` → `slack_alert`
- PSI threshold: > 0.2 triggers automatic Slack alert + model retraining ticket

**DAG: `report_generation_dag`**
- Schedule: `@monthly`
- Tasks: `aggregate_risk_trends` → `run_bias_audit` → `generate_model_risk_card` → `upload_to_s3` → `email_to_stakeholders`

---

### 4.3 Data Warehouse Layer — PostgreSQL + dbt

**Schema design (4 layers):**

```sql
-- RAW SCHEMA: exact copy of source data, never modified
raw.employee_events
raw.hiring_funnel_events
raw.hris_employee_snapshot

-- STAGING SCHEMA: cleaned, typed, renamed
staging.stg_employees          -- deduped, null-handled, typed
staging.stg_hiring_events      -- normalized stage transitions
staging.stg_risk_scores        -- validated score ranges

-- MART SCHEMA: business-facing, optimized for queries
mart.dim_employee              -- slowly changing dimension (SCD Type 2)
mart.fact_risk_scores          -- one row per employee per scoring run
mart.fact_hiring_funnel        -- conversion rates by department/role
mart.mart_risk_index           -- composite risk with all three components
mart.feature_store             -- output of PySpark feature engineering jobs

-- AUDIT SCHEMA: immutable, append-only
audit.model_decisions          -- every inference with inputs and outputs
audit.hitl_overrides           -- every human override with reason and timestamp
audit.drift_reports            -- weekly PSI results
audit.active_learning_labels   -- HITL labels queued for retraining
```

**dbt features to implement:**
- `dbt test` for data quality (not_null, unique, accepted_values, relationships)
- `dbt docs generate` — deploy the docs site so it's visible in your portfolio
- Incremental models on `fact_risk_scores` (only process new rows)
- Macros for repeated logic (e.g., `risk_band()` macro to categorize 0-100 into Low/Medium/High/Critical)

---

### 4.4 Batch Feature Engineering — PySpark

**Why PySpark here:** At 100K employees with 2 years of daily event history (~70M rows of time-series data), computing rolling aggregations and peer-group percentiles in pure SQL becomes slow and hard to maintain. PySpark is the right tool and it directly targets what Amazon and PayPal want to see.

**Job 1: `peer_percentile_job.py`**
```python
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

spark = SparkSession.builder.appName("TalentLens-PeerPercentiles").getOrCreate()

df = spark.read.jdbc(url=POSTGRES_URL, table="mart.dim_employee", properties=props)

# Compute income percentile within each job_level + department group
peer_window = Window.partitionBy("job_level", "department")

df = df.withColumn(
    "monthly_income_vs_peer_median",
    F.percent_rank().over(peer_window.orderBy("monthly_income"))
).withColumn(
    "income_peer_percentile",
    F.ntile(4).over(peer_window.orderBy("monthly_income"))  # quartile
)

df.write.jdbc(url=POSTGRES_URL, table="mart.feature_store", mode="overwrite", properties=props)
```

**Job 2: `rolling_aggregations.py`**
```python
# Computes rolling 30/90/180-day stats per employee from event history
events = spark.read.jdbc(url=POSTGRES_URL, table="raw.employee_events", properties=props)

# Time-based window per employee, ordered by event_timestamp
emp_window_30d  = Window.partitionBy("employee_id").orderBy("event_ts").rangeBetween(-30*86400, 0)
emp_window_90d  = Window.partitionBy("employee_id").orderBy("event_ts").rangeBetween(-90*86400, 0)
emp_window_180d = Window.partitionBy("employee_id").orderBy("event_ts").rangeBetween(-180*86400, 0)

features = events.withColumn("manager_changes_30d",  F.sum("is_manager_change").over(emp_window_30d)) \
                 .withColumn("manager_changes_90d",  F.sum("is_manager_change").over(emp_window_90d)) \
                 .withColumn("absence_rate_90d",     F.mean("is_absent").over(emp_window_90d)) \
                 .withColumn("overtime_rate_180d",   F.mean("is_overtime").over(emp_window_180d))
```

**Interview talking point (Amazon):** *"I used PySpark window functions to compute rolling 30/90/180-day behavioral aggregations over 70M event rows, writing the feature store back to PostgreSQL for XGBoost consumption. This is the kind of large-scale feature engineering that wouldn't be feasible in a single-node SQL query."*

---

### 4.5 Risk ML Layer — XGBoost + Isolation Forest

**Model 1: Flight Risk (XGBoost Classifier)**

Features engineered from the synthetic dataset + PySpark feature store:
```python
features = [
    # Raw employee attributes
    'years_at_company', 'years_since_last_promotion',
    'overtime_flag', 'job_satisfaction', 'work_life_balance',
    'distance_from_home', 'number_of_companies_worked',
    'training_times_last_year', 'performance_rating',
    # PySpark-computed features (from feature_store)
    'monthly_income_vs_peer_median',   # percentile within job level + dept
    'income_peer_percentile',           # quartile rank
    'manager_changes_30d',              # rolling 30-day count
    'manager_changes_90d',              # rolling 90-day count
    'absence_rate_90d',                 # rolling 90-day absence rate
    'overtime_rate_180d',               # rolling 180-day overtime rate
]
```

Training setup:
- Train/val/test split: 70/15/15 with temporal holdout (last 3 months as test)
- Class imbalance handling: `scale_pos_weight` in XGBoost
- Hyperparameter tuning: Optuna with 100 trials, 5-fold CV
- Target metric: AUC-ROC (aim for > 0.85), F1 on high-risk class
- **HITL-labeled samples:** Any confirmed override labels from `audit.active_learning_labels` are included in the training set with their corrected label

**Model 2: Performance Anomaly (Isolation Forest)**

Detects employees whose recent behavior deviates significantly from their own historical baseline:
```python
anomaly_features = [
    'performance_rating_delta',        # change from 6-month rolling avg
    'attendance_anomaly_score',
    'project_completion_rate_delta',
    'peer_review_score_delta',
    'absence_rate_90d',                # from PySpark feature store
    'overtime_rate_180d'
]
# contamination=0.05 (assume ~5% are anomalous)
```

**Composite Risk Index:**
```python
def compute_risk_index(flight_risk_prob, anomaly_score, compliance_flag):
    # Configurable weights, defaults tuned on validation set
    w_flight = 0.50
    w_anomaly = 0.35
    w_compliance = 0.15
    
    normalized_anomaly = (anomaly_score - min_score) / (max_score - min_score)
    
    risk_index = (
        w_flight * flight_risk_prob * 100 +
        w_anomaly * normalized_anomaly * 100 +
        w_compliance * compliance_flag * 100
    )
    return round(risk_index, 2)  # 0–100

# Risk Bands:
# 0–25: Low | 26–50: Medium | 51–75: High | 76–100: Critical
```

**SHAP Explainability:**
```python
import shap
explainer = shap.TreeExplainer(xgb_model)
shap_values = explainer.shap_values(X_test)
# Top 3 drivers per employee exposed via API and rendered in React dashboard
```

---

### 4.6 Model Governance Layer — MLflow + Fairlearn

**MLflow Setup:**
```python
# Champion/challenger model management
mlflow.set_experiment("talentlens-flight-risk")

with mlflow.start_run(run_name="xgb_v3_optuna"):
    mlflow.log_params(best_params)
    mlflow.log_metrics({
        "auc_roc": auc, "f1_high_risk": f1,
        "psi_vs_baseline": psi_score
    })
    mlflow.xgboost.log_model(model, "model")
    mlflow.set_tag("stage", "challenger")  # promote to champion after validation
```

**PSI Drift Monitoring:**
```python
def compute_psi(expected, actual, buckets=10):
    # Population Stability Index
    # PSI < 0.1: No significant change
    # PSI 0.1–0.2: Moderate change, monitor
    # PSI > 0.2: Significant shift, retrain
    breakpoints = np.percentile(expected, np.linspace(0, 100, buckets + 1))
    expected_pcts = np.histogram(expected, breakpoints)[0] / len(expected)
    actual_pcts = np.histogram(actual, breakpoints)[0] / len(actual)
    psi = np.sum((actual_pcts - expected_pcts) * np.log(actual_pcts / expected_pcts))
    return psi
```

**Fairlearn Bias Audit:**
```python
from fairlearn.metrics import MetricFrame, demographic_parity_difference

metrics = MetricFrame(
    metrics={"accuracy": accuracy_score, "selection_rate": selection_rate},
    y_true=y_test,
    y_pred=y_pred,
    sensitive_features=df_test[['gender', 'age_band', 'department']]
)
# Flagged if demographic_parity_difference > 0.1
```

**Model Risk Card auto-generated fields:**
- Model name, version, training date, data cutoff
- Performance metrics (AUC, F1, precision, recall)
- Fairness metrics by demographic group
- Active learning label count included in training set
- Known limitations and failure modes
- Recommended review frequency

---

### 4.7 HITL Active Learning Loop

**This section specifies the full mechanics of how human overrides feed back into model retraining.** This is the piece that differentiates TalentLens from a simple ML project — it closes the feedback loop and makes the system self-improving.

**Step-by-step flow:**

```
1. Model predicts: Employee 7429 → risk_index = 88 (Critical)
2. HR manager sees this in dashboard, disagrees — clicks "Dispute Prediction"
3. Manager selects one of:
   - "Not at risk" (label override: 0)
   - "At risk for different reason" (label override: 1, notes required)
   - "Needs more information" (deferred — not used for retraining)
4. API writes to audit.hitl_overrides:
   {employee_id, original_score, override_label, reason, reviewer_id, timestamp}
5. Also writes to audit.active_learning_labels:
   {employee_id, feature_snapshot (JSON), corrected_label, confidence: "human_verified"}

6. Weekly drift_monitor_dag checks: if new_hitl_labels >= 50 OR psi > 0.2 → trigger retraining
7. Retraining job:
   a. Loads base training set from synthetic data
   b. Pulls all rows from audit.active_learning_labels
   c. Uncertainty sampling: also pulls 200 model-predicted samples near decision boundary
      (0.4 < predicted_prob < 0.6) for inclusion as "uncertain" training signal
   d. Combines, retrains XGBoost with Optuna tuning
   e. Registers new model as "challenger" in MLflow
   f. Auto-promotes to "champion" if: AUC_new > AUC_current AND fairness_metrics pass
```

**Why this matters in interviews:**
- At AmEx: *"We use uncertainty sampling from the model's own prediction confidence to prioritize which samples to include in retraining — this is active learning. It means the model focuses its retraining budget on the cases it's least sure about, which is where performance degrades first."*
- At PayPal: *"This mirrors real-world fraud model workflows where analyst overrides on suspicious transactions feed back into model retraining."*

---

### 4.8 LLM & Agentic Layer — LangChain

**LLM Abstraction Layer (multi-provider):**
```python
from abc import ABC, abstractmethod

class LLMProvider(ABC):
    @abstractmethod
    def complete(self, messages: list[dict], **kwargs) -> str: ...

class OpenAIProvider(LLMProvider):
    def complete(self, messages, **kwargs):
        # openai.ChatCompletion.create(...)

class AnthropicProvider(LLMProvider):
    def complete(self, messages, **kwargs):
        # anthropic.messages.create(...)

class OllamaProvider(LLMProvider):
    def complete(self, messages, **kwargs):
        # Local Llama 3 via Ollama REST API — zero cost fallback

# Factory with cost/latency tradeoff config
def get_provider(tier: str) -> LLMProvider:
    return {"premium": AnthropicProvider, "standard": OpenAIProvider,
            "local": OllamaProvider}[tier]()
```

**LangChain ReAct Agent — 4 Tools:**

```python
# Tool 1: query_risk_db
@tool
def query_risk_db(employee_id: str) -> dict:
    """Query the live PostgreSQL database for an employee's current risk scores,
    SHAP drivers, and historical score trend."""
    # Returns: {risk_index, flight_risk_prob, anomaly_score, top_shap_drivers, trend}

# Tool 2: search_hr_policy
@tool  
def search_hr_policy(query: str) -> str:
    """Search the HR policy document corpus using RAG to answer questions
    about company policies, procedures, and compliance requirements."""
    # FAISS retrieval over indexed HR PDFs and BLS occupational handbooks

# Tool 3: flag_for_review
@tool
def flag_for_review(employee_id: str, reason: str, reviewer_id: str) -> str:
    """Submit a Human-in-the-Loop override request for a risk prediction.
    Writes to audit.hitl_overrides and queues for active learning."""
    # Returns: confirmation with override_id

# Tool 4: generate_report
@tool
def generate_report(department: str, report_type: str) -> str:
    """Generate a PDF risk summary report for a department.
    report_type: 'risk_summary' | 'model_card' | 'hiring_funnel'"""
    # Returns: S3 presigned URL to downloaded PDF
```

**LLM-as-Judge Risk Narrator:**
```python
def generate_risk_narrative(employee_id, shap_values, risk_index):
    prompt = f"""
    You are an HR analytics assistant. Given the following risk assessment data,
    generate a clear, actionable, 3-sentence explanation for an HR manager.
    
    Employee Risk Index: {risk_index}/100 (Critical)
    Top risk drivers (SHAP): {shap_values}
    
    Rules: Be specific. Use plain English. Suggest one concrete action.
    Do not speculate beyond the data provided.
    """
    return llm_provider.complete([{"role": "user", "content": prompt}])
```

**RAG Pipeline:**
- Documents: HR policy manuals, onboarding guides, compensation frameworks, BLS Occupational Outlook Handbook sections (public domain — no licensing risk), O*NET occupation data
- Chunking: 512 tokens with 50-token overlap
- Embeddings: `text-embedding-3-small` (OpenAI) or `nomic-embed-text` (local)
- Vector store: FAISS with cosine similarity
- Retrieval: Top-5 chunks with MMR (Maximal Marginal Relevance) for diversity

**RAGAS Evaluation:**
```python
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_recall

results = evaluate(
    dataset=eval_dataset,  # 50 Q&A pairs manually crafted
    metrics=[faithfulness, answer_relevancy, context_recall]
)
# Target: faithfulness > 0.85, answer_relevancy > 0.80
```

---

### 4.9 API Layer — FastAPI

**Endpoints:**
```
GET  /api/v1/employees/{id}          Employee profile + current risk scores
GET  /api/v1/employees/{id}/trend    Historical risk score timeline
GET  /api/v1/risk/department/{dept}  Department-level risk aggregation
POST /api/v1/risk/score              Trigger on-demand risk scoring
GET  /api/v1/risk/top-n?n=10        Top N highest risk employees

POST /api/v1/agent/chat             Send message to ReAct agent
GET  /api/v1/agent/history/{session} Conversation history

GET  /api/v1/models                 List all registered MLflow models
GET  /api/v1/models/{id}/card       Fetch model risk card
POST /api/v1/models/{id}/override   Submit HITL override

GET  /api/v1/audit/decisions        Model decision log
GET  /api/v1/audit/overrides        HITL override log
GET  /api/v1/alerts/active          Current high-risk alerts

WS   /ws/dashboard                  Real-time risk score stream (WebSocket)
```

**Key implementation details:**
- **Authentication:** JWT tokens with role-based access (HR_MANAGER, DATA_SCIENTIST, ADMIN)
- **Rate limiting:** `slowapi` — 100 req/min for scoring endpoint
- **Async:** All DB operations use `asyncpg` with connection pooling
- **Validation:** All request/response models defined with Pydantic v2
- **Docs:** Auto-generated Swagger UI at `/docs`, ReDoc at `/redoc`

---

### 4.10 External API Integrations

**Integration 1 — Slack Alerts API**
```python
def send_risk_alert(employee_id, risk_index, top_drivers, reviewer_slack_id):
    payload = {
        "channel": "#hr-risk-alerts",
        "blocks": [
            {"type": "header", "text": {"type": "plain_text",
             "text": f"🚨 Critical Risk Alert: Employee #{employee_id}"}},
            {"type": "section", "fields": [
                {"type": "mrkdwn", "text": f"*Risk Index:* {risk_index}/100"},
                {"type": "mrkdwn", "text": f"*Top Driver:* {top_drivers[0]}"}
            ]},
            {"type": "actions", "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "Review"},
                 "url": f"https://talentlens.app/employee/{employee_id}"}
            ]}
        ]
    }
    requests.post(SLACK_WEBHOOK_URL, json=payload)
```
Trigger condition: `risk_index > 85 AND previous_risk_index < 75` (sudden spike)

**Integration 2 — Mock HRIS API (Workday Simulation)**
```python
# Separate FastAPI app that simulates Workday HR System
# Endpoints:
GET  /hris/employees              # Paginated employee list
GET  /hris/employees/{id}         # Single employee with full profile
GET  /hris/events?since={ts}      # Delta sync: events since timestamp
POST /hris/employees/{id}/update  # Simulate HR record update

# Called by Airflow hris_ingestion_dag every hour
# Demonstrates enterprise data integration patterns
```

**Integration 3 — LLM Provider APIs (with fallback chain)**
```python
# Priority: Anthropic Claude → OpenAI GPT-4o → Ollama Llama3 (local)
# Fallback triggers on: rate limit, API error, cost threshold exceeded
# Cost tracking: log token usage per request to audit.llm_costs table
```

---

### 4.11 Frontend Dashboard — React

**Pages and components:**

**Dashboard (home):**
- Risk heatmap: all employees plotted by department, color-coded by risk band
- KPI cards: Total Critical (red), High (orange), Medium (yellow), Low (green)
- Real-time feed: WebSocket-powered live risk score updates
- Trend chart: 30-day rolling average risk by department (Recharts)

**Risk Explorer:**
- Employee search and filter (department, risk band, tenure)
- Employee detail panel: composite risk index gauge, SHAP waterfall chart
- LLM-generated narrative explanation
- "Dispute Prediction" button → HITL form → feeds active learning queue

**Model Governance:**
- Champion model card with all metrics and fairness breakdown
- Challenger model comparison table
- PSI drift chart over time
- Override history log + active learning label count

**Agent Chatbot:**
- Embedded chat interface in sidebar
- Shows which tool the agent called (tool trace visible)
- Conversation history persisted per session

---

### 4.12 Infrastructure — Docker + Kubernetes + AWS

**Deployment honesty rule:** Only claim EKS deployment on your resume if you actually deploy to it. If budget is a concern, deploy to **minikube locally** for the demo and state *"architected for AWS EKS; local demo runs on minikube."* That is 100% credible. Amazon interviewers will ask detailed EKS/IAM/node-group questions — only claim what you've done.

**8 Kubernetes Services:**

| Service | Image | Replicas | Resources |
|---|---|---|---|
| `talentlens-api` | `./docker/Dockerfile.api` | 2–5 (HPA) | 500m CPU, 512Mi |
| `talentlens-worker` | `./docker/Dockerfile.worker` | 2 | 1 CPU, 1Gi |
| `talentlens-risk-engine` | `./docker/Dockerfile.risk-engine` | 1–10 (HPA on Kafka lag) | 2 CPU, 2Gi |
| `talentlens-rag` | `./docker/Dockerfile.rag` | 1–3 (HPA) | 1 CPU, 2Gi |
| `talentlens-frontend` | nginx + built React | 2 | 200m CPU, 256Mi |
| `kafka` | `confluentinc/cp-kafka` | 3 (StatefulSet) | 2 CPU, 4Gi |
| `postgres` | `postgres:15` | 1 (StatefulSet + PVC) | 1 CPU, 2Gi |
| `mlflow-server` | `./docker/Dockerfile.mlflow` | 1 | 500m CPU, 1Gi |

**HPA for risk-engine (Kafka consumer lag metric):**
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: risk-engine-hpa
  namespace: talentlens-prod
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: talentlens-risk-engine
  minReplicas: 1
  maxReplicas: 10
  metrics:
  - type: External
    external:
      metric:
        name: kafka_consumer_lag
        selector:
          matchLabels:
            topic: employee-events
            group: risk-engine-consumer
      target:
        type: AverageValue
        averageValue: "1000"   # Scale up when lag > 1000 messages per pod
```

**AWS Services Used:**
- **S3:** Raw data backup, audit log archive, model artifact storage, report PDFs
- **Lambda:** Triggered by S3 PutObject events to kick off Airflow DAGs
- **EKS:** Kubernetes cluster (target environment; minikube acceptable for portfolio demo)
- **ECR:** Private container registry for all Docker images
- **Secrets Manager:** Stores DB passwords, API keys (referenced by K8s Secrets)
- **CloudWatch:** Log aggregation from all pods

---

## 5. Data Sources & Schema

### ⚠️ Data Strategy — Synthetic Generator is the Hero

**The primary dataset for TalentLens is the synthetic generator you build, not any third-party dataset.** This is intentional and strategically stronger:
- No licensing, attribution, or data use agreement issues whatsoever
- Scale is unlimited — generate 100K employees and 2M events, not capped at 1,470 rows
- Patterns are designed, not discovered — you control attrition curves, seasonal spikes, department-specific behaviors
- In interviews: *"I built a synthetic data generator that produces 100K employee records and 2M+ HR event records across 2 years, with realistic statistical properties"* is more impressive than *"I downloaded a Kaggle dataset"*

### Primary Dataset: Synthetic Generator (`data/synthetic_generator.py`)

**Generates:**
- 100,000 employee records with full profile attributes
- 2,000,000+ HR event records across 24 months
- Designed patterns:
  - Seasonal hiring spikes (Q1, Q3)
  - Department-specific attrition rates (Sales: 22%, Engineering: 8%, Finance: 12%)
  - Manager change cascades (one manager departure triggers 3-8 direct-report risk spikes)
  - Promotion cycles aligned to performance review periods
  - Realistic income distributions with peer-group variance

**Statistical design principles:**
```python
# Attrition is NOT random — it correlates with:
# - Low satisfaction (job_satisfaction < 2) → 4x attrition multiplier
# - No promotion in 3+ years → 2.5x multiplier
# - Manager changed 2+ times in 12 months → 2x multiplier
# - Below peer median income → 1.8x multiplier
# These ensure XGBoost has real signal to learn from
```

### Supplementary Public Datasets (no licensing issues)

| Dataset | Source | Use | License |
|---|---|---|---|
| BLS Occupational Employment Statistics | Bureau of Labor Statistics (bls.gov) | Realistic salary bands by occupation/region | Public domain (US government) |
| O*NET Occupation Data | O*NET OnLine (onetonline.org) | Job role attributes, skill requirements | Public domain (CC BY 4.0) |
| BLS Occupational Outlook Handbook | Bureau of Labor Statistics | RAG document corpus — career path info | Public domain (US government) |

> **Why not IBM HR Attrition (Kaggle)?** The IBM dataset has only 1,470 rows — too small for enterprise-scale storytelling. It is also extremely well-known and overused; interviewers have seen it many times. Using your own synthetic generator is original, scalable, and more impressive. The IBM dataset can optionally be used as a **validation reference** to confirm that your synthetic data has similar statistical properties, but should not be the primary training data.

### RAG Document Corpus
- 5 synthetic HR policy documents (compensation, PTO, code of conduct, performance review process, remote work policy) — each 10–20 pages
- BLS Occupational Outlook Handbook sections (public domain) — career and market context
- O*NET job descriptions for top 20 roles in the synthetic company (public domain)
- Total: ~250 pages of indexable content, all public domain or self-authored

---

## 6. Architecture Decision Records

### ADR-001: Kafka Over Direct Database Writes for Event Ingestion

**Status:** Accepted

**Context:** We needed to choose between having the HRIS API write directly to PostgreSQL vs. publishing events to Kafka for downstream consumption.

**Decision:** Use Kafka as the event backbone.

**Reasons:**
1. Decouples ingestion rate from processing rate — HRIS can produce events at burst speed without overwhelming the risk engine
2. Enables fan-out: one `employee-events` message is consumed by three independent consumer groups (risk-engine, dashboard, audit) without re-querying the source
3. Durable event log with configurable retention — if risk engine goes down, it replays from last committed offset on restart with zero data loss
4. Natural fit for future expansion (add new consumers without touching producers)

**Tradeoffs accepted:** Operational complexity of managing a Kafka cluster; eventual consistency between event time and query availability.

---

### ADR-002: XGBoost Over Neural Networks for Risk Scoring

**Status:** Accepted

**Context:** Choosing the ML model for employee flight risk prediction.

**Decision:** Use XGBoost as the primary model, with Isolation Forest for anomaly detection.

**Reasons:**
1. Tabular data with engineered features — XGBoost consistently outperforms neural nets on tabular data at this scale
2. SHAP explainability is native and fast — critical for HR use case where managers need to understand every prediction
3. Model Risk Management requirements (mirroring PayPal's framework) demand interpretable models for high-stakes decisions
4. Training time is seconds vs. minutes; retraining on drift is operationally feasible weekly
5. No GPU required — reduces infrastructure cost

**Tradeoffs accepted:** Cannot capture complex sequential patterns in employee behavior over time (future work: temporal feature engineering via rolling aggregations in PySpark, which is already implemented).

---

### ADR-003: Separate RAG Service from Core API

**Status:** Accepted

**Context:** Deciding whether to embed RAG/LLM logic inside the FastAPI backend or deploy it as a separate service.

**Decision:** Separate `talentlens-rag` microservice with its own deployment.

**Reasons:**
1. LLM calls are high-latency (1–10s) and should not block the low-latency risk scoring API (target < 100ms)
2. FAISS index loads into memory once per pod — separating allows independent scaling
3. LLM provider failures should not cascade to the core API
4. Independent deployability — can upgrade RAG pipeline (swap models, re-index) without touching the risk engine

**Tradeoffs accepted:** Network hop between API and RAG service adds ~5ms latency; additional service to monitor and deploy.

---

### ADR-004: HPA on Kafka Consumer Lag Metric

**Status:** Accepted

**Context:** Choosing the autoscaling trigger for the risk-engine pods.

**Decision:** Use Kafka consumer lag as the HPA external metric instead of CPU/memory.

**Reasons:**
1. CPU is a lagging indicator — by the time CPU spikes, the lag has already grown to thousands of messages
2. Consumer lag directly measures the work backlog, which is exactly what we want to drain
3. Allows proactive scaling before users experience latency
4. Kafka lag is a well-understood operational metric in data engineering

**Tradeoffs accepted:** Requires KEDA (Kubernetes Event Driven Autoscaler) or custom metrics adapter to expose Kafka lag to HPA; additional setup complexity.

---

### ADR-005: PySpark for Batch Feature Engineering

**Status:** Accepted

**Context:** Choosing the compute engine for batch feature engineering over 100K employees × 2 years of daily event history (~70M rows).

**Decision:** Use PySpark via `SparkSubmitOperator` in Airflow for rolling aggregations and peer-group percentile computations.

**Reasons:**
1. Rolling window functions over 70M rows are slow in single-node PostgreSQL; Spark distributes the computation
2. Peer-group percentile ranking (income vs. peers within job level + department) requires a full partition scan — natural fit for Spark `Window` functions
3. Decouples feature computation from the warehouse layer — feature engineering can be iterated independently
4. Directly targets Amazon DE and PayPal MLE job requirements (Spark is listed in both JDs)

**Tradeoffs accepted:** Spark cluster adds infrastructure complexity; for smaller datasets, pure dbt/SQL would suffice. Mitigated by running Spark in local mode for development.

---

## 7. System Design Document

### Scale Assumptions
| Metric | Value | Rationale |
|---|---|---|
| Total employees | 100,000 | Large enterprise; enables realistic Spark justification |
| Daily HR events | 500K–2M | 2 years of history across 100K employees |
| Risk scoring frequency | Daily full + real-time on events | Balance freshness vs. cost |
| Dashboard concurrent users | ~50 HR managers | Internal tool |
| RAG queries/day | ~500 | Chatbot usage |
| Model retraining frequency | Weekly or on PSI > 0.2 or ≥50 new HITL labels | Drift-driven + active learning |

### Bottlenecks Identified and Solutions

**Bottleneck 1: Feature engineering throughput**
- Problem: Rolling aggregations over 70M event rows are slow in pure SQL
- Solution: PySpark batch job via Airflow `SparkSubmitOperator`; runs daily before risk scoring DAG

**Bottleneck 2: Risk scoring throughput during daily full run**
- Problem: Scoring 100K employees sequentially takes too long
- Solution: Batch inference with XGBoost (score all 100K in one `predict_proba` call — milliseconds), parallelize SHAP computation across CPU cores

**Bottleneck 3: FAISS index load time**
- Problem: Loading 250-page document index into memory takes 3–5 seconds per pod restart
- Solution: Separate RAG service (ADR-003); index loads once at startup, stays warm; readiness probe waits for index load before accepting traffic

**Bottleneck 4: LLM API latency**
- Problem: OpenAI/Anthropic calls take 1–10 seconds
- Solution: Async API calls, streaming responses to frontend, cache frequent queries (Redis with 1-hour TTL on identical prompts)

**Bottleneck 5: Dashboard real-time updates at scale**
- Problem: 50 concurrent WebSocket connections all receiving every risk update creates fan-out
- Solution: Dashboard subscribes to department-specific Kafka topics, only receives updates relevant to their filtered view

### Data Flow for a Single Employee Risk Score Request
```
1. HR event arrives (e.g., promotion) → Kafka employee-events topic
2. risk-engine-consumer picks up message (within 100ms)
3. Feature engineering: JOIN employee history from PostgreSQL mart.feature_store
4. XGBoost inference: predict_proba (< 10ms)
5. Isolation Forest: anomaly score (< 5ms)
6. Composite Risk Index computed
7. Risk narrative generated via LLM (async, ~2s)
8. Score written to fact_risk_scores
9. Delta published to risk-score-updates Kafka topic
10. dashboard-consumer pushes update to connected WebSocket clients
11. If risk_index > 85 AND spike detected → Slack alert triggered
Total latency (score available): ~200ms | With narrative: ~2.5s (async)
```

---

## 8. Skills Coverage Matrix

| Skill | Where Demonstrated | Target JD |
|---|---|---|
| Kafka multi-topic architecture | `ingestion/kafka/` | Amazon, AmEx |
| Airflow DAG design | `orchestration/airflow/dags/` | Amazon, AmEx |
| PySpark feature engineering | `spark/feature_engineering.py` | Amazon, PayPal |
| PySpark window functions | `spark/rolling_aggregations.py` | Amazon, PayPal |
| PostgreSQL schema design | `warehouse/migrations/` | Amazon, Tesla |
| dbt data modeling | `warehouse/dbt_project/` | Amazon, Tesla |
| AWS (S3, Lambda, EKS, ECR) | `integrations/aws/`, K8s on EKS | Amazon |
| XGBoost model training | `ml/risk_engine/train_attrition.py` | PayPal |
| Isolation Forest anomaly detection | `ml/risk_engine/train_anomaly.py` | PayPal |
| SHAP explainability | `ml/risk_engine/shap_explainer.py` | PayPal, AmEx |
| MLflow model registry | `ml/governance/mlflow_registry.py` | AmEx, PayPal |
| PSI drift monitoring | `ml/governance/drift_monitor.py` | AmEx, PayPal |
| Fairlearn bias audit | `ml/governance/bias_audit.py` | AmEx |
| HITL active learning loop | `ml/governance/hitl_workflow.py` | AmEx, PayPal |
| Synthetic data generation | `data/synthetic_generator.py` | All |
| LangChain ReAct agent | `llm/agent/react_agent.py` | AmEx |
| RAG pipeline (FAISS) | `llm/rag/` | AmEx |
| LLM abstraction layer | `llm/providers/` | AmEx |
| RAGAS evaluation | `ml/evaluation/ragas_eval.py` | AmEx, PayPal |
| LLM-as-Judge narration | `llm/risk_narrator.py` | AmEx |
| FastAPI backend | `api/` | Tesla, AmEx |
| WebSocket real-time feed | `api/websocket.py` | Tesla |
| React dashboard | `frontend/` | Tesla |
| Docker containerization | `infrastructure/docker/` | AmEx |
| Kubernetes deployments | `infrastructure/kubernetes/` | AmEx |
| HPA autoscaling | `infrastructure/kubernetes/hpa/` | AmEx |
| Slack API integration | `integrations/slack_alerts.py` | AmEx |
| Mock HRIS API | `ingestion/mock_hris_api/` | Amazon |
| Multi-provider API abstraction | `llm/providers/` | AmEx |
| System design (ADRs) | `docs/adr/` | All |
| Data quality testing | `warehouse/dbt_project/tests/` | Amazon, Tesla |
| Load testing | `tests/load/locustfile.py` | Amazon |
| Python (async, OOP, typing) | Throughout | All |
| SQL (complex queries, window functions) | `warehouse/dbt_project/models/` | All |

---

## 9. Resume Bullet Points

> **Honesty rule:** Adjust bullets to reflect what you actually built vs. designed. Interviewers at all four target companies will probe deeply. "Designed and deployed" means running code; "architected" means you have the YAML and can explain every decision.

### Version A (ML/LLM/MLOps/AI Engineer — AmEx focus)

- **Designed and deployed TalentLens**, a production-grade workforce intelligence platform with a multi-topic Kafka event streaming architecture (4 topics, 3 consumer groups), Airflow-orchestrated ETL pipelines, and dbt-modeled PostgreSQL warehouse; primary dataset is a custom synthetic generator producing 100K employee records and 2M+ HR events with designed attrition and behavioral patterns
- **Built a multi-factor employee risk scoring engine** combining XGBoost (AUC 0.87) and Isolation Forest with SHAP explainability, composite Risk Index (0–100), and MLflow-tracked model governance including PSI drift monitoring, Fairlearn demographic bias audits, and an active learning HITL loop where human override labels feed back into weekly model retraining via uncertainty sampling
- **Engineered a LangChain ReAct agent** with 4 live tool integrations (risk DB query, HR policy RAG, HITL override write-back, PDF report generation), multi-provider LLM abstraction (OpenAI/Anthropic/Ollama), and RAGAS-evaluated RAG pipeline (faithfulness > 0.85) over 250-page public-domain document corpus
- **Deployed 8 microservices on Kubernetes** with HPA scaling on Kafka consumer lag, namespace separation (prod/dev), ConfigMap-managed secrets, and liveness/readiness probes; containerized all services with Docker; infrastructure designed for AWS EKS with S3, Lambda, ECR, and Secrets Manager

### Version B (Data Engineer / MLE — Amazon, PayPal focus)

- **Built TalentLens**, an end-to-end workforce analytics platform; authored a synthetic data generator producing 100K employee records and 2M+ HR events, ingested through Kafka → Airflow → PostgreSQL pipelines with dbt models (dim/fact schema, SCD Type 2, incremental processing) and AWS S3 backup via Lambda triggers
- **Designed PySpark feature engineering pipeline** computing rolling 30/90/180-day behavioral aggregations and peer-group income percentiles over 70M event rows using Spark Window functions, orchestrated daily via Airflow `SparkSubmitOperator` before XGBoost model inference
- **Developed and validated a multi-factor employee risk model** using XGBoost (flight risk, AUC 0.87) and Isolation Forest (performance anomaly), with SHAP-based explainability, champion/challenger MLflow registry, PSI-driven drift detection, automated Fairlearn bias audits, and active learning retraining loop incorporating HITL-verified labels and uncertainty-sampled boundary cases
- **Designed full-stack analytics platform** with FastAPI backend (JWT auth, async PostgreSQL, WebSocket real-time feed), React dashboard (risk heatmap, SHAP waterfall charts, hiring funnel visualization), and Slack webhook alerting; integrated LangChain agentic HR copilot with FAISS-based RAG over public-domain document corpus, evaluated with RAGAS

---

## 10. Build Phases & Timeline

> **No fixed deadline.** Build completely and correctly. A polished Phase 1–3 beats a buggy full build. Each phase has a clear checkpoint — don't proceed until the checkpoint passes.

### Phase 1 — Data Foundation
- [ ] Build synthetic data generator (100K employees, 2M events, designed statistical patterns)
- [ ] Validate synthetic data properties: check attrition rate ~15%, salary distributions, seasonal patterns
- [ ] Set up PostgreSQL + raw/staging/mart/audit schemas + Alembic migrations
- [ ] Build mock HRIS API (FastAPI, 4 endpoints)
- [ ] Set up Kafka locally (Docker Compose) — 4 topics with correct configs
- [ ] Write Kafka producer that reads from HRIS API and publishes to employee-events
- [ ] Write `hris_ingestion_dag` in Airflow with schema validation branch
- [ ] Build dbt staging + mart models (dim_employee, fact_risk_scores)
- [ ] Add dbt tests for data quality (not_null, unique, accepted_values)

**Checkpoint:** Full end-to-end: synthetic data → mock HRIS API → Kafka → PostgreSQL → dbt mart. Can query `mart.dim_employee` and see 100K employees.

### Phase 2 — PySpark Feature Engineering
- [ ] Set up Spark locally (Docker or standalone)
- [ ] Write `peer_percentile_job.py` — income percentile within job_level + department
- [ ] Write `rolling_aggregations.py` — 30/90/180-day rolling stats per employee
- [ ] Write `spark_features_dag` in Airflow using SparkSubmitOperator
- [ ] Validate feature output: check `mart.feature_store` is populated correctly
- [ ] Add feature quality assertions (no nulls in key columns, value range checks)

**Checkpoint:** `mart.feature_store` populated with all PySpark features for 100K employees. Can JOIN with dim_employee cleanly.

### Phase 3 — Risk ML
- [ ] Feature engineering pipeline (pulls from mart + feature_store)
- [ ] Train XGBoost on synthetic data with engineered features
- [ ] Train Isolation Forest for anomaly detection
- [ ] Implement composite Risk Index with configurable weights
- [ ] Add SHAP explainer, expose top-3 drivers per employee
- [ ] Set up MLflow experiment tracking (local server)
- [ ] Write `risk_scoring_dag` in Airflow
- [ ] Validate: score distribution looks sensible (not all high, not all low)

**Checkpoint:** Can score all 100K employees daily with SHAP explanations, all tracked in MLflow. Risk band distribution roughly: 60% Low, 25% Medium, 12% High, 3% Critical.

### Phase 4 — Model Governance + HITL
- [ ] PSI drift monitoring in `drift_monitor_dag`
- [ ] Fairlearn bias audit in `report_generation_dag`
- [ ] Model Risk Card PDF generator
- [ ] HITL override form (DB schema + API endpoint)
- [ ] Active learning loop: uncertainty sampling + label incorporation into retraining
- [ ] MLflow champion/challenger promotion workflow
- [ ] Document the full retraining trigger logic

**Checkpoint:** Full model governance lifecycle. Can simulate a drift event (inject distribution shift into synthetic data), trigger PSI alert, retrain, and promote new champion.

### Phase 5 — LLM & Agent
- [ ] LLM provider abstraction layer (3 providers + fallback chain)
- [ ] RAG pipeline: index public-domain HR documents into FAISS
- [ ] LLM-as-Judge risk narrator
- [ ] LangChain ReAct agent with all 4 tools
- [ ] Agent conversation history + session management
- [ ] RAGAS evaluation harness — craft 50 Q&A pairs, run evaluation

**Checkpoint:** Agent answers "Why is Employee 7429 high risk?" using live DB + RAG. RAGAS faithfulness > 0.80.

### Phase 6 — API + Frontend
- [ ] FastAPI backend with all endpoints + WebSocket
- [ ] JWT authentication + role-based access
- [ ] React dashboard: Risk Heatmap + SHAP charts + Agent chatbot + HITL form
- [ ] Slack alert integration
- [ ] dbt docs site generated and hosted

**Checkpoint:** Full working UI with real-time risk feed, embedded chatbot, and HITL dispute form.

### Phase 7 — Infrastructure + Polish
- [ ] Write all Dockerfiles
- [ ] Write all K8s YAML (deployments, services, HPA, ConfigMaps, StatefulSets)
- [ ] Deploy to minikube locally; verify all 8 services run end-to-end
- [ ] If budget allows: deploy to AWS EKS (only claim this on resume if done)
- [ ] Write SYSTEM_DESIGN.md and all 5 ADRs
- [ ] Write comprehensive README with architecture diagram
- [ ] Record 3-minute demo video
- [ ] Update resume bullets to accurately reflect what is built

---

## 11. Interview Talking Points

### System Design Questions You Can Now Answer

**"Design a real-time employee risk monitoring system"**
Walk through the exact architecture above. Kafka for event streaming, consumer groups for fan-out, PySpark for batch feature engineering, XGBoost for low-latency inference (< 10ms batch), SHAP for explainability, WebSocket for real-time dashboard, HPA on consumer lag for autoscaling.

**"How would you handle model drift in production?"**
PSI monitoring weekly via Airflow DAG. PSI < 0.1: stable. 0.1–0.2: alert and monitor. > 0.2: automatic retraining trigger. Additionally, when ≥50 HITL override labels accumulate, retraining is also triggered. Champion/challenger in MLflow. New model auto-promoted only if AUC improves and fairness metrics pass.

**"Tell me about your active learning implementation"**
HITL overrides from HR managers are written to `audit.active_learning_labels`. At retraining time, I also pull 200 samples near the decision boundary (0.4 < predicted_prob < 0.6) using uncertainty sampling — these are the cases the model is least confident about. Both sets are combined with the base training data. This is active learning: the model directs where human attention is most valuable.

**"How do you ensure your ML system is fair and compliant?"**
Fairlearn MetricFrame across demographic groups (gender, age band, department). Demographic parity difference threshold of 0.1. Auto-generated model risk card. Audit log of every decision. HITL override workflow for disputed predictions. New model versions cannot be promoted if fairness metrics regress.

**"Walk me through your Kafka architecture"**
4 topics, purpose of each, partition count rationale, 3 consumer groups with different delivery semantics (exactly-once for risk engine, at-most-once for dashboard, at-least-once for audit), retention policy per topic, replay on failure.

**"Why PySpark for feature engineering?"**
At 100K employees with 2 years of daily event history, that's ~70M rows of time-series data. Computing rolling 30/90/180-day aggregations and peer-group percentile rankings across that volume in a single PostgreSQL node is slow and resource-intensive. PySpark distributes the computation, and the Window functions map naturally onto what we need — partitioning by employee_id for temporal features, by job_level + department for peer-group features.

**"How does your RAG pipeline work?"**
Document ingestion → chunking (512 tokens, 50 overlap) → embedding (text-embedding-3-small) → FAISS index. At query time: embed query → top-5 MMR retrieval → stuff into LangChain prompt → LLM generates answer. Evaluated with RAGAS on 50 manually crafted Q&A pairs. Documents are all public-domain: BLS Occupational Outlook Handbook, O*NET data, and self-authored HR policy documents.

**"Why did you choose XGBoost over a neural network?"**
ADR-002. Tabular data with engineered features: XGBoost wins consistently. SHAP explainability is a hard requirement for HR use cases — model risk governance demands interpretability. Training in seconds makes weekly retraining operationally feasible. No GPU cost. The temporal signal I'd need for an RNN is already captured by the PySpark rolling aggregation features.

**"How do you scale the risk engine under load?"**
Kafka consumer lag as HPA metric via KEDA. When lag on `employee-events` exceeds 1,000 messages per pod, HPA scales up to max 10 replicas. CPU would be a lagging indicator — lag is a leading indicator of work backlog. Stateless inference pods scale horizontally trivially.

**"Tell me about your dataset"**
I built a synthetic data generator that produces 100K employee records and 2M+ HR events over a 2-year simulated period. The generator is statistically designed — attrition correlates with low satisfaction, stagnant compensation relative to peers, and frequent manager changes. This gives XGBoost real signal to learn from. All supplementary documents for RAG are public-domain BLS and O*NET data. No third-party dataset licensing concerns anywhere in the project.

---

## 12. MVP Scope — Must-Ship Baseline

**If time or resources are constrained, ship this subset first.** Everything else is additive. A polished MVP is better than a broken full build.

### MVP (Non-negotiable — ship this before anything else)
- [ ] Synthetic data generator (100K employees)
- [ ] PostgreSQL + dbt models (dim_employee, fact_risk_scores)
- [ ] Kafka ingestion + hris_ingestion_dag
- [ ] XGBoost risk model + SHAP explainer
- [ ] MLflow experiment tracking
- [ ] FastAPI backend (employees, risk, audit endpoints)
- [ ] Docker Compose running all MVP services locally

**What this proves:** End-to-end data engineering + ML pipeline. Enough to talk to for 30 minutes in any interview.

### Layer 2 (Strong portfolio — add after MVP is solid)
- [ ] PySpark feature engineering
- [ ] PSI drift monitoring + Fairlearn bias audit
- [ ] HITL override workflow + active learning loop
- [ ] React dashboard (heatmap + SHAP chart)
- [ ] Kubernetes YAML (even if running on minikube)

### Layer 3 (Full showcase — complete when time allows)
- [ ] LangChain ReAct agent + RAG pipeline + RAGAS evaluation
- [ ] Slack integration
- [ ] Full K8s deployment
- [ ] SYSTEM_DESIGN.md + all 5 ADRs
- [ ] Demo video + portfolio site

---

*This document serves as both the project specification for building TalentLens and a skills file for Claude to understand Anshita's project context when helping with future related tasks.*

*Last updated: April 2026 | Version: 2.0 — Major revision: removed NVIDIA scope, added PySpark layer, replaced IBM dataset with synthetic-first strategy, added HITL active learning mechanics, added MVP tier structure, added dataset licensing clarity, added Spark ADR-005.*
