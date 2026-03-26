#!/usr/bin/env bash
# Tessellarium — Build and push backend container image to ACR
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/../backend"

echo "=== Building Tessellarium Backend ==="

# Build the Docker image
echo "Building Docker image..."
docker build -t tessellarium-backend:latest "$BACKEND_DIR"

echo ""
echo "Image built: tessellarium-backend:latest"
echo "To push to ACR, run:"
echo "  az acr login --name <registry-name>"
echo "  docker tag tessellarium-backend:latest <registry-name>.azurecr.io/tessellarium-backend:latest"
echo "  docker push <registry-name>.azurecr.io/tessellarium-backend:latest"
