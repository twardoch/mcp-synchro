#!/usr/bin/env bash
# this_file: publish.sh
# Publish mcp-synchro to PyPI
set -euo pipefail

echo "Building mcp-synchro..."
uvx hatch build

echo "Publishing to PyPI..."
uv publish

echo "Done!"
