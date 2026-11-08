# DELTA — GRE Tunnel Manager

An interactive Ubuntu/Debian IPv4 GRE tunnel installer that works on **Iran** or **Foreign** servers, from one peer to many peers. No HAProxy or unrelated network services are modified.

## Install (one command, on EACH server)

```bash
curl -fsSL https://raw.githubusercontent.com/deltashopsiavash/rclocall/main/install.sh -o /tmp/rclocall-install.sh && sudo bash /tmp/rclocall-install.sh
```

Run again at any time (opens the English **DELTA** menu):

```bash
sudo delta
```

The old `sudo rclocall` command remains available for backward compatibility. The installer does not remove, recreate, or restart existing GRE links.

The large **DELTA** terminal banner appears on every menu page, followed by Telegram channel `@delta_vpn_1`, Telegram support `@delta_vpn12`, developer name DELTA, configured server IPv4 and role. The terminal clears between menu pages so earlier menus do not remain on screen. The main menu offers **1) Install Tunnel** (green), **2) Tunnel Settings** (red), **3) Install PasarGuard (Foreign only)** (purple), **4) Install HAProxy (Iran only)** (cyan), and **0) Exit** (white). For installation, select the local server role, enter its public IPv4, the number of remote peers, each peer public IPv4, and a **Shared Link ID** for each pair. The same Link ID must be entered on both ends of a tunnel, even when each end has a different number of peers. The server's public IP must actually be assigned to its network interface (providers using NAT may require an adapted setup).

The installer writes `/etc/rclocall/tunnels.json`, creates GRE interfaces named `rclg<ID>`, and installs `rclocall-gre.service` to recreate them after reboot. It validates local address conflicts and keeps dated backups when reconfiguring. The final display shows local/remote GRE IPs and green **CONNECTED** only after a successful ICMP ping. A **WAITING / NO REPLY** status does not automatically mean the GRE link is broken: the opposite end may not be configured, ICMP may be blocked, or GRE protocol 47 may be filtered by a host/provider firewall. It does **not** modify firewalls or routing of other services.

## Classic DELTA terminal logo

The previous simple **cyan outline ASCII DELTA** header has been restored at the user's request. The solid green 3D logo, custom pixel fonts, and block shadows were removed. It renders as plain terminal text on desktop and mobile, without additional fonts or packages. Header details still include the Telegram channel/support, developer name and server IPv4, but not GitHub or datacenter details.

Colored menu options and clear-screen transitions are retained. PasarGuard remains purple per the earlier menu preference. Updating via the install command does not replace saved GRE configuration or restart running tunnels.

## HAProxy — main menu option 4 (Iran only)

Select **4) Install HAProxy (Iran only)** on an Iran server with DELTA GRE already configured. **Foreign servers are refused.** This mode does **not** put HAProxy on the Foreign server.

The installer reads /etc/rclocall/tunnels.json and takes the **FOREIGN local GRE IP** from the matching Link ID automatically. **Do not use the Iran local GRE IP in an HAProxy backend.** For example:

| Link ID | Iran local GRE IP | Foreign local GRE backend |
| --- | --- | --- |
| 1 | 10.10.10.2 | **10.10.10.1** |
| 2 | 10.10.10.6 | **10.10.10.5** |

If the Iran server has several Foreign peers, the menu lists each peer's **public IPv4**, local GRE IP, and foreign GRE IP, and asks which Link ID to use for HAProxy.

All 15 original ports are proposed by default:

```text
443,80,8880,2052,2082,2095,2086,1370,1372,15156,8443,12321,1379,11231,8080
```

Press Enter to use all defaults, or supply your own comma-separated list such as `443,2083,8282`. Only the selected ports are configured; ports must be unique and between 1 and 65535. Each generated frontend/backend pair uses TCP and exactly the same incoming and outgoing port, with one backend named web<port> and the correct Foreign local GRE IP.

**Ubuntu 24.04 x86_64/amd64** is required for the supplied DEB files. On a fresh server, the setup downloads these exact SHA-256-verified files from this repository's `packages/` directory and installs them using apt's local-DEB dependency handling. In case the repository download is unavailable, it can fetch the same checksum-verified files from the public Ubuntu mirrors listed in `haproxy_manager.py`. If HAProxy is already installed, the setup retains its existing installed version. The two uploaded binaries were verified for package architecture/version before being added to the repository.

