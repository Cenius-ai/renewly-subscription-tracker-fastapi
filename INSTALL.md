# Installing Renewly

Renewly runs as a single Python process with an embedded SQLite database. There is no
external database, cache, queue or email service to configure.

## Prerequisites

- Python **3.11 or newer** (`python3 --version`)
- pip (`python3 -m pip --version`)
- A POSIX shell for the helper scripts (Linux, macOS, WSL)

SQLite is part of the Python standard library; nothing else is required.

## 1. Install dependencies, create the schema and seed demo data

```bash
sh install.sh
```

`install.sh` installs `requirements.txt` with pip, copies `.env.example` to `.env` if you do
not have one, generates a random `SECRET_KEY` into `.env`, creates the database tables and
runs the idempotent demo seed. It **exits** when finished — it never starts the web server,
so it is safe to run in a setup script or CI job.

Prefer doing it by hand? The same steps:

```bash
python3 -m pip install --upgrade pip setuptools wheel
python3 -m pip install -r requirements.txt
python3 -c "from app.db import init_db; init_db()"
python3 -m app.seed
```

## 2. Run the app

```bash
sh start.sh                              # honours $PORT, defaults to 8000
# or
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Open <http://localhost:8000>. You should land on the sign-in page with the demo credentials
shown on the card.

## 3. Sign in

| Email | Password | What it shows |
| --- | --- | --- |
| `cenius@cenius.ai` | `cenius` | Ten subscriptions across Streaming, SaaS, Music, Gaming, Fitness, News and Cloud in USD, GBP and EUR, with two cancelled |
| `demo@renewly.app` | `demo1234` | Five subscriptions, including one cancelled |

## Configuration

All configuration is optional. Put values in `.env` (loaded at boot) or in the environment.

```dotenv
SECRET_KEY=            # session signing key; empty = documented dev key
DATABASE_URL=sqlite:///./renewly.db
RENEWLY_RATE_LIMIT=on  # failed-login throttle; 'off' only for test runs
PORT=8000              # read by start.sh, not by the app
```

`DATABASE_URL` may point at any SQLAlchemy-compatible database, but SQLite is the only one
Renewly is tested against and the only one the defaults assume. The path in the default URL
is relative to the directory you start the app from (the project root when using
`start.sh`).

## Running the tests

```bash
python3 -m pytest
```

The suite uses a temporary SQLite database, disables the login throttle, and makes no
network calls.

## Upgrading

```bash
git pull
sh install.sh    # re-installs deps, re-creates missing tables, re-runs the idempotent seed
sh start.sh
```

The seed only inserts rows that are missing, so restarting never duplicates demo data.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `ModuleNotFoundError: fastapi` | Run `python3 -m pip install -r requirements.txt` from the project root. |
| `Address already in use` | Another process holds the port: `PORT=8001 sh start.sh`. |
| Login page appears but sign-in fails | Check the credentials table above; the seed prints what it created when you run `python3 -m app.seed`. |
| Data looks empty | The seed runs on boot; if you deleted rows, run `python3 -m app.seed` again. |
| Session drops immediately | If you put the app behind HTTPS, keep cookies working end-to-end (the cookie is `HttpOnly`, `SameSite=Lax`, not `Secure`, so plain-HTTP self-hosting works). |
