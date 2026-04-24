#!/usr/bin/env bash
# this_file: test.sh
set -euo pipefail
fd -e py -x uvx ruff check --output-format=github --fix {} 2>/dev/null || true
fd -e py -x uvx ruff format --respect-gitignore --target-version py312 {} 2>/dev/null || true
uvx hatch test
