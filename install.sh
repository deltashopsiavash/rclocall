#!/usr/bin/env bash
set -Eeuo pipefail

REPO_RAW='https://raw.githubusercontent.com/deltashopsiavash/rclocall/main'
BIN_DIR='/usr/local/lib/rclocall'
LAUNCHER='/usr/local/bin/delta'
LEGACY_LAUNCHER='/usr/local/bin/rclocall'

if [[ "$EUID" -ne 0 ]]; then
    echo 'Run as root: sudo bash install.sh' >&2
    exit 1
fi

if [[ ! -f /etc/os-release ]]; then
    echo 'This installer requires Ubuntu or Debian.' >&2
    exit 1
fi
. /etc/os-release
if [[ "$ID" != 'ubuntu' && "$ID" != 'debian' ]]; then
    echo 'Supported operating systems: Ubuntu and Debian.' >&2
    exit 1
fi

missing=()
for command in python3 ip ping modprobe curl; do
    command -v "$command" >/dev/null 2>&1 || missing+=("$command")
done
if (( ${#missing[@]} > 0 )); then
    echo '[INFO] Installing required system packages...'
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y python3 iproute2 iputils-ping kmod curl ca-certificates
fi

mkdir -p "$BIN_DIR"
staging="$(mktemp -d "$BIN_DIR/.delta-upgrade.XXXXXX")"
trap 'rm -rf "$staging"' EXIT
cache_token="$(date +%s%N)-$RANDOM"

for name in rclocall.py haproxy_manager.py; do
    curl --fail --silent --show-error --location \
        --header 'Cache-Control: no-cache' --header 'Pragma: no-cache' \
        --retry 2 --max-time 90 \
        "$REPO_RAW/$name?delta_update=$cache_token" \
        -o "$staging/$name"
    python3 -m py_compile "$staging/$name"
done

# Reject unexpected/stale 3D versions before modifying installed code.
if ! grep -Fq 'DELTA_LOGO = r"""' "$staging/rclocall.py" ||
   grep -Eq 'DELTA_FONTS|def render_delta_logo' "$staging/rclocall.py"; then
    echo '[ERROR] Outdated or unexpected DELTA source; installation cancelled.' >&2
    exit 1
fi

chmod 0755 "$staging/rclocall.py" "$staging/haproxy_manager.py"
mv -f "$staging/rclocall.py" "$BIN_DIR/rclocall.py"
mv -f "$staging/haproxy_manager.py" "$BIN_DIR/haproxy_manager.py"
echo '[OK] Verified original cyan DELTA logo and HAProxy installer.'

cat > "$LAUNCHER" <<'EOF'
#!/usr/bin/env bash
exec /usr/bin/python3 /usr/local/lib/rclocall/rclocall.py "$@"
EOF
chmod 0755 "$LAUNCHER"

# Keep the old entry point so existing GRE systemd services are uninterrupted.
cp -f "$LAUNCHER" "$LEGACY_LAUNCHER"
chmod 0755 "$LEGACY_LAUNCHER"

echo '[OK] DELTA installed. Opening manager...'
exec "$LAUNCHER" menu