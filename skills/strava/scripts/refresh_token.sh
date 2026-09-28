#!/usr/bin/env bash
# Refresh Strava access token and write back to credentials store.
#
# Credentials are read from (in priority order):
#   1. Environment variables (STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, STRAVA_REFRESH_TOKEN)
#   2. ~/.config/strava/credentials.json
#
# On success, new tokens are written back to ~/.config/strava/credentials.json.

set -e

CREDENTIALS_FILE="$HOME/.config/strava/credentials.json"

# --- Read from credentials.json if env vars not already set ---
if [ -z "$STRAVA_CLIENT_ID" ] || [ -z "$STRAVA_CLIENT_SECRET" ] || [ -z "$STRAVA_REFRESH_TOKEN" ]; then
  if [ -f "$CREDENTIALS_FILE" ]; then
    eval "$(python3 - "$CREDENTIALS_FILE" <<'EOF'
import json, sys

creds_path = sys.argv[1]
with open(creds_path) as f:
    env = json.load(f)

for key in ["STRAVA_CLIENT_ID", "STRAVA_CLIENT_SECRET", "STRAVA_REFRESH_TOKEN", "STRAVA_ACCESS_TOKEN"]:
    val = env.get(key, "")
    if val:
        print(f'export {key}="{val}"')
EOF
)"
  fi
fi

# --- Validate we have what we need ---
if [ -z "$STRAVA_CLIENT_ID" ] || [ -z "$STRAVA_CLIENT_SECRET" ] || [ -z "$STRAVA_REFRESH_TOKEN" ]; then
  echo "Error: Missing Strava credentials."
  echo "Set environment variables or create ~/.config/strava/credentials.json with:"
  echo "  STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, STRAVA_REFRESH_TOKEN"
  exit 1
fi

# --- Call Strava token endpoint ---
RESPONSE=$(curl -s -X POST https://www.strava.com/oauth/token \
  -d client_id="$STRAVA_CLIENT_ID" \
  -d client_secret="$STRAVA_CLIENT_SECRET" \
  -d grant_type=refresh_token \
  -d refresh_token="$STRAVA_REFRESH_TOKEN")

NEW_ACCESS_TOKEN=$(echo "$RESPONSE" | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)
NEW_REFRESH_TOKEN=$(echo "$RESPONSE" | grep -o '"refresh_token":"[^"]*' | cut -d'"' -f4)
EXPIRES_AT=$(echo "$RESPONSE" | grep -o '"expires_at":[0-9]*' | cut -d':' -f2)

if [ -z "$NEW_ACCESS_TOKEN" ]; then
  echo "Error: Token refresh failed"
  echo "$RESPONSE"
  exit 1
fi

echo "✓ Token refreshed successfully"
echo "  Expires at: $(date -d "@$EXPIRES_AT" 2>/dev/null || date -r "$EXPIRES_AT" 2>/dev/null || echo "$EXPIRES_AT")"

# --- Write new tokens back to ~/.config/strava/credentials.json ---
python3 - <<EOF
import json, os

creds_path = os.path.expanduser("~/.config/strava/credentials.json")

if not os.path.exists(creds_path):
    print("Warning: ~/.config/strava/credentials.json not found, skipping write-back.", file=__import__('sys').stderr)
    exit(0)

with open(creds_path) as f:
    creds = json.load(f)
creds["STRAVA_ACCESS_TOKEN"] = "$NEW_ACCESS_TOKEN"
creds["STRAVA_REFRESH_TOKEN"] = "$NEW_REFRESH_TOKEN"
tmp = creds_path + ".tmp"
with open(tmp, "w") as f:
    json.dump(creds, f, indent=4)
os.replace(tmp, creds_path)
print(f"✓ Updated {creds_path}")
EOF
