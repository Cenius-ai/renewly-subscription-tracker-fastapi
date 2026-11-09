#!/usr/bin/env bash
# Renewly installer: dependencies -> schema -> demo seed.
# It never starts the HTTP server, so it is safe to run in scripts and CI.
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"

echo "==> Installing Python dependencies"
"$PYTHON" -m pip install --upgrade pip setuptools wheel
"$PYTHON" -m pip install -r requirements.txt

echo "==> Preparing .env"
if [ ! -f .env ]; then
  cp .env.example .env
  # generate per-install secrets (auto-added by cenius)
  _cenius_gen() { openssl rand -hex 32 2>/dev/null || (head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n'); }
  for _k in SECRET_KEY; do
    if grep -qiE "^${_k}=(<.*>|change[-_]?me.*|your[-_]secret|replace[-_]?me.*|[[:space:]]*)$" .env 2>/dev/null; then
      sed -i "s|^${_k}=.*|${_k}=$(_cenius_gen)|" .env; fi
  done
fi
if grep -q '^SECRET_KEY=..*' .env; then
  echo "    SECRET_KEY already present; keeping it."
else
  key="$("$PYTHON" -c 'import secrets; print(secrets.token_hex(32))')"
  grep -v '^SECRET_KEY=' .env > .env.tmp || true
  printf 'SECRET_KEY=%s\n' "$key" >> .env.tmp
  mv .env.tmp .env
  echo "    Generated a fresh session key in .env"
fi

echo "==> Creating the database schema"
"$PYTHON" -c "from app.db import init_db; init_db(); print('    schema ready')"

echo "==> Seeding the demo accounts"
"$PYTHON" -m app.seed

echo "==> Self-check"
"$PYTHON" -c "import app.main; print('    import app.main: ok')"

printf '\nSetup complete. Start Renewly with:\n\n'
printf '    sh start.sh\n'
printf '    # or: python3 -m uvicorn main:app --host 0.0.0.0 --port 8000\n\n'
printf 'Demo login: cenius@cenius.ai / cenius\n'
