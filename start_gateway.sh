#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x ".venv/bin/python" ]]; then
    PYTHON_BIN=".venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  else
    PYTHON_BIN="python"
  fi
fi

HOST="${KIRO_GATEWAY_HOST:-127.0.0.1}"
PORT="${KIRO_GATEWAY_PORT:-8000}"

"$PYTHON_BIN" scripts/ensure_gateway.py \
  --gateway-dir "$SCRIPT_DIR" \
  --python "$PYTHON_BIN" \
  --host "$HOST" \
  --port "$PORT"

printf '\nKiro Gateway is ready.\n'
printf 'Base URL: http://%s:%s\n' "$HOST" "$PORT"
printf 'OpenAI-compatible URL: http://%s:%s/v1\n' "$HOST" "$PORT"
printf 'Logs: %s/.kiro-gateway/gateway.log\n' "$SCRIPT_DIR"
