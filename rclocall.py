#!/usr/bin/env python3
"""RCLocalL: interactive, multi-peer IPv4 GRE tunnel manager for Ubuntu."""

import copy
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime

CONFIG_DIR = Path('/etc/rclocall')
CONFIG_FILE = CONFIG_DIR / 'tunnels.json'
SERVICE_FILE = Path('/etc/systemd/system/rclocall-gre.service')
MAX_LINK_ID = 15000
MAX_PEERS = 64
BASE = int(ipaddress.IPv4Address('10.10.10.0'))
SERVICE_TEXT = '''[Unit]
Description=RCLocalL managed GRE tunnels
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/bin/rclocall apply
ExecStop=/usr/local/bin/rclocall down
TimeoutStartSec=60

[Install]
WantedBy=multi-user.target
'''


def paint(message, ansi):
    if sys.stdout.isatty() and not os.environ.get('NO_COLOR'):
        return f'\033[{ansi}m{message}\033[0m'
    return message


def info(message):
    print(paint(message, '36'))


def okay(message):
    print(paint(message, '1;32'))


def warn(message):
    print(paint(message, '1;33'))


def fail(message):
    print(paint(message, '1;31'), file=sys.stderr)


def invoke(*args, check=True, capture=False):
    return subprocess.run(list(args), check=check, text=True,
                          stdout=subprocess.PIPE if capture else None,
                          stderr=subprocess.PIPE if capture else None)


def valid_ip(value):
    try:
        return str(ipaddress.IPv4Address(value))
    except ipaddress.AddressValueError:
        raise ValueError('Enter a valid IPv4 address.') from None


def link_addresses(link_id, role):
    if not 1 <= link_id <= MAX_LINK_ID:
        raise ValueError(f'Link ID must be 1 through {MAX_LINK_ID}.')
    network = ipaddress.IPv4Network((BASE + (link_id - 1) * 4, 30))
    foreign_ip = str(network.network_address + 1)
    iran_ip = str(network.network_address + 2)
    return (foreign_ip, iran_ip) if role == 'foreign' else (iran_ip, foreign_ip)


def interface(link_id):
    return f'rclg{link_id}'  # Linux interface names must be <= 15 characters.


def validate(data):
    if not isinstance(data, dict) or data.get('role') not in ('iran', 'foreign'):
        raise ValueError('Invalid role in configuration.')
    local_public = valid_ip(data.get('local_public', ''))
    links = data.get('links')
    if not isinstance(links, list) or not 0 <= len(links) <= MAX_PEERS:
        raise ValueError('Invalid number of links.')
    ids, peers = set(), set()
    for link in links:
        if not isinstance(link, dict) or type(link.get('id')) is not int:
            raise ValueError('Each link must have an integer ID.')
        link_addresses(link['id'], data['role'])
        peer = valid_ip(link.get('peer_public', ''))
        if peer == local_public or link['id'] in ids or peer in peers:
            raise ValueError('Duplicate ID, duplicate peer, or peer equals local IP.')
        ids.add(link['id'])
        peers.add(peer)
    return data


def config():
    with CONFIG_FILE.open(encoding='utf-8') as file:
        return validate(json.load(file))


def managed_interfaces():
    return sorted((p.name for p in Path('/sys/class/net').iterdir()
                   if re.fullmatch(r'rclg\d+', p.name)))


def remove_managed():
    for name in managed_interfaces():
        invoke('ip', 'tunnel', 'del', name)


def apply():
    data = config()
    invoke('modprobe', 'ip_gre')
    remove_managed()
    try:
        for link in data['links']:
            name = interface(link['id'])
            local, remote = link_addresses(link['id'], data['role'])
            invoke('ip', 'tunnel', 'add', name, 'mode', 'gre',
                   'local', data['local_public'], 'remote', link['peer_public'],
                   'ttl', '255')
            invoke('ip', 'link', 'set', name, 'mtu', '1400')
            invoke('ip', 'addr', 'add', f'{local}/30', 'dev', name)
            invoke('ip', 'link', 'set', name, 'up')
    except (subprocess.CalledProcessError, OSError):
        remove_managed()
        raise


def default_public():
    result = invoke('ip', '-4', 'route', 'get', '1.1.1.1', check=False, capture=True)
    if result.returncode == 0:
        match = re.search(r'\bsrc\s+(\d+\.\d+\.\d+\.\d+)', result.stdout)
        if match:
            return match.group(1)
    return ''


