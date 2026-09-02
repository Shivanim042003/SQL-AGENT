CREATE INDEX IF NOT EXISTS idx_events_session_id
ON events (session_id);

CREATE INDEX IF NOT EXISTS idx_events_event_type
ON events (event_type);