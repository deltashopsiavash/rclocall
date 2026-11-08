import importlib.util
import io
from contextlib import redirect_stdout
from pathlib import Path
import unittest
from unittest.mock import patch, Mock

spec = importlib.util.spec_from_file_location('rclocall', Path(__file__).with_name('rclocall.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def sample():
    return {'role': 'foreign', 'local_public': '167.233.221.152',
            'links': [{'id': 1, 'peer_public': '109.94.164.237'},
                      {'id': 2, 'peer_public': '109.94.164.82'}]}


class AddressTests(unittest.TestCase):
    def test_original_links(self):
        self.assertEqual(module.link_addresses(1, 'foreign'), ('10.10.10.1', '10.10.10.2'))
        self.assertEqual(module.link_addresses(2, 'foreign'), ('10.10.10.5', '10.10.10.6'))
        self.assertEqual(module.link_addresses(1, 'iran'), ('10.10.10.2', '10.10.10.1'))
        self.assertEqual(module.link_addresses(2, 'iran'), ('10.10.10.6', '10.10.10.5'))

    def test_crosses_octet_boundary(self):
        self.assertEqual(module.link_addresses(65, 'foreign'), ('10.10.11.1', '10.10.11.2'))

    def test_multi_peer_validation(self):
        data = sample()
        self.assertEqual(module.validate(data), data)
        with self.assertRaises(ValueError):
            module.validate({**data, 'links': [data['links'][0], data['links'][0]]})

    def test_zero_links_after_last_delete_is_valid(self):
        data = sample()
        data['links'] = []
        self.assertEqual(module.validate(data), data)


class ManagerTests(unittest.TestCase):
    def test_edit_changes_only_target_peer_public(self):
        before = sample()
        with patch.object(module, 'CONFIG_FILE') as path, \
             patch.object(module, 'config', return_value=before), \
             patch.object(module, 'choose_tunnel', return_value=before['links'][0]), \
             patch.object(module, 'ask_ipv4', return_value='203.0.113.50'), \
             patch.object(module, 'yes', return_value=True), \
             patch.object(module, 'save_config') as save, \
             patch.object(module, 'status'):
            path.exists.return_value = True
            module.edit_tunnel()
        updated = save.call_args.args[0]
        self.assertEqual(updated['links'][0], {'id': 1, 'peer_public': '203.0.113.50'})
        self.assertEqual(updated['links'][1], before['links'][1])
        self.assertEqual(module.link_addresses(updated['links'][0]['id'], 'foreign'),
                         ('10.10.10.1', '10.10.10.2'))

    def test_delete_changes_only_selected_link(self):
        before = sample()
        with patch.object(module, 'CONFIG_FILE') as path, \
             patch.object(module, 'config', return_value=before), \
             patch.object(module, 'choose_tunnel', return_value=before['links'][1]), \
             patch.object(module, 'yes', return_value=True), \
             patch.object(module, 'save_config') as save, \
             patch.object(module, 'status'):
            path.exists.return_value = True
            module.delete_tunnel()
        self.assertEqual(save.call_args.args[0]['links'], [before['links'][0]])

    def test_reconcile_does_not_touch_other_link(self):
        old = sample()
        new = sample()
        new['links'][0]['peer_public'] = '203.0.113.50'
        with patch.object(module, 'invoke') as invoke, \
             patch.object(module.Path, 'exists', return_value=True), \
             patch.object(module, 'setup_link') as setup:
            module.reconcile_links(old, new)
        invoke.assert_called_once_with('ip', 'tunnel', 'del', 'rclg1')
        setup.assert_called_once_with(new['links'][0], new)

    def test_pasarguard_is_foreign_only(self):
        iran = sample()
        iran['role'] = 'iran'
        with patch.object(module, 'CONFIG_FILE') as path, \
             patch.object(module, 'config', return_value=iran), \
             patch.object(module, 'yes') as confirm, \
             patch.object(module, 'invoke') as invoke:
            path.exists.return_value = True
            module.install_pasarguard()
        confirm.assert_not_called()
        invoke.assert_not_called()


class MenuTests(unittest.TestCase):
    def test_header_shows_brand_contact_and_server(self):
        output = io.StringIO()
        with patch.object(module, 'default_public', return_value='167.233.221.152'), \
             patch.object(module, 'CONFIG_FILE') as path, \
             patch.object(module, 'config', return_value=sample()), \
             redirect_stdout(output):
            path.exists.return_value = True
            module.show_header('Main Menu')
        shown = output.getvalue()
        for expected in ('DELTA', '@delta_vpn_1', '@delta_vpn12',
                         'Telegram Channel', 'Telegram Support',
                         '167.233.221.152', 'FOREIGN', 'MAIN MENU'):
            self.assertIn(expected, shown)
        self.assertNotIn('Datacenter', shown)
        self.assertNotIn('github.com', shown)

    def test_main_menu_can_open_settings_and_go_back(self):
        output = io.StringIO()
        with patch.object(module, 'new_page') as pages, \
             patch.object(module, 'ask', side_effect=['2', '0']), \
             patch.object(module, 'tunnel_settings') as settings, \
             redirect_stdout(output):
            module.menu()
        settings.assert_called_once_with()
        self.assertEqual(pages.call_count, 2)
        self.assertIn('Install PasarGuard (Foreign only)', output.getvalue())

    def test_submenu_status_and_return(self):
        output = io.StringIO()
        with patch.object(module, 'new_page') as pages, \
             patch.object(module, 'ask', side_effect=['3', '4']), \
             patch.object(module, 'status') as status, \
             patch.object(module, 'pause'), \
             redirect_stdout(output):
            module.tunnel_settings()
        status.assert_called_once_with()
        self.assertEqual(pages.call_count, 3)
        for expected in ('Delete Tunnel', 'Edit Tunnel', 'Show Configured Tunnels',
                         'Back to Main Menu'):
            self.assertIn(expected, output.getvalue())


    def test_classic_logo_restored(self):
        self.assertIn('____   _____', module.DELTA_LOGO)
        self.assertIn('|____/ |_____', module.DELTA_LOGO)
        self.assertNotIn('█', module.DELTA_LOGO)
        self.assertEqual(len(module.DELTA_LOGO.strip('\n').splitlines()), 5)

    def test_header_uses_classic_cyan_logo(self):
        output = io.StringIO()
        with patch.object(module, 'default_public', return_value='167.233.221.152'), \
             patch.object(module, 'CONFIG_FILE') as path, \
             patch.object(module, 'config', return_value=sample()), \
             redirect_stdout(output):
            path.exists.return_value = True
            module.show_header('Main Menu')
        self.assertIn('____   _____', output.getvalue())
        self.assertIn('Telegram Channel', output.getvalue())

    def test_not_tty_clear_screen_is_safe(self):
        with redirect_stdout(io.StringIO()) as output:
            module.clear_screen()
        self.assertEqual(output.getvalue(), '')


if __name__ == '__main__':
    unittest.main()