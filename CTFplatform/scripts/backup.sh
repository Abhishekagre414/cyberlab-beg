#!/usr/bin/env bash
# Dump the Postgres database to ./backups/ (keeps the last 14).
source "$(dirname "$0")/_lib.sh"
mkdir -p backups
f="backups/ctfdb-$(date +%Y%m%d-%H%M%S).sql.gz"
compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "$f"
ls -1t backups/ctfdb-*.sql.gz | tail -n +15 | xargs -r rm -f
say "Backup written: $f"
