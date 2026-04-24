-- TalentLens Database Initialization
-- Creates: talentlens DB, users, and all schemas/tables
-- Run via: psql -U postgres -f init_schema.sql
-- In Docker: mounted as /docker-entrypoint-initdb.d/01_init_schema.sql

-- ─────────────────────────────────────────────────────────────────────────────
-- Database and user
-- ─────────────────────────────────────────────────────────────────────────────
SELECT 'CREATE DATABASE talentlens' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'talentlens') \gexec
SELECT 'CREATE DATABASE airflow'    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'airflow') \gexec

\c talentlens

DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'talentlens') THEN
    CREATE ROLE talentlens LOGIN PASSWORD 'talentlens';
  END IF;
END $$;

GRANT ALL PRIVILEGES ON DATABASE talentlens TO talentlens;

-- ─────────────────────────────────────────────────────────────────────────────
-- Schema creation
-- ─────────────────────────────────────────────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS mart;
CREATE SCHEMA IF NOT EXISTS audit;

GRANT USAGE ON SCHEMA raw, staging, mart, audit TO talentlens;
ALTER DEFAULT PRIVILEGES IN SCHEMA raw, staging, mart, audit
  GRANT ALL ON TABLES TO talentlens;

-- ─────────────────────────────────────────────────────────────────────────────
-- RAW SCHEMA — exact copies of source data, never modified
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS raw.hris_employee_snapshot (
    employee_id                 UUID        PRIMARY KEY,
    first_name                  TEXT        NOT NULL,
    last_name                   TEXT        NOT NULL,
    email                       TEXT        NOT NULL,
    department                  TEXT        NOT NULL,
    job_level                   TEXT        NOT NULL,
    job_role                    TEXT        NOT NULL,
    hire_date                   DATE        NOT NULL,
    termination_date            DATE,
    is_active                   BOOLEAN     NOT NULL DEFAULT TRUE,
    monthly_income              NUMERIC(10,2) NOT NULL,
    job_satisfaction            SMALLINT    CHECK (job_satisfaction BETWEEN 1 AND 4),
    environment_satisfaction    SMALLINT    CHECK (environment_satisfaction BETWEEN 1 AND 4),
    work_life_balance           SMALLINT    CHECK (work_life_balance BETWEEN 1 AND 4),
    performance_rating          SMALLINT    CHECK (performance_rating BETWEEN 1 AND 4),
    years_since_last_promotion  NUMERIC(5,2),
    years_with_current_manager  NUMERIC(5,2),
    years_at_company            NUMERIC(5,2),
    distance_from_home          SMALLINT,
    num_companies_worked        SMALLINT,
    training_times_last_year    SMALLINT,
    overtime_flag               BOOLEAN     NOT NULL DEFAULT FALSE,
    education                   SMALLINT    CHECK (education BETWEEN 1 AND 5),
    education_field             TEXT,
    marital_status              TEXT        CHECK (marital_status IN ('Single', 'Married', 'Divorced')),
    gender                      TEXT        CHECK (gender IN ('Male', 'Female', 'Non-binary')),
    age                         SMALLINT,
    age_band                    TEXT,
    manager_id                  UUID,
    _ingested_at                TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_raw_employee_dept     ON raw.hris_employee_snapshot(department);
CREATE INDEX IF NOT EXISTS idx_raw_employee_active   ON raw.hris_employee_snapshot(is_active);
CREATE INDEX IF NOT EXISTS idx_raw_employee_manager  ON raw.hris_employee_snapshot(manager_id);

-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS raw.employee_events (
    event_id        UUID        PRIMARY KEY,
    employee_id     UUID        NOT NULL,
    event_type      TEXT        NOT NULL,
    event_date      DATE        NOT NULL,
    department      TEXT,
    payload         JSONB,
    _ingested_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_raw_events_employee  ON raw.employee_events(employee_id);
CREATE INDEX IF NOT EXISTS idx_raw_events_type      ON raw.employee_events(event_type);
CREATE INDEX IF NOT EXISTS idx_raw_events_date      ON raw.employee_events(event_date);

-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS raw.hiring_funnel_events (
    event_id        UUID        PRIMARY KEY,
    candidate_id    UUID        NOT NULL,
    stage           TEXT        NOT NULL,
    event_date      DATE        NOT NULL,
    department      TEXT,
    payload         JSONB,
    _ingested_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_raw_funnel_candidate ON raw.hiring_funnel_events(candidate_id);
CREATE INDEX IF NOT EXISTS idx_raw_funnel_stage     ON raw.hiring_funnel_events(stage);

-- ─────────────────────────────────────────────────────────────────────────────
-- STAGING SCHEMA — cleaned, typed, deduplicated
-- (These are populated by dbt; DDL mirrors dbt output for raw queries)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS staging.stg_employees (
    employee_id                 UUID        PRIMARY KEY,
    first_name                  TEXT        NOT NULL,
    last_name                   TEXT        NOT NULL,
    full_name                   TEXT        GENERATED ALWAYS AS (first_name || ' ' || last_name) STORED,
    email                       TEXT        NOT NULL,
    department                  TEXT        NOT NULL,
    job_level                   TEXT        NOT NULL,
    job_level_type              TEXT        GENERATED ALWAYS AS (
                                    CASE WHEN job_level LIKE 'IC%' THEN 'individual_contributor'
                                         WHEN job_level LIKE 'M%'  THEN 'manager'
                                         ELSE 'unknown' END
                                ) STORED,
    job_role                    TEXT        NOT NULL,
    hire_date                   DATE        NOT NULL,
    termination_date            DATE,
    is_active                   BOOLEAN     NOT NULL DEFAULT TRUE,
    monthly_income              NUMERIC(10,2) NOT NULL,
    annual_income               NUMERIC(12,2) GENERATED ALWAYS AS (monthly_income * 12) STORED,
    job_satisfaction            SMALLINT,
    environment_satisfaction    SMALLINT,
    work_life_balance           SMALLINT,
    performance_rating          SMALLINT,
    avg_satisfaction            NUMERIC(4,2),
    years_since_last_promotion  NUMERIC(5,2),
    years_with_current_manager  NUMERIC(5,2),
    years_at_company            NUMERIC(5,2),
    distance_from_home          SMALLINT,
    num_companies_worked        SMALLINT,
    training_times_last_year    SMALLINT,
    overtime_flag               BOOLEAN,
    education                   SMALLINT,
    education_field             TEXT,
    marital_status              TEXT,
    gender                      TEXT,
    age                         SMALLINT,
    age_band                    TEXT,
    manager_id                  UUID,
    _loaded_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS staging.stg_hiring_events (
    event_id        UUID        PRIMARY KEY,
    candidate_id    UUID        NOT NULL,
    stage           TEXT        NOT NULL,
    stage_order     SMALLINT    GENERATED ALWAYS AS (
                        CASE stage
                            WHEN 'APPLICATION'  THEN 1
                            WHEN 'PHONE_SCREEN' THEN 2
                            WHEN 'INTERVIEW'    THEN 3
                            WHEN 'OFFER'        THEN 4
                            WHEN 'HIRE'         THEN 5
                            WHEN 'REJECT'       THEN 5
                            ELSE 0
                        END
                    ) STORED,
    event_date      DATE        NOT NULL,
    department      TEXT,
    passed          BOOLEAN,
    offered_salary  NUMERIC(10,2),
    _loaded_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS staging.stg_risk_scores (
    score_id        UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id     UUID        NOT NULL,
    scored_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    flight_risk_prob NUMERIC(5,4) CHECK (flight_risk_prob BETWEEN 0 AND 1),
    anomaly_score   NUMERIC(8,4),
    compliance_flag BOOLEAN     NOT NULL DEFAULT FALSE,
    risk_index      NUMERIC(5,2) CHECK (risk_index BETWEEN 0 AND 100),
    risk_band       TEXT        GENERATED ALWAYS AS (
                        CASE
                            WHEN risk_index <= 25 THEN 'Low'
                            WHEN risk_index <= 50 THEN 'Medium'
                            WHEN risk_index <= 75 THEN 'High'
                            ELSE 'Critical'
                        END
                    ) STORED,
    model_version   TEXT,
    _loaded_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stg_scores_employee ON staging.stg_risk_scores(employee_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- MART SCHEMA — business-facing, query-optimized
-- ─────────────────────────────────────────────────────────────────────────────

-- SCD Type 2 employee dimension
CREATE TABLE IF NOT EXISTS mart.dim_employee (
    dim_employee_id             BIGSERIAL   PRIMARY KEY,
    employee_id                 UUID        NOT NULL,
    first_name                  TEXT        NOT NULL,
    last_name                   TEXT        NOT NULL,
    full_name                   TEXT        NOT NULL,
    email                       TEXT        NOT NULL,
    department                  TEXT        NOT NULL,
    job_level                   TEXT        NOT NULL,
    job_level_type              TEXT        NOT NULL,
    job_role                    TEXT        NOT NULL,
    hire_date                   DATE        NOT NULL,
    termination_date            DATE,
    is_active                   BOOLEAN     NOT NULL,
    monthly_income              NUMERIC(10,2),
    annual_income               NUMERIC(12,2),
    job_satisfaction            SMALLINT,
    environment_satisfaction    SMALLINT,
    work_life_balance           SMALLINT,
    performance_rating          SMALLINT,
    avg_satisfaction            NUMERIC(4,2),
    years_since_last_promotion  NUMERIC(5,2),
    years_with_current_manager  NUMERIC(5,2),
    years_at_company            NUMERIC(5,2),
    distance_from_home          SMALLINT,
    num_companies_worked        SMALLINT,
    training_times_last_year    SMALLINT,
    overtime_flag               BOOLEAN,
    education                   SMALLINT,
    education_field             TEXT,
    marital_status              TEXT,
    gender                      TEXT,
    age                         SMALLINT,
    age_band                    TEXT,
    manager_id                  UUID,
    -- SCD Type 2 fields
    dbt_scd_id                  TEXT,
    dbt_updated_at              TIMESTAMPTZ,
    dbt_valid_from              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    dbt_valid_to                TIMESTAMPTZ,
    dbt_is_current_record       BOOLEAN     NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_dim_employee_id      ON mart.dim_employee(employee_id);
CREATE INDEX IF NOT EXISTS idx_dim_employee_dept    ON mart.dim_employee(department);
CREATE INDEX IF NOT EXISTS idx_dim_employee_active  ON mart.dim_employee(is_active);
CREATE INDEX IF NOT EXISTS idx_dim_employee_current ON mart.dim_employee(dbt_is_current_record);

-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS mart.fact_risk_scores (
    score_id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id         UUID        NOT NULL,
    scoring_run_id      UUID,
    scored_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    flight_risk_prob    NUMERIC(5,4),
    anomaly_score       NUMERIC(8,4),
    compliance_flag     BOOLEAN     NOT NULL DEFAULT FALSE,
    risk_index          NUMERIC(5,2),
    risk_band           TEXT,
    shap_top_feature_1  TEXT,
    shap_top_feature_2  TEXT,
    shap_top_feature_3  TEXT,
    shap_value_1        NUMERIC(8,4),
    shap_value_2        NUMERIC(8,4),
    shap_value_3        NUMERIC(8,4),
    model_version       TEXT,
    model_id            UUID,
    _loaded_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fact_scores_employee  ON mart.fact_risk_scores(employee_id);
CREATE INDEX IF NOT EXISTS idx_fact_scores_scored_at ON mart.fact_risk_scores(scored_at);
CREATE INDEX IF NOT EXISTS idx_fact_scores_band      ON mart.fact_risk_scores(risk_band);

-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS mart.fact_hiring_funnel (
    funnel_id           BIGSERIAL   PRIMARY KEY,
    candidate_id        UUID        NOT NULL,
    department          TEXT,
    application_date    DATE,
    screen_date         DATE,
    interview_date      DATE,
    offer_date          DATE,
    outcome             TEXT        CHECK (outcome IN ('hired', 'rejected', 'in_progress', 'withdrawn')),
    offered_salary      NUMERIC(10,2),
    days_to_screen      SMALLINT,
    days_to_interview   SMALLINT,
    days_to_offer       SMALLINT,
    days_to_close       SMALLINT,
    _loaded_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fact_funnel_dept    ON mart.fact_hiring_funnel(department);
CREATE INDEX IF NOT EXISTS idx_fact_funnel_outcome ON mart.fact_hiring_funnel(outcome);

-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS mart.mart_risk_index (
    employee_id         UUID        PRIMARY KEY,
    full_name           TEXT,
    department          TEXT,
    job_level           TEXT,
    latest_risk_index   NUMERIC(5,2),
    latest_risk_band    TEXT,
    prev_risk_index     NUMERIC(5,2),
    risk_delta          NUMERIC(5,2),
    is_spike            BOOLEAN GENERATED ALWAYS AS (
                            latest_risk_index > 85 AND (prev_risk_index IS NULL OR prev_risk_index < 75)
                        ) STORED,
    flight_risk_prob    NUMERIC(5,4),
    anomaly_score       NUMERIC(8,4),
    shap_top_feature_1  TEXT,
    shap_top_feature_2  TEXT,
    shap_top_feature_3  TEXT,
    last_scored_at      TIMESTAMPTZ,
    _updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mart_risk_dept  ON mart.mart_risk_index(department);
CREATE INDEX IF NOT EXISTS idx_mart_risk_band  ON mart.mart_risk_index(latest_risk_band);
CREATE INDEX IF NOT EXISTS idx_mart_risk_spike ON mart.mart_risk_index(is_spike);

-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS mart.feature_store (
    employee_id                     UUID        PRIMARY KEY,
    computed_at                     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- PySpark rolling aggregation features
    manager_changes_30d             SMALLINT    DEFAULT 0,
    manager_changes_90d             SMALLINT    DEFAULT 0,
    absence_rate_90d                NUMERIC(5,4) DEFAULT 0,
    overtime_rate_180d              NUMERIC(5,4) DEFAULT 0,
    -- PySpark peer-group features
    monthly_income_vs_peer_median   NUMERIC(5,4),   -- percent_rank within job_level+dept
    income_peer_percentile          SMALLINT,        -- quartile (1-4)
    -- Performance trend features
    performance_rating_delta        NUMERIC(5,2),    -- change from 6-month rolling avg
    training_count_90d              SMALLINT    DEFAULT 0
);

-- ─────────────────────────────────────────────────────────────────────────────
-- AUDIT SCHEMA — immutable, append-only
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS audit.model_decisions (
    decision_id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id         UUID        NOT NULL,
    model_id            UUID,
    model_version       TEXT,
    decision_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    input_features      JSONB,
    flight_risk_prob    NUMERIC(5,4),
    anomaly_score       NUMERIC(8,4),
    risk_index          NUMERIC(5,2),
    risk_band           TEXT,
    kafka_message_id    TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_decisions_employee ON audit.model_decisions(employee_id);
CREATE INDEX IF NOT EXISTS idx_audit_decisions_at       ON audit.model_decisions(decision_at);

-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS audit.hitl_overrides (
    override_id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id         UUID        NOT NULL,
    reviewer_id         TEXT        NOT NULL,
    original_risk_index NUMERIC(5,2),
    override_label      SMALLINT    CHECK (override_label IN (0, 1)),
    reason              TEXT        NOT NULL,
    notes               TEXT,
    override_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decision_id         UUID        REFERENCES audit.model_decisions(decision_id)
);

CREATE INDEX IF NOT EXISTS idx_audit_overrides_employee ON audit.hitl_overrides(employee_id);
CREATE INDEX IF NOT EXISTS idx_audit_overrides_at       ON audit.hitl_overrides(override_at);

-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS audit.active_learning_labels (
    label_id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id         UUID        NOT NULL,
    feature_snapshot    JSONB,
    corrected_label     SMALLINT    NOT NULL CHECK (corrected_label IN (0, 1)),
    confidence          TEXT        NOT NULL DEFAULT 'human_verified',
    labeled_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    override_id         UUID        REFERENCES audit.hitl_overrides(override_id),
    used_in_training    BOOLEAN     NOT NULL DEFAULT FALSE,
    training_run_id     TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_labels_trained ON audit.active_learning_labels(used_in_training);

-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS audit.drift_reports (
    report_id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_date            DATE        NOT NULL,
    model_version       TEXT,
    psi_score           NUMERIC(8,4),
    psi_status          TEXT        GENERATED ALWAYS AS (
                            CASE
                                WHEN psi_score < 0.1  THEN 'stable'
                                WHEN psi_score < 0.2  THEN 'monitor'
                                ELSE 'retrain'
                            END
                        ) STORED,
    feature_psi_detail  JSONB,
    retrain_triggered   BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS audit.llm_costs (
    cost_id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    provider            TEXT        NOT NULL,
    model               TEXT        NOT NULL,
    endpoint            TEXT,
    input_tokens        INTEGER,
    output_tokens       INTEGER,
    estimated_cost_usd  NUMERIC(10,6),
    request_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    session_id          TEXT
);
