#!/usr/bin/env bash
# Aarogyam Pathology - deploy helper for the PowerEdge server (Cloudflare Tunnel mode).
#
#   bash deploy.sh up        first build + start
#   bash deploy.sh update    git pull (fast-forward only) + rebuild + restart; migrations run on web start
#   bash deploy.sh logs      tail all logs (Ctrl+C to stop)
#   bash deploy.sh status    containers + memory
#   bash deploy.sh backup    run a database backup now
#   bash deploy.sh url       print the current public ngrok address
#   bash deploy.sh admin     create the first Admin (interactive)
#   bash deploy.sh down      stop everything (data volumes are kept)
set -euo pipefail

ACTION="${1:-status}"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
COMPOSE=(docker compose -f "$PROJECT_DIR/docker-compose.server.yml" --env-file "$PROJECT_DIR/.env")
BRANCH="${DEPLOY_BRANCH:-main}"

cd "$PROJECT_DIR"

# Public link: start the cloudflared container only once a tunnel token is in .env.
if [ -f .env ] && grep -qE '^CLOUDFLARE_TUNNEL_TOKEN=.+' .env; then
  COMPOSE+=(--profile tunnel)
fi
if [ -f .env ] && grep -qE '^NGROK_AUTHTOKEN=.+' .env; then
  COMPOSE+=(--profile ngrok)
fi

if [ ! -f .env ]; then
  echo "ERROR: .env not found in $PROJECT_DIR"
  echo "  cp .env.example .env   then fill in every value (DEBUG=False, SECRET_KEY, POSTGRES_PASSWORD, ALLOWED_HOSTS ...)"
  exit 1
fi
if grep -qE '^(SECRET_KEY|POSTGRES_PASSWORD)=(change-me.*)?$' .env; then
  echo "ERROR: .env still has a placeholder SECRET_KEY or POSTGRES_PASSWORD."
  exit 1
fi

mkdir -p "${BACKUP_DIR:-/home/mmilab/aarogyam-backups}"

case "$ACTION" in
  up)
    "${COMPOSE[@]}" build web nginx db_backup
    "${COMPOSE[@]}" up -d
    "${COMPOSE[@]}" ps
    ;;

  update)
    if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
      echo "ERROR: tracked files were edited on the server. Make changes on the laptop and push;"
      echo "       inspect with 'git status' / 'git diff' before discarding anything here."
      exit 1
    fi
    before="$(git rev-parse --short HEAD)"
    git fetch origin "$BRANCH"
    git merge --ff-only "origin/$BRANCH"
    after="$(git rev-parse --short HEAD)"
    echo "Code: $before -> $after"
    git --no-pager log --oneline "$before..$after" || true
    "${COMPOSE[@]}" build web nginx db_backup
    "${COMPOSE[@]}" up -d
    echo "Waiting for web to report healthy (migrations run first)..."
    for _ in $(seq 1 40); do
      state="$(docker inspect -f '{{.State.Health.Status}}' "$("${COMPOSE[@]}" ps -q web)" 2>/dev/null || echo starting)"
      [ "$state" = "healthy" ] && break
      sleep 3
    done
    echo "web: ${state:-unknown}"
    "${COMPOSE[@]}" logs --tail 30 web
    docker image prune -f >/dev/null
    "${COMPOSE[@]}" ps
    ;;

  logs)
    "${COMPOSE[@]}" logs -f --tail 50 "${@:2}"
    ;;

  status)
    "${COMPOSE[@]}" ps
    echo
    echo "Deployed commit: $(git rev-parse --short HEAD) ($(git log -1 --format=%cd --date=format:'%d-%m-%Y %H:%M'))"
    ids="$("${COMPOSE[@]}" ps -q)"
    [ -n "$ids" ] && docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" $ids
    ;;

  backup)
    "${COMPOSE[@]}" exec db_backup /usr/local/bin/backup.sh
    ls -lh "${BACKUP_DIR:-/home/mmilab/aarogyam-backups}" | tail -5
    ;;

  url)
    # Current public ngrok address (changes on restart unless NGROK_URL is set).
    "${COMPOSE[@]}" logs ngrok 2>/dev/null | grep -o 'url=https://[^ ]*' | tail -1 | cut -d= -f2 \
      || echo "ngrok is not running (set NGROK_AUTHTOKEN in .env, then: bash deploy.sh up)"
    ;;

  admin)
    "${COMPOSE[@]}" exec web python manage.py create_first_admin
    ;;

  seed-users)
    # Create/update accounts from apps/accounts/seed_users.py (TGMA model). Passwords for
    # NEW users come from SEED_PW_* lines in .env, read fresh here so the web container
    # does not need recreating after you add one. Add --reset-passwords to reset existing.
    seed_env=()
    while IFS= read -r line; do
      seed_env+=(-e "$line")
    done < <(grep -E '^SEED_PW_[A-Z0-9_]+=.+' .env || true)
    "${COMPOSE[@]}" exec "${seed_env[@]}" web python manage.py seed_users "${@:2}"
    ;;

  unlock)
    [ -n "${2:-}" ] || { echo "Usage: bash deploy.sh unlock <username>"; exit 1; }
    "${COMPOSE[@]}" exec web python manage.py unlock_user "$2"
    ;;

  reset-password)
    [ -n "${2:-}" ] || { echo "Usage: bash deploy.sh reset-password <username>"; exit 1; }
    "${COMPOSE[@]}" exec web python manage.py reset_password "$2"
    ;;

  down)
    "${COMPOSE[@]}" down
    ;;

  *)
    echo "Usage: bash deploy.sh [up|update|logs|status|url|backup|admin|seed-users [--reset-passwords]|unlock <user>|reset-password <user>|down]"
    exit 1
    ;;
esac
