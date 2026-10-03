"""Loopback-only server for the local browser GUI."""
from __future__ import annotations

import argparse
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .market import DEFAULT_SYMBOLS, INTERVALS, RANGES, MarketError, get_market_data

WEB_ROOT = Path(__file__).parent / "web"
ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/charts.js": ("charts.js", "text/javascript; charset=utf-8"),
    "/favicon.svg": ("favicon.svg", "image/svg+xml"),
}


class Handler(BaseHTTPRequestHandler):
    server_version = "MarketGridLocal"
    sys_version = ""

    def setup(self):
        super().setup()
        self.connection.settimeout(20)

    def log_message(self, format, *args):
        # Do not persist requested tickers or query strings in access logs.
        pass

    def _send(self, body: bytes, status: int, content_type: str, head: bool = False):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        if not head:
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def _json(self, value: dict, status: int = 200):
        self._send(json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8"), status, "application/json; charset=utf-8", self.command == "HEAD")

    def _allowed_origin(self):
        port = self.server.server_port
        allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}
        host = self.headers.get("Host", "")
        origin = self.headers.get("Origin")
        fetch_site = self.headers.get("Sec-Fetch-Site")
        return host in allowed and (origin is None or origin == f"http://{host}") and fetch_site != "cross-site"

    def do_HEAD(self):
        self._handle(head=True)

    def do_GET(self):
        self._handle()

    def _handle(self, head: bool = False):
        if not self._allowed_origin():
            self._json({"error": "Esta aplicación solo admite solicitudes desde su dirección local."}, 403)
            return
        if len(self.path) > 2048:
            self._json({"error": "La solicitud es demasiado larga."}, 400)
            return
        try:
            parsed = urlsplit(self.path)
            params = parse_qs(parsed.query, keep_blank_values=True, max_num_fields=8)
        except ValueError:
            self._json({"error": "Parámetros de consulta no válidos."}, 400)
            return
        if parsed.path in ASSETS:
            filename, content_type = ASSETS[parsed.path]
            self._send((WEB_ROOT / filename).read_bytes(), 200, content_type, head)
        elif parsed.path == "/api/config" and not head:
            self._json({"intervals": INTERVALS, "ranges": RANGES, "defaultSymbols": DEFAULT_SYMBOLS, "autoRefreshMs": 300000})
        elif parsed.path == "/api/market" and not head:
            if any(len(value) != 1 for value in params.values()) or any(key not in {"symbol", "interval", "range"} for key in params):
                self._json({"error": "Parámetros de consulta no válidos."}, 400)
                return
            try:
                self._json(get_market_data(params.get("symbol", [""])[0], params.get("interval", ["1d"])[0], params.get("range", ["6mo"])[0]))
            except MarketError as error:
                self._json({"error": str(error)}, error.status)
            except (ValueError, TypeError, KeyError, IndexError, AttributeError, OverflowError, OSError):
                self._json({"error": "La fuente devolvió un historial no válido."}, 502)
        else:
            self._json({"error": "Recurso no encontrado."}, 404)


def create_server(port: int = 8000):
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main():
    parser = argparse.ArgumentParser(description="Market Grid: Python + interfaz local HTML/JavaScript")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true", help="No abrir automáticamente el navegador")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("El puerto debe estar entre 1 y 65535.")
    try:
        server = create_server(args.port)
    except OSError:
        parser.exit(1, "No se pudo abrir el puerto local. Prueba otro con --port.\n")
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"Market Grid: {url}\nDeja esta terminal abierta. Ctrl+C para cerrar.", flush=True)
    if not args.no_browser:
        timer = threading.Timer(0.5, webbrowser.open, args=(url,))
        timer.daemon = True
        timer.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nMarket Grid cerrado.")
    finally:
        server.server_close()
