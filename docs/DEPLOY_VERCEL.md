# Deploy cloud SaaS to Vercel + Neon

Same pattern as [HyperlinksSpaceProgram](https://github.com/HyperlinksSpace/HyperlinksSpaceProgram):

- **Neon** holds accounts, teams, TON payment state
- **Vercel** runs the SaaS API (`api/index.py`)
- **`python scripts/migrate_db.py`** runs on every deploy (`vercel.json` → `buildCommand`)
- **Local forge** stays on users' machines (`aityuahn serve`)

```
Browser / GitHub Pages UI
        │
        ├── sign-in, teams, billing ──► Vercel SaaS API ──► Neon Postgres
        │
        └── kanban, forge, agents ──────► http://127.0.0.1:8765 (local forge)
```

---

## Part 1 — Create a Neon project

1. Go to [console.neon.tech](https://console.neon.tech) and sign in (GitHub is fine).
2. Click **New Project**.
3. Settings:
   - **Name:** `aityuahn` (or any name)
   - **Region:** pick closest to your Vercel region (e.g. `US East` if Vercel is `iad1`)
   - **Postgres version:** default (16+)
4. Click **Create project**.

### Copy connection strings

In Neon → your project → **Connect**:

| String | Use for |
|--------|---------|
| **Pooled connection** (host has `-pooler`) | **Vercel** (`DATABASE_URL`) — required for serverless |
| Direct connection | Local migrations / `psql` debugging |

Example pooled URL:

```
postgresql://neondb_owner:npg_xxxx@ep-cool-name-123456-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require
```

Save it — you will paste this as `DATABASE_URL` in Vercel.

### Optional: Neon ↔ Vercel integration

Neon dashboard → **Integrations** → **Vercel** → connect your Vercel team.  
This can auto-create `DATABASE_URL` on the Vercel project. You can also set it manually (below).

---

## Part 2 — Create / import Vercel project

### Option A — Vercel dashboard (recommended)

1. [vercel.com/new](https://vercel.com/new) → **Import** `HyperlinksSpace/AityUahn`.
2. **Root Directory:** `.` (repo root)
3. **Framework Preset:** Other
4. Vercel reads `vercel.json`:
   - `installCommand`: `pip install -r requirements-vercel.txt`
   - `buildCommand`: `python scripts/migrate_db.py` (runs Neon schema)
5. **Do not deploy yet** — add env vars first (Part 3).

### Option B — Vercel CLI

```bash
npm i -g vercel
vercel login
cd /path/to/AityUahn
vercel link
```

---

## Part 3 — Environment variables

**Vercel → Project → Settings → Environment Variables**

Set for **Production** (and **Preview** if you want PR deploys).

### Required

| Variable | Where to get it | Example |
|----------|-----------------|---------|
| `DATABASE_URL` | Neon → Connect → **Pooled** connection string | `postgresql://…-pooler.…neon.tech/neondb?sslmode=require` |
| `AITYUAHN_JWT_SECRET` | Generate random 32+ chars | `openssl rand -hex 32` |

### TON billing (if using Team payments)

| Variable | Source |
|----------|--------|
| `AITYUAHN_TON_WALLET_ADDRESS` | `saas.yaml` or your wallet |
| `AITYUAHN_TONCENTER_API_KEY` | [toncenter.com](https://toncenter.com) API key |
| `AITYUAHN_TON_TEAM_PRICE` | Optional, default `10` |
| `AITYUAHN_TON_NETWORK` | `mainnet` or `testnet` |
| `CRON_SECRET` | Random string — protects `/api/cron/ton-poll` |

### Auto-set by Vercel (do not add manually)

| Variable | Meaning |
|----------|---------|
| `VERCEL=1` | Set automatically — disables background TON loop, enables cron mode |

### Local `.env` (optional)

```bash
cp .env.example .env
# paste DATABASE_URL (pooled), AITYUAHN_JWT_SECRET, etc.
```

Pull from Vercel:

```bash
vercel env pull .env.local
```

---

## Part 4 — Deploy

```bash
vercel --prod
```

Or push to `main` if GitHub integration is enabled.

**Build log should show:**

```
[db] Running schema migrations against DATABASE_URL...
[db] Schema is up to date.
```

If `DATABASE_URL` is missing, the build **fails** (intentional — same as HyperlinksSpaceProgram).

Skip migrations locally only:

```bash
SKIP_DB_MIGRATE=1 vercel dev
```

---

## Part 5 — Verify deployment

Replace `YOUR-APP` with your Vercel URL.

```bash
curl https://YOUR-APP.vercel.app/api/health
```

Expected:

```json
{"ok": true, "role": "saas", "serverless": true, "storage": "neon"}
```

```bash
curl https://YOUR-APP.vercel.app/api/saas/pricing
```

Register test user:

```bash
curl -X POST https://YOUR-APP.vercel.app/api/saas/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@test.com","password":"secret12","name":"You","plan":"personal"}'
```

In Neon → **Tables**, you should see `saas_users` with your row.

---

## Part 6 — Wire the frontend

Edit `python/static/config.json`:

```json
{
  "defaultSaasApi": "https://YOUR-APP.vercel.app",
  "defaultForgeApi": "http://127.0.0.1:8765"
}
```

Rebuild GitHub Pages:

```bash
python scripts/build_pages.py
git add docs/ python/static/config.json
git commit -m "Point SaaS API to Vercel"
git push
```

**User flow:**

1. Open landing / controller (GitHub Pages or local UI)
2. **Sign in / register** → hits Vercel (`defaultSaasApi`)
3. **Connect local forge** → `http://127.0.0.1:8765` after `aityuahn serve`

---

## Part 7 — GitHub Actions deploy (optional)

Like HyperlinksSpaceProgram `.github/workflows/vercel-deploy-test-envs.yml`.

Add GitHub repo secrets:

| Secret | From |
|--------|------|
| `VERCEL_TOKEN` | Vercel → Settings → Tokens |
| `VERCEL_ORG_ID` | `vercel whoami` / team settings |
| `VERCEL_PROJECT_ID` | Project → Settings → General |

Workflow: `.github/workflows/vercel-deploy.yml` (run manually or on push).

---

## Local dev matching production

**Terminal 1 — SaaS (Neon):**

```bash
export DATABASE_URL="postgresql://…-pooler.…neon.tech/neondb?sslmode=require"
export AITYUAHN_JWT_SECRET=dev-secret-change-me-32chars-min
python scripts/migrate_db.py
aityuahn serve-saas
```

**Terminal 2 — Local forge:**

```bash
aityuahn serve --demo
```

**UI config:**

```json
"defaultSaasApi": "http://127.0.0.1:8780",
"defaultForgeApi": "http://127.0.0.1:8765"
```

---

## What runs where (summary)

| Component | Host | Command / URL |
|-----------|------|----------------|
| Static UI | GitHub Pages | `hyperlinksspace.github.io/AityUahn` |
| Cloud SaaS API | Vercel | `api/index.py` |
| SaaS database | Neon | `DATABASE_URL` (pooled) |
| Schema migrate | Vercel build | `python scripts/migrate_db.py` |
| TON poll | Vercel Cron | `GET /api/cron/ton-poll` every 5 min |
| Local forge | User PC | `aityuahn serve` |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Build fails on migrate | Set `DATABASE_URL` in Vercel; use **pooled** Neon URL |
| `storage: "json"` in health | `DATABASE_URL` not visible to function — redeploy after setting env |
| Users disappear | You were on JSON `/tmp` before — ensure `storage: "neon"` |
| CORS / sign-in from Pages | Check `defaultSaasApi` matches Vercel URL exactly |
| TON 429 | Add `AITYUAHN_TONCENTER_API_KEY`; cron runs every 5 min not 10 sec |
| `Team members require Team plan` on invite | Owner must complete TON payment or use demo upgrade |

---

## Neon SQL editor (manual checks)

```sql
SELECT id, email, plan, created_at FROM saas_users ORDER BY created_at DESC LIMIT 10;
SELECT * FROM saas_projects;
SELECT * FROM saas_payments WHERE status = 'pending';
```

Or from CLI:

```bash
psql "$DATABASE_URL" -c "SELECT count(*) FROM saas_users;"
```
