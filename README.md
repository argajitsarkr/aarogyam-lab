# Aarogyam Pathology — Internal Lab Management Dashboard

Internal-only Django dashboard for the Aarogyam Pathology lab network (Agartala, Tripura).
Covers centre-scoped patient registration, follow-ups, re-test calling, competitor price
comparison and multi-centre analytics.

**Stack:** Python 3.12 · Django 5.2 LTS · PostgreSQL 16 · Celery + Redis · Gunicorn + Nginx ·
HTMX + Alpine.js + Tailwind · Chart.js · Leaflet/OpenStreetMap.

---

## 1. Quick start (Docker, dev/evaluation)

```bash
docker compose up --build
```

Open **https://localhost** (self-signed certificate — accept the browser warning).

On first start the `web` container migrates, collects static files, seeds the 3 centres,
5 competitors and ~50 tests, and creates the first Admin:

| Username | Password |
|---|---|
| `admin` | `ChangeMe-Admin-2026` (you must change it at first login) |

Override with `ADMIN_USERNAME` / `ADMIN_PASSWORD` in a `.env` file. To also load fake demo
patients across all centres: `LOAD_DEMO_DATA=1 docker compose up`, or later
`docker compose exec web python manage.py create_demo_data`
(demo logins `demo_admin`, `arp_staff1`, `rrm_staff1`, `bhy_staff1`; password `Demo-Pass-2026!`).

Services: `web` (Gunicorn), `db` (Postgres 16), `nginx` (TLS, static, protected reports),
`redis`, `celery_worker`, `celery_beat`, `db_backup`.

## 2. Local development without Docker

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv -r requirements-dev.txt
cp .env.example .env      # then set DEBUG=True, a SECRET_KEY, CELERY_TASK_ALWAYS_EAGER=True, remove DATABASE_URL to use SQLite
python manage.py migrate
python manage.py create_demo_data
python manage.py runserver
```

With `DEBUG=True` and no built Tailwind bundle, pages load Tailwind/HTMX/Alpine from a CDN.
Production images build and self-host all assets (no CDN at runtime).

Run the tests:

```bash
python -m pytest
```

## 3. Environment variables (`.env`)

| Variable | Purpose |
|---|---|
| `DEBUG` | `False` in production. Demo data is refused unless `True`. |
| `SECRET_KEY` | Long random string. `python -c "import secrets;print(secrets.token_urlsafe(50))"` |
| `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` | Your domain(s); origins need `https://`. |
| `DATABASE_URL` | `postgres://user:pass@db:5432/name` |
| `POSTGRES_DB/USER/PASSWORD` | Used by the `db` and `db_backup` containers. |
| `REDIS_URL` | Celery broker + cache. |
| `PRIVATE_MEDIA_ROOT` | Report PDFs & imports (outside web root). |
| `USE_X_ACCEL_REDIRECT` | `True` behind Nginx — Nginx streams PDFs after Django authorises. |
| `MAX_ACTIVE_EMPLOYEES` | Initial employee cap (default 10; Admins can change it in Settings). |
| `DEVELOPER_ACCOUNTS` | Usernames with full Admin/superuser rights that do not count against the 3-Admin cap. |
| `NGROK_AUTHTOKEN`, `NGROK_URL` | Optional ngrok public link (server stack). |
| `CLOUDFLARE_TUNNEL_TOKEN` | Optional Cloudflare tunnel public link (server stack). |
| `SESSION_IDLE_SECONDS` | Idle timeout (default 1800 = 30 min). |
| `AXES_COOLOFF_HOURS` | Lockout duration after 5 failed logins. |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | First Admin, created on boot if missing. |
| `EMAIL_*` | Optional; daily reminder digests to staff (contain counts only, no patient data). |
| `BACKUP_KEEP_DAYS`, `BACKUP_HOUR` | Backup retention (14) and hour (02:00 IST). |
| `SERVER_NAME`, `LETSENCRYPT_EMAIL` | Production domain for Nginx / certificates. |

## 4. Users, roles and centres

* **Admin** (max 3 active, enforced in the model and forms): all centres, users, prices,
  settings, exports, imports, audit log, map, analytics, DPDP data requests.
