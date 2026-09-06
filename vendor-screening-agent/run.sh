#!/usr/bin/env bash
# AI Vendor / Legal-Entity Screening Agent - one-command launcher
# Usage:  ./run.sh        then open http://127.0.0.1:8000
set -e
cd "$(dirname "$0")"

echo "[1/2] Installing dependencies (first run only)..."
python3 -m pip install --quiet --disable-pip-version-check -r requirements.txt

echo "[2/2] Starting server on http://127.0.0.1:8000  (Ctrl+C to stop)"
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000