Before modifying `/etc/haproxy/haproxy.cfg`, the installer keeps unrelated HAProxy sections and asks permission to replace preexisting `inbound-PORT` frontend/backend sections. Every successful change is preceded by a timestamped configuration backup; it tests the proposed configuration with `haproxy -c -f ...` and then runs **`service haproxy restart`**. If the restart fails, it attempts to restore the prior file and service state. The installer does not edit HAProxy settings on the Foreign server and does not alter GRE tunnel settings.

**Important:** The target service on the Foreign server must listen on the corresponding TCP ports via its GRE interface (or 0.0.0.0), and firewall rules must allow the traffic. HAProxy installation alone does not deploy the destination service. The uploaded HAProxy version is pinned to 2.8.16-0ubuntu0.24.04.2 and may be older than current Ubuntu security updates; you may want to upgrade it using Ubuntu's normal package updates when appropriate.

## Package integrity

| File | SHA-256 |
| --- | --- |
| `packages/liblua5.4-0_5.4.6-3build2_amd64.deb` | `6a520259e5b06e86191a25af6d448387cdd2b3d291a0aa956ce272e84d071260` |
| `packages/haproxy_2.8.16-0ubuntu0.24.04.2_amd64.deb` | `05df8fef3a26e6535cfe579b0c99c3196e7d9e3390d9be707991d44ab75ffcd6` |

These SHA-256 values are calculated from the two uploaded DEBs. The GitHub binary blobs were checked against the uploaded files as well.


## Offline installation (for Iranian VPS without GitHub access)

Use the **one-file self-extracting** DELTA installer. Its archive includes the current DELTA manager, the HAProxy option-4 manager, and both exact SHA-256-verified Ubuntu 24.04 amd64 DEB files.

