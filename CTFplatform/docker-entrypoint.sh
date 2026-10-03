#!/bin/sh
# Runs once per container start, BEFORE gunicorn forks its workers, so the
# tables/seed data are created exactly once instead of racing 4 times.
set -e
mkdir -p /app/database /app/data/uploaded_labs
export AUTO_INIT_DB=true
python -c "from app import init_db; init_db()"
export AUTO_INIT_DB=false
exec "$@"
