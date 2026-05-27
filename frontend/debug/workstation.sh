#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8010}"

usage() {
  cat <<EOF
Usage: $(basename "$0") [--port PORT] [--host HOST]

Starts the unit workstation at /debug/.

Options:
  -p, --port PORT   Port to bind. Defaults to PORT env var or 8010.
      --host HOST   Host to bind. Defaults to HOST env var or 127.0.0.1.
  -h, --help        Show this help message.

Examples:
  $(basename "$0") --port 8011
  $(basename "$0") -p 3000 --host 0.0.0.0
  PORT=8012 $(basename "$0")
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -p|--port)
      if [[ $# -lt 2 || "$2" == -* ]]; then
        echo "Error: $1 requires a port value." >&2
        usage >&2
        exit 2
      fi
      PORT="$2"
      shift 2
      ;;
    --port=*)
      PORT="${1#*=}"
      shift
      ;;
    --host)
      if [[ $# -lt 2 || "$2" == -* ]]; then
        echo "Error: $1 requires a host value." >&2
        usage >&2
        exit 2
      fi
      HOST="$2"
      shift 2
      ;;
    --host=*)
      HOST="${1#*=}"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    -*)
      echo "Error: unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      if [[ "${PORT_SET_FROM_POSITIONAL:-0}" == "1" ]]; then
        echo "Error: unexpected argument: $1" >&2
        usage >&2
        exit 2
      fi
      PORT="$1"
      PORT_SET_FROM_POSITIONAL=1
      shift
      ;;
  esac
done

if ! [[ "$PORT" =~ ^[0-9]+$ ]] || (( PORT < 1 || PORT > 65535 )); then
  echo "Error: port must be a number from 1 to 65535." >&2
  exit 2
fi

echo "Starting unit workstation at http://${HOST}:${PORT}/debug/"
python3 -m http.server "${PORT}" --bind "${HOST}"