1. Download [DELTA-offline.run](https://raw.githubusercontent.com/deltashopsiavash/rclocall/main/dist/DELTA-offline.run) **on your PC or phone with internet access**. You never need to connect to GitHub from the restricted VPS.
2. Transfer that one file to the Iran VPS at /root/DELTA-offline.run using SFTP, WinSCP, Termius, or from another machine:
   `scp DELTA-offline.run root@YOUR_SERVER_IP:/root/`
3. SSH into the VPS, then run **one command**:

   ```bash
   sudo bash /root/DELTA-offline.run
   ```

   The self-extracting installer checks the checksums and Python syntax, installs DELTA and the bundled HAProxy DEB files into /usr/local/lib/rclocall, and opens the interactive English menu without any curl, GitHub or apt update calls.

4. On subsequent logins: `sudo delta`. For a later update, simply upload a fresh DELTA-offline.run and run it again.

**Compatibility:** Ubuntu/Debian with system commands python3, ip, ping, modprobe, systemctl, dpkg, dpkg-deb and sha256sum available. The included HAProxy 2.8.16 DEB packages require Ubuntu **24.04 x86_64/amd64** and the usual OS dependencies. Offline option 4 uses **dpkg -i** on the bundled files and never attempts network; if a required Ubuntu dependency is missing, the install reports the dependency error rather than going online. Other actions do not install the DEBs until HAProxy option 4 is selected.

**Preserves state:** Existing /etc/rclocall/tunnels.json, GRE systemd service, local GRE addresses and HAProxy configuration are **not changed by installing or upgrading the menu itself**. Network services are modified only when you explicitly select an installation or tunnel settings action in the interactive menu.


## Link IDs and deterministic local addresses

Link IDs 1 through 15000 uniquely identify GRE /30 subnets. Each pair's addresses depend on its Link ID, **not** on its public IP, so a Foreign server can be replaced without changing tunnel local IPs.

| Shared Link ID | Foreign GRE IP | Iran GRE IP |
| --- | --- | --- |
| 1 | `10.10.10.1/30` | `10.10.10.2/30` |
| 2 | `10.10.10.5/30` | `10.10.10.6/30` |
| 3 | `10.10.10.9/30` | `10.10.10.10/30` |

Example with two Iran servers and one Foreign server:

- Foreign server: choose **Foreign**, **2 Iran peers**. Link 1 → IR1 public IP; Link 2 → IR2 public IP.
- Iran 1: choose **Iran**, **1 Foreign peer**. Use the Foreign public IP and **Link ID 1**.
- Iran 2: choose **Iran**, **1 Foreign peer**. Use the same Foreign public IP and **Link ID 2**.

Example with one Iran and two Foreign servers: create Link IDs 1 and 2 on the Iran server, then use Link ID 1 on Foreign server A and Link ID 2 on Foreign server B. Other topologies work as long as every pair has a unique Link ID and both endpoints agree on it. Do not reuse the same Link ID for different links anywhere in your connected network.

## Commands

```bash
sudo delta                # English DELTA interactive menu
sudo delta status       # Show configured tunnels and ping peers
sudo systemctl status rclocall-gre.service
sudo systemctl restart rclocall-gre.service
```


## Tunnel Settings (menu option 2)

The settings submenu is in English and opens on a clean terminal page:

1. **Delete Tunnel** (red) — shows every configured Link ID together with its peer's public IPv4 and the local/remote GRE addresses. Select only the tunnel to delete. After confirmation only that connection is removed; other active connections remain running. If the last tunnel is deleted, the GRE boot service is disabled.
2. **Edit Tunnel (change peer IPv4)** (green) — select a Link ID from the same list, enter the new **peer public IPv4** and confirm. The tunnel keeps its Link ID and its **existing local/remote GRE IPs**. Only the selected tunnel is reconfigured; on the remote server, update the corresponding endpoint as well if needed.
3. **Show Configured Tunnels** (purple) — lists the local public IP, each peer's public IPv4, Link ID, interface name, local/remote GRE IPs, and per-peer connectivity (green **CONNECTED** if a ping succeeds).
4. **Back to Main Menu** (white).

Existing configurations in /etc/rclocall/tunnels.json are preserved across upgrades; when a tunnel is edited or deleted, a timestamped backup is written before changes. The other working tunnel interfaces are not restarted during normal edits/deletes.

## PasarGuard Node (main menu option 3)

**Foreign servers only.** The menu displays Install PasarGuard (Foreign only) on every server, but refuses to run on a server with the saved **Iran** role (or without a saved server role). It asks for confirmation, downloads the official PasarGuard Node installer, validates the download and Bash syntax, then executes the equivalent of:

```bash
sudo bash -c "$(curl -sL https://github.com/PasarGuard/scripts/raw/main/pg-node.sh)" @ install
```

This runs third-party code as root and may change services on the Foreign VPS. Review the upstream PasarGuard script and use a suitable VPS backup beforehand. This does **not** install the PasarGuard panel on Iran or modify HAProxy directly.

## Network requirements and troubleshooting

- Allow IPv4 **GRE protocol number 47**, not TCP/UDP port 47, in host and provider firewalls.
- Keep ICMP echo permitted across the tunnel if you want green CONNECTED checks.
- If an old `gre-tunnels.service` runs, the wizard offers to disable it. Review any old `/etc/rc.local` GRE commands and remove them to prevent tunnels being recreated after reboot. Other GRE tools or addresses may need manual cleanup.
- `rclocall` does not install HAProxy or route traffic through the tunnel. Set up target services separately.
- Run the installer on the counterpart after the first server; until then connectivity may show **WAITING / NO REPLY**.
- Ensure the tunnel subnet chosen does not overlap LAN/VPN routes already in use.

## Security / operations

The installer fetches source over HTTPS from the `main` branch. Review the source and optionally pin the URL to a commit SHA for production deployments. Files are installed under `/usr/local/lib/rclocall` and configuration stays in `/etc/rclocall` with restrictive permissions. Upgrading via the install command replaces only the manager code, not the saved GRE configuration; run the same one-command installer again to update DELTA. The legacy `rclocall` command and GRE service remain compatible. Re-running the wizard rewrites only the RCLocalL-managed GRE tunnels after confirmation. SSH/network configuration and existing HAProxy configs are left untouched.