from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from python.forge import LForge
from python.saas.models import AuthToken, MemberRole, Plan
from python.saas.store import SaaSStore, create_saas_store, resolve_saas_data_dir
from python.saas.ton import TonPaymentService, wallet_configured
from python.saas.settings import team_price_ton


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str = ""
    plan: Plan = Plan.PERSONAL


class LoginRequest(BaseModel):
    email: str
    password: str


class CreateProjectRequest(BaseModel):
    name: str
    slug: str
    description: str = ""
    create_demo: bool = False


class InviteMemberRequest(BaseModel):
    email: str
    role: MemberRole = MemberRole.MEMBER


class ApiConfigRequest(BaseModel):
    default_provider: str = "claude"
    providers: list[dict] = Field(default_factory=list)
    notes: str = ""


def create_saas_router(forge: LForge) -> APIRouter:
    store = create_saas_store(forge.config.forge_data_dir)
    ton = TonPaymentService(store)
    router = APIRouter(prefix="/api/saas", tags=["saas"])

    def current_user(authorization: str | None = Header(default=None)):
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(401, "Missing or invalid Authorization header")
        token = authorization.split(" ", 1)[1].strip()
        try:
            return store.user_from_token(token)
        except Exception as e:
            raise HTTPException(401, str(e)) from e

    @router.get("/pricing")
    def pricing():
        return [p.model_dump(mode="json") for p in store.pricing()]

    @router.get("/billing/ton-config")
    def ton_config():
        return {
            "enabled": wallet_configured(),
            "team_price_ton": team_price_ton(),
            "payment_method": "ton" if wallet_configured() else None,
        }

    @router.post("/billing/team-payment")
    async def create_team_payment(user=Depends(current_user)):
        if user.plan == Plan.TEAM:
            raise HTTPException(400, "Already on Team plan")
        try:
            payment = ton.create_team_payment(user.id)
        except ValueError as e:
            raise HTTPException(503, str(e)) from e
        return ton.payment_payload(payment)

    @router.get("/billing/team-payment/{payment_id}")
    async def get_team_payment(payment_id: str, user=Depends(current_user)):
        payment = store.get_payment(payment_id)
        if not payment or payment.user_id != user.id:
            raise HTTPException(404, "Payment not found")
        if payment.status.value == "pending":
            await ton.poll_once()
            payment = store.get_payment(payment_id) or payment
            refreshed = store.get_user(user.id)
            if refreshed and refreshed.plan == Plan.TEAM:
                payment = store.get_payment(payment_id) or payment
        payload = ton.payment_payload(payment)
        payload["plan"] = store.get_user(user.id).plan.value if store.get_user(user.id) else user.plan.value
        return payload

    @router.get("/billing/team-payment")
    async def get_active_team_payment(user=Depends(current_user)):
        if user.plan == Plan.TEAM:
            return {"status": "completed", "plan": Plan.TEAM.value}
        payment = store.find_pending_payment(user.id)
        if not payment:
            return {"status": "none"}
        await ton.poll_once()
        payment = store.find_pending_payment(user.id) or store.get_payment(payment.id)
        refreshed = store.get_user(user.id)
        if refreshed and refreshed.plan == Plan.TEAM:
            return {"status": "completed", "plan": Plan.TEAM.value}
        if payment:
            return ton.payment_payload(payment)
        return {"status": "none"}

    @router.post("/auth/register")
    def register(body: RegisterRequest):
        requested_team = body.plan == Plan.TEAM
        try:
            user, token = store.register(body.email, body.password, body.name, body.plan)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        response = AuthToken(access_token=token, user=store.public_user(user))
        if requested_team and wallet_configured() and user.plan != Plan.TEAM:
            return {
                **response.model_dump(mode="json"),
                "requires_ton_payment": True,
                "message": "Account created. Complete the TON payment to activate Team plan.",
            }
        return response

    @router.post("/auth/login", response_model=AuthToken)
    def login(body: LoginRequest):
        try:
            user, token = store.login(body.email, body.password)
        except ValueError as e:
            raise HTTPException(401, str(e)) from e
        return AuthToken(access_token=token, user=store.public_user(user))

    @router.get("/auth/me")
    def me(user=Depends(current_user)):
        return store.public_user(user).model_dump(mode="json")

    @router.get("/projects")
    def list_projects(user=Depends(current_user)):
        projects = store.user_projects(user.id)
        return [
            {
                **p.model_dump(mode="json"),
                "role": next(
                    (
                        m.role.value
                        for m in store.list_members()
                        if m.project_id == p.id and m.user_id == user.id
                    ),
                    "owner" if p.owner_id == user.id else "member",
                ),
                "members": store.project_roster(p.id),
            }
            for p in projects
        ]

    @router.post("/projects")
    def create_project(body: CreateProjectRequest, user=Depends(current_user)):
        try:
            project = store.create_project(
                user,
                body.name,
                body.slug,
                body.description,
                is_demo=body.create_demo,
            )
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        if body.create_demo:
            from python.demo import seed_demo_data

            seed_demo_data(forge.storage)
        return project.model_dump(mode="json")

    @router.post("/projects/{project_id}/members")
    def invite_member(project_id: str, body: InviteMemberRequest, user=Depends(current_user)):
        try:
            member = store.add_member(user.id, project_id, body.email, body.role)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        return {
            "project_id": member.project_id,
            "user_id": member.user_id,
            "role": member.role.value,
            "roster": store.project_roster(project_id),
        }

    @router.get("/projects/{project_id}/api-config")
    def get_api_config(project_id: str, user=Depends(current_user)):
        if not store.can_access_project(user.id, project_id):
            raise HTTPException(403, "Not a member of this project")
        project = store.get_project(project_id)
        if not project:
            raise HTTPException(404, "Project not found")
        cfg = project.api_config or {}
        return {
            "default_provider": cfg.get("default_provider", forge.config.default_provider),
            "providers": [
                {k: v for k, v in p.items() if k not in ("api_key", "secret")}
                for p in cfg.get("providers", [])
            ],
            "notes": cfg.get("notes", ""),
            "configured": bool(cfg.get("providers")),
        }

    @router.put("/projects/{project_id}/api-config")
    def put_api_config(project_id: str, body: ApiConfigRequest, user=Depends(current_user)):
        try:
            project = store.set_api_config(
                user.id,
                project_id,
                {
                    "default_provider": body.default_provider,
                    "providers": body.providers,
                    "notes": body.notes,
                },
            )
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        return {"ok": True, "project_id": project.id}

    @router.post("/billing/upgrade-team")
    def upgrade_team(user=Depends(current_user)):
        if wallet_configured():
            raise HTTPException(
                402,
                f"Team plan requires a {team_price_ton():g} TON payment. Use POST /api/saas/billing/team-payment.",
            )
        users = store.list_users()
        for i, u in enumerate(users):
            if u.id == user.id:
                users[i] = u.model_copy(update={"plan": Plan.TEAM})
                store.save_users(users)
                return {
                    "ok": True,
                    "plan": Plan.TEAM.value,
                    "message": "Upgraded to Team plan (demo mode — set ton_wallet_address in saas.yaml for TON billing).",
                }
        raise HTTPException(404, "User not found")

    return router, ton
