"""Market queries and indicators; no GUI or deployment dependency."""
from __future__ import annotations

import copy
import json
import math
import re
import socket
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

INTERVALS = [
    {"value": "1m", "label": "1 minuto", "ranges": ["1d", "5d"], "fallback": "1d"},
    {"value": "5m", "label": "5 minutos", "ranges": ["1d", "5d", "1mo"], "fallback": "5d"},
    {"value": "15m", "label": "15 minutos", "ranges": ["1d", "5d", "1mo"], "fallback": "5d"},
    {"value": "30m", "label": "30 minutos", "ranges": ["1d", "5d", "1mo"], "fallback": "1mo"},
    {"value": "1h", "label": "1 hora", "ranges": ["1d", "5d", "1mo"], "fallback": "1mo"},
    {"value": "1d", "label": "Diario", "ranges": ["1mo", "3mo", "6mo", "ytd", "1y", "2y", "5y", "10y", "max"], "fallback": "6mo"},
    {"value": "1wk", "label": "Semanal", "ranges": ["3mo", "6mo", "ytd", "1y", "2y", "5y", "10y", "max"], "fallback": "2y"},
]
RANGES = [
    {"value": value, "label": label} for value, label in [
        ("1d", "1 día"), ("5d", "5 días"), ("1mo", "1 mes"),
        ("3mo", "3 meses"), ("6mo", "6 meses"), ("ytd", "YTD"),
        ("1y", "1 año"), ("2y", "2 años"), ("5y", "5 años"),
        ("10y", "10 años"), ("max", "Máximo"),
    ]
]
DEFAULT_SYMBOLS = ["AAPL", "MSFT", "SPY", "BTC-USD"]


class MarketError(Exception):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_request(symbol: str, interval: str, range_key: str) -> str:
    symbol = symbol.strip().upper()
    if not re.fullmatch(r"[A-Z0-9.^=_-]{1,24}", symbol) or not re.search(r"[A-Z0-9]", symbol):
        raise MarketError("Introduce un símbolo válido de Yahoo Finance.", 400)
    if not any(item["value"] == interval and range_key in item["ranges"] for item in INTERVALS):
        raise MarketError("La combinación de intervalo y rango no es compatible.", 400)
    return symbol


def calculate_indicators(candles: list[dict]) -> list[dict]:
    """SMA 30, population Bollinger deviation, and Wilder RSI 14."""
    output = []
    average_gain = average_loss = 0.0
    for index, candle in enumerate(candles):
        window = candles[max(0, index - 29):index + 1]
        sma = sum(point["close"] for point in window) / 30 if len(window) == 30 else None
        deviation = math.sqrt(sum((point["close"] - sma) ** 2 for point in window) / 30) if sma is not None else None
        change = candle["close"] - candles[index - 1]["close"] if index else 0
        gain, loss = max(change, 0), max(-change, 0)
        if index <= 14:
            average_gain += gain / 14
            average_loss += loss / 14
        else:
            average_gain = (average_gain * 13 + gain) / 14
            average_loss = (average_loss * 13 + loss) / 14
        rsi = None
        if index >= 14:
            rsi = 100 if average_loss == 0 else 100 - 100 / (1 + average_gain / average_loss)
        output.append({
            **candle, "sma": sma, "rsi": rsi,
            "upper": sma + 2 * deviation if sma is not None else None,
            "lower": sma - 2 * deviation if sma is not None else None,
        })
    return output


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # The upstream host is fixed; do not follow a redirect to another host.
        return None


def _download(symbol: str, interval: str, range_key: str) -> dict:
    url = "https://query1.finance.yahoo.com/v8/finance/chart/" + quote(symbol, safe="")
    url += "?" + urlencode({"interval": interval, "range": range_key, "includePrePost": "false", "events": "div,splits"})
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0 MarketGridLocal/1.0"})
    try:
        with build_opener(NoRedirect()).open(request, timeout=12) as response:
            raw = response.read(12_000_001)
        if len(raw) > 12_000_000:
            raise MarketError("El historial recibido supera el tamaño permitido.")
        return json.loads(raw)
    except HTTPError as error:
        if error.code == 429:
            raise MarketError("Yahoo Finance limitó las consultas. Intenta de nuevo en un momento.", 429) from None
        if error.code == 404:
            raise MarketError("Yahoo Finance no reconoció este símbolo.", 404) from None
        raise MarketError("La fuente de mercado no pudo responder a esta consulta.") from None
    except (TimeoutError, socket.timeout):
        raise MarketError("La fuente de mercado tardó demasiado en responder.") from None
    except (URLError, ValueError, OSError):
        raise MarketError("No se pudo conectar con la fuente de mercado.") from None