* **Centre Employee** (cap configurable, default 10): bound to a home centre. Registers
  patients/visits only there; sees only patients linked to their centre. Admins can tick
  *Extra access* centres for read access to other centres' full records.

First admin by hand: `python manage.py create_first_admin`.
Add employees: **Admin → Users → Add user** (set role, home centre, temporary password —
they must change it at first login; min 12 characters, as on TGMA). Locked for 15 minutes after 5 failed attempts;
Admins can **Unlock** from the Users page.
Add/deactivate centres: **Admin → Centres**. The short code becomes the patient-ID prefix
(e.g. `ARP-2026-000123`) and is frozen once patients exist. Set latitude/longitude to show
the centre on the map; PIN-code map points live under *System admin → PIN code locations*.

**Cross-centre lookups:** the registration screen searches *all* centres by exact phone or
patient ID and shows only a minimal card (name, ID, last visit date/centre). Opening another
centre's full record without access returns **403** and writes an `ACCESS_DENIED` audit entry;
granted access writes `VIEW_CROSS_CENTRE`.

## 5. Key workflows

* **Register / New visit** — phone first → duplicate check → new patient or "Add new visit".
  Visits are always tagged to the employee's centre; the patient keeps one master record.
* **Results** — open a visit, set status/flag/summary, upload a PDF. *Abnormal* auto-creates a
  high-priority follow-up for that centre.
* **Follow-ups** — tabs Due today / Overdue / Upcoming / Completed; Table, Cards, Kanban
  (drag-and-drop) and Calendar (month/week/day). A return visit auto-completes open
  follow-ups and links the visit.
* **Re-test calling** — Celery beat runs daily at 06:00 IST (`generate_retest_candidates`
  management command runs it on demand). Due = report date + test's re-test interval, within
  the look-ahead window (default 7 days) or overdue; patient must have consent and not be
  Do Not Call; skipped if the test was repeated at any centre. Ranked Abnormal > Borderline >
  chronic monitoring > others, then days overdue; assigned round-robin (least-loaded) within
  the centre. "My Call List" has `tel:` links and one-tap outcomes. *Booked* creates a
  scheduled follow-up; the return visit marks it converted. *Do Not Call* is permanent.
* **Price comparison** — manual competitor prices (no scraping), "You save" vs cheapest and
  average, stale (>90 days) prices greyed with *re-check*, front-desk card, package totals,
  Admin grid editor and Excel upload.
* **Views** — Scope switcher (Admins: All centres / one centre; *Compare* page), Table/Card on
  every list, column chooser, 25/50/100 rows, saved & pinned filters. Preferences persist
  on the user profile.

## 6. Security & privacy (DPDP Act 2023)

* No public pages except login; `noindex` meta + `X-Robots-Tag` + `robots.txt`.
* HTTPS only in production, HSTS, secure cookies, CSRF, strict `ALLOWED_HOSTS`.
* Centre scoping enforced in querysets and permission checks, not templates.
* Audit log for create/update/soft-delete/export/import, logins, cross-centre views and
  denials, with user, centre, IP and field-level diff (Admin → Audit Log).
* Soft delete only from the UI. Contact consent is captured with a timestamp and required for
  any re-test calling.
* Data-principal requests: patient page → *Admin & data requests* → export JSON or erase
  personal data (irreversible; clinical/billing rows are kept de-identified). Both logged.
* Report PDFs stored outside the web root; served only via an authorised view + Nginx
  `internal` location.

## 7. Backups & restore

`db_backup` runs `pg_dump` (custom format) daily at `BACKUP_HOUR` IST into `./backups/`,
keeping `BACKUP_KEEP_DAYS` (14) days. Copy `./backups` off the server regularly
(e.g. `rclone` / `rsync` to another machine). Also back up the `private_media` volume (PDFs).

Manual backup now:

```bash
docker compose -f docker-compose.prod.yml exec db_backup /usr/local/bin/backup.sh
```

Restore (replaces current data — stop the app first):

```bash
docker compose -f docker-compose.prod.yml stop web celery_worker celery_beat
```

