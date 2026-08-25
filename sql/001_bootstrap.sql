BEGIN;
CREATE SCHEMA IF NOT EXISTS cloudiff_v2;
CREATE TABLE IF NOT EXISTS cloudiff_v2.schema_meta (
    version integer PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO cloudiff_v2.schema_meta(version) VALUES (1) ON CONFLICT (version) DO NOTHING;

CREATE TABLE IF NOT EXISTS cloudiff_v2.nodes (
    node_id uuid PRIMARY KEY,
    hostname text NOT NULL,
    role text NOT NULL CHECK (role IN ('control','forja','edge','other')),
    capabilities text[] NOT NULL DEFAULT '{}',
    certificate_fingerprint text,
    observed_at timestamptz NOT NULL,
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE TABLE IF NOT EXISTS cloudiff_v2.projects (
    project_id uuid PRIMARY KEY,
    slug text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS cloudiff_v2.jobs (
    job_id uuid PRIMARY KEY,
    kind text NOT NULL,
    status text NOT NULL CHECK (status IN ('ready','leased','waiting_retry','succeeded','failed','dead_letter','cancelled')),
    partition_key text NOT NULL,
    idempotency_key text NOT NULL UNIQUE,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    result jsonb,
    attempt integer NOT NULL DEFAULT 0 CHECK (attempt >= 0),
    max_attempts integer NOT NULL DEFAULT 5 CHECK (max_attempts >= 1),
    lease_owner text,
    lease_expires_at timestamptz,
    ready_at timestamptz NOT NULL DEFAULT now(),
    retry_at timestamptz,
    trace_id text,
    last_error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS jobs_claim_idx ON cloudiff_v2.jobs(status, ready_at, retry_at, created_at);
CREATE INDEX IF NOT EXISTS jobs_partition_idx ON cloudiff_v2.jobs(partition_key, status);
CREATE TABLE IF NOT EXISTS cloudiff_v2.job_attempts (
    job_id uuid NOT NULL REFERENCES cloudiff_v2.jobs(job_id) ON DELETE CASCADE,
    attempt integer NOT NULL,
    worker_id text NOT NULL,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    outcome text,
    error text,
    PRIMARY KEY(job_id, attempt)
);
CREATE TABLE IF NOT EXISTS cloudiff_v2.desired_state (
    resource_type text NOT NULL,
    resource_id text NOT NULL,
    revision bigint NOT NULL CHECK (revision >= 0),
    state jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(resource_type, resource_id)
);
CREATE TABLE IF NOT EXISTS cloudiff_v2.observed_state (
    resource_type text NOT NULL,
    resource_id text NOT NULL,
    revision bigint NOT NULL CHECK (revision >= 0),
    state jsonb NOT NULL,
    observed_at timestamptz NOT NULL,
    node_id uuid REFERENCES cloudiff_v2.nodes(node_id),
    PRIMARY KEY(resource_type, resource_id)
);
CREATE TABLE IF NOT EXISTS cloudiff_v2.events (
    event_id uuid PRIMARY KEY,
    event_type text NOT NULL,
    occurred_at timestamptz NOT NULL,
    producer text NOT NULL,
    resource_id text NOT NULL,
    trace_id text NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS events_resource_idx ON cloudiff_v2.events(resource_id, occurred_at DESC);
CREATE TABLE IF NOT EXISTS cloudiff_v2.audit_log (
    audit_id bigserial PRIMARY KEY,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    actor text NOT NULL,
    action text NOT NULL,
    resource_type text NOT NULL,
    resource_id text NOT NULL,
    trace_id text,
    details jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE TABLE IF NOT EXISTS cloudiff_v2.agent_credentials (
    node_id uuid PRIMARY KEY REFERENCES cloudiff_v2.nodes(node_id) ON DELETE CASCADE,
    token_hash text NOT NULL,
    certificate_fingerprint text,
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','rotating','revoked')),
    created_at timestamptz NOT NULL DEFAULT now(),
    rotated_at timestamptz
);
CREATE OR REPLACE FUNCTION cloudiff_v2.claim_jobs(p_worker text, p_limit integer, p_lease_seconds integer)
RETURNS SETOF cloudiff_v2.jobs
LANGUAGE sql
AS $$
    WITH candidates AS (
        SELECT job_id
        FROM cloudiff_v2.jobs
        WHERE (status = 'ready' AND ready_at <= now())
           OR (status = 'waiting_retry' AND retry_at IS NOT NULL AND retry_at <= now())
           OR (status = 'leased' AND lease_expires_at IS NOT NULL AND lease_expires_at <= now())
        ORDER BY created_at
        FOR UPDATE SKIP LOCKED
        LIMIT GREATEST(p_limit, 0)
    ), claimed AS (
        UPDATE cloudiff_v2.jobs j
        SET status='leased', lease_owner=p_worker,
            lease_expires_at=now() + make_interval(secs => GREATEST(p_lease_seconds, 1)),
            attempt=j.attempt+1, updated_at=now()
        FROM candidates c
        WHERE j.job_id=c.job_id
        RETURNING j.*
    ) SELECT * FROM claimed;
$$;
COMMIT;
