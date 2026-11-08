#!/usr/bin/env bash
set -Eeuo pipefail
die() { printf '[ERROR] %s\n' "$*" >&2; exit 1; }
ok() { printf '[OK] %s\n' "$*"; }
[ "$EUID" -eq 0 ] || die 'Run as root.'
ROOT="$(cd -- "$(dirname -- "$0")" && pwd)"
[ -f "$ROOT/rclocall.py" ] && [ -f "$ROOT/haproxy_manager.py" ] || die 'Incomplete bundle.'
. /etc/os-release
case "$ID" in ubuntu|debian) ;; *) die 'Ubuntu/Debian required';; esac
for cmd in python3 ip ping modprobe systemctl dpkg dpkg-deb sha256sum; do
  command -v "$cmd" >/dev/null 2>&1 || die "Missing offline prerequisite: $cmd"
done
(cd "$ROOT"; sha256sum -c SHA256SUMS) || die 'SHA256 verification failed.'
python3 -m py_compile "$ROOT/rclocall.py" "$ROOT/haproxy_manager.py" || die 'Invalid source.'
mkdir -p /usr/local/lib/rclocall/packages
install -m 0755 "$ROOT/rclocall.py" /usr/local/lib/rclocall/rclocall.py
install -m 0755 "$ROOT/haproxy_manager.py" /usr/local/lib/rclocall/haproxy_manager.py
for deb in "$ROOT"/packages/*.deb; do
  [ -f "$deb" ] || die 'HAProxy DEB packages are missing.'
  install -m 0644 "$deb" "/usr/local/lib/rclocall/packages/$(basename "$deb")"
done
touch /usr/local/lib/rclocall/.offline
cat > /usr/local/bin/delta <<'LAUNCHER'
#!/usr/bin/env bash
exec /usr/bin/python3 /usr/local/lib/rclocall/rclocall.py "$@"
LAUNCHER
chmod 0755 /usr/local/bin/delta
cp -f /usr/local/bin/delta /usr/local/bin/rclocall
chmod 0755 /usr/local/bin/rclocall
ok 'DELTA installed offline; existing GRE configurations are preserved.'
ok 'HAProxy DEB packages copied for offline menu option 4.'
exec /usr/local/bin/delta menu