def assigned_public(ip):
    result = invoke('ip', '-o', '-4', 'addr', 'show', check=False, capture=True)
    return result.returncode == 0 and bool(re.search(r'\binet\s+' + re.escape(ip) + r'/', result.stdout))


def local_address_conflicts(data):
    result = invoke('ip', '-o', '-4', 'addr', 'show', check=False, capture=True)
    if result.returncode:
        return ['Unable to inspect existing addresses.']
    occupied = {}
    for line in result.stdout.splitlines():
        match = re.search(r'^\d+:\s+(\S+)\s+inet\s+(\d+\.\d+\.\d+\.\d+)/', line)
        if match:
            occupied.setdefault(match.group(2), set()).add(match.group(1).split('@')[0])
    errors = []
    for link in data['links']:
        local, _ = link_addresses(link['id'], data['role'])
        other = {name for name in occupied.get(local, set()) if not re.fullmatch(r'rclg\d+', name)}
        if other:
            errors.append(f'{local} is already assigned to {", ".join(sorted(other))}')
    return errors


def ask(message, default=None):
    suffix = f' [{default}]' if default is not None else ''
    response = input(f'{message}{suffix}: ').strip()
    return response or (str(default) if default is not None else '')


def ask_number(message, low, high, default=None):
    while True:
        value = ask(message, default)
        if value.isdigit() and low <= int(value) <= high:
            return int(value)
        warn(f'Enter a number from {low} to {high}.')


def ask_ipv4(message, default=None):
    while True:
        try:
            return valid_ip(ask(message, default))
        except ValueError as error:
            warn(str(error))


def yes(message, default=False):
    answer = input(f'{message} [{"Y/n" if default else "y/N"}]: ').strip().lower()
    return default if not answer else answer in ('y', 'yes')


def print_links(data):
    print('\n  Link  Interface  Peer public IP      Local GRE IP     Remote GRE IP')
    print('  ----  ---------  ------------------  ---------------  ---------------')
    for link in sorted(data['links'], key=lambda x: x['id']):
        local, remote = link_addresses(link['id'], data['role'])
        print(f"  {link['id']:<4}  {interface(link['id']):<9}  {link['peer_public']:<18}  {local:<15}  {remote}")


def status():
    if not CONFIG_FILE.exists():
        warn('No tunnel configuration found. Choose Install Tunnel first.')
        return
    data = config()
    print(f'\n  Server role: {data["role"].upper()}')
    print(f'  Public IP:   {data["local_public"]}')
    print_links(data)
    if not data['links']:
        warn('  No GRE tunnels are configured.')
        return
    print('\n  Connectivity check:')
    successes = 0
    for link in sorted(data['links'], key=lambda x: x['id']):
        name = interface(link['id'])
        local, remote = link_addresses(link['id'], data['role'])
        if not Path('/sys/class/net', name).exists():
            state = paint('NOT INSTALLED', '1;31')
        else:
            result = subprocess.run(['ping', '-n', '-I', name, '-c', '1', '-W', '2', remote],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    timeout=5, check=False)
            if result.returncode == 0:
                state = paint('CONNECTED', '1;32')
                successes += 1
            else:
                state = paint('WAITING / NO REPLY', '1;33')
        print(f'  Link {link["id"]}: {local} -> {remote} : {state}')
    if successes == len(data['links']):
        okay('\n  All GRE peers are reachable.')
    else:
        warn(f'\n  Reachable peers: {successes}/{len(data["links"])}')
        print('  Install the matching Link IDs on the other side and allow GRE protocol 47.')


def setup_link(link, data):
    """Create one GRE interface without disturbing other active links."""
    name = interface(link['id'])
    local, _ = link_addresses(link['id'], data['role'])
    invoke('ip', 'tunnel', 'add', name, 'mode', 'gre',
           'local', data['local_public'], 'remote', link['peer_public'],
           'ttl', '255')
    invoke('ip', 'link', 'set', name, 'mtu', '1400')
    invoke('ip', 'addr', 'add', f'{local}/30', 'dev', name)
    invoke('ip', 'link', 'set', name, 'up')


