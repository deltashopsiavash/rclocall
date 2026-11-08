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

The large **DELTA** terminal banner appears on every menu page, followed by Telegram channel `@delta_vpn_1`, Telegram support `@delta_vpn12`, developer name DELTA, configured server IPv4 and role. The terminal clears between menu pages so earlier menus do not remain on screen. The main menu offers **1) Install Tunnel** (green), **2) Tunnel Settings** (red), **3) Install PasarGuard (Foreign only)** (purple), and **0) Exit** (white). For installation, select the local server role, enter its public IPv4, the number of remote peers, each peer public IPv4, and a **Shared Link ID** for each pair. The same Link ID must be entered on both ends of a tunnel, even when each end has a different number of peers. The server's public IP must actually be assigned to its network interface (providers using NAT may require an adapted setup).

The installer writes `/etc/rclocall/tunnels.json`, creates GRE interfaces named `rclg<ID>`, and installs `rclocall-gre.service` to recreate them after reboot. It validates local address conflicts and keeps dated backups when reconfiguring. The final display shows local/remote GRE IPs and green **CONNECTED** only after a successful ICMP ping. A **WAITING / NO REPLY** status does not automatically mean the GRE link is broken: the opposite end may not be configured, ICMP may be blocked, or GRE protocol 47 may be filtered by a host/provider firewall. It does **not** modify firewalls or routing of other services.

## Classic DELTA terminal logo

The previous simple **cyan outline ASCII DELTA** header has been restored at the user's request. The solid green 3D logo, custom pixel fonts, and block shadows were removed. It renders as plain terminal text on desktop and mobile, without additional fonts or packages. Header details still include the Telegram channel/support, developer name and server IPv4, but not GitHub or datacenter details.

Colored menu options and clear-screen transitions are retained. PasarGuard remains purple per the earlier menu preference. Updating via the install command does not replace saved GRE configuration or restart running tunnels.

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