"""Neon migration smoke test (skipped without DATABASE_URL)."""

import os

import pytest


@pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")
def test_neon_migrations_idempotent():
    from python.saas.db.migrate import run_migrations

    run_migrations()
    run_migrations()
