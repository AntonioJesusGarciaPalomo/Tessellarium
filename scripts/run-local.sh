#!/usr/bin/env bash
# Tessellarium — Run locally for development
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$SCRIPT_DIR/.."

echo "=== Tessellarium Local Development ==="

# Check for .env
if [ ! -f "$ROOT_DIR/backend/.env" ]; then
  echo "Warning: backend/.env not found. Copying from template..."
  cp "$ROOT_DIR/backend/.env.template" "$ROOT_DIR/backend/.env"
  echo "Edit backend/.env with your Azure credentials before using LLM features."
  echo ""
fi

# Start backend
echo "Starting backend on http://localhost:8000 ..."
cd "$ROOT_DIR/backend"
pip install -r requirements.txt --quiet
uvicorn main:app --reload --host 0.0.0.0 --port 8000
