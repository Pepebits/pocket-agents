#!/usr/bin/env bash
# tunnel-setup.sh — exposes the VPS development servers over HTTPS,
# without opening a single inbound port. Run as `dev` AFTER:
#
#     cloudflared tunnel login          # once, pick the zone in the browser
#
# Idempotent: if the tunnel already exists, it rewrites the config and the routes.
set -euo pipefail

# Settings come from config.env at the repo root (see config.env.example), and
# what's still missing is asked for: this one, unlike setup.sh, runs by hand on
# a terminal. The zone has no default because it's yours.
CONF="$(dirname "$(readlink -f "$0")")/../config.env"
# shellcheck source=/dev/null
[ -r "$CONF" ] && . "$CONF"
if [ -z "${ZONE:-}" ]; then
  if [ -t 0 ]; then
    read -rp "Cloudflare zone for the previews (e.g. example.com): " ZONE
  fi
  [ -n "${ZONE:-}" ] || { echo "ZONE is required: set it in config.env"; exit 1; }
fi

TUNNEL=${TUNNEL:-dev-vps}
LABEL=${LABEL:-dev}
# Published ports. Each one ends up at p<port>-$LABEL.$ZONE
#
# CAREFUL with the depth of the name: Cloudflare's (free) Universal SSL
# certificate covers "$ZONE" and "*.$ZONE", ONE level ONLY. A host like
# p8000.dev.$ZONE has two and the TLS handshake fails with error 35, with no
# useful message. That's why the separator is a hyphen and not a dot: covering
# *.dev.$ZONE would require Advanced Certificate Manager, which is paid.
PORTS=${PORTS:-"3000 4321 5000 5173 8000 8080 8090"}
host_for(){ echo "p$1-$LABEL.$ZONE"; }
CFDIR="$HOME/.cloudflared"

log() { printf '\n\033[1;36m▶ %s\033[0m\n' "$*"; }
ok()  { printf '  \033[32m✓\033[0m %s\n' "$*"; }

[ -f "$CFDIR/cert.pem" ] || {
  echo "Missing $CFDIR/cert.pem. Run first:  cloudflared tunnel login"
  exit 1
}

log "Tunnel «$TUNNEL»"
if cloudflared tunnel list 2>/dev/null | awk '{print $2}' | grep -qx "$TUNNEL"; then
  ok "already exists"
else
  cloudflared tunnel create "$TUNNEL" >/dev/null
  ok "created"
fi
UUID=$(cloudflared tunnel list --output json | python3 -c "
import json,sys
print(next(t['id'] for t in json.load(sys.stdin) if t['name']=='$TUNNEL'))")
ok "uuid $UUID"

log "Ingress config"
{
  echo "tunnel: $UUID"
  echo "credentials-file: $CFDIR/$UUID.json"
  echo "originRequest:"
  echo "  connectTimeout: 10s"
  echo "  noTLSVerify: true      # the dev servers speak http on loopback"
  echo "ingress:"
  for p in $PORTS; do
    echo "  - hostname: $(host_for "$p")"
    echo "    service: http://localhost:$p"
  done
  echo "  - service: http_status:404"
} > "$CFDIR/config.yml"
ok "$(echo $PORTS | wc -w) ports → p<port>-$LABEL.$ZONE"

log "DNS routes"
for p in $PORTS; do
  h=$(host_for "$p")
  cloudflared tunnel route dns --overwrite-dns "$TUNNEL" "$h" >/dev/null 2>&1 \
    && ok "$h" || echo "  ✗ $h — check that the zone is yours"
done

log "System service"
# The service runs as root and ALWAYS reads /etc/cloudflared/config.yml.
# `service install` does NOT overwrite that file if it already exists, so rerunning
# the script would leave the tunnel serving the old config: everything 404 from the
# catch-all, with no hint that the config wasn't applied. It's copied by hand.
if [ ! -f /etc/cloudflared/cloudflared.service ] && ! systemctl list-unit-files cloudflared.service >/dev/null 2>&1; then
  sudo cloudflared --config "$CFDIR/config.yml" service install
fi
sudo install -d -m0755 /etc/cloudflared
sudo install -m0644 "$CFDIR/config.yml" /etc/cloudflared/config.yml
ok "config published to /etc/cloudflared/config.yml"
sudo systemctl enable cloudflared >/dev/null 2>&1 || true
sudo systemctl restart cloudflared
sleep 3
systemctl is-active cloudflared && ok "cloudflared active"

cat <<EOF

$(printf '\033[1;32m═══ DONE ═══\033[0m')

  Start something on the VPS and open it from your phone:

     cd ~/dev/<project> && npm run dev        →  https://p3000-$LABEL.$ZONE
     cd ~/dev/<project> && make serve         →  https://p8080-$LABEL.$ZONE

$(printf '\033[1;33m  IMPORTANT\033[0m') — these URLs are public while the development
  server is running. Put Cloudflare Access in front of them:

     Zero Trust → Access → Applications → Add
       domain:  p*-$LABEL.$ZONE
       policy:  Emails = your email   (One-time PIN)

  Without that, anyone with the URL sees your development environment.
EOF