def reconcile_links(before, after):
    """Reconfigure only changed/removed links; preserve unaffected GRE sessions."""
    old = {link['id']: link for link in before['links']} if before else {}
    new = {link['id']: link for link in after['links']}
    change_all = before is not None and (before['role'] != after['role'] or
                                         before['local_public'] != after['local_public'])
    changed_ids = {link_id for link_id in (old.keys() | new.keys())
                   if change_all or old.get(link_id) != new.get(link_id)}
    for link_id in sorted(old.keys() | new.keys()):
        name = interface(link_id)
        exists = Path('/sys/class/net', name).exists()
        if link_id in changed_ids and exists:
            invoke('ip', 'tunnel', 'del', name)
            exists = False
        if link_id in new and not exists:
            setup_link(new[link_id], after)


def save_config(data):
    validate(data)
    CONFIG_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(CONFIG_DIR, 0o700)
    previous = CONFIG_FILE.read_bytes() if CONFIG_FILE.exists() else None
    previous_data = config() if previous is not None else None
    if previous is not None:
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        backup = CONFIG_DIR / f'tunnels.json.backup-{stamp}'
        backup.write_bytes(previous)
        os.chmod(backup, 0o600)
    fd, name = tempfile.mkstemp(prefix='.tunnels-', dir=CONFIG_DIR)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as output:
            json.dump(data, output, indent=2)
            output.write('\n')
        os.chmod(name, 0o600)
        os.replace(name, CONFIG_FILE)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    try:
        SERVICE_FILE.write_text(SERVICE_TEXT, encoding='utf-8')
        invoke('systemctl', 'daemon-reload')
        if not data['links']:
            # On the last deletion, stop the service and remove managed links.
            invoke('systemctl', 'disable', '--now', 'rclocall-gre.service', check=False)
            remove_managed()
        else:
            invoke('modprobe', 'ip_gre')
            invoke('systemctl', 'enable', 'rclocall-gre.service')
            active = invoke('systemctl', 'is-active', '--quiet',
                            'rclocall-gre.service', check=False)
            if active.returncode == 0:
                # Avoid systemctl restart: it drops every active GRE tunnel.
                reconcile_links(previous_data, data)
            else:
                # Initial boot/start applies the saved configuration.
                invoke('systemctl', 'start', 'rclocall-gre.service')
    except (OSError, subprocess.CalledProcessError):
        fail('Tunnel activation failed. Restoring previous configuration.')
        if previous is None:
            CONFIG_FILE.unlink(missing_ok=True)
            invoke('systemctl', 'disable', '--now', 'rclocall-gre.service', check=False)
            remove_managed()
        else:
            CONFIG_FILE.write_bytes(previous)
            os.chmod(CONFIG_FILE, 0o600)
            if previous_data and previous_data['links']:
                invoke('systemctl', 'enable', 'rclocall-gre.service', check=False)
                invoke('systemctl', 'restart', 'rclocall-gre.service', check=False)
                # Reconcile as a best-effort fallback when service is not active.
                if invoke('systemctl', 'is-active', '--quiet',
                          'rclocall-gre.service', check=False).returncode != 0:
                    invoke('modprobe', 'ip_gre', check=False)
                    try:
                        reconcile_links(data, previous_data)
                    except (OSError, subprocess.CalledProcessError):
                        pass
            else:
                invoke('systemctl', 'disable', '--now', 'rclocall-gre.service', check=False)
                remove_managed()
        raise


def choose_tunnel(data):
    """Display peer IPv4 and both GRE addresses before asking which one to edit."""
    if not data['links']:
        warn('No GRE tunnels are configured.')
        return None
    print_links(data)
    ids = {link['id'] for link in data['links']}
    while True:
        selection = ask('Select Link ID (or b to go back)')
        if selection.lower() in ('b', 'back', '0'):
            return None
        if selection.isdigit() and int(selection) in ids:
            return next(link for link in data['links'] if link['id'] == int(selection))
        warn('Select a Link ID listed above, or b to go back.')


