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
new_file="$(mktemp "$BIN_DIR/.rclocall.XXXXXX")"
trap 'rm -f "$new_file"' EXIT
curl --fail --silent --show-error --location "$REPO_RAW/rclocall.py" -o "$new_file"
python3 -m py_compile "$new_file"
chmod 0755 "$new_file"
mv -f "$new_file" "$BIN_DIR/rclocall.py"

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