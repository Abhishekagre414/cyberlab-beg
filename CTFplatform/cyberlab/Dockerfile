# NOTE: not build-tested in the environment this project was developed in
# (no Docker daemon / restricted network access there). Review before relying
# on it -- see README.md "Docker" section.

FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Non-root user, isolated to /app
RUN useradd --create-home --shell /bin/bash cyberlab \
    && chown -R cyberlab:cyberlab /app
USER cyberlab

COPY --chown=cyberlab:cyberlab . .

EXPOSE 5000

# HOST=0.0.0.0 so the port mapping in docker-compose.yml (itself bound to
# 127.0.0.1 on the HOST machine) can reach the container. FLASK_DEBUG stays
# off by default -- safe even if someone forgets to change it.
ENV HOST=0.0.0.0
ENV FLASK_DEBUG=0

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=3)" || exit 1

CMD ["python3", "app.py"]
