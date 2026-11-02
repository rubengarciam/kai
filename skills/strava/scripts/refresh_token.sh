#!/usr/bin/env bash
# Kept so older instructions that say `bash refresh_token.sh` still work. The script is refresh_token.py now.
exec python3 "$(dirname "${BASH_SOURCE[0]}")/refresh_token.py" "$@"
