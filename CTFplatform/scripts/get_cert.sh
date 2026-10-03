#!/usr/bin/env bash
# Get (or renew) a free Let's Encrypt certificate and install it in ./ssl.
#   scripts/get_cert.sh your.domain.com you@example.com
# Needs: DNS A record pointing at this server, ports 80/443 reachable.
# Safe to run from cron monthly:  0 4 1 * * /path/to/scripts/get_cert.sh your.domain you@mail
source "$(dirname "$0")/_lib.sh"
domain="${1:?usage: get_cert.sh <domain> <email>}"
email="${2:?usage: get_cert.sh <domain> <email>}"
mkdir -p ssl certbot-data

say "Stopping nginx so certbot can use port 80"
compose stop nginx >/dev/null 2>&1 || true
docker run --rm -p 80:80 -v "$ROOT/certbot-data:/etc/letsencrypt" certbot/certbot \
  certonly --standalone -d "$domain" -m "$email" --agree-tos --no-eff-email -n --keep-until-expiring \
  || { compose start nginx >/dev/null 2>&1 || true; die "certbot failed (check DNS and that port 80 is open)"; }

cp -L "certbot-data/live/${domain}/fullchain.pem" ssl/fullchain.pem
cp -L "certbot-data/live/${domain}/privkey.pem"   ssl/privkey.pem
chmod 600 ssl/privkey.pem
say "Certificate installed in ssl/ for ${domain}"
compose up -d nginx >/dev/null 2>&1 || true
compose exec -T nginx nginx -s reload >/dev/null 2>&1 || true
