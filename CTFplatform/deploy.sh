#!/usr/bin/env bash
# One-command deployment for a Linux server with Docker.
#
#   ./deploy.sh                                   # interactive
#   DOMAIN=ctf.example.com EMAIL=me@example.com ./deploy.sh      # HTTPS via Let's Encrypt
#   LAB_REMOTE=yes ./deploy.sh                    # let remote learners reach labs (see README)
#
# Safe to re-run: existing secrets in .env are kept; only missing ones are generated.
source "$(dirname "$0")/scripts/_lib.sh"

command -v docker >/dev/null   || die "Docker is not installed (https://docs.docker.com/engine/install/)"
docker compose version >/dev/null 2>&1 || die "Docker Compose v2 is required ('docker compose')"
command -v openssl >/dev/null  || die "openssl is required"
docker info >/dev/null 2>&1    || die "Cannot talk to the Docker daemon (is it running? are you in the 'docker' group?)"

# ---- .env ---------------------------------------------------------------
[[ -f .env ]] || { cp .env.example .env; say "Created .env"; }
created_admin=""
[[ -n "$(get_env SECRET_KEY)" ]]        || set_env SECRET_KEY "$(rand_hex 32)"
[[ -n "$(get_env POSTGRES_PASSWORD)" ]] || set_env POSTGRES_PASSWORD "$(rand_hex 16)"
if [[ -z "$(get_env ADMIN_PASSWORD)" ]]; then
  pw="$(rand_hex 9)"; set_env ADMIN_PASSWORD "$pw"; created_admin="$pw"
fi
set_env FLASK_ENV production

# ---- domain / TLS -------------------------------------------------------
DOMAIN="${DOMAIN:-}"; EMAIL="${EMAIL:-}"
if [[ -z "$DOMAIN" && -t 0 ]]; then
  read -rp "Domain name for HTTPS (e.g. ctf.example.com), or press Enter to use plain HTTP: " DOMAIN
fi
if [[ -n "$DOMAIN" ]]; then
  [[ -n "$EMAIL" ]] || { [[ -t 0 ]] && read -rp "Email for Let's Encrypt notices: " EMAIL; }
  [[ -n "$EMAIL" ]] || die "EMAIL is required with DOMAIN"
  say "Getting a TLS certificate for $DOMAIN"
  bash scripts/get_cert.sh "$DOMAIN" "$EMAIL"
  set_env SERVER_NAME "$DOMAIN"; set_env NGINX_MODE https; set_env FORCE_HTTPS true
  BASE="https://$DOMAIN"
else
  warn "No domain given: serving plain HTTP. Passwords travel unencrypted - fine for a private LAN/test, NOT for the internet."
  set_env SERVER_NAME _; set_env NGINX_MODE http; set_env FORCE_HTTPS false
  BASE="http://localhost"
fi

# ---- lab access ----------------------------------------------------------
LAB_REMOTE="${LAB_REMOTE:-}"
if [[ -z "$LAB_REMOTE" && -t 0 ]]; then
  read -rp "Will learners open labs from OTHER computers (not the server itself)? [y/N] " a
  [[ "$a" =~ ^[Yy] ]] && LAB_REMOTE=yes
fi
if [[ "$LAB_REMOTE" =~ ^(yes|y|true|1)$ ]]; then
  host="${LAB_PUBLIC_HOST:-${DOMAIN:-}}"
  [[ -n "$host" ]] || { [[ -t 0 ]] && read -rp "Server name or IP learners use to reach it: " host; }
  [[ -n "$host" ]] || die "LAB_PUBLIC_HOST is required for remote labs"
  set_env LAB_BIND_ADDR 0.0.0.0; set_env LAB_PUBLIC_HOST "$host"
  warn "Labs are intentionally vulnerable apps on ports 10000-20000. Allow those ports ONLY from your learners' IPs/VPN in your firewall, never from the whole internet."
else
  set_env LAB_BIND_ADDR 127.0.0.1; set_env LAB_PUBLIC_HOST 127.0.0.1
fi

# ---- build & start --------------------------------------------------------
say "Building and starting the stack (first build takes a few minutes)"
compose up -d --build

say "Waiting for the app to become healthy"
for i in $(seq 1 60); do
  [[ "$(compose ps --format '{{.Health}}' web 2>/dev/null | head -1)" == "healthy" ]] && break
  sleep 3
  [[ $i -eq 60 ]] && { compose logs --tail 50 web; die "web did not become healthy - see logs above"; }
done

say "Importing the bundled labs"
compose exec -T web python import_lab_library.py --publish

say "Running the smoke test"
if python3 scripts/smoke_test.py "$BASE"; then ok=1; else ok=0; fi

echo
say "Deployment finished: $BASE"
[[ -n "$created_admin" ]] && echo "    Admin login:  admin / $created_admin   (saved in .env as ADMIN_PASSWORD - change it after first login)"
[[ "$ok" == 1 ]] || warn "The smoke test reported problems - read the output above, then 'docker compose logs web'."
echo "    Backups:      scripts/backup.sh      Logs: docker compose logs -f web"
[[ "$ok" == 1 ]]
