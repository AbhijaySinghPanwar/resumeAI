#!/usr/bin/env bash
# run_backend.sh — Start the FastAPI backend server
set -e

cd "$(dirname "$0")"

echo ""
echo "  ┌─────────────────────────────────────┐"
echo "  │  ResumeAI Backend  ·  v7.0.0        │"
echo "  │  http://localhost:8000              │"
echo "  │  Docs → http://localhost:8000/docs  │"
echo "  └─────────────────────────────────────┘"
echo ""

# Install deps if needed
pip install fastapi uvicorn python-multipart pdfplumber rapidfuzz python-dateutil --break-system-packages -q 2>/dev/null || true

# Install the resumeai package if not already installed
pip install -e "$(dirname "$0")/../" --break-system-packages -q 2>/dev/null || \
pip install -e . --break-system-packages -q 2>/dev/null || true

uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
