"""TON deposit listener — follows toncenter/examples deposits.js pattern."""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import urllib.parse
import uuid
from typing import Any

import httpx

from python.saas.models import PaymentStatus, Plan, TonPayment
from python.saas.settings import poll_interval_sec, team_price_nano, team_price_ton, ton_network, ton_wallet_address

logger = logging.getLogger(__name__)


def wallet_address() -> str | None:
    return ton_wallet_address()


def toncenter_api_key() -> str | None:
    key = os.environ.get("AITYUAHN_TONCENTER_API_KEY", "").strip()
    return key or None


def is_mainnet() -> bool:
    return ton_network() != "testnet"


def toncenter_base_url() -> str:
    if is_mainnet():
        return "https://toncenter.com/api/v2"
    return "https://testnet.toncenter.com/api/v2"


def wallet_configured() -> bool:
    return wallet_address() is not None


def payment_deeplink(address: str, amount_nano: int, comment: str) -> str:
    query = urllib.parse.urlencode({"amount": amount_nano, "text": comment})
    return f"ton://transfer/{address}?{query}"


def extract_text_comment(in_msg: dict[str, Any]) -> str | None:
    msg_data = in_msg.get("msg_data") or {}
    if msg_data.get("@type") != "msg.dataText":
        return None
    message = in_msg.get("message")
    if message:
        return str(message).strip()
    text_b64 = msg_data.get("text")
    if not text_b64:
        return None
    try:
        return base64.b64decode(text_b64).decode("utf-8", errors="replace").strip()
    except Exception:
        return None


def is_incoming_deposit(tx: dict[str, Any]) -> bool:
    in_msg = tx.get("in_msg") or {}
    if not in_msg.get("source"):
        return False
    if tx.get("out_msgs"):
        return False
    return extract_text_comment(in_msg) is not None


class TonPaymentService:
    """Poll wallet transactions and match UUID text comments to pending payments."""

    def __init__(self, store: Any) -> None:
        self.store = store
        self._poll_task: asyncio.Task | None = None

    def create_team_payment(self, user_id: str) -> TonPayment:
        if not wallet_configured():
            raise ValueError("TON wallet not configured (set ton_wallet_address in saas.yaml or AITYUAHN_TON_WALLET_ADDRESS in .env)")
        existing = self.store.find_pending_payment(user_id)
        if existing:
            return existing
        amount = team_price_nano()
        payment = TonPayment(
            id=str(uuid.uuid4()),
            user_id=user_id,
            amount_nano=amount,
            wallet_address=wallet_address() or "",
            status=PaymentStatus.PENDING,
        )
        self.store.save_payment(payment)
        return payment

    def payment_payload(self, payment: TonPayment) -> dict[str, Any]:
        addr = payment.wallet_address or wallet_address() or ""
        price = team_price_ton()
        return {
            "payment_id": payment.id,
            "status": payment.status.value,
            "amount_ton": price,
            "amount_nano": payment.amount_nano,
            "wallet_address": addr,
            "comment": payment.id,
            "deeplink": payment_deeplink(addr, payment.amount_nano, payment.id),
            "instructions": (
                f"Send exactly {price:g} TON to the wallet address with the payment ID "
                "as the transfer comment (memo). Do not change the comment text."
            ),
            "created_at": payment.created_at.isoformat(),
            "completed_at": payment.completed_at.isoformat() if payment.completed_at else None,
        }

    async def fetch_transactions(
        self,
        limit: int = 20,
        lt: int | None = None,
        tx_hash: str | None = None,
    ) -> list[dict[str, Any]]:
        address = wallet_address()
        if not address:
            return []
        params: dict[str, Any] = {"address": address, "limit": limit}
        if lt is not None and tx_hash:
            params["lt"] = lt
            params["hash"] = tx_hash
        api_key = toncenter_api_key()
        if api_key:
            params["api_key"] = api_key
        url = f"{toncenter_base_url()}/getTransactions"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(payload.get("error", "toncenter getTransactions failed"))
        return payload.get("result") or []

    async def poll_once(self) -> int:
        if not wallet_configured():
            return 0
        start_utime = self.store.last_poll_utime()
        latest_utime = start_utime
        processed = 0
        offset_lt: int | None = None
        offset_hash: str | None = None

        while True:
            try:
                transactions = await self.fetch_transactions(
                    limit=10,
                    lt=offset_lt,
                    tx_hash=offset_hash,
                )
            except Exception as exc:
                logger.warning("TON poll failed: %s", exc)
                break

            if not transactions:
                break

            if latest_utime == start_utime and transactions:
                candidate = int(transactions[0].get("utime") or 0)
                if candidate > latest_utime:
                    latest_utime = candidate

            for tx in transactions:
                utime = int(tx.get("utime") or 0)
                if utime < start_utime:
                    self.store.set_last_poll_utime(latest_utime)
                    return processed

                if self._try_complete_payment(tx):
                    processed += 1

            if len(transactions) < 2:
                break

            last = transactions[-1]
            tx_id = last.get("transaction_id") or {}
            offset_lt = tx_id.get("lt")
            offset_hash = tx_id.get("hash")
            if offset_lt is None or not offset_hash:
                break

        if latest_utime > start_utime:
            self.store.set_last_poll_utime(latest_utime)
        return processed

    def _try_complete_payment(self, tx: dict[str, Any]) -> bool:
        if not is_incoming_deposit(tx):
            return False
        in_msg = tx.get("in_msg") or {}
        comment = extract_text_comment(in_msg)
        if not comment:
            return False
        payment = self.store.get_payment(comment)
        if not payment or payment.status != PaymentStatus.PENDING:
            return False
        value = int(in_msg.get("value") or 0)
        if value < payment.amount_nano:
            logger.info(
                "Underpaid TON deposit for %s: got %s nano, need %s",
                comment,
                value,
                payment.amount_nano,
            )
            return False

        tx_id = tx.get("transaction_id") or {}
        tx_ref = f"{tx_id.get('lt')}:{tx_id.get('hash')}"
        sender = str(in_msg.get("source") or "")

        self.store.complete_payment(payment.id, tx_ref, sender)
        self.store.upgrade_user_plan(payment.user_id, Plan.TEAM)
        logger.info("Team plan activated via TON payment %s from %s", comment, sender)
        return True

    async def poll_loop(self) -> None:
        while True:
            try:
                await self.poll_once()
            except Exception as exc:
                logger.warning("TON poll loop error: %s", exc)
            await asyncio.sleep(poll_interval_sec())

    def start_background_poll(self) -> None:
        if not wallet_configured():
            return
        if self._poll_task and not self._poll_task.done():
            return
        self._poll_task = asyncio.create_task(self.poll_loop())
