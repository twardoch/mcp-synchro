#!/usr/bin/env bash
# install.sh — Install mcp-synchro locally
# mcp-synchro synchronizes MCP server configurations across 20+ AI agents and tools
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Installing mcp-synchro..."
uv pip install -e . 2>/dev/null || pip install -e . 2>/dev/null || echo "Install failed"
echo "Done."