def parse_response(source: dict, symbol: str, interval: str, range_key: str) -> dict:
    if not isinstance(source, dict) or not isinstance(source.get("chart"), dict):
        raise MarketError("La fuente devolvió un historial no válido.")
    chart = source.get("chart") or {}
    if chart.get("error"):
        raise MarketError("No se encontró historial para este símbolo.", 404)
    results = chart.get("result")
    result = results[0] if isinstance(results, list) and results else None
    if not isinstance(result, dict):
        raise MarketError("No se encontró historial para este símbolo.", 404)
    indicators = result.get("indicators")
    if not isinstance(indicators, dict):
        raise MarketError("La fuente devolvió un historial no válido.")
    quotes = indicators.get("quote")
    quote_data = quotes[0] if isinstance(quotes, list) and quotes else None
    timestamps = result.get("timestamp")
    if not isinstance(quote_data, dict) or not isinstance(timestamps, list):
        raise MarketError("La fuente devolvió un historial no válido.")
    candles = []
    for index, timestamp in enumerate(timestamps):
        candle = {"time": timestamp}
        for field in ("open", "high", "low", "close", "volume"):
            values = quote_data.get(field) or []
            if not isinstance(values, list):
                raise MarketError("La fuente devolvió un historial no válido.")
            value = values[index] if index < len(values) else None
            candle[field] = value if finite(value) else (0 if field == "volume" else None)
        # Restrict to timestamps representable by Python and the browser.
        if not finite(timestamp) or not -2208988800 <= timestamp <= 4102444800 or any(candle[field] is None for field in ("open", "high", "low", "close")):
            continue
        candles.append(candle)
    if not candles:
        raise MarketError("La respuesta no contiene velas completas para este período.", 404)
    meta = result.get("meta") or {}
    if not isinstance(meta, dict):
        raise MarketError("La fuente devolvió un historial no válido.")
    previous_close = meta.get("previousClose", meta.get("chartPreviousClose"))
    if not finite(previous_close):
        previous_close = None
    if len(candles) > 1:
        if interval in ("1d", "1wk"):
            previous_close = candles[-2]["close"]
        else:
            # Exchange UTC offset works without installing timezone data on Windows.
            try:
                zone = ZoneInfo(str(meta.get("exchangeTimezoneName", "UTC")))
                day = lambda timestamp: datetime.fromtimestamp(timestamp, zone).date()
            except (ZoneInfoNotFoundError, ValueError):
                offset = meta.get("gmtoffset", 0)
                offset = offset if finite(offset) else 0
                day = lambda timestamp: datetime.fromtimestamp(timestamp + offset, timezone.utc).date()
            last_day = day(candles[-1]["time"])
            previous_close = next((point["close"] for point in reversed(candles) if day(point["time"]) != last_day), previous_close)
    return {
        "symbol": symbol, "interval": interval, "range": range_key,
        "currency": str(meta.get("currency") or "—"),
        "exchange": str(meta.get("fullExchangeName") or meta.get("exchangeName") or "MERCADO"),
        "longName": str(meta.get("longName") or meta.get("shortName") or symbol),
        "previousClose": previous_close,
        "candles": candles, "points": calculate_indicators(candles),
    }


_cache: OrderedDict = OrderedDict()
_cache_lock = threading.Lock()
_upstream_slots = threading.BoundedSemaphore(4)


def get_market_data(symbol: str, interval: str = "1d", range_key: str = "6mo") -> dict:
    symbol = validate_request(symbol, interval, range_key)
    key = (symbol, interval, range_key)
    ttl = 45 if interval.endswith("m") or interval == "1h" else 300
    with _cache_lock:
        cached = _cache.get(key)
        if cached and time.monotonic() - cached[0] < ttl:
            _cache.move_to_end(key)
            return copy.deepcopy(cached[1])
    if not _upstream_slots.acquire(timeout=3):
        raise MarketError("Hay varias consultas en curso. Intenta de nuevo en un momento.", 503)
    try:
        source = _download(symbol, interval, range_key)
        try:
            payload = parse_response(source, symbol, interval, range_key)
        except (ValueError, TypeError, KeyError, IndexError, AttributeError, OverflowError, OSError):
            raise MarketError("La fuente devolvió un historial no válido.") from None
    finally:
        _upstream_slots.release()
    with _cache_lock:
        _cache[key] = (time.monotonic(), payload)
        _cache.move_to_end(key)
        while len(_cache) > 256:
            _cache.popitem(last=False)
    return copy.deepcopy(payload)
