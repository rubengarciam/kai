#!/usr/bin/env bash
# Garmin Health Analysis - dependency installer
# Run from anywhere. Installs the packages listed in the Kai repo's requirements.txt
# into ./.venv at the repo root (Python 3.12+ required).

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "🏃 Installing Garmin Health Analysis dependencies..."
echo

if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is required but not found"
    exit 1
fi

if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)'; then
    echo "❌ Python 3.12+ is required (found $(python3 --version))."
    echo "   Get a 3.12 environment with uv: https://docs.astral.sh/uv/ (see the top-level README)"
    exit 1
fi

echo "✓ Python found: $(python3 --version)"

python3 -m venv "$REPO_ROOT/.venv"
"$REPO_ROOT/.venv/bin/pip" install -r "$REPO_ROOT/requirements.txt"

echo
echo "✅ Installation complete!"
echo
echo "Next steps:"
echo "  1. Log in (run this yourself in a terminal; it asks for your password):"
echo "     $REPO_ROOT/.venv/bin/python3 $REPO_ROOT/skills/garmin-health-analysis/scripts/garmin_auth.py login"
echo
echo "  2. Test:"
echo "     $REPO_ROOT/.venv/bin/python3 $REPO_ROOT/skills/garmin-health-analysis/scripts/garmin_data.py summary --days 7"
