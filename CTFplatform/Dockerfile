FROM python:3.11-slim

WORKDIR /app

# build-essential: some wheels need compiling; libpq-dev not needed because
# psycopg2-binary ships its own libpq. curl is used by the HEALTHCHECK.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# requirements.txt includes requirements-core.txt (-r), so copy both.
COPY requirements.txt requirements-core.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x /app/docker-entrypoint.sh \
    && useradd --create-home appuser \
    && mkdir -p /app/database /app/data/uploaded_labs \
    && chown -R appuser:appuser /app/database /app/data

ENV FLASK_APP=app.py \
    FLASK_ENV=production \
    PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

# Runs as an unprivileged user. Docker access (for lab containers) goes through
# the dockerproxy service over TCP, so this process never needs root or the
# raw Docker socket.
USER appuser

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--threads", "2", "--timeout", "60", "--access-logfile", "-", "app:app"]
