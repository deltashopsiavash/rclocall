#!/usr/bin/env bash
# Create a self-extracting, single-file DELTA offline installer.
set -Eeuo pipefail
cd "$(dirname "$0")/.."

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/DELTA-offline/packages" dist
cp rclocall.py haproxy_manager.py install-offline.sh "$tmp/DELTA-offline/"
cp packages/*.deb "$tmp/DELTA-offline/packages/"
chmod 0755 "$tmp/DELTA-offline/install-offline.sh"

# Verify the two exact user-uploaded DEBs.
(
cd "$tmp/DELTA-offline"
echo '6a520259e5b06e86191a25af6d448387cdd2b3d291a0aa956ce272e84d071260  packages/liblua5.4-0_5.4.6-3build2_amd64.deb' | sha256sum -c -
echo '05df8fef3a26e6535cfe579b0c99c3196e7d9e3390d9be707991d44ab75ffcd6  packages/haproxy_2.8.16-0ubuntu0.24.04.2_amd64.deb' | sha256sum -c -
sha256sum rclocall.py haproxy_manager.py packages/*.deb > SHA256SUMS
)
tar -czf "$tmp/payload.tar.gz" -C "$tmp" DELTA-offline

cat > dist/DELTA-offline.run <<'WRAPPER'
#!/usr/bin/env bash
# DELTA offline one-file installer. No internet access is required.
set -Eeuo pipefail
if [ "$EUID" -ne 0 ]; then
  echo '[ERROR] Run as root: sudo bash /root/DELTA-offline.run' >&2
  exit 1
fi
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
line="$(awk '/^__DELTA_BUNDLE_PAYLOAD__$/ {print NR + 1; exit}' "$0")"
if [ -z "$line" ]; then
  echo '[ERROR] Broken DELTA offline archive.' >&2
  exit 1
fi
tail -n +"$line" "$0" | tar -xz -C "$work"
bash "$work/DELTA-offline/install-offline.sh"
exit 0
__DELTA_BUNDLE_PAYLOAD__
WRAPPER
cat "$tmp/payload.tar.gz" >> dist/DELTA-offline.run
chmod 0755 dist/DELTA-offline.run

# Verify the actual embedded archive (not just its source directory).
mkdir -p "$tmp/verify"
marker="$(awk '/^__DELTA_BUNDLE_PAYLOAD__$/ {print NR + 1; exit}' dist/DELTA-offline.run)"
tail -n +"$marker" dist/DELTA-offline.run | tar -xz -C "$tmp/verify"
(cd "$tmp/verify/DELTA-offline" && sha256sum -c SHA256SUMS)
python3 -m py_compile "$tmp/verify/DELTA-offline/rclocall.py" \
    "$tmp/verify/DELTA-offline/haproxy_manager.py"
bash -n "$tmp/verify/DELTA-offline/install-offline.sh"

echo "DELTA offline bundle created: dist/DELTA-offline.run"
sha256sum dist/DELTA-offline.run
