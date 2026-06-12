"""Postgres-backed SaaS store for Vercel + Neon (serverless-safe)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from python.saas.models import PaymentStatus, ProjectMember, TeamProject, TonPayment, User
from python.saas.store import SaaSStore


def _parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


class PostgresSaaSStore(SaaSStore):
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self.data_dir = Path("/tmp/aityuahn-saas-unused")

    def _connect(self):
        return psycopg.connect(self.dsn, row_factory=dict_row)

    def list_users(self) -> list[User]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, name, password_hash, plan, created_at FROM saas_users ORDER BY created_at"
            )
            rows = cur.fetchall()
        return [
            User(
                id=r["id"],
                email=r["email"],
                name=r["name"],
                password_hash=r["password_hash"],
                plan=r["plan"],
                created_at=_parse_dt(r["created_at"]),
            )
            for r in rows
        ]

    def save_users(self, users: list[User]) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM saas_users")
            for u in users:
                cur.execute(
                    """
                    INSERT INTO saas_users (id, email, name, password_hash, plan, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (u.id, u.email, u.name, u.password_hash, u.plan.value, u.created_at),
                )
            conn.commit()

    def list_projects(self) -> list[TeamProject]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, slug, name, owner_id, forge_slug, description, is_demo, api_config, created_at
                FROM saas_projects ORDER BY created_at
                """
            )
            rows = cur.fetchall()
        return [
            TeamProject(
                id=r["id"],
                slug=r["slug"],
                name=r["name"],
                owner_id=r["owner_id"],
                forge_slug=r["forge_slug"],
                description=r["description"] or "",
                is_demo=bool(r["is_demo"]),
                api_config=r["api_config"] if isinstance(r["api_config"], dict) else json.loads(r["api_config"] or "{}"),
                created_at=_parse_dt(r["created_at"]),
            )
            for r in rows
        ]

    def save_projects(self, projects: list[TeamProject]) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM saas_projects")
            for p in projects:
                cur.execute(
                    """
                    INSERT INTO saas_projects
                      (id, slug, name, owner_id, forge_slug, description, is_demo, api_config, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                    """,
                    (
                        p.id,
                        p.slug,
                        p.name,
                        p.owner_id,
                        p.forge_slug,
                        p.description,
                        p.is_demo,
                        json.dumps(p.api_config),
                        p.created_at,
                    ),
                )
            conn.commit()

    def list_members(self) -> list[ProjectMember]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT project_id, user_id, role, joined_at FROM saas_members ORDER BY joined_at"
            )
            rows = cur.fetchall()
        return [
            ProjectMember(
                project_id=r["project_id"],
                user_id=r["user_id"],
                role=r["role"],
                joined_at=_parse_dt(r["joined_at"]),
            )
            for r in rows
        ]

    def save_members(self, members: list[ProjectMember]) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM saas_members")
            for m in members:
                cur.execute(
                    """
                    INSERT INTO saas_members (project_id, user_id, role, joined_at)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (m.project_id, m.user_id, m.role.value, m.joined_at),
                )
            conn.commit()

    def _load_payments_doc(self) -> dict:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT id, user_id, amount_nano, wallet_address, status, sender_address, ton_tx_ref, created_at, completed_at FROM saas_payments")
            payment_rows = cur.fetchall()
            cur.execute("SELECT value FROM saas_meta WHERE key = 'last_poll_utime'")
            meta = cur.fetchone()
        last_poll = 0
        if meta and meta["value"] is not None:
            val = meta["value"]
            last_poll = int(val) if isinstance(val, int) else int(json.loads(val) if isinstance(val, str) else val)
        payments = []
        for r in payment_rows:
            payments.append(
                {
                    "id": r["id"],
                    "user_id": r["user_id"],
                    "amount_nano": int(r["amount_nano"]),
                    "wallet_address": r["wallet_address"],
                    "status": r["status"],
                    "sender_address": r["sender_address"],
                    "ton_tx_ref": r["ton_tx_ref"],
                    "created_at": _parse_dt(r["created_at"]).isoformat(),
                    "completed_at": _parse_dt(r["completed_at"]).isoformat() if r["completed_at"] else None,
                }
            )
        return {"last_poll_utime": last_poll, "payments": payments}

    def _save_payments_doc(self, doc: dict) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM saas_payments")
            for row in doc.get("payments", []):
                payment = TonPayment.model_validate(row)
                cur.execute(
                    """
                    INSERT INTO saas_payments
                      (id, user_id, amount_nano, wallet_address, status, sender_address, ton_tx_ref, created_at, completed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        payment.id,
                        payment.user_id,
                        payment.amount_nano,
                        payment.wallet_address,
                        payment.status.value,
                        payment.sender_address,
                        payment.ton_tx_ref,
                        payment.created_at,
                        payment.completed_at,
                    ),
                )
            cur.execute(
                """
                INSERT INTO saas_meta (key, value) VALUES ('last_poll_utime', %s::jsonb)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                """,
                (json.dumps(int(doc.get("last_poll_utime") or 0)),),
            )
            conn.commit()

    def save_payment(self, payment: TonPayment) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO saas_payments
                  (id, user_id, amount_nano, wallet_address, status, sender_address, ton_tx_ref, created_at, completed_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                  status = EXCLUDED.status,
                  sender_address = EXCLUDED.sender_address,
                  ton_tx_ref = EXCLUDED.ton_tx_ref,
                  completed_at = EXCLUDED.completed_at
                """,
                (
                    payment.id,
                    payment.user_id,
                    payment.amount_nano,
                    payment.wallet_address,
                    payment.status.value,
                    payment.sender_address,
                    payment.ton_tx_ref,
                    payment.created_at,
                    payment.completed_at,
                ),
            )
            conn.commit()

    def complete_payment(self, payment_id: str, tx_ref: str, sender: str) -> TonPayment | None:
        payment = self.get_payment(payment_id)
        if not payment or payment.status != PaymentStatus.PENDING:
            return payment
        from python.saas.models import utc_now

        updated = payment.model_copy(
            update={
                "status": PaymentStatus.COMPLETED,
                "ton_tx_ref": tx_ref,
                "sender_address": sender,
                "completed_at": utc_now(),
            }
        )
        self.save_payment(updated)
        return updated

    def set_last_poll_utime(self, utime: int) -> None:
        current = self.last_poll_utime()
        value = max(current, int(utime))
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO saas_meta (key, value) VALUES ('last_poll_utime', %s::jsonb)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                """,
                (json.dumps(value),),
            )
            conn.commit()
