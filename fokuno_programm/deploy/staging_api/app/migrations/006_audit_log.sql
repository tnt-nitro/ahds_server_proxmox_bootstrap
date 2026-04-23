CREATE TABLE IF NOT EXISTS audit_log (
  id BIGSERIAL PRIMARY KEY,
  event TEXT NOT NULL,
  ok BOOLEAN NOT NULL,
  user_id BIGINT NULL REFERENCES users(id) ON DELETE SET NULL,
  email TEXT NULL,
  detail TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_event ON audit_log(event);
