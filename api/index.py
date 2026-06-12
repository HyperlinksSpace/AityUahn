"""Vercel serverless entry — cloud SaaS API only (not local forge).

Deploy from repo root:
  vercel
  vercel --prod

Set env vars in Vercel dashboard (see docs/DEPLOY_VERCEL.md).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Repo root on Vercel: api/ is one level below root
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("VERCEL", "1")
# DATABASE_URL must be set in Vercel project env (Neon pooled connection string).

from python.backend.saas_app import create_saas_app

app = create_saas_app()
