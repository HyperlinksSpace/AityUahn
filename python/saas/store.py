from __future__ import annotations

import hashlib
import json
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt

from python.saas.models import (
    MemberRole,
    Plan,
    PricingPlan,
    ProjectMember,
    TeamProject,
    User,
    UserPublic,
    utc_now,
)

JWT_ALG = "HS256"
JWT_TTL_HOURS = 72


def _hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    salt, _hex = stored.split("$", 1)
    return _hash_password(password, salt) == stored


def jwt_secret() -> str:
    return os.environ.get(
        "AITYUAHN_JWT_SECRET",
        "dev-only-change-in-production-use-32b-min",
    )


class SaaSStore:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.users_file = self.data_dir / "users.json"
        self.projects_file = self.data_dir / "projects.json"
        self.members_file = self.data_dir / "members.json"

    def _load(self, path: Path, key: str) -> list[dict]:
        if not path.is_file():
            return []
        return json.loads(path.read_text(encoding="utf-8")).get(key, [])

    def _save(self, path: Path, key: str, rows: list[dict]) -> None:
        path.write_text(json.dumps({key: rows}, indent=2, default=str), encoding="utf-8")

    def list_users(self) -> list[User]:
        return [User.model_validate(u) for u in self._load(self.users_file, "users")]

    def save_users(self, users: list[User]) -> None:
        self._save(self.users_file, "users", [u.model_dump(mode="json") for u in users])

    def list_projects(self) -> list[TeamProject]:
        return [TeamProject.model_validate(p) for p in self._load(self.projects_file, "projects")]

    def save_projects(self, projects: list[TeamProject]) -> None:
        self._save(self.projects_file, "projects", [p.model_dump(mode="json") for p in projects])

    def list_members(self) -> list[ProjectMember]:
        return [ProjectMember.model_validate(m) for m in self._load(self.members_file, "members")]

    def save_members(self, members: list[ProjectMember]) -> None:
        self._save(self.members_file, "members", [m.model_dump(mode="json") for m in members])

    def get_user_by_email(self, email: str) -> User | None:
        email = email.strip().lower()
        return next((u for u in self.list_users() if u.email == email), None)

    def get_user(self, user_id: str) -> User | None:
        return next((u for u in self.list_users() if u.id == user_id), None)

    def get_project(self, project_id: str) -> TeamProject | None:
        return next((p for p in self.list_projects() if p.id == project_id), None)

    def public_user(self, user: User) -> UserPublic:
        return UserPublic(
            id=user.id,
            email=user.email,
            name=user.name,
            plan=user.plan,
            created_at=user.created_at,
        )

    def create_token(self, user: User) -> str:
        payload = {
            "sub": user.id,
            "email": user.email,
            "plan": user.plan.value,
            "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_TTL_HOURS),
        }
        return jwt.encode(payload, jwt_secret(), algorithm=JWT_ALG)

    def decode_token(self, token: str) -> dict:
        return jwt.decode(token, jwt_secret(), algorithms=[JWT_ALG])

    def register(self, email: str, password: str, name: str, plan: Plan) -> tuple[User, str]:
        if self.get_user_by_email(email):
            raise ValueError("Email already registered")
        user = User(
            id=f"U-{uuid.uuid4().hex[:10]}",
            email=email.strip().lower(),
            name=name.strip() or email.split("@")[0],
            password_hash=_hash_password(password),
            plan=plan,
        )
        users = self.list_users()
        users.append(user)
        self.save_users(users)
        return user, self.create_token(user)

    def login(self, email: str, password: str) -> tuple[User, str]:
        user = self.get_user_by_email(email)
        if not user or not verify_password(password, user.password_hash):
            raise ValueError("Invalid email or password")
        return user, self.create_token(user)

    def user_from_token(self, token: str) -> User:
        payload = self.decode_token(token)
        user = self.get_user(payload["sub"])
        if not user:
            raise ValueError("User not found")
        return user

    def pricing(self) -> list[PricingPlan]:
        return [
            PricingPlan(
                id=Plan.PERSONAL,
                name="Personal",
                price_label="Free",
                features=[
                    "1 user · 1 active project",
                    "Kanban, backlog & agent prompts",
                    "Bring your own API keys",
                    "Community support",
                ],
            ),
            PricingPlan(
                id=Plan.TEAM,
                name="Team",
                price_label="$49 / seat / mo",
                features=[
                    "Unlimited team members per project",
                    "Shared codebase & single API pool",
                    "Owner-managed provider keys for the team",
                    "Priority support & SSO (roadmap)",
                ],
            ),
        ]

    def user_projects(self, user_id: str) -> list[TeamProject]:
        member_project_ids = {
            m.project_id for m in self.list_members() if m.user_id == user_id
        }
        return [p for p in self.list_projects() if p.id in member_project_ids or p.owner_id == user_id]

    def can_access_project(self, user_id: str, project_id: str) -> bool:
        project = self.get_project(project_id)
        if not project:
            return False
        if project.owner_id == user_id:
            return True
        return any(
            m.project_id == project_id and m.user_id == user_id for m in self.list_members()
        )

    def can_manage_project(self, user_id: str, project_id: str) -> bool:
        project = self.get_project(project_id)
        if not project or project.owner_id == user_id:
            return bool(project)
        return any(
            m.project_id == project_id
            and m.user_id == user_id
            and m.role in (MemberRole.OWNER, MemberRole.ADMIN)
            for m in self.list_members()
        )

    def create_project(
        self,
        owner: User,
        name: str,
        slug: str,
        description: str = "",
        is_demo: bool = False,
    ) -> TeamProject:
        projects = self.list_projects()
        if owner.plan == Plan.PERSONAL:
            owned = [p for p in projects if p.owner_id == owner.id and not p.is_demo]
            if len(owned) >= 1:
                raise ValueError("Personal plan allows one project. Upgrade to Team for more.")
        slug = slug.strip().lower().replace(" ", "-")
        if any(p.slug == slug for p in projects):
            raise ValueError(f"Project slug '{slug}' already exists")
        project = TeamProject(
            id=f"P-{uuid.uuid4().hex[:10]}",
            slug=slug,
            name=name.strip() or slug,
            owner_id=owner.id,
            forge_slug=slug,
            description=description,
            is_demo=is_demo,
        )
        projects.append(project)
        self.save_projects(projects)
        members = self.list_members()
        members.append(
            ProjectMember(project_id=project.id, user_id=owner.id, role=MemberRole.OWNER)
        )
        self.save_members(members)
        return project

    def add_member(self, actor_id: str, project_id: str, email: str, role: MemberRole) -> ProjectMember:
        if not self.can_manage_project(actor_id, project_id):
            raise ValueError("Only project owners/admins can invite members")
        project = self.get_project(project_id)
        owner = self.get_user(project.owner_id) if project else None
        if owner and owner.plan != Plan.TEAM and role != MemberRole.OWNER:
            raise ValueError("Team members require a Team plan. Upgrade billing to invite collaborators.")
        user = self.get_user_by_email(email)
        if not user:
            raise ValueError(f"No account for {email}. Ask them to sign up first.")
        members = self.list_members()
        if any(m.project_id == project_id and m.user_id == user.id for m in members):
            raise ValueError("User is already on this project")
        member = ProjectMember(project_id=project_id, user_id=user.id, role=role)
        members.append(member)
        self.save_members(members)
        return member

    def set_api_config(self, actor_id: str, project_id: str, api_config: dict) -> TeamProject:
        if not self.can_manage_project(actor_id, project_id):
            raise ValueError("Only project owners/admins can update shared API config")
        projects = self.list_projects()
        for i, p in enumerate(projects):
            if p.id == project_id:
                updated = p.model_copy(update={"api_config": api_config})
                projects[i] = updated
                self.save_projects(projects)
                return updated
        raise ValueError("Project not found")

    def project_roster(self, project_id: str) -> list[dict]:
        members = [m for m in self.list_members() if m.project_id == project_id]
        roster = []
        for m in members:
            user = self.get_user(m.user_id)
            if user:
                roster.append(
                    {
                        "user_id": user.id,
                        "email": user.email,
                        "name": user.name,
                        "role": m.role.value,
                        "joined_at": m.joined_at.isoformat(),
                    }
                )
        return roster
