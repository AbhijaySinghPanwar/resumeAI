#!/usr/bin/env bash
# run_frontend.sh — Serve the frontend with Python's built-in HTTP server
set -e

cd "$(dirname "$0")/frontend"

PORT=3000
echo ""
echo "  ┌─────────────────────────────────┐"
echo "  │  ResumeAI Frontend  ·  v7.0.0   │"
echo "  │  http://localhost:${PORT}          │"
echo "  └─────────────────────────────────┘"
echo ""
echo "  Open http://localhost:${PORT} in your browser"
echo "  Make sure the backend is running on http://localhost:8000"
echo ""

python3 -m http.server $PORT