def delete_tunnel():
    if not CONFIG_FILE.exists():
        warn('No tunnel configuration found. Install Tunnel first.')
        return
    data = config()
    print('\n  === Delete Tunnel ===')
    link = choose_tunnel(data)
    if link is None:
        return
    local, remote = link_addresses(link['id'], data['role'])
    warn(f"Selected: Link {link['id']} - peer {link['peer_public']}")
    print(f'  Local GRE: {local}  |  Remote GRE: {remote}')
    if not yes('Delete ONLY this tunnel? The other GRE links will be preserved'):
        warn('Cancelled; no changes made.')
        return
    updated = copy.deepcopy(data)
    updated['links'] = [item for item in updated['links'] if item['id'] != link['id']]
    save_config(updated)
    okay(f"Deleted Link {link['id']} ({link['peer_public']}).")
    if updated['links']:
        status()
    else:
        okay('No links remain; the GRE boot service has been disabled.')


def edit_tunnel():
    if not CONFIG_FILE.exists():
        warn('No tunnel configuration found. Install Tunnel first.')
        return
    data = config()
    print('\n  === Edit Tunnel Peer IPv4 ===')
    link = choose_tunnel(data)
    if link is None:
        return
    local, remote = link_addresses(link['id'], data['role'])
    print(f"  Current peer IPv4: {link['peer_public']}")
    print(f'  Local GRE: {local}  |  Remote GRE: {remote} (unchanged)')
    new_ip = ask_ipv4('New peer public IPv4', link['peer_public'])
    if new_ip == link['peer_public']:
        warn('No changes made.')
        return
    updated = copy.deepcopy(data)
    for item in updated['links']:
        if item['id'] == link['id']:
            item['peer_public'] = new_ip
            break
    try:
        validate(updated)
    except ValueError as error:
        warn(f'Cannot update tunnel: {error}')
        return
    print(f"  Link {link['id']}: {link['peer_public']} -> {new_ip}")
    print(f'  GRE addresses remain: {local} -> {remote}')
    if not yes('Save new peer IPv4 and reconnect ONLY this tunnel?'):
        warn('Cancelled; no changes made.')
        return
    save_config(updated)
    okay(f"Updated Link {link['id']}. Local GRE addresses are unchanged.")
    status()


def tunnel_settings():
    while True:
        print('\n' + paint('========== Tunnel Settings ==========', '1;36'))
        print('  1) Delete Tunnel')
        print('  2) Edit Tunnel (change peer IPv4)')
        print('  3) Show Configured Tunnels')
        print('  4) Back to Main Menu')
        choice = ask('Select an option')
        if choice == '1':
            delete_tunnel()
        elif choice == '2':
            edit_tunnel()
        elif choice == '3':
            status()
        elif choice == '4':
            return
        else:
            warn('Invalid option.')


def install_pasarguard():
    print('\n  === Install PasarGuard Node (Foreign only) ===')
    if not CONFIG_FILE.exists():
        warn('Install a GRE tunnel as a Foreign server first to confirm server role.')
        return
    data = config()
    if data['role'] != 'foreign':
        warn('PasarGuard installation is available on Foreign servers ONLY.')
        return
    url = 'https://github.com/PasarGuard/scripts/raw/main/pg-node.sh'
    info(f'  Source: {url}')
    warn('This downloads and executes the official PasarGuard node installer as root.')
    if not yes('Run the PasarGuard node installer now?'):
        warn('Cancelled.')
        return
    with tempfile.TemporaryDirectory(prefix='rclocall-pg-') as directory:
        script = Path(directory) / 'pg-node.sh'
        invoke('curl', '--fail', '--location', '--silent', '--show-error',
               '--retry', '2', '--max-time', '90', url, '--output', str(script))
        if not script.exists() or script.stat().st_size == 0:
            raise RuntimeError('PasarGuard installer download is empty.')
        invoke('bash', '-n', str(script))
        # Equivalent to: sudo bash -c "$(curl -sL URL)" @ install
        result = subprocess.run(['bash', '-c', script.read_text(encoding='utf-8'),
                                 '@', 'install'], check=False)
    if result.returncode == 0:
        okay('PasarGuard installer finished successfully.')
    else:
        warn(f'PasarGuard installer exited with code {result.returncode}. Check output above.')


