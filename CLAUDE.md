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
| Server (PowerEdge R730, Ubuntu, shared) `mmilab@100.126.84.75` | `/home/mmilab/aarogyam` | read-only deploy key `~/.ssh/aarogyam_deploy` via host alias `github-aarogyam` |

1. Laptop: `.venv/Scripts/python -m pytest` must pass, then `git push origin main`.
2. Server: `ssh mmilab@100.126.84.75 "cd /home/mmilab/aarogyam && bash deploy.sh update"`.

Never edit tracked files on the server - `deploy.sh update` refuses to run if you do.
The server's `~/.ssh/config` has one alias per repo (github-tgma, github-phytosynergy, ...),
so the lab remote must stay `git@github-aarogyam:...`; plain `git@github.com:` will be denied.

## Server specifics

- Compose file: `docker-compose.server.yml` (project name `aarogyam`). Not `docker-compose.prod.yml`,
  which is for a standalone VPS with its own public IP and Let's Encrypt.
- SSH: `ssh mmilab@100.126.84.75` (Tailscale) works from this laptop with the default key;
  `mmilab` can run docker but `sudo` needs a password.
- Public link: own `tunnel` (cloudflared) container -> `http://nginx:80`, token in `.env` as
  `CLOUDFLARE_TUNNEL_TOKEN` (same pattern as phytosynergy). `deploy.sh` adds the `tunnel`
  profile only when the token is set. The host-level cloudflared service belongs to GrantSetu.
- nginx is also on **127.0.0.1:8090** (`LAB_HTTP_PORT`) for checks over SSH. Host ports
  80, 3000, 7070, 8000, 8080, 8082, 8100 are other apps' - never publish on them.
- The server disk was 99% full (31 GB free) on 2026-11-17 - check `df -h /` before big builds.
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
