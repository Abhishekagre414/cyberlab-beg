#!/usr/bin/env bash
# Create a SELF-SIGNED certificate in ./ssl (testing only: browsers will warn).
#   scripts/selfsigned.sh [hostname-or-ip]
source "$(dirname "$0")/_lib.sh"
host="${1:-localhost}"
mkdir -p ssl
san="DNS:${host}"; [[ "$host" =~ ^[0-9.]+$ ]] && san="IP:${host}"
openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
  -keyout ssl/privkey.pem -out ssl/fullchain.pem \
  -subj "/CN=${host}" -addext "subjectAltName=${san}" 2>/dev/null
chmod 600 ssl/privkey.pem
say "Self-signed certificate written to ssl/ for ${host}"
