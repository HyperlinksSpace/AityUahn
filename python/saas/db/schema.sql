-- AityUahn cloud SaaS schema (Neon Postgres)
-- Applied automatically on Vercel deploy via scripts/migrate_db.py

CREATE TABLE IF NOT EXISTS saas_users (
    id              TEXT PRIMARY KEY,
    email           TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    password_hash   TEXT NOT NULL,
    plan            TEXT NOT NULL CHECK (plan IN ('personal', 'team')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_saas_users_email ON saas_users (email);

CREATE TABLE IF NOT EXISTS saas_projects (
    id              TEXT PRIMARY KEY,
    slug            TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    owner_id        TEXT NOT NULL REFERENCES saas_users(id) ON DELETE CASCADE,
    forge_slug      TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    is_demo         BOOLEAN NOT NULL DEFAULT FALSE,
    api_config      JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_saas_projects_owner ON saas_projects (owner_id);

CREATE TABLE IF NOT EXISTS saas_members (
    project_id      TEXT NOT NULL REFERENCES saas_projects(id) ON DELETE CASCADE,
    user_id         TEXT NOT NULL REFERENCES saas_users(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('owner', 'admin', 'member')),
    joined_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (project_id, user_id)
);

CREATE TABLE IF NOT EXISTS saas_payments (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES saas_users(id) ON DELETE CASCADE,
    amount_nano     BIGINT NOT NULL,
    wallet_address  TEXT NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('pending', 'completed', 'expired')),
    sender_address  TEXT,
    ton_tx_ref      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_saas_payments_user_status
    ON saas_payments (user_id, status);

CREATE TABLE IF NOT EXISTS saas_meta (
    key             TEXT PRIMARY KEY,
    value           JSONB NOT NULL
);

INSERT INTO saas_meta (key, value)
VALUES ('last_poll_utime', '0'::jsonb)
ON CONFLICT (key) DO NOTHING;