```bash
docker compose -f docker-compose.prod.yml exec -T db pg_restore --clean --if-exists --no-owner -U "$POSTGRES_USER" -d "$POSTGRES_DB" < backups/aarogyam_YYYYMMDD_HHMM.dump
```

```bash
docker compose -f docker-compose.prod.yml start web celery_worker celery_beat
```

Test a restore on a spare machine every few months.

## 8. Deploying on a single Ubuntu VPS

1. Ubuntu 22.04/24.04, 2 vCPU / 4 GB RAM is plenty. Point your domain's A record at the VPS.
2. Install Docker Engine + compose plugin (docs.docker.com/engine/install/ubuntu), then
   `sudo ufw allow 22,80,443/tcp && sudo ufw enable`.
3. Copy the project to `/opt/aarogyam`, then `cp .env.example .env` and fill in every value
   (`DEBUG=False`, strong `SECRET_KEY` and DB password, `SERVER_NAME`, `ALLOWED_HOSTS`,
   `CSRF_TRUSTED_ORIGINS`, `ADMIN_USERNAME`/`ADMIN_PASSWORD`).
4. Start: `docker compose -f docker-compose.prod.yml up -d --build`. Nginx boots with a
   temporary self-signed certificate.
5. Issue the real certificate (replace `lab.example.in` with your `SERVER_NAME`). Nginx keeps
   serving the self-signed cert it already loaded, so the HTTP challenge still works, but
   certbot refuses to write into an existing `live/` folder — remove the placeholder first:

   ```bash
   docker compose -f docker-compose.prod.yml run --rm --entrypoint sh certbot -c "rm -rf /etc/letsencrypt/live/lab.example.in"
   ```

   ```bash
   docker compose -f docker-compose.prod.yml run --rm --entrypoint certbot certbot certonly --webroot -w /var/www/certbot -d lab.example.in --email you@example.in --agree-tos --no-eff-email
   ```

   ```bash
   docker compose -f docker-compose.prod.yml restart nginx
   ```

   The self-signed fallback is only created when no certificate exists at
   `/etc/letsencrypt/live/$SERVER_NAME/`. The `certbot` service renews automatically.
6. Log in, change the admin password, set BeHealthy's address, add employees, review the
   test catalogue prices/intervals, and enter competitor prices.
7. Updates: `git pull && docker compose -f docker-compose.prod.yml up -d --build`
   (migrations run automatically on `web` start).

## 8b. Laptop push -> PowerEdge pull (current setup, behind Cloudflare Tunnel)

The lab runs on the shared PowerEdge R730 (`mmilab@100.126.84.75` over Tailscale), next to
GrantSetu, phytosynergy, tgma and mmilab. Like phytosynergy, it has **its own Cloudflare tunnel
container** in front of **its own nginx**: Cloudflare terminates HTTPS, the `tunnel` service
forwards to `http://nginx:80` inside the compose network, and no public host port is opened.
nginx is additionally published on `127.0.0.1:8090` for checks over SSH. No certbot, no sudo.

**Day-to-day**

```bash
python -m pytest            # on the laptop, before every push
git push origin main
```

then on the server:

```bash
ssh mmilab@100.126.84.75 "cd /home/mmilab/aarogyam && bash deploy.sh update"
```

`update` refuses to run if tracked files were edited on the server, fast-forwards to
`origin/main`, rebuilds, restarts and waits for `web` to be healthy (migrations run on start).
Other commands: `bash deploy.sh status | logs | backup | admin | down`.

**One-time server setup**

1. Read-only deploy key. GitHub will not reuse one deploy key on two repos, so - like
   `github-tgma` / `github-phytosynergy` already in the server's `~/.ssh/config` - this repo
   gets its own key and host alias:

   ```bash
   ssh-keygen -t ed25519 -C "aarogyam-server" -f ~/.ssh/aarogyam_deploy -N ""
   ```

   ```bash
   cat ~/.ssh/aarogyam_deploy.pub
   ```

   Paste it into GitHub -> repo -> Settings -> Deploy keys, title `aarogyam-server`,
   **Allow write access unticked**. Then:

   ```bash
   printf '\nHost github-aarogyam\n  HostName github.com\n  User git\n  IdentityFile ~/.ssh/aarogyam_deploy\n  IdentitiesOnly yes\n' >> ~/.ssh/config && chmod 600 ~/.ssh/config
   ```

   ```bash
   ssh -T github-aarogyam
   ```

