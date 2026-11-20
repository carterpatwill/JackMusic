#!/usr/bin/env bash
# Quigley Discovery — local dev launcher.
# Sets up the venv, installs deps, and starts the server with live reload.
#
#   ./run.sh              start the site at http://127.0.0.1:8000
#   ./run.sh --port 9000  start on a different port
#   ./run.sh refresh      take a stats snapshot from the CLI and exit
#   ./run.sh publish      sync seed.py's week into the DB (keep earlier weeks)
#
set -euo pipefail

cd "$(dirname "$0")"

VENV=".venv"
PY="$VENV/bin/python"

# 1. Create the venv on first run.
if [[ ! -x "$PY" ]]; then
  echo "→ Creating virtualenv in $VENV"
  python3 -m venv "$VENV"
fi

# 2. Install / update dependencies (quiet unless something changes).
#    Skip psycopg locally if it fails to build — it's only needed when
#    DATABASE_URL points at Postgres; local dev uses the SQLite data.db.
echo "→ Installing dependencies"
if ! "$PY" -m pip install -q -r requirements.txt 2>/dev/null; then
  echo "  (full install failed — installing core deps without psycopg)"
  "$PY" -m pip install -q "fastapi>=0.110" "uvicorn[standard]>=0.27" \
    "requests>=2.31" "python-dotenv>=1.0"
fi

# 3. Make sure there's a .env to read keys from.
if [[ ! -f .env ]]; then
  echo "→ No .env found — copying .env.example. Add your API keys to .env."
  cp .env.example .env
fi

# 4. Sub-commands.
case "${1:-}" in
  refresh)
    echo "→ Taking a stats snapshot (Spotify + YouTube)"
    exec "$PY" -m backend.refresh
    ;;
  publish)
    echo "→ Publishing seed.py's week into the DB"
    exec "$PY" -m backend.db --publish
    ;;
esac

# 5. Default: run the dev server.
PORT=8000
if [[ "${1:-}" == "--port" && -n "${2:-}" ]]; then
  PORT="$2"
fi

echo "→ Starting Quigley Discovery at http://127.0.0.1:$PORT  (Ctrl+C to stop)"
exec "$VENV/bin/uvicorn" backend.app:app --reload --port "$PORT"
