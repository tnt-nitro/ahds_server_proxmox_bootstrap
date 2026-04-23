ALTER TABLE users
  ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'user';

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS password_salt TEXT;

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS password_hash TEXT;

CREATE INDEX IF NOT EXISTS idx_users_email_lower ON users ((lower(email)));
