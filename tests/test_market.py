import math
import unittest
from unittest.mock import patch

from market_grid import market


def source(count=40):
    return {"chart": {"error": None, "result": [{
        "meta": {"currency": "USD", "exchangeName": "TEST", "previousClose": 5},
        "timestamp": [1700000000 + i * 86400 for i in range(count)],
        "indicators": {"quote": [{field: [i + 10 for i in range(count)]
                                    for field in ("open", "high", "low", "close", "volume")}]},
    }]}}


class MarketTests(unittest.TestCase):
    def setUp(self):
        market._cache.clear()

    def test_validation(self):
        self.assertEqual(market.validate_request(" brk-b ", "1d", "1y"), "BRK-B")
        for symbol in ("", "..", "../../secret", "AAPL?x=y", "<script>", "A" * 25):
            with self.assertRaises(market.MarketError):
                market.validate_request(symbol, "1d", "1y")
        with self.assertRaises(market.MarketError):
            market.validate_request("AAPL", "1m", "1y")

    def test_indicator_windows_and_population_deviation(self):
        candles = [{"close": i} for i in range(1, 41)]
        points = market.calculate_indicators(candles)
        self.assertIsNone(points[28]["sma"])
        self.assertEqual(points[29]["sma"], 15.5)
        self.assertAlmostEqual(points[29]["upper"], 15.5 + 2 * math.sqrt(899 / 12))
        self.assertEqual(points[-1]["sma"], 25.5)
        self.assertIsNone(points[13]["rsi"])
        self.assertEqual(points[14]["rsi"], 100)

    def test_wilder_rsi(self):
        closes = [44.34,44.09,44.15,43.61,44.33,44.83,45.10,45.42,
                  45.84,46.08,45.89,46.03,45.61,46.28,46.28,46.00]
        points = market.calculate_indicators([{"close": value} for value in closes])
        self.assertAlmostEqual(points[14]["rsi"], 70.464135, places=5)
        self.assertAlmostEqual(points[15]["rsi"], 66.249619, places=5)

    def test_parser_filters_incomplete_and_nonfinite_candles(self):
        raw = source()
        result = raw["chart"]["result"][0]
        result["indicators"]["quote"][0]["close"][0] = None
        result["indicators"]["quote"][0]["high"][1] = float("inf")
        result["indicators"]["quote"][0]["volume"][2] = None
        parsed = market.parse_response(raw, "TEST", "1d", "6mo")
        self.assertEqual(len(parsed["points"]), 38)
        self.assertEqual(parsed["candles"][0]["volume"], 0)
        self.assertEqual(parsed["previousClose"], 48)
        self.assertEqual(parsed["range"], "6mo")

    def test_malformed_provider(self):
        for raw in ([], {}, {"chart": {"result": []}}, {"chart": {"result": [{}]}}):
            with self.assertRaises(market.MarketError):
                market.parse_response(raw, "TEST", "1d", "6mo")

    def test_intraday_previous_exchange_day(self):
        raw = source(3)
        result = raw["chart"]["result"][0]
        result["timestamp"] = [1700000000, 1700086400, 1700086700]
        parsed = market.parse_response(raw, "TEST", "5m", "5d")
        self.assertEqual(parsed["previousClose"], 10)

    def test_cache_separates_ranges_and_returns_copies(self):
        with patch.object(market, "_download", return_value=source()) as download:
            first = market.get_market_data("TEST", "1d", "6mo")
            first["points"].clear()
            self.assertEqual(len(market.get_market_data("TEST", "1d", "6mo")["points"]), 40)
            market.get_market_data("TEST", "1d", "1y")
            self.assertEqual(download.call_count, 2)
            self.assertEqual(download.call_args.args, ("TEST", "1d", "1y"))

    def test_invalid_request_never_downloads(self):
        with patch.object(market, "_download") as download:
            with self.assertRaises(market.MarketError):
                market.get_market_data("../private")
            download.assert_not_called()

    def test_provider_schema_errors_use_public_error_type(self):
        raw = source()
        raw["chart"]["result"][0]["indicators"]["quote"][0]["close"] = {"unexpected": 1}
        with patch.object(market, "_download", return_value=raw):
            with self.assertRaises(market.MarketError):
                market.get_market_data("TEST")


if __name__ == "__main__":
    unittest.main()