def installation():
    print('\n  === Install GRE Tunnel ===')
    print('  Each GRE link must use the SAME Link ID on both ends.')
    print('  Link 1: foreign 10.10.10.1 <-> Iran 10.10.10.2')
    print('  Link 2: foreign 10.10.10.5 <-> Iran 10.10.10.6\n')
    print('  1) Iran server')
    print('  2) Foreign server')
    role = 'iran' if ask_number('Select server role', 1, 2) == 1 else 'foreign'
    local = ask_ipv4('This server public IPv4', default_public() or None)
    if not assigned_public(local):
        warn('This IP is not assigned to a local network interface.')
        warn('GRE "local" requires a locally assigned IP; check NAT/provider networking.')
        return
    peers = ask_number('How many FOREIGN servers?' if role == 'iran' else 'How many IRAN servers?', 1, MAX_PEERS, 1)
    links = []
    used_ids, used_peers = set(), set()
    for i in range(1, peers + 1):
        print(f'\n  --- Peer {i} of {peers} ---')
        while True:
            peer_ip = ask_ipv4('Peer public IPv4')
            if peer_ip != local and peer_ip not in used_peers:
                break
            warn('Peer IP must be different and unique.')
        while True:
            link_id = ask_number('Shared Link ID (same ID on peer server)', 1, MAX_LINK_ID, i)
            if link_id not in used_ids:
                break
            warn('This Link ID is already in use on this server.')
        used_ids.add(link_id)
        used_peers.add(peer_ip)
        links.append({'id': link_id, 'peer_public': peer_ip})
        mine, theirs = link_addresses(link_id, role)
        info(f'  GRE addresses: local {mine} -> peer {theirs}')
    data = validate({'role': role, 'local_public': local, 'links': links})
    print('\n  === Review Configuration ===')
    print_links(data)
    legacy = invoke('systemctl', 'is-active', '--quiet', 'gre-tunnels.service', check=False)
    if legacy.returncode == 0:
        warn('Legacy gre-tunnels.service is active and may conflict with this installation.')
        if yes('Disable and stop the legacy gre-tunnels.service now?'):
            invoke('systemctl', 'disable', '--now', 'gre-tunnels.service')
            conflicts = local_address_conflicts(data)
            if conflicts:
                for conflict in conflicts:
                    fail('Address conflict remains: ' + conflict)
                return
        else:
            warn('Installation cancelled. Stop the old GRE service before installing.')
            return
    conflicts = local_address_conflicts(data)
    if conflicts:
        for conflict in conflicts:
            fail('Address conflict: ' + conflict)
        warn('Stop/remove the old tunnel configuration before continuing.')
        return
    if Path('/etc/rc.local').exists():
        rc_text = Path('/etc/rc.local').read_text(errors='replace')
        if re.search(r'ip\s+tunnel\s+add', rc_text):
            warn('WARNING: /etc/rc.local contains old tunnel commands.')
            warn('Remove the obsolete GRE startup commands to avoid conflicts after reboot.')
            if not yes('Continue despite legacy rc.local commands?'):
                return
    if not yes('Apply this configuration and enable GRE tunnels at boot?'):
        warn('Cancelled. No new configuration was saved.')
        return
    save_config(data)
    okay('\n  Tunnel interfaces configured; boot service enabled.')
    status()


def menu():
    while True:
        print('\n' + paint('========================================', '1;36'))
        print(paint('             RCLocalL Manager', '1;36'))
        print(paint('========================================', '1;36'))
        print('  1) Install Tunnel')
        print('  2) Tunnel Settings')
        print('  3) Install PasarGuard (Foreign only)')
        print('  0) Exit')
        choice = ask('Select an option')
        if choice == '1':
            installation()
        elif choice == '2':
            tunnel_settings()
        elif choice == '3':
            install_pasarguard()
        elif choice == '0':
            return
        else:
            warn('Invalid option.')


def main():
    if os.geteuid() != 0:
        fail('Run as root: sudo rclocall')
        return 1
    try:
        command = sys.argv[1] if len(sys.argv) > 1 else 'menu'
        if command == 'menu':
            menu()
        elif command == 'status':
            status()
        elif command == 'apply':
            apply()
        elif command == 'down':
            remove_managed()
        else:
            fail('Usage: rclocall [menu|status|apply|down]')
            return 2
        return 0
    except (ValueError, RuntimeError, json.JSONDecodeError, OSError, subprocess.CalledProcessError) as error:
        fail(f'Error: {error}')
        return 1
    except (KeyboardInterrupt, EOFError):
        print('\nExited.')
        return 130


if __name__ == '__main__':
    sys.exit(main())