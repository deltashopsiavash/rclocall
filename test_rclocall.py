import importlib.util
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


if __name__ == '__main__':
    unittest.main()