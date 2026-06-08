from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Plan(str, Enum):
    PERSONAL = "personal"
    TEAM = "team"


class MemberRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class User(BaseModel):
    id: str
    email: str
    name: str
    password_hash: str
    plan: Plan = Plan.PERSONAL
    created_at: datetime = Field(default_factory=utc_now)


class UserPublic(BaseModel):
    id: str
    email: str
    name: str
    plan: Plan
    created_at: datetime


class TeamProject(BaseModel):
    id: str
    slug: str
    name: str
    owner_id: str
    forge_slug: str
    description: str = ""
    is_demo: bool = False
    api_config: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class ProjectMember(BaseModel):
    project_id: str
    user_id: str
    role: MemberRole
    joined_at: datetime = Field(default_factory=utc_now)


class AuthToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class PricingPlan(BaseModel):
    id: Plan
    name: str
    price_label: str
    features: list[str]
    price_ton: float | None = None
    payment_method: str | None = None


class PaymentStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    EXPIRED = "expired"


class TonPayment(BaseModel):
    id: str
    user_id: str
    amount_nano: int
    wallet_address: str
    status: PaymentStatus = PaymentStatus.PENDING
    sender_address: str | None = None
    ton_tx_ref: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
