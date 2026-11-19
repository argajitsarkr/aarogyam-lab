# CLAUDE.md - Aarogyam Pathology Lab Dashboard

Internal staff-only Django app for the Aarogyam Pathology network (ARP head centre, RRM, BHY).
Full feature, env and ops docs live in `README.md`; this file is the short working guide.

**Typography:** use a plain hyphen `-`, never the long em-dash, in new docs, comments and commits.

## Stack

Django 5.2 / Python 3.12, PostgreSQL 16, Celery + Redis, Gunicorn + Nginx, HTMX + Alpine +
Tailwind, Chart.js, Leaflet. Docker Compose for every deployed environment.

**Fonts and icons are Google's**, loaded from `fonts.googleapis.com` in `templates/_assets.html`:
**Inter** for all UI text (Tailwind's `sans`), **Space Grotesk** for headings
(Tailwind's `display`) and **Material Symbols Rounded** for every icon.

**The type scale is four steps**, defined once in `_components.css`: `.page-title` 28px,
`.section-title` 19px and `.subsection-title` 16px in Space Grotesk 600, Inter 14px body, and
11px bold uppercase labels (`.filter-label`, `.stat-label`). Headings carry only
`.section-title` / `.subsection-title` - never a `font-*` or `text-*` utility beside them,
which would pin the heading back to body size and weight. Figures stay in Inter:
`.stat-value`, `.rcard-number` and `.kpi-value` override the family for its tabular numerals.
Before this the scale was 18/16/14 at one weight and read as one size. No emoji in templates - use the `{% icon %}` tag (`apps/core/templatetags/ui.py`)
with the Material Symbols ligature name. Icons are `aria-hidden`, so each needs visible text
or an `aria-label`. Arrows that are data rather than decoration (audit diffs, status changes)
stay as text characters.

**The icon font is SUBSET** via `icon_names=` in that link: the whole font is 3 MB, our ~46
icons are ~15 KB. `apps/core/tests/test_icons.py` fails if the list and the `{% icon %}` tags
drift apart, in either direction, or if the list stops being alphabetical - an icon missing
from the subset renders as its own name in plain text.

**Multi-line `{# ... #}` is NOT a comment** in Django: only the first line is dropped and the
rest renders as text and is parsed as tags. It has leaked onto a page twice. Use
`{% comment %}`; `apps/core/tests/test_template_comments.py` enforces it.

**Palette: Electric Blue on a neutral shell** - `#86FAF2 #30E7ED #00A6D7 #0058B3 #001B87`
on a `#F0F0F2` canvas with white cards and a **white sidebar**. The shell stays quiet; the
blues carry everything you can act on. Which blue is not taste: white text needs 4.5:1 and
only the bottom two clear it (`#0058B3` 6.9:1 for buttons and links, `#001B87` 13.9:1 for
table headers and the gradient end). `#00A6D7` is 2.8:1, so it is a non-text accent only,
and the aqua pair are tints. Red, amber and green are untouched - an abnormal result must
never read as neutral.
The ramps live in **two** places, because the DEBUG CDN build cannot read
`tailwind.config.js`: that file, and an inline `tailwind.config` in `_assets.html`.
`apps/core/tests/test_theme.py` fails if they drift. Tailwind's `teal` ramp is redefined as
the blues and `slate` as neutral greys, rather than rewriting the utilities in forty
templates, so every existing `bg-teal-700` / `text-slate-500` follows the palette.

**A visit does not need a test.** The front desk often does not yet know what was run, so
`VisitForm.tests` is optional (the Excel importer always allowed this). Tests are added to an
existing visit from the visit page - `AddVisitTestsForm`, posted with `add_tests`, in its own
`<form>` outside the results grid, since nested forms are invalid HTML and the browser drops
the inner one. A visit with no tests simply never produces a re-test candidate.

**Centre colours** come from the retro VHS palette: ARP `#7B2D56` plum, RRM `#D6303A` red,
BHY `#F4873A` orange. They are editable per centre, so `{% centre_badge %}` computes its own
text colour (`readable_ink` in `apps/core/templatetags/ui.py`) instead of assuming white -
white on the orange is 2.5:1, near-black on it is 7.9:1. `seed_centres` only fills in centres
that do not exist, so a colour change needs a data migration (`centres/0002`), which repaints
only centres still holding the old default.

**No money anywhere.** The lab earns a commission from the partner labs, so the app records
no billing: `Visit` has no `total_amount` / `discount` / `amount_paid` / `payment_mode`,
`VisitTest` has no `price_charged`, and no screen shows revenue. `TestCatalog.price` stays -
the price-comparison screens are the whole point of it.

**Design tokens live in `:root` at the top of `templates/_components.css`** - colours, radius,
shadow, sidebar widths, font stack. Change the theme there, not in the templates. The component
classes (`.card`, `.btn`, `.tbl`, `.filter-panel`, `.pill-filter`, `.rcard`, `.stat-band`) are
built from those tokens.

**Layout patterns, taken from PhytoSynergyDB (`D:\Sites\Projects`) in 2026-11-18:**
- Sidebar collapses to an icon rail (`#sidebar.rail`), remembered per user in the
  `ui:sidebar_rail` preference. Its width must set `flex-basis` as well as `width`: it is a
  flex item, and a flex item's default `min-width: auto` otherwise refuses to shrink below
  its content, so `width` alone does nothing.
- Each page has a one-line `{% block page_subtitle %}` under its title.
- Lists use `core/_filter_form.html`: a tinted `.filter-panel`, uppercase micro-labels, the
  most-used filter as one-click pills (the filterset names it in `pill_field`), then the rest
  as selects, then Clear / Apply. The pills are hidden radios inside their labels so they work
  by keyboard and without JS; `:has(input:checked)` paints the active one, because HTMX
  swaps only the results and never re-renders the form.
- `core/_results_head.html` sits above every result list ("Showing 1-25 of 2,088 patients").
  The noun comes from the view's `results_label`.
- Tables go in `.tbl-wrap` (rounded, clipped, dark header row).
- The call list uses `.rcard`: badge, title, then the one number that decides the work (days
  overdue) in `.rcard-number`, then an `.action-bar` of small outline buttons.
- The dashboard uses `.stat-band` - big figure over a small caps label, no box per figure.

The two webfonts are the only runtime CDN dependency: if the lab ever needs to run without
reaching Google, self-host them and change that one `<link>`.

## Two halves: public site and staff app

Since Phase 0 (2026-11-19) the url tree is split, and the split is by **path prefix** so
the login gate, the no-index header and `robots.txt` can tell the halves apart without
knowing every view:

- **`/staff/...`** - the whole internal app (dashboard, patients, followups, retest,
  pricing, audit, core). `/accounts/` and `/system-admin/` sit outside `/staff/` but count
  as staff: `is_staff_area()` in `apps/core/middleware.py` is the single rule, and
  `LoginRequiredMiddleware` and `NoIndexMiddleware` both use it. Only `/accounts/login/`
  and `/accounts/locked/` are reachable without a session.
- **`/`** - `apps.public`, which owns the rest of the tree. It is open, indexable and gets
  no `no-store`. Its include is **last** in `config/urls.py` so it cannot shadow the
  staff prefixes. Today it is one placeholder page (`templates/public/home.html`) on its
  own shell (`templates/public/base.html`) - Phase 1 replaces it.

**The two halves do not share a typeface.** The public site uses 1mg's own pairing -
**Poppins** for everything you read, **Figtree** 700 for everything you act on (buttons,
the nav ribbon, chips, the callback bar) - at 1mg's measured scale: 14px/1.5 body, 20px/600
section headings, 12px uppercase nav. Both are Google Fonts / OFL. The tokens are
`--font-public` / `--font-public-ui` and the `.pub-*` classes at the foot of
`_components.css`, all scoped to `body.public` so none of it reaches the staff app, which
keeps Inter / Space Grotesk. Only the public shell loads the two faces.
Poppins is a geometric face with no tabular figures and a narrow 1/l distinction, which is
fine for a brochure page and wrong for a dense result table - that is the reason for the
split, not taste. `.pub-h1` is 36px where 1mg's largest text is 20px, because their hero is
an image with the words baked in and ours is real text.

`robots.txt` now disallows only `/staff/`, `/accounts/` and `/system-admin/` instead of
the whole site, and points at `/sitemap.xml`. `apps/public/tests/test_routing.py` asserts
both halves.

**The nginx blanket `X-Robots-Tag` is gone** (it used to sit at server level in both
templates). It was right while everything was private and wrong the moment the public site
existed: it would have made every public page unindexable while Django said the opposite,
with nothing in the app to explain why. `NoIndexMiddleware` is now the only thing that
sets it. Note that nginx drops inherited `add_header`s inside any location that sets one
of its own, which is why `/media/` repeats `nosniff`.

**nginx still blankets the whole server with `X-Robots-Tag: noindex` (line 28 of
`docker/nginx/tunnel/default.conf.template`), which masks Django's rule.** That is right
while the public side is a placeholder, and it is the one thing that must be narrowed to
the staff locations before the public site goes live - otherwise the new pages ship
unindexable and the cause is invisible from the Django side.

Nothing in the staff templates hardcodes a path - every link is `{% url %}`, so the move
needed no template edits. `SavedFilter.get_absolute_url()` reverses by view name too, so
filters saved before the split still resolve.

## The public site (`apps/public`, label `public_site`)

A shop window, not a shop: **no cart, no payment, no patient login.** Everything a visitor
can do ends in one `Enquiry` row that the staff work from `/staff/enquiries/` and act on by
phone, which is how the lab already runs. The 1mg patterns we took are the sticky callback
bar, the three booking channels (phone / prescription upload / WhatsApp), the need-based
concern tiles and the trust row; what we did not take is their cart, checkout, payments,
patient logins and analytics stack.

- **Published is a separate switch from active.** `Centre.is_public` and
  `TestCatalog.is_public` both default **False**, so nothing reaches the public site until
  someone turns it on. An unpublished centre or test is a 404, not a hidden listing -
  there are tests for exactly that.
- **The site never invents a fact.** Phone number, WhatsApp, opening hours, licence number
  and pharmacist name all live on `SiteSettings` / `Centre` and every block that uses one
  is wrapped in an `{% if %}`. `seed_public_content` seeds only structure (health concerns,
  medicine aisles) and says so when it finishes. An empty field means a hidden block, never
  a placeholder.
- **Partner prices, no recommendation.** The test page lists every partner's price cheapest
  first and nothing else - no "our price", no cheapest-wins badge, no "you save". A test
  asserts those words do not appear in the rendered page, because this is the rule most
  likely to be undone by someone trying to be helpful.
- **Prescriptions are medical documents.** They go to `PRIVATE_MEDIA_ROOT` through
  `PrivateFileSystemStorage` and are served only by the staff-only view, via
  `X-Accel-Redirect` in production. `FileSystemStorage(base_url=None)` does **not** give
  you a private file - `base_url` falls back to `settings.MEDIA_URL`, so the moment
  MEDIA_URL existed a prescription started reporting a `/media/...` url. The subclass
  forces the property to None so `.url` raises again.
- **Two media roots, and they are not interchangeable.** `MEDIA_ROOT` (`/media/`, nginx
  serves it) is for centre and doctor photos *only*. Nothing patient-related may be written
  there.
- **The form variant is read from the POST, not `initial`.** `EnquiryForm.is_prescription`
  looks at `self.data` first: on a re-render after a failed submit there is no `initial`,
  and a template keyed off it drops the file input along with the error telling the visitor
  to attach the prescription. Same family of bug as the prefix one below.
- **The no-JS path redirects with messages.** Django's own `form_invalid` would re-render
  with a *fresh, unbound* form and silently lose every error.
- The form field for `phone` is declared **wider** than the model's 10 characters on
  purpose: `max_length` runs before `clean_phone`, so inheriting it would reject
  "+91 98765 43210" before there was a chance to strip it.

- **The logo is a white wordmark on its own blue field** (`static/img/aarogyam-logo.png`,
  the long lockup; `aarogyam-mark.png` is the square one). It is shown as the block it is -
  rounded corners, no padding - rather than knocked out onto white, because the artwork
  carries its own background. It already reads "aarogyam pathology", so the only text
  beside it in the header is the line it does not carry: "Agartala, Tripura".
- **Agartala first, then Tripura.** Somebody searching "blood test near me" needs their own
  city in the first line, and the h1 is "Agartala's trusted pathology lab". "Trusted" is a
  claim about the people who already come, not an accreditation the lab may not hold - keep
  it that way.
- **The rotating banner strip is rows, not markup** (`Banner`, `templates/public/_banners.html`).
  The lab changes a camp or a package far more often than anything else on the site. An image
  is optional: with none the slide is a coloured panel whose ink comes from `readable_ink`, so
  an editable accent can never produce white-on-aqua. Two traps already hit:
  **`overflow: hidden` must not go on the element being translated** - the track carries its
  own clip box along and every slide but the first disappears; the wrapper does the clipping.
  And a **seeded link must be `reverse()`d, not typed** - `/prescription/` is really
  `/upload-prescription/`, and the hand-typed path shipped as a 404.

Content is edited from `/system-admin/`:

- **Site settings** - the public phone, WhatsApp, e-mail, the pharmacy licence and the
  pharmacist. `SiteSettings` had **no admin at all** until the public site needed one,
  which made every one of those fields uneditable by anybody; it is a singleton, so adding
  and deleting are off and the changelist redirects straight to the single row.
- **Centres** and **Tests** both carry a "ready?" column saying whether the page has what
  it needs (photo + hours + phone; a written description) *before* the publish tick is on.
  `is_public` is editable from the test changelist, and the bulk action only ever takes
  tests **off** the site - a bulk publish would produce public pages with no description.
- **Doctors (public site)**, Health concerns, Medicine categories. The public `Doctor`
  carries an explicit `verbose_name`, because `patients.Doctor` (referring doctors)
  already exists and the admin index otherwise lists "Doctors" twice.
- **Enquiries** are registered read-only, since they are worked in the staff queue, which
  records who handled each one.

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
    **In use since 2026-11-18: https://aarogyam.argajitsrkar.in**, tunnel `aarogyam-lab`
    in the lab's own `tunnel` container. `.env` needs the long `eyJ...` token, not the
    tunnel ID; the route is added separately in the dashboard (Service URL
    `http://nginx:80`), and a healthy tunnel with 0 routes serves nothing.
    No Cloudflare Access gate yet - the login page is the only barrier.
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
- **Static files are content-hashed in production** (`ForgivingManifestStaticFilesStorage`):
  `collectstatic` writes `dist/app.<hash>.css` and `{% static %}` emits that name, so every
  deploy produces new urls and nginx can hold them for a year (`immutable`). Before this,
  `/static/dist/app.css` never changed name, so browsers kept it for 7 days and Cloudflare
  served edge HITs - redeploys looked like they had not taken effect.
  Two traps: `manifest_strict = False` does **not** stop a missing `url()` reference from
  failing collectstatic, which is why `hashed_name` is overridden; and collectstatic runs
  with `--ignore=src`, because `static/src/app.css` is the Tailwind input and its `@import`
  lines point outside the static root.

## Accounts

- **Site developer:** `argajit05@gmail.com` (username = email, like TGMA's named logins).
  Admin role + Django superuser = complete access, including `/system-admin/`. Listed in
  `DEVELOPER_ACCOUNTS` on the server, so it does **not** use one of the lab's 3 Admin slots.
  Its bootstrap password is `ADMIN_PASSWORD` in the server `.env`; it must be changed at
  first login, after which that line can be cleared.
- **Managed on the server only, like TGMA's `scripts/init_db.py`.** The account list is
  `apps/accounts/seed_users.py` (`SEED_USERS`, `REMOVE_USERS`); today it holds only the
  developer - the user will define lab roles and access later. New accounts get their
  bootstrap password from `SEED_PW_<NAME>` in the server `.env`.
- Server: `bash deploy.sh seed-users [--reset-passwords]`, `bash deploy.sh unlock <user>`,
  `bash deploy.sh reset-password <user>`. `web` runs `seed_users` at every start.
- The app's Users page is read-only (no add/edit/unlock/remove). Caps still apply in the
  model: max 3 Admins, Employees per Settings, Employees need a home centre.

## Login (aligned with TGMA, `D:\Sites\Tgmabase\app\auth.py`)

- Username (email for named accounts), case-insensitive, + password (`UsernameBackend`).
  Phone numbers are not login names. One generic error for
  unknown user / bad password / inactive account - never reveal which.
- django-axes: 5 failures -> account locked **15 min** (`AXES_COOLOFF_HOURS=0.25`), per
  username not per IP (front desks share an IP). Locked attempts are refused before the
  password is checked; `accounts/locked.html` says how long. Unlock: `bash deploy.sh unlock <user>`.
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
- Tests: `python -m pytest` (112 tests; settings isolation in `conftest.py`). The `django-dev` preview runs with `--noreload` - restart it after code changes.
- Docker Desktop on this laptop has been unreliable (engine stuck stopped); the full
  `docker compose up` stack has not yet been verified here.

## Working habits - mistakes already made here, do not repeat them

**Verify once, not three times.** One targeted check per change: the single thing that
would fail if the change were wrong. Prefer one combined command (one ssh, one grep with
several patterns) over several calls. Do not re-screenshot a page, re-grep what was just
read, or re-verify what a passing test already covers. Report it in a line, not a table.
Spend the checks where tests cannot see: destructive migrations, anything on the server,
template rendering, cache headers. That is where every real bug in this project came from.

**Run `python manage.py migrate` locally right after `makemigrations`.** The test suite
builds its database from migrations and passes, while the dev SQLite file still has the old
columns - a page then 500s in the browser with a green test run. Cost an hour once.

**Restart the `django-dev` preview after ANY template or code change.** It runs with
`--noreload`. Stale templates were mistaken for broken code three times in one session.

**Browser-driving traps:**
- `document.querySelector('form')` is the scope switcher in `base.html`, not the page's
  form. Reach the right one with `document.querySelector('#id_p-phone').form`.
- `ref_N` ids go stale after a navigation; re-run `find` first.
- A scripted `.click()` can beat Alpine to initialisation - a real `computer` click is the
  honest test of an Alpine control.

**Alpine `:class="cond && 'x'"` writes the literal string `false`** onto the element when
the condition is false. Use the object form: `:class="{ 'x': cond }"`.

**A Django form used with a prefix** does not see `self.data.get("field")` - the posted key
is `prefix-field`. Use `self.add_prefix("field")`.

**Measure before blaming the CSS cascade.** The sidebar rail ignored `width` because a flex
item defaults to `min-width: auto`, not because of layer order; several rounds went into
specificity and `!important` first.

**After removing a model field, grep the TEMPLATES too.** Removing `report_pdf` left a file
input with no field behind it and a column header for a column that no longer existed,
sitting live on the visit page for several commits.

**Keep `git push` and the ssh deploy as two separate Bash calls.** Chained in one command
they read as a single risky action and get refused.

## Removed on purpose (2026-11-18) - do not re-add without asking

Report PDF upload/download, the printed visit receipt, both Excel exports (patients and
prices), round-robin call assignment and call reassignment, the DPDP data export and
erasure, and the daily e-mail digest. `report_upload_to` and `apps/core/storage.py` stay
only because migration `patients/0001_initial` imports them.

## Rules worth keeping

- Centre scoping is enforced in querysets/permission checks (`apps/core/scoping.py`), never only in templates.
- **The lab does not compete on price.** Partner companies pay a commission and the customer
  chooses one, so the price screens list each company's price only - no "our price" column,
  no cheapest-wins highlight, no "you save". `TestCatalog.price` stays for billing a visit.
- **Re-test calls are a shared centre pool.** `RetestCandidate` has no `assigned_to`:
  any employee of the candidate's centre may call, and `CallLog.employee` records who did.
  Follow-ups are different - they still have an owner and still auto-assign round-robin.
- Competitor prices are entered manually. No scrapers.
- Seeded test intervals/prices are placeholders flagged `needs_clinical_review`.
- No secrets in the repo: `.env` is gitignored; `.env.example` is the template.
