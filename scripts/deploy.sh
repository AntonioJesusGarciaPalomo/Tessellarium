#!/usr/bin/env bash
# Tessellarium — Deploy infrastructure and services to Azure
set -euo pipefail

echo "=== Tessellarium Deploy ==="

# Check prerequisites
command -v azd >/dev/null 2>&1 || { echo "Error: azd CLI not found. Install from https://aka.ms/azd"; exit 1; }
command -v az >/dev/null 2>&1 || { echo "Error: az CLI not found. Install from https://aka.ms/installazurecli"; exit 1; }

# Provision and deploy
echo "Provisioning Azure resources and deploying services..."
azd up

echo ""
echo "=== Deployment complete ==="
echo "Run 'azd show' to see your deployed endpoints."
