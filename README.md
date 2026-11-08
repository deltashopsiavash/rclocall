# RCLocalL — GRE Tunnel Manager

An interactive Ubuntu/Debian IPv4 GRE tunnel installer that works on **Iran** or **Foreign** servers, from one peer to many peers. No HAProxy or unrelated network services are modified.

## Install (one command, on EACH server)

```bash
curl -fsSL https://raw.githubusercontent.com/deltashopsiavash/rclocall/main/install.sh -o /tmp/rclocall-install.sh && sudo bash /tmp/rclocall-install.sh
```

Run again at any time (opens the English menu):

```bash
sudo rclocall
```

The manager currently has one action: `1) Install Tunnel`. Select the local server role, enter its public IPv4, the number of remote peers, each peer public IPv4, and a **Shared Link ID** for each pair. The same Link ID must be entered on both ends of a tunnel, even when each end has a different number of peers. The server's public IP must actually be assigned to its network interface (providers using NAT may require an adapted setup).

The installer writes `/etc/rclocall/tunnels.json`, creates GRE interfaces named `rclg<ID>`, and installs `rclocall-gre.service` to recreate them after reboot. It validates local address conflicts and keeps dated backups when reconfiguring. The final display shows local/remote GRE IPs and green **CONNECTED** only after a successful ICMP ping. A **WAITING / NO REPLY** status does not automatically mean the GRE link is broken: the opposite end may not be configured, ICMP may be blocked, or GRE protocol 47 may be filtered by a host/provider firewall. It does **not** modify firewalls or routing of other services.

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
sudo rclocall              # English interactive menu
sudo rclocall status       # Show configured tunnels and ping peers
sudo systemctl status rclocall-gre.service
sudo systemctl restart rclocall-gre.service
```

## Network requirements and troubleshooting

- Allow IPv4 **GRE protocol number 47**, not TCP/UDP port 47, in host and provider firewalls.
- Keep ICMP echo permitted across the tunnel if you want green CONNECTED checks.
- If an old `gre-tunnels.service` runs, the wizard offers to disable it. Review any old `/etc/rc.local` GRE commands and remove them to prevent tunnels being recreated after reboot. Other GRE tools or addresses may need manual cleanup.
- `rclocall` does not install HAProxy or route traffic through the tunnel. Set up target services separately.
- Run the installer on the counterpart after the first server; until then connectivity may show **WAITING / NO REPLY**.
- Ensure the tunnel subnet chosen does not overlap LAN/VPN routes already in use.

## Security / operations

The installer fetches source over HTTPS from the `main` branch. Review the source and optionally pin the URL to a commit SHA for production deployments. Files are installed under `/usr/local/lib/rclocall` and configuration stays in `/etc/rclocall` with restrictive permissions. Upgrading via the install command replaces only the manager code, not the saved GRE configuration. Re-running the wizard rewrites only the RCLocalL-managed GRE tunnels after confirmation. SSH/network configuration and existing HAProxy configs are left untouched.