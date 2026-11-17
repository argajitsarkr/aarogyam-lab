#!/bin/sh
set -e
. /etc/backup.env
STAMP=$(date +%Y%m%d_%H%M)
OUT="/backups/${PGDATABASE}_${STAMP}.dump"
echo "[backup] $(date) dumping ${PGDATABASE} -> ${OUT}"
pg_dump --format=custom --no-owner --file="${OUT}.partial"
mv "${OUT}.partial" "${OUT}"
# Retention
find /backups -name "*.dump" -type f -mtime +"$((BACKUP_KEEP_DAYS - 1))" -print -delete
echo "[backup] done: $(du -h "${OUT}" | cut -f1)"
