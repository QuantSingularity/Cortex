-- Cortex MLOps Backbone – Database Initialization
-- Run automatically on first postgres startup

-- ─── Feature Store ────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS feature_groups (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(128) UNIQUE NOT NULL,
    description TEXT,
    tags        JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS feature_definitions (
    id              SERIAL PRIMARY KEY,
    feature_group   VARCHAR(128) NOT NULL REFERENCES feature_groups(name) ON DELETE CASCADE,
    name            VARCHAR(128) NOT NULL,
    dtype           VARCHAR(64)  NOT NULL,  -- float, int, string, bool
    description     TEXT,
    default_value   TEXT,
    tags            JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (feature_group, name)
);

CREATE TABLE IF NOT EXISTS feature_values (
    id              BIGSERIAL PRIMARY KEY,
    feature_group   VARCHAR(128) NOT NULL,
    entity_id       VARCHAR(256) NOT NULL,
    feature_name    VARCHAR(128) NOT NULL,
    feature_value   TEXT,
    event_timestamp TIMESTAMPTZ  NOT NULL,
    created_at      TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fv_entity_group ON feature_values (feature_group, entity_id);
CREATE INDEX IF NOT EXISTS idx_fv_timestamp    ON feature_values (event_timestamp DESC);

-- ─── Model Registry ───────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS registered_models (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(128) UNIQUE NOT NULL,
    description TEXT,
    tags        JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS model_versions (
    id              SERIAL PRIMARY KEY,
    model_name      VARCHAR(128) NOT NULL REFERENCES registered_models(name) ON DELETE CASCADE,
    version         VARCHAR(64)  NOT NULL,
    stage           VARCHAR(32)  NOT NULL DEFAULT 'staging',  -- staging, production, archived
    artifact_uri    TEXT         NOT NULL,
    framework       VARCHAR(64),
    python_version  VARCHAR(16),
    description     TEXT,
    tags            JSONB DEFAULT '{}',
    metrics         JSONB DEFAULT '{}',
    params          JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (model_name, version)
);

CREATE TABLE IF NOT EXISTS model_metrics_history (
    id          BIGSERIAL PRIMARY KEY,
    model_name  VARCHAR(128) NOT NULL,
    version     VARCHAR(64)  NOT NULL,
    metric_name VARCHAR(128) NOT NULL,
    metric_value FLOAT       NOT NULL,
    step        INT          DEFAULT 0,
    timestamp   TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_metrics_model ON model_metrics_history (model_name, version);

-- ─── Drift Detection ──────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS drift_reports (
    id              BIGSERIAL PRIMARY KEY,
    model_name      VARCHAR(128) NOT NULL,
    version         VARCHAR(64)  NOT NULL,
    feature_name    VARCHAR(128) NOT NULL,
    test_type       VARCHAR(32)  NOT NULL,  -- ks, psi
    statistic       FLOAT        NOT NULL,
    p_value         FLOAT,
    psi_score       FLOAT,
    drift_detected  BOOLEAN      NOT NULL DEFAULT FALSE,
    threshold       FLOAT        NOT NULL,
    sample_size     INT,
    reported_at     TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_drift_model ON drift_reports (model_name, version, reported_at DESC);

-- ─── Scheduler / Retraining Jobs ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS retraining_jobs (
    id              BIGSERIAL PRIMARY KEY,
    model_name      VARCHAR(128) NOT NULL,
    trigger_type    VARCHAR(32)  NOT NULL,  -- scheduled, drift, manual
    status          VARCHAR(32)  NOT NULL DEFAULT 'pending', -- pending, running, success, failed
    triggered_at    TIMESTAMPTZ  DEFAULT NOW(),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    error_message   TEXT,
    metadata        JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_jobs_model ON retraining_jobs (model_name, triggered_at DESC);
