#!/bin/sh
# Daily pg_dump via busybox crond. crond does not inherit env, so persist it.
set -e
cat > /etc/backup.env <<ENV
export PGHOST="${PGHOST:-db}"
export PGUSER="${POSTGRES_USER}"
export PGPASSWORD="${POSTGRES_PASSWORD}"
export PGDATABASE="${POSTGRES_DB}"
export BACKUP_KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
export TZ="${TZ:-Asia/Kolkata}"
ENV
chmod 600 /etc/backup.env
echo "${BACKUP_MINUTE:-0} ${BACKUP_HOUR:-2} * * * /usr/local/bin/backup.sh >> /proc/1/fd/1 2>&1" > /etc/crontabs/root
echo "Backups scheduled daily at ${BACKUP_HOUR:-2}:$(printf %02d ${BACKUP_MINUTE:-0}) ${TZ:-Asia/Kolkata}; keeping ${BACKUP_KEEP_DAYS:-14} days."
if [ "${BACKUP_ON_START:-0}" = "1" ]; then /usr/local/bin/backup.sh; fi
exec crond -f -l 8
