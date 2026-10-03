# shared helpers for the deploy scripts (sourced, not executed)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

say()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m  %s\n' "$*" >&2; }
die()  { printf '\033[1;31mxx\033[0m  %s\n' "$*" >&2; exit 1; }

# set_env KEY VALUE : replace KEY=... in .env, or append it
set_env() {
  local key="$1" val="$2"
  if grep -qE "^${key}=" .env; then
    local tmp; tmp="$(mktemp)"
    awk -v k="$key" -v v="$val" 'BEGIN{FS=OFS="="} $1==k {print k"="v; next} {print}' .env > "$tmp" && cat "$tmp" > .env && rm -f "$tmp"
  else
    printf '%s=%s\n' "$key" "$val" >> .env
  fi
}
get_env() { grep -E "^$1=" .env | head -1 | cut -d= -f2- || true; }
rand_hex() { openssl rand -hex "${1:-32}"; }
compose()  { docker compose "$@"; }
