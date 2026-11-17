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
- Public link, two optional containers, each switched on by its token in `.env`:
  - **ngrok** (`NGROK_AUTHTOKEN`, optional static `NGROK_URL`) - same approach as TGMA
    (`D:\Sites\Tgmabase`). `bash deploy.sh url` prints the address. A free ngrok account
    allows one online agent, so the lab and TGMA cannot share one token at the same time.
  - **Cloudflare tunnel** (`CLOUDFLARE_TUNNEL_TOKEN`) -> `http://nginx:80`, as phytosynergy.
  The host-level cloudflared service belongs to GrantSetu - do not edit it.
- No plain-HTTP LAN port (unlike TGMA's :8100): cookies are `Secure`, so login over
  `http://192.168.1.x` would fail (TGMA mistake #1). Use the tunnel, or an SSH port-forward.
- nginx is also on **127.0.0.1:8090** (`LAB_HTTP_PORT`) for checks over SSH. Host ports
  80, 3000, 7070, 8000, 8080, 8082, 8100 are other apps' - never publish on them.
- The server disk was 99% full (31 GB free) on 2026-11-17 - check `df -h /` before big builds.
- Real client IP comes from `CF-Connecting-IP` (nginx tunnel template) into the audit log.
- Backups: `db_backup` container, daily 02:00 IST, 14 days, written to
  `/home/mmilab/aarogyam-backups` (outside the checkout). `.env` and the `private_media`
  volume (report PDFs) are not in those dumps - back them up separately.
- Migrations, collectstatic and seed commands run automatically when `web` starts.

## Accounts

- **Site developer:** `argajit05@gmail.com` (username = email, like TGMA's named logins).
  Admin role + Django superuser = complete access, including `/system-admin/`. Listed in
  `DEVELOPER_ACCOUNTS` on the server, so it does **not** use one of the lab's 3 Admin slots.
  Its bootstrap password is `ADMIN_PASSWORD` in the server `.env`; it must be changed at
  first login, after which that line can be cleared.
- Lab Admins (max 3) and Employees (cap in Settings) are created in the app's Users page.

## Login (aligned with TGMA, `D:\Sites\Tgmabase\app\auth.py`)

- Username **or** 10-digit phone + password (`UsernameOrPhoneBackend`). One generic error for
  unknown user / bad password / inactive account - never reveal which.
- django-axes: 5 failures -> account locked **15 min** (`AXES_COOLOFF_HOURS=0.25`), per
  username not per IP (front desks share an IP). Locked attempts are refused before the
  password is checked; `accounts/locked.html` says how long. Admins can Unlock on Users.
- Forced change: `must_change_password` lets the user reach only the change form + logout.
  New password min **12** chars and must differ from the current one.
- Audit (`apps/audit/signals.py`, views): `LOGIN`, `LOGOUT`, `LOGIN_FAILED` (note gives the
  reason: unknown user / bad password / inactive account), `LOGIN_BLOCKED`,
  `PASSWORD_CHANGED`, all with the client IP.
- Session: 30-min idle, refreshed every request, HttpOnly + SameSite=Lax + Secure, cookies
  `aarogyam_session` / `aarogyam_csrftoken`. Logout is POST-only (TGMA uses GET).
- Production refuses to start with a placeholder or < 32-char `SECRET_KEY`.
- Tests: `conftest.py` turns axes off suite-wide; `apps/accounts/tests/test_login_flow.py`
  turns it back on to test the lockout.
- Not copied from TGMA yet: its Content-Security-Policy header (Alpine.js here needs
  `unsafe-eval`; every page would need re-checking).

## Local development

- Python is the uv venv at `.venv` (3.12). Run Python scripts with `PYTHONUTF8=1` on this laptop
  (cp1252 default otherwise).
- Local runs use SQLite and CDN assets when `DEBUG=True` (`.env` here is dev-only).
- `python manage.py create_demo_data` for fake data; refused when `DEBUG=False`.
- Tests: `python -m pytest` (80 tests; settings isolation in `conftest.py`). The `django-dev` preview runs with `--noreload` - restart it after code changes.
- Docker Desktop on this laptop has been unreliable (engine stuck stopped); the full
  `docker compose up` stack has not yet been verified here.

## Rules worth keeping

- Centre scoping is enforced in querysets/permission checks (`apps/core/scoping.py`), never only in templates.
- Competitor prices are entered manually. No scrapers.
- Seeded test intervals/prices are placeholders flagged `needs_clinical_review`.
- No secrets in the repo: `.env` is gitignored; `.env.example` is the template.
