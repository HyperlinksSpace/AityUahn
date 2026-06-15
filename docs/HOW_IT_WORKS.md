# How AityUahn Works — Architecture Deep-Dive

Companion to [TEST_AND_LAUNCH.md](TEST_AND_LAUNCH.md) (launch & test steps) and [guide.html](guide.html) (browsable summary).

**Version 0.2.1** · Three runtime surfaces: **UI**, **local forge**, **cloud SaaS**.

---

## 1. System overview

```
                    ┌─────────────────────────────────────┐
                    │  Static UI (HTML/JS/CSS)            │
                    │  landing · controller · docs · guide│
                    └───────────┬─────────────┬───────────┘
                                │             │
                     forge API  │             │  saas API
                                ▼             ▼
              ┌─────────────────────┐   ┌─────────────────────┐
              │  Local forge        │   │  Cloud SaaS         │
              │  forge_app.py       │   │  saas_app.py        │
              │  :8765              │   │  Vercel + Neon      │
              └──────────┬──────────┘   └──────────┬──────────┘
                         │                         │
                         ▼                         ▼
              ┌─────────────────────┐   ┌─────────────────────┐
              │  Disk               │   │  Postgres (Neon)    │
              │  ideas, backlogs,     │   │  users, projects,   │
              │  workspace projects │   │  payments, members  │
              └─────────────────────┘   └─────────────────────┘
```

| Surface | Technology | Persistence | Who runs it |
|---------|------------|-------------|-------------|
| UI | GitHub Pages or `aityuahn serve` static files | None | HyperlinksSpace / you |
| Forge API | FastAPI (`python/backend/forge_app.py`) | YAML + JSON under `.python/` | You, locally |
| SaaS API | FastAPI (`python/backend/saas_app.py`) | Neon when `DATABASE_URL` set | Vercel (production) |

---

## 2. Local forge — what happens when you run `aityuahn serve`

1. **CLI** loads `forge.yaml` and `.env`, constructs `LForge` orchestrator.
2. **FastAPI app** mounts:
   - REST routes: `/api/health`, `/api/dashboard`, `/api/idea`, `/api/forge`, …
   - Static UI: `/`, `/controller.html`, `/docs.html`, `/guide.html`
3. **Default port 8765** — only this process should answer with `"role": "forge"`.
4. **Data** lives under `forge_data_dir` (usually repo `.python/`):
   - `ideas/<slug>.yaml` — structured project briefs
   - `backlogs/<slug>.yaml` — tasks, status, test history
   - `registry.json` — registered project slugs
5. **Scaffolded code** goes to `workspace_root/<slug>/` (separate from forge data).

### Forge API routes (common)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/health` | Liveness + version + workspace paths |
| GET | `/api/dashboard` | Kanban summary for UI |
| GET | `/api/registry` | Ideas, backlogs, projects list |
| POST | `/api/idea` | Generate idea from prompt |
| POST | `/api/forge` | Full pipeline: idea + backlog + scaffold |
| PATCH | `/api/task/status` | Update task on kanban |

OpenAPI: `http://127.0.0.1:8765/docs`

---

## 3. Cloud SaaS — auth, teams, billing

Hosted entry: `api/index.py` on Vercel (`VERCEL=1`).

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/health` | Deploy readiness (`jwt_configured`, `database_reachable`, `issues`) |
| GET | `/api/saas/pricing` | Public plan list |
| POST | `/api/saas/auth/register` | Create account → JWT |
| POST | `/api/saas/auth/login` | Sign in → JWT |
| GET | `/api/saas/projects` | List team projects (Bearer token) |
| POST | `/api/saas/projects` | Create project + optional demo forge slug |
| POST | `/api/saas/projects/{id}/members` | Invite by email |
| GET | `/api/cron/ton-poll` | Vercel Cron — TON payment polling |

**JWT:** signed with `AITYUAHN_JWT_SECRET` (Vercel env only). Tokens last 72 hours. UI stores token in `localStorage`.

**Database:** when `DATABASE_URL` is set, `PostgresSaaSStore` replaces JSON files. Vercel build runs `python scripts/migrate_db.py`.

---

## 4. How the UI connects

File: `python/static/config.json` (copied to `docs/config.json` for Pages).

| Key | Used for |
|-----|----------|
| `defaultForgeApi` | Forge URL prefill (`http://127.0.0.1:8765`) |
| `defaultSaasApi` | Cloud URL for `AityAuth.saasApi()` |
| `backendExe`, `backendInstallerSh`, … | Download / install links |

**auth.js** reads:
- Forge: `readForgeBase()` — query `?forge=`, localStorage, config, or localhost origin
- SaaS: `readSaasBase()` — query `?saas=`, localStorage, `defaultSaasApi`

**Controller flow:**
1. Page loads → tries forge health at stored URL
2. **Forge live** pill when `role === "forge"` and `ok === true`
3. Separate **cloud** pill from `probeSaasHealth()` when `defaultSaasApi` set
4. Kanban/agents → forge API; sign-in/register → SaaS API

---

## 5. CLI command map

| Command | Runs | Port |
|---------|------|------|
| `aityuahn serve` | Forge + UI | 8765 |
| `aityuahn serve --demo` | Forge + seeded kanban | 8765 |
| `aityuahn serve --with-saas` | Forge + SaaS monolith (dev) | 8765 |
| `aityuahn serve-saas` | SaaS only (dev) | 8780 |
| `aityuahn forge "…"` | One-shot pipeline, no server | — |
| `aityuahn doctor` | Probe URLs, table output | — |
| `aityuahn verify` | Probe URLs, pass/fail exit code | — |
| `aityuahn version` | Print package version | — |

---

## 6. Environment variables

### Local forge (`.env`)

| Variable | Required | Purpose |
|----------|----------|---------|
| `PYTHON_CONFIG` | No | Path to `forge.yaml` |
| `PYTHON_WORKSPACE_ROOT` | No | Override workspace parent |
| `ANTHROPIC_API_KEY`, etc. | For AI | Provider keys per `forge.yaml` |

### Cloud SaaS (Vercel)

| Variable | Required | Purpose |
|----------|----------|---------|
| `DATABASE_URL` | Yes (prod) | Neon pooled connection |
| `AITYUAHN_JWT_SECRET` | Yes (prod) | JWT signing (32+ chars) |
| `CRON_SECRET` | For TON cron | Protects `/api/cron/ton-poll` |
| `AITYUAHN_TON_*` | For billing | TON wallet, API key, price |

---

## 7. CI and releases

| Workflow | Trigger | Output |
|----------|---------|--------|
| `pages.yml` | Push `main` | GitHub Pages from `docs/` |
| `release-installer.yml` | Push forge paths | `aityuahn-installer.exe` on Releases |
| `vercel-deploy.yml` | Push SaaS paths | Vercel deploy (needs GH secrets) |

Vercel also deploys via its own GitHub integration when the repo is imported — no GH Action secrets required for that path.

---

## 8. Mental model (one paragraph)

**You run the forge on your machine** — it owns your code, tasks, and AI calls. **HyperlinksSpace runs the SaaS API** — it owns accounts, team membership, and payment state in Neon. **GitHub Pages hosts the UI** — it is a thin client that talks to both APIs. Testing means confirming each layer independently (`aityuahn verify`), then end-to-end in the controller (connect forge, sign in via cloud, move a kanban card).

→ Next: [TEST_AND_LAUNCH.md](TEST_AND_LAUNCH.md) for step-by-step launch and the full 22-item checklist.
