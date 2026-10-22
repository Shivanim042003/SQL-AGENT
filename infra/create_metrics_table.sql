-- Per-request metrics written by app/metrics/repository.py (owner connection).
CREATE TABLE IF NOT EXISTS agent_request_metrics (
    id              BIGSERIAL PRIMARY KEY,
    request_id      TEXT NOT NULL,
    retry_count     INTEGER NOT NULL DEFAULT 0,
    error_type      TEXT,
    total_latency   DOUBLE PRECISION,
    success         BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    latencies       JSONB NOT NULL DEFAULT '{}'::jsonb,
    retry_latencies JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_agent_request_metrics_created_at
ON agent_request_metrics (created_at DESC);
