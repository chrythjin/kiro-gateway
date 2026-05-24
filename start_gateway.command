#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

./start_gateway.sh

if [[ -t 0 ]]; then
  printf '\nPress Enter to close this window...'
  read -r _
fi
