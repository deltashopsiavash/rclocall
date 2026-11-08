import importlib.util
import unittest

spec = importlib.util.spec_from_file_location('rclocall', 'rclocall.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class AddressTests(unittest.TestCase):
    def test_original_links(self):
        self.assertEqual(module.link_addresses(1, 'foreign'), ('10.10.10.1', '10.10.10.2'))
        self.assertEqual(module.link_addresses(2, 'foreign'), ('10.10.10.5', '10.10.10.6'))
        self.assertEqual(module.link_addresses(1, 'iran'), ('10.10.10.2', '10.10.10.1'))
        self.assertEqual(module.link_addresses(2, 'iran'), ('10.10.10.6', '10.10.10.5'))

    def test_crosses_octet_boundary(self):
        self.assertEqual(module.link_addresses(65, 'foreign'), ('10.10.11.1', '10.10.11.2'))

    def test_multi_peer_validation(self):
        data = {'role': 'foreign', 'local_public': '167.233.221.152',
                'links': [{'id': 1, 'peer_public': '109.94.164.237'},
                          {'id': 2, 'peer_public': '109.94.164.82'}]}
        self.assertEqual(module.validate(data), data)
        with self.assertRaises(ValueError):
            module.validate({**data, 'links': [data['links'][0], data['links'][0]]})


if __name__ == '__main__':
    unittest.main()