#!/usr/bin/env bash
# run_backend.sh — Start the FastAPI backend server
set -e

cd "$(dirname "$0")"

echo ""
echo "  ┌─────────────────────────────────────┐"
echo "  │  TalentLens AI Backend  ·  v7.1.0   │"
echo "  │  http://localhost:8000              │"
echo "  │  Docs → http://localhost:8000/docs  │"
echo "  └─────────────────────────────────────┘"
echo ""

# Install deps if needed
pip install fastapi uvicorn python-multipart pdfplumber rapidfuzz python-dateutil \
    "sentence-transformers>=2.2.0" "numpy>=1.24.0" \
    --break-system-packages -q 2>/dev/null || true

# Install the resumeai package if not already installed
pip install -e "$(dirname "$0")/../" --break-system-packages -q 2>/dev/null || \
pip install -e . --break-system-packages -q 2>/dev/null || true

# Preload and validate the embedding model before starting server
echo "  → Preloading semantic embedding model (all-MiniLM-L6-v2)..."
python3 -c "
from resumeai.matching.embedding_engine import preload_model, is_available
preload_model()
if is_available():
    print('  ✓ Semantic embedding model loaded successfully.')
else:
    print('  ✗ WARNING: Embedding model failed to load — semantic scoring will be degraded.')
    exit(1)
" || {
    echo "  ✗ STARTUP FAILED: Could not load sentence-transformers model."
    echo "     Run: pip install sentence-transformers"
    exit 1
}

uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
