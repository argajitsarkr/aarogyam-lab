#!/bin/sh
set -e

# Wait for PostgreSQL
python - <<'PY'
import os, sys, time
import psycopg
url = os.environ.get("DATABASE_URL", "")
if url.startswith("postgres"):
    for i in range(60):
        try:
            psycopg.connect(url.replace("postgres://", "postgresql://", 1), connect_timeout=2).close()
            break
        except Exception as e:
            print(f"Waiting for database… ({e.__class__.__name__})", flush=True)
            time.sleep(2)
    else:
        sys.exit("Database not reachable")
PY

if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
  python manage.py migrate --noinput
  python manage.py collectstatic --noinput --verbosity 0
  python manage.py seed_centres
  python manage.py seed_competitors
  python manage.py seed_test_catalog
  if [ -n "${ADMIN_USERNAME}" ] && [ -n "${ADMIN_PASSWORD}" ]; then
    python manage.py create_first_admin --noinput
  fi
  if [ "${LOAD_DEMO_DATA:-0}" = "1" ]; then
    python manage.py create_demo_data || true
  fi
fi

exec "$@"
