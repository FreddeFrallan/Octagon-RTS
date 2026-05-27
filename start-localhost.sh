#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

export HOST="${HOST:-127.0.0.1}"
export PORT="${PORT:-8000}"

echo "Starting Octagon-RTS at http://localhost:${PORT}"
exec python3 backend/server.py
