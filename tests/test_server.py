import http.client
import json
import threading
import unittest
from unittest.mock import patch

from market_grid import market, server
from test_market import source


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = server.create_server(0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def request(self, path="/", headers=None, method="GET"):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            connection.request(method, path, headers=headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_only_loopback(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")

    def test_assets_and_security_headers(self):
        for path in server.ASSETS:
            status, headers, body = self.request(path)
            self.assertEqual(status, 200, path)
            self.assertTrue(body)
            self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
            self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])

    def test_config(self):
        status, _, body = self.request("/api/config")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["autoRefreshMs"], 300000)

    def test_foreign_host_origin_and_fetch_site_rejected(self):
        for headers in ({"Host": "foreign.example"}, {"Origin": "https://foreign.example"},
                        {"Sec-Fetch-Site": "cross-site"}):
            self.assertEqual(self.request("/api/config", headers)[0], 403)

    def test_no_directory_listing_or_source_access(self):
        for path in ("/market_grid/market.py", "/../run.py", "/%2e%2e/run.py", "/.env", "/web/"):
            self.assertEqual(self.request(path)[0], 404)

    def test_bad_queries(self):
        for query in ("symbol=..", "symbol=AAPL&interval=1m&range=1y", "symbol=",
                      "symbol=AAPL&symbol=MSFT", "symbol=AAPL&unknown=1", "&".join(f"x{i}=1" for i in range(9))):
            self.assertEqual(self.request("/api/market?" + query)[0], 400, query)

    def test_market_api_returns_python_indicators(self):
        market._cache.clear()
        with patch.object(market, "_download", return_value=source()):
            status, _, body = self.request("/api/market?symbol=TEST&interval=1d&range=1y")
        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(payload["range"], "1y")
        self.assertEqual(payload["points"][29]["sma"], 24.5)

    def test_malformed_source_does_not_leak_traceback(self):
        market._cache.clear()
        with patch.object(market, "_download", return_value=[]):
            status, _, body = self.request("/api/market?symbol=TEST")
        self.assertEqual(status, 502)
        self.assertNotIn(b"Traceback", body)

    def test_head_has_no_body_even_for_errors(self):
        for path, status in (("/", 200), ("/missing", 404)):
            result = self.request(path, method="HEAD")
            self.assertEqual(result[0], status)
            self.assertEqual(result[2], b"")


if __name__ == "__main__":
    unittest.main()
