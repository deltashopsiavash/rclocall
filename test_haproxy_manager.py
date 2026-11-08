import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import io
from contextlib import redirect_stdout

def load(name):
    path = Path(__file__).with_name(name + '.py')
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

hm = load('haproxy_manager')
delta = load('rclocall')


class HAProxyTests(unittest.TestCase):
    def test_default_ports_and_custom_list(self):
        self.assertEqual(hm.parse_ports(''), list(hm.DEFAULT_PORTS))
        self.assertEqual(len(hm.DEFAULT_PORTS), 15)
        self.assertEqual(hm.parse_ports('443,2083,8282'), [443, 2083, 8282])
        self.assertEqual(hm.parse_ports(' 443 , 2083 '), [443, 2083])

    def test_invalid_ports(self):
        for invalid in ('0', '65536', '443,', '443,,80', '443,443',
                        '443;80', 'abc', '80 443'):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    hm.parse_ports(invalid)

    def test_backend_uses_foreign_gre_address(self):
        iran_local, foreign_local = delta.link_addresses(1, 'iran')
        self.assertEqual((iran_local, foreign_local),
                         ('10.10.10.2', '10.10.10.1'))
        generated = hm.make_block([443, 2083, 8282], foreign_local)
        self.assertIn('server web443 10.10.10.1:443 check', generated)
        self.assertIn('server web2083 10.10.10.1:2083 check', generated)
        self.assertIn('server web8282 10.10.10.1:8282 check', generated)
        self.assertNotIn('10.10.10.2:', generated)

    def test_second_link_keeps_legacy_foreign_local(self):
        _, foreign_local = delta.link_addresses(2, 'iran')
        self.assertEqual(foreign_local, '10.10.10.5')
        self.assertIn('10.10.10.5:443', hm.make_block([443], foreign_local))

    def test_reinstall_removes_only_old_managed_sections(self):
        original = ('global\n    daemon\n'
                    'defaults\n    timeout client 50s\n'
                    'frontend other-service\n    bind *:9999\n'
                    'frontend inbound-443\n    bind *:443\n'
                    'backend inbound-443-backend\n    server old 10.10.10.2:443\n'
                    'frontend inbound-80\n    bind *:80\n'
                    'backend inbound-80-backend\n    server old 10.10.10.2:80\n')
        filtered, sections = hm.filter_existing_config(original)
        self.assertEqual(sections, 4)
        self.assertIn('frontend other-service', filtered)
        self.assertIn('bind *:9999', filtered)
        self.assertNotIn('frontend inbound-443', filtered)
        self.assertNotIn('backend inbound-80-backend', filtered)

    def test_marked_block_is_replaced_not_duplicated(self):
        original = hm.fallback_config() + '\n' + hm.make_block([443], '10.10.10.1')
        result, count = hm.filter_existing_config(original)
        self.assertEqual(count, 0)
        self.assertNotIn(hm.BEGIN, result)
        self.assertIn('defaults', result)

    def test_unmanaged_conflicting_ports_are_rejected(self):
        with self.assertRaises(ValueError):
            hm.detect_unmanaged_conflicts('frontend other\n    bind *:443\n', [443])
        hm.detect_unmanaged_conflicts('frontend other\n    bind *:443\n', [80])

    def test_foreign_role_cannot_install_haproxy(self):
        data = {'role': 'foreign', 'links': [{'id': 1, 'peer_public': '198.51.100.1'}]}
        out = io.StringIO()
        with patch.object(hm, 'install_packages') as install, \
             patch.object(hm, 'persist_config') as persist, redirect_stdout(out):
            hm.setup(data, delta.link_addresses)
        install.assert_not_called()
        persist.assert_not_called()
        self.assertIn('IRAN servers only', out.getvalue())

    def test_iran_multiple_foreign_selects_right_link(self):
        data = {'role': 'iran', 'links': [
            {'id': 1, 'peer_public': '203.0.113.11'},
            {'id': 2, 'peer_public': '203.0.113.12'}
        ]}
        out = io.StringIO()
        with patch('builtins.input', side_effect=['2', '', 'y']), \
             patch.object(hm, 'install_packages') as install, \
             patch.object(hm, 'persist_config', return_value=True) as persist, \
             redirect_stdout(out):
            hm.setup(data, delta.link_addresses)
        install.assert_called_once_with()
        args = persist.call_args.args
        self.assertEqual(args[0], list(hm.DEFAULT_PORTS))
        self.assertEqual(args[1], '10.10.10.5')


if __name__ == '__main__':
    unittest.main()
