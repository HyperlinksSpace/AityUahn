# Test & Launch Guide — AityUahn

Complete reference for **how AityUahn works**, **how to launch it**, and **how to verify everything** (local forge, cloud SaaS, UI, CLI, CI).

**Version:** 0.2.1 · **Repo:** [HyperlinksSpace/AityUahn](https://github.com/HyperlinksSpace/AityUahn)

Related docs:

| Doc | Purpose |
|-----|---------|
| [HOW_IT_WORKS.md](HOW_IT_WORKS.md) | Architecture deep-dive (APIs, auth, data flow) |
| [DEPLOY_VERCEL.md](DEPLOY_VERCEL.md) | Cloud SaaS on Vercel + Neon |
| [INSTALL_RELEASE.md](INSTALL_RELEASE.md) | Windows `.exe` auto-releases |
| [README.md](../README.md) | CLI, providers, architecture |

---

## 1. How it works (architecture)

AityUahn is split into **three layers** that can run in different places:

```
┌─────────────────────────────────────────────────────────────────┐
│  Browser UI (GitHub Pages or aityuahn serve)                    │
│  landing · controller · docs                                    │
└───────────────┬─────────────────────────────┬───────────────────┘
                │                             │
                │ forge: kanban, agents,      │ cloud: sign-in,
                │ ideas, backlogs, tests      │ teams, TON billing
                ▼                             ▼
┌───────────────────────────┐   ┌───────────────────────────────┐
│  Local forge API          │   │  Cloud SaaS API (Vercel)      │
│  aityuahn serve           │   │  api/index.py                 │
│  http://127.0.0.1:8765    │   │  https://YOUR-APP.vercel.app  │
│  role: "forge"            │   │  role: "saas"                   │
└───────────────┬───────────┘   └───────────────┬───────────────┘
                │                               │
                ▼                               ▼
┌───────────────────────────┐   ┌───────────────────────────────┐
│  Local disk               │   │  Neon Postgres                │
│  .python/ideas, backlogs  │   │  saas_users, saas_projects,   │
│  workspace_root/<slug>/   │   │  saas_payments, …             │
└───────────────────────────┘   └───────────────────────────────┘
```

### What runs where

| Component | Where | Command / URL | Health check |
|-----------|--------|---------------|--------------|
| **Static UI** | GitHub Pages | `https://hyperlinksspace.github.io/AityUahn/` | N/A (HTML only) |
| **Local forge** | Your PC | `aityuahn serve` → `:8765` | `GET /api/health` → `"role": "forge"` |
| **Cloud SaaS** | Vercel | Your Vercel project URL | `GET /api/health` → `"role": "saas"` |
| **SaaS database** | Neon | `DATABASE_URL` (pooled) on Vercel | visible in SaaS health as `"storage": "neon"` |
| **Windows installer** | GitHub Releases | `releases/latest/download/aityuahn-installer.exe` | CI builds on push to `main` |

### User journey

1. **Install** the local forge (one-line script, `.exe`, or git clone).
2. **Run** `aityuahn serve` — forge API + UI on port **8765**.
3. **Open** the controller (locally or on GitHub Pages) and **connect** forge URL `http://127.0.0.1:8765`.
4. **Sign in / register** — hits **cloud SaaS** when `defaultSaasApi` is set in `config.json` (Vercel URL).
5. **Work** — kanban, forge pipeline, agents use the **local forge**; team membership and billing use **cloud SaaS**.

The controller header shows **two status pills** when configured:

- **Forge live** — local API reachable
- **Cloud v…** — Vercel SaaS health (or issues if misconfigured)

### CLI vs serve

| Mode | Purpose |
|------|---------|
| `aityuahn forge "…"` | One-shot: idea → backlog → scaffold folder |
| `aityuahn serve` | Long-running forge API + web UI (default) |
| `aityuahn serve-saas` | Local SaaS API only (port 8780, dev) |
| `aityuahn serve --with-saas` | Monolith dev mode (forge + SaaS on one port) |
| `aityuahn doctor` | Probe forge + optional cloud URLs |
| `aityuahn version` | Print installed version |

---

## 2. Prerequisites

| Requirement | Check |
|-------------|--------|
| Python **3.11+** | `python --version` |
| pip + venv | `python -m venv .venv` |
| Git (optional) | `git --version` |
| **Forge AI keys** (optional) | `.env` — `ANTHROPIC_API_KEY`, etc. |
| **Cloud SaaS** (optional) | Vercel project + Neon `DATABASE_URL` + `AITYUAHN_JWT_SECRET` |

Sign-up and kanban demo work **without** AI keys. Forge, agents, and AI backlog generation need at least one provider in `forge.yaml` + `.env`.

---

## 3. Launch paths (pick one)

### Path A — One-line install (recommended for users)

**Windows PowerShell:**

```powershell
irm https://raw.githubusercontent.com/HyperlinksSpace/AityUahn/main/scripts/install.ps1 | iex
```

**Git Bash / WSL / macOS / Linux:**

```bash
curl -LsSf https://raw.githubusercontent.com/HyperlinksSpace/AityUahn/main/scripts/install.sh | sh
```

Default install: `%USERPROFILE%\AityUahn` (Windows) or `~/AityUahn`.

Then:

```bash
cd ~/AityUahn   # or %USERPROFILE%\AityUahn
serve.bat       # Windows
# or: aityuahn serve
```

### Path B — Windows installer (.exe)

Download (always latest):

```
https://github.com/HyperlinksSpace/AityUahn/releases/latest/download/aityuahn-installer.exe
```

Requires Python 3.11+ on the machine. Installs to `%USERPROFILE%\AityUahn`, creates venv, writes `serve.bat`.

### Path C — Developer clone (this repo)

```bash
git clone https://github.com/HyperlinksSpace/AityUahn.git
cd AityUahn
python -m venv .venv
source .venv/Scripts/activate    # Git Bash on Windows
pip install -e ".[dev]"
cp config/forge.example.yaml forge.yaml
cp .env.example .env
aityuahn init
aityuahn serve --demo
```

### Path D — GitHub Pages UI only

1. Open **https://hyperlinksspace.github.io/AityUahn/**
2. You still need **Path A/B/C** for a live forge — Pages hosts HTML/JS only.
3. Connect `http://127.0.0.1:8765` in the controller (works when UI is served from `aityuahn serve`; from Pages you need a tunnel to reach localhost).

---

## 4. Step-by-step launch (full stack)

### Step 1 — Configure forge (local)

Edit `forge.yaml`:

```yaml
workspace_root: C:/1/1/1/1/1   # parent folder for forged projects
```

Edit `.env` (optional for AI):

```env
ANTHROPIC_API_KEY=sk-ant-...
```

### Step 2 — Start local forge

```bash
aityuahn serve --demo
aityuahn serve --demo --open   # also opens controller in browser
aityuahn status
```

Expected console output:

```
Forge UI    http://127.0.0.1:8765/
Forge API   http://127.0.0.1:8765/api/health
SaaS        off — set defaultSaasApi in UI config for cloud auth
```

Keep this terminal open.

### Step 3 — Verify forge (second terminal)

```bash
curl http://127.0.0.1:8765/api/health
aityuahn doctor
aityuahn version
```

Expected forge health:

```json
{
  "ok": true,
  "role": "forge",
  "version": "0.2.1",
  "workspace": "...",
  "forge_data": "...",
  "default_provider": "..."
}
```

With cloud URL configured:

```bash
aityuahn doctor --saas-url https://YOUR-APP.vercel.app
```

### Step 4 — Open the UI

| Page | URL |
|------|-----|
| Landing | http://127.0.0.1:8765/ |
| Controller | http://127.0.0.1:8765/controller.html |
| Docs | http://127.0.0.1:8765/docs.html |
| OpenAPI | http://127.0.0.1:8765/docs |

### Step 5 — Connect in controller

1. Open **Controller**.
2. **Local forge API** field → `http://127.0.0.1:8765`
3. Click **Connect**
4. Header should show **Forge live · v0.2.1**
5. If `defaultSaasApi` is set in `config.json`, a second pill shows cloud status.

**Common mistake:** pasting the Vercel URL into the forge field. Forge must be port **8765** (role `forge`), not the cloud URL (role `saas`).

### Step 6 — Cloud SaaS (optional)

Deploy per [DEPLOY_VERCEL.md](DEPLOY_VERCEL.md). Minimum Vercel env vars:

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Neon **pooled** connection string |
| `AITYUAHN_JWT_SECRET` | JWT signing — generate: `openssl rand -hex 32` |

Point the UI at your deployment in `python/static/config.json`:

```json
{
  "defaultSaasApi": "https://YOUR-APP.vercel.app",
  "defaultForgeApi": "http://127.0.0.1:8765"
}
```

Rebuild Pages: `python scripts/build_pages.py`

Verify cloud:

```bash
curl https://YOUR-APP.vercel.app/api/health
curl https://YOUR-APP.vercel.app/api/saas/pricing
```

Expected SaaS health (production):

```json
{
  "ok": true,
  "role": "saas",
  "version": "0.2.1",
  "serverless": true,
  "storage": "neon",
  "jwt_configured": true,
  "database_reachable": true
}
```

If `"ok": false`, read the `"issues"` array.

---

## 5. Testing checklist

Use this table to confirm each layer works.

### 5.1 CLI & backend

| # | Test | Command | Pass criteria |
|---|------|---------|---------------|
| 1 | CLI installed | `aityuahn version` | Prints `aityuahn 0.2.1` |
| 2 | Forge data dirs | `aityuahn init` | Prints workspace + forge data paths |
| 3 | Forge health | `curl localhost:8765/api/health` | `"ok": true`, `"role": "forge"` |
| 3b | Forge info | `curl localhost:8765/api/info` | `"role": "forge"`, `"links"` object |
| 4 | Doctor | `aityuahn doctor` | Forge check **ok** |
| 5 | Demo data | `aityuahn serve --demo` | Dashboard has demo project |
| 6 | Registry | `aityuahn list` | Lists ideas/backlogs/projects |
| 7 | Unit tests | `pytest -q` | All tests pass |

### 5.2 Controller UI (live forge)

| # | Test | Steps | Pass criteria |
|---|------|-------|---------------|
| 8 | Connect | Paste `:8765` → Connect | **Forge live** pill |
| 9 | Kanban | Change task status | Updates without error |
| 10 | Task list | Add task, mark done | Task appears |
| 11 | Forge tab | Refresh backlog | No error (AI needs keys) |
| 12 | Agents | Send prompt | Response or clear “no provider” error |
| 13 | Offline demo | `?demo=1` or Offline demo btn | Kanban works without API |

### 5.3 Cloud SaaS (if deployed)

| # | Test | Steps | Pass criteria |
|---|------|-------|---------------|
| 14 | SaaS health | `curl …/api/health` | `"role": "saas"`, `"ok": true` |
| 15 | Cloud pill | Open controller on Pages | Shows **cloud v…** or clear issue |
| 16 | Register | Landing → Register | Returns token |
| 17 | Team project | Create project in UI | Appears in sidebar |
| 18 | Invite member | Team tab → invite email | Roster updates |
| 19 | Neon data | Neon SQL editor | Row in `saas_users` |

### 5.4 CI / releases (maintainers)

| # | Test | Where | Pass criteria |
|---|------|-------|---------------|
| 20 | GitHub Pages | Actions → pages workflow | Site updates on push |
| 21 | Windows exe | Actions → Windows installer release | `.exe` on Releases |
| 22 | Vercel deploy | Vercel dashboard or GH Action | `/api/health` ok on prod URL |

---

## 6. Quick smoke test (5 minutes)

```bash
# Terminal 1
cd AityUahn && source .venv/Scripts/activate
aityuahn serve --demo

# Terminal 2
curl -s http://127.0.0.1:8765/api/health | python -m json.tool
aityuahn doctor
pytest -q --tb=no
```

Browser:

1. http://127.0.0.1:8765/controller.html
2. Connect → **Forge live**
3. Kanban → move one task
4. Optional: register on landing (needs `defaultSaasApi`)

---

## 7. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Connect fails from GitHub Pages | Browser cannot reach `127.0.0.1` | Use UI from `aityuahn serve` or set up ngrok/Cloudflare tunnel |
| “Expected local forge… got saas” | Vercel URL in forge field | Use `http://127.0.0.1:8765` for forge |
| Cloud pill shows issues | Missing Vercel env | Set `DATABASE_URL`, `AITYUAHN_JWT_SECRET` on Vercel |
| Sign-in 405 on Pages | No SaaS URL | Set `defaultSaasApi` in `config.json`, rebuild Pages |
| `pip install -e ".[dev]"` fails in Git Bash | Path with spaces | `(cd "$DIR" && pip install -e ".[dev]")` — fixed in install scripts |
| Forge works, cloud offline | SaaS not deployed | See [DEPLOY_VERCEL.md](DEPLOY_VERCEL.md) |
| `aityuahn doctor` forge fail | serve not running | Start `aityuahn serve` |

---

## 8. Ports reference

| Service | Default port | Command |
|---------|--------------|---------|
| Local forge | **8765** | `aityuahn serve` |
| Local SaaS (dev) | **8780** | `aityuahn serve-saas` |
| Vercel | 443 | Hosted |

Override forge port: `aityuahn serve --port 9000`

---

## 9. Rebuild GitHub Pages after config changes

```bash
python scripts/build_pages.py
git add docs/ python/static/config.json
git commit -m "Update Pages config"
git push
```

---

## 10. Summary

| Goal | Minimal steps |
|------|-----------------|
| **Try UI only** | Open controller with `?demo=1` |
| **Run locally** | Install → `aityuahn serve --demo` → connect `:8765` |
| **Full product** | Local forge + Vercel SaaS + Neon + `defaultSaasApi` in config |
| **Verify** | `aityuahn doctor` + checklist above |

For cloud deployment details see [DEPLOY_VERCEL.md](DEPLOY_VERCEL.md). For Windows installer CI see [INSTALL_RELEASE.md](INSTALL_RELEASE.md).

---

## 11. Windows walkthrough (Git Bash vs PowerShell)

| Step | Git Bash | PowerShell |
|------|----------|------------|
| Install one-line | `curl -LsSf …/install.sh \| sh` | `irm …/install.ps1 \| iex` |
| Activate venv | `source .venv/Scripts/activate` | `.\.venv\Scripts\Activate.ps1` |
| Start forge | `aityuahn serve --demo` | same |
| Verify | `bash scripts/verify_setup.sh` | `.\scripts\verify_setup.ps1` |
| Doctor | `aityuahn doctor` | same |

**Do not** run `irm | iex` inside Git Bash — use PowerShell for the Windows installer script.

After one-line install, open a **new** terminal in `%USERPROFILE%\AityUahn` and run `serve.bat`.

---

## 12. Automated verification scripts

With `aityuahn serve --demo` running:

**Git Bash / Linux / macOS:**

```bash
bash scripts/verify_setup.sh
# optional cloud:
SAAS_URL=https://YOUR-APP.vercel.app bash scripts/verify_setup.sh
```

**PowerShell:**

```powershell
.\scripts\verify_setup.ps1
.\scripts\verify_setup.ps1 -SaasUrl https://YOUR-APP.vercel.app
```

Equivalent manual check:

```bash
aityuahn verify
aityuahn verify --saas-url https://YOUR-APP.vercel.app
aityuahn doctor --forge-url http://127.0.0.1:8765 --saas-url https://YOUR-APP.vercel.app
```

---

## 13. API endpoints (manual curl tests)

### Local forge (`:8765`)

```bash
curl -s http://127.0.0.1:8765/api/health
curl -s http://127.0.0.1:8765/api/dashboard
curl -s http://127.0.0.1:8765/api/registry
curl -s http://127.0.0.1:8765/api/providers
```

### Cloud SaaS (Vercel)

```bash
curl -s https://YOUR-APP.vercel.app/api/health
curl -s https://YOUR-APP.vercel.app/api/saas/pricing
curl -s -X POST https://YOUR-APP.vercel.app/api/saas/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"secret12","name":"Test","plan":"personal"}'
```

OpenAPI (local forge only): http://127.0.0.1:8765/docs

---

## 14. `config.json` (GitHub Pages UI)

File: `python/static/config.json` — controls download links and default API URLs on Pages.

| Key | Purpose |
|-----|---------|
| `defaultForgeApi` | Pre-filled local forge URL (`http://127.0.0.1:8765`) |
| `defaultSaasApi` | Your Vercel URL for sign-in / teams (empty until deployed) |
| `backendExe` | Windows installer download link |
| `backendInstallerSh` / `backendInstallerPs1` | One-line install script URLs |

After editing, rebuild Pages:

```bash
python scripts/build_pages.py
```

---

## 15. Browsable guide on GitHub Pages

Full HTML version (same content, easy navigation):

**https://hyperlinksspace.github.io/AityUahn/guide.html**

Also linked from **Docs** and **Controller** header menus.

