import json
import unittest
from scripts.connect_proxy import MARKER, choose_network, choose_proxy, override


class ProxySetupTests(unittest.TestCase):
    def test_identifies_proxy_without_confusing_other_nginx_services(self):
        containers = [{"Names": "other", "Image": "nginx:latest"},
                      {"Names": "npm-app-1", "Image": "jc21/nginx-proxy-manager:2"}]
        self.assertEqual(choose_proxy(containers), "npm-app-1")
        with self.assertRaises(ValueError):
            choose_proxy(containers + [{"Names": "npm-two", "Image": "jc21/nginx-proxy-manager:2"}])

    def test_uses_user_defined_proxy_network_and_preserves_default(self):
        networks = [{"Name": "bridge", "Driver": "bridge"},
                    {"Name": "npm_default", "Driver": "bridge", "Labels": {"com.docker.compose.network": "default"}}]
        selected = choose_network(networks)
        config = json.loads(override(selected).removeprefix(MARKER))
        self.assertEqual(config["networks"]["npm"]["name"], "npm_default")
        self.assertTrue(config["networks"]["npm"]["external"])
        self.assertIn("default", config["services"]["cados"]["networks"])
        self.assertNotIn("ports", config["services"]["cados"])

    def test_rejects_ambiguous_or_isolated_networks(self):
        with self.assertRaises(ValueError):
            choose_network([{"Name":"a", "Driver":"bridge"}, {"Name":"b", "Driver":"bridge"}])
        with self.assertRaises(ValueError):
            choose_network([{"Name":"private", "Driver":"bridge", "Internal":True}])
