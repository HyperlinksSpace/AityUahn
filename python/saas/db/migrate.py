"""Neon Postgres migrations for cloud SaaS."""

from __future__ import annotations

import os
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Create a Neon project and add the connection string "
            "to Vercel Environment Variables (use the pooled connection string for serverless)."
        )
    return url


def run_migrations() -> None:
    import psycopg

    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with psycopg.connect(database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
