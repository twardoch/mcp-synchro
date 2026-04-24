#!/usr/bin/env bash
# this_file: publish.sh
# Release mcp-synchro: commit → tag → build → push → publish.
#
# Usage:
#   ./publish.sh                # bumps patch of latest v* tag
#   ./publish.sh 1.2.3          # uses explicit version
#   ./publish.sh --dry-run      # builds without pushing or publishing

set -euo pipefail

DRY_RUN=0
VERSION=""
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        -h|--help)
            sed -n '2,11p' "$0"; exit 0 ;;
        *) VERSION="$arg" ;;
    esac
done

cd "$(dirname "$0")"

# --- sanity: must be on a clean-enough repo ---------------------------------
if ! git rev-parse --git-dir >/dev/null 2>&1; then
    echo "error: not a git repository" >&2; exit 1
fi

BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "▶ branch: $BRANCH"

# --- determine next version -------------------------------------------------
LAST_TAG=$(git tag --list 'v*' --sort=-v:refname | head -n1 || true)
if [[ -z "$VERSION" ]]; then
    if [[ -z "$LAST_TAG" ]]; then
        VERSION="0.1.0"
    else
        IFS='.' read -r MA MI PA <<<"${LAST_TAG#v}"
        VERSION="${MA}.${MI}.$((PA + 1))"
    fi
fi
TAG="v${VERSION}"
echo "▶ last tag: ${LAST_TAG:-<none>}"
echo "▶ new tag:  $TAG"

if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
    echo "error: tag $TAG already exists" >&2; exit 1
fi

# --- pull, then stage + commit any pending changes --------------------------
echo "▶ pulling from origin/$BRANCH..."
git pull --ff-only origin "$BRANCH" || true

if ! git diff --quiet || ! git diff --cached --quiet || [[ -n "$(git ls-files --others --exclude-standard)" ]]; then
    echo "▶ committing pending changes..."
    git add -A
    git commit -m "chore(release): $TAG"
else
    echo "▶ working tree clean; no commit needed"
fi

# --- tag HEAD so hatch-vcs produces a clean version -------------------------
echo "▶ tagging $TAG..."
git tag -a "$TAG" -m "$TAG"

# --- clean + build ----------------------------------------------------------
echo "▶ cleaning build artifacts..."
uvx hatch clean
rm -rf dist build

echo "▶ building..."
uvx hatch build

# sanity check: no dev/local version suffix
BUILT=$(ls dist/mcp_synchro-*.tar.gz 2>/dev/null | head -n1 || true)
if [[ -z "$BUILT" || "$BUILT" == *".dev"* || "$BUILT" == *"+g"* ]]; then
    echo "error: build produced unclean version: $BUILT" >&2
    git tag -d "$TAG" >/dev/null
    exit 1
fi
echo "▶ built: $BUILT"

if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "▶ dry-run: skipping push and publish"
    echo "▶ to undo the local tag: git tag -d $TAG"
    exit 0
fi

# --- push commits + tag, then publish --------------------------------------
echo "▶ pushing branch and tag to origin..."
git push origin "$BRANCH"
git push origin "$TAG"

echo "▶ publishing to PyPI..."
uv publish

echo "✓ released $TAG"
