# CLAUDE.md - Aarogyam Pathology Lab Dashboard

Internal staff-only Django app for the Aarogyam Pathology network (ARP head centre, RRM, BHY).
Full feature, env and ops docs live in `README.md`; this file is the short working guide.

**Typography:** use a plain hyphen `-`, never the long em-dash, in new docs, comments and commits.

## Stack

Django 5.2 / Python 3.12, PostgreSQL 16, Celery + Redis, Gunicorn + Nginx, HTMX + Alpine +
Tailwind, Chart.js, Leaflet. Docker Compose for every deployed environment.

## Pipeline: laptop -> GitHub -> PowerEdge

| Where | Path | Git auth |
|---|---|---|
| Laptop (Windows) | `D:\Sites\labs` | HTTPS, Windows Credential Manager (same login as GrantSetu) |
| GitHub | `argajitsarkr/aarogyam-lab` (private) | - |
| Server (PowerEdge R730, Ubuntu, shared with GrantSetu) | `/home/mmilab/aarogyam` | read-only deploy key `~/.ssh/aarogyam_deploy` via host alias `github-aarogyam` |

1. Laptop: `.venv/Scripts/python -m pytest` must pass, then `git push origin main`.
2. Server (AnyDesk): `cd /home/mmilab/aarogyam && bash deploy.sh update`.

Never edit tracked files on the server - `deploy.sh update` refuses to run if you do.
The server's `~/.ssh/config` maps `github.com` to the **GrantSetu** key with `IdentitiesOnly`,
so the lab remote must stay `git@github-aarogyam:...`; plain `git@github.com:` will be denied.

## Server specifics

- Compose file: `docker-compose.server.yml` (project name `aarogyam`). Not `docker-compose.prod.yml`,
  which is for a standalone VPS with its own public IP and Let's Encrypt.
- nginx publishes **127.0.0.1:8090** only (`LAB_HTTP_PORT`). TLS is Cloudflare's; the existing
  GrantSetu tunnel gets one extra ingress rule (`docker/cloudflared-ingress.example.yml`).
  GrantSetu owns ports 3000 and 8000 - do not publish anything on them.
- Real client IP comes from `CF-Connecting-IP` (nginx tunnel template) into the audit log.
- Backups: `db_backup` container, daily 02:00 IST, 14 days, written to
  `/home/mmilab/aarogyam-backups` (outside the checkout). `.env` and the `private_media`
  volume (report PDFs) are not in those dumps - back them up separately.
- Migrations, collectstatic and seed commands run automatically when `web` starts.

## Local development

- Python is the uv venv at `.venv` (3.12). Run Python scripts with `PYTHONUTF8=1` on this laptop
  (cp1252 default otherwise).
- Local runs use SQLite and CDN assets when `DEBUG=True` (`.env` here is dev-only).
- `python manage.py create_demo_data` for fake data; refused when `DEBUG=False`.
- Tests: `python -m pytest` (69 tests; settings isolation in `conftest.py`).
- Docker Desktop on this laptop has been unreliable (engine stuck stopped); the full
  `docker compose up` stack has not yet been verified here.

## Rules worth keeping

- Centre scoping is enforced in querysets/permission checks (`apps/core/scoping.py`), never only in templates.
- Competitor prices are entered manually. No scrapers.
- Seeded test intervals/prices are placeholders flagged `needs_clinical_review`.
- No secrets in the repo: `.env` is gitignored; `.env.example` is the template.
