#!/bin/sh
# startup.sh
# Creates DB tables if they don't exist, then starts the dashboard.
# Does NOT generate sample data — the real DB (4841 reviews) is shipped with the repo.

set -e

echo "[startup] Ensuring DB tables exist..."
python - <<'EOF'
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent if '__file__' in dir() else Path('.').resolve()))
from storage.db import get_engine, init_db
init_db()
print("[startup] Tables OK.")
EOF

echo "[startup] Starting dashboard..."
exec python dashboard/app.py
