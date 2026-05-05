#!/usr/bin/env bash
# =============================================================================
# build_for_deploy.sh — Build the public site only, no admin / api.
# =============================================================================
#
# Used by Cloudflare Pages (configure as the "Build command" in CF dashboard)
# and by anyone deploying manually.
#
# Why: admin and api pages need a Node.js runtime (file IO + ollama / gemini
# clients). Cloudflare Pages serves static HTML only, so we exclude those
# routes from the build entirely. They stay available locally via npm run dev.
# =============================================================================

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

EXCLUDE_DIR=".build_excluded"
mkdir -p "$EXCLUDE_DIR"

# Move admin/api out of src/pages/ before build
[ -d src/pages/admin ] && mv src/pages/admin "$EXCLUDE_DIR/" && echo "  · 排除 src/pages/admin"
[ -d src/pages/api ] && mv src/pages/api "$EXCLUDE_DIR/" && echo "  · 排除 src/pages/api"

# Restore on exit even if build fails
restore() {
  [ -d "$EXCLUDE_DIR/admin" ] && mv "$EXCLUDE_DIR/admin" src/pages/ 2>/dev/null
  [ -d "$EXCLUDE_DIR/api" ] && mv "$EXCLUDE_DIR/api" src/pages/ 2>/dev/null
  rmdir "$EXCLUDE_DIR" 2>/dev/null || true
}
trap restore EXIT

echo ""
echo "=== Building public site (Astro static) ==="
npm run build

echo ""
echo "✅ Build 完成 — 結果在 dist/"
