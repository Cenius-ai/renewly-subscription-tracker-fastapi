#!/usr/bin/env bash
# Start the Renewly web server on 0.0.0.0:$PORT (default 8000).
set -euo pipefail
cd "$(dirname "$0")"
exec "${PYTHON:-python3}" -m uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