2. Clone (note the alias instead of `github.com`):

   ```bash
   git clone git@github-aarogyam:argajitsarkr/aarogyam-lab.git /home/mmilab/aarogyam
   ```

3. `cd /home/mmilab/aarogyam && cp .env.example .env && chmod 600 .env`, then fill in:
   `DEBUG=False`, a new `SECRET_KEY`, `POSTGRES_PASSWORD` (and the same password inside
   `DATABASE_URL`), `ALLOWED_HOSTS=lab.example.in`, `CSRF_TRUSTED_ORIGINS=https://lab.example.in`,
   `ADMIN_USERNAME` / `ADMIN_PASSWORD`. Keep `LAB_HTTP_PORT=8090` unless that port is taken
   (`ss -ltnp | grep 8090`).
4. `bash deploy.sh up`, then `curl -sI http://127.0.0.1:8090/accounts/login/` should answer
   (a 301 to https is expected - Django sees every request as HTTPS).
5. Public link - pick one (both are optional containers switched on by a token in `.env`):

   **ngrok (as TGMA):** put `NGROK_AUTHTOKEN=...` in `.env` (optionally `NGROK_URL=` your
   free static domain), add `.ngrok-free.app` to `ALLOWED_HOSTS` and
   `https://*.ngrok-free.app` to `CSRF_TRUSTED_ORIGINS`, run `bash deploy.sh up`, then
   `bash deploy.sh url`. A free ngrok account allows one online agent at a time.

   **Cloudflare:** Cloudflare Zero Trust -> Networks -> Tunnels -> **Create a tunnel**
   (Cloudflared), name `aarogyam-lab`. Copy the token from the install command into `.env`
   as `CLOUDFLARE_TUNNEL_TOKEN=...`. Under **Public hostname** add the lab hostname with
   service type `HTTP` and URL `nginx:80`. Make sure `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS`
   contain that hostname, then `bash deploy.sh up` again (it starts the tunnel container
   once the token is present).
6. **Strongly recommended:** put a Cloudflare Access (Zero Trust) policy on the lab hostname
   that allows only staff emails. Patient data should not sit behind a login page alone.
7. Copy `.env` somewhere safe off the server; it is gitignored and not inside the DB backups.
   Database dumps land in `/home/mmilab/aarogyam-backups` (outside the checkout).

> The seeded test catalogue uses **placeholder prices and generic re-test intervals**, all
> flagged ⚕ *needs clinical review*. Have the pathologist confirm intervals before
> enabling calling.

## 9. Management commands

| Command | What it does |
|---|---|
| `seed_centres` | Aarogyam Pathology (ARP, head), Radha Rani MediClinic (RRM), BeHealthy (BHY). Idempotent. |
| `seed_competitors` | Agilus, Redcliffe, Dr Lal PathLabs, Metropolis, PathCare. |
| `seed_test_catalog` | ~54 common tests with re-test intervals (for clinical review). |
| `create_first_admin` | Interactive or `--noinput` via env vars. |
| `create_demo_data` | Fake patients/visits/calls across centres. **Blocked when `DEBUG=False`.** |
| `generate_retest_candidates` | Run the re-test scan now. |

## 10. Project layout

```
config/            settings, urls, celery
apps/core          scoping (Scope, CentreScopedQuerySet), list/view-mode mixins, preferences,
                   saved filters, calendar builder, site settings, middleware
apps/accounts      custom User (roles, caps, home centre), login by username/phone
apps/centres       Centre model + admin UI
apps/patients      Patient, Doctor, TestCatalog, Visit, VisitTest, import/export, DPDP
apps/followups     FollowUp + contact history, Kanban/Calendar
apps/retest        RetestCandidate, CallLog, generator, analytics
apps/pricing       Competitor, CompetitorPrice, comparison views
apps/dashboard     KPIs, centre comparison, charts, map
apps/audit         AuditLog + signal-based field diffs
docker/            entrypoint, nginx (TLS template), backup container
```
