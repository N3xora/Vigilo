#!/usr/bin/env bash
# First-time production setup on the VPS, run BY YOU on the server, from the repo root:
#   git clone https://github.com/N3xora/Vigilo.git && cd Vigilo
#   ./scripts/vps_setup.sh [--web-host app.onenexora.com] [--api-host vigilo-api.onenexora.com] [--no-start]
#
# Builds .env from .env.production.example: generates the two internal passwords, asks for the
# secrets with hidden input (they never echo, never go on a command line, and are never sent
# anywhere), starts the stack behind your EXISTING reverse proxy, runs the migrations and prints
# the Caddy blocks to add. Refuses to overwrite an existing .env. --no-start only writes .env.
set -euo pipefail
cd "$(dirname "$0")/.."

WEB_HOST=app.onenexora.com
API_HOST=vigilo-api.onenexora.com
START=1
while [ $# -gt 0 ]; do
  case "$1" in
    --web-host) WEB_HOST="${2:?}"; shift 2 ;;
    --api-host) API_HOST="${2:?}"; shift 2 ;;
    --no-start) START=0; shift ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

for tool in git openssl awk; do command -v "$tool" >/dev/null || { echo "missing: $tool" >&2; exit 1; }; done
if [ "$START" = 1 ]; then
  command -v docker >/dev/null && docker compose version >/dev/null 2>&1 \
    || { echo "needs Docker with Compose v2" >&2; exit 1; }
fi
[ -f .env.production.example ] || { echo "run from the repo root (.env.production.example missing)" >&2; exit 1; }
[ ! -e .env ] || { echo ".env already exists; edit it by hand or move it away first." >&2; exit 1; }

umask 077
cp .env.production.example .env

setenv() { # KEY VALUE: replace the KEY= line (value passed via the environment, safe for any character)
  KEY="$1" VAL="$2" awk 'BEGIN{FS=OFS="="} $1==ENVIRON["KEY"]{print $1, ENVIRON["VAL"]; next} {print}' .env > .env.tmp
  mv .env.tmp .env
}
ask() { # KEY PROMPT REQUIRED-PREFIX(optional)
  local key="$1" prompt="$2" prefix="${3:-}" val
  while true; do
    read -rsp "$prompt: " val; echo
    if [ -z "$val" ]; then echo "  (left empty)"; break; fi
    if [ -n "$prefix" ] && [[ "$val" != "$prefix"* ]]; then
      echo "  must start with $prefix; try again, or press Enter to leave it empty." >&2; continue
    fi
    break
  done
  setenv "$key" "$val"
}

gen() { openssl rand -base64 48 | tr -d '/+=\n' | cut -c1-32; }
setenv ENV production
setenv WEB_DOMAIN "$WEB_HOST"
setenv API_DOMAIN "$API_HOST"
setenv WEB_APP_URL "https://$WEB_HOST"
setenv PUBLIC_API_BASE_URL "https://$API_HOST"
setenv POSTGRES_PASSWORD "$(gen)"
setenv OBJECT_STORE_SECRET_KEY "$(gen)"
# Existing reverse proxy owns 80/443: do not start the bundled Caddy.
if grep -q '^COMPOSE_FILE=' .env; then :; else
  printf 'COMPOSE_FILE=docker-compose.self-host.yml:docker-compose.external-proxy.yml\n' >> .env
fi

echo "Paste each secret when asked. Nothing is shown while you type."
ask CLERK_SECRET_KEY "Clerk PRODUCTION secret key (sk_live_...)" sk_live_
ask NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY "Clerk PRODUCTION publishable key (pk_live_...)" pk_live_
setenv CLERK_JWKS_URL "https://clerk.onenexora.com/.well-known/jwks.json"
ask STRIPE_SECRET_KEY "Stripe LIVE secret key (sk_live_..., Enter to skip billing for now)" sk_live_
ask STRIPE_WEBHOOK_SECRET "Stripe webhook signing secret (whsec_..., Enter if not created yet)" whsec_
setenv STRIPE_PRICE_ID_PRO price_1UOfNwDimAgl5dOBTvKitHMZ
setenv STRIPE_PRICE_ID_PRO_YEARLY price_1UOfNxDimAgl5dOBMzk5gfOd
setenv STRIPE_PORTAL_CONFIGURATION_ID bpc_1UOfNxDimAgl5dOBcdbPf6PT
setenv SENTRY_ENVIRONMENT production
chmod 600 .env
echo ".env written (mode 600)."

[ "$START" = 1 ] || { echo "--no-start: stopping here."; exit 0; }

for p in 3000 8000; do
  if (ss -ltn 2>/dev/null || netstat -ltn 2>/dev/null) | grep -qE "[:.]$p\s"; then
    echo "port $p is already in use on this host; free it or change the published port, then re-run docker compose." >&2
    exit 1
  fi
done

docker compose up -d --build
echo "waiting for the API..."
for i in $(seq 1 60); do
  curl -fs -m 3 http://127.0.0.1:8000/healthz >/dev/null && break
  [ "$i" = 60 ] && { echo "API did not come up; check: docker compose logs api" >&2; exit 1; }
  sleep 2
done
docker compose exec -T api uv run alembic -c packages/persistence/alembic.ini upgrade head

cat <<MSG

The stack is up on 127.0.0.1:3000 (web) and 127.0.0.1:8000 (api).
Next, add these to the Caddy that already serves this machine, validate, reload:

$(sed -n '/^app\.onenexora\.com/,$p' Caddyfile.external-proxy.example | sed "s/app\.onenexora\.com/$WEB_HOST/; s/vigilo-api\.onenexora\.com/$API_HOST/")

Then, from any machine:
  ./scripts/smoke.sh https://$WEB_HOST https://$API_HOST
MSG
