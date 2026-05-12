#!/usr/bin/env python3
"""
Unified production server for NLLM.ING Sovereign Stack.
Serves the Mission Control dashboard (static export) and proxies:
  /api/*   → Mission Control (port 3004)
  /bifrost/* → Bifrost v2 (port 8001)
  /ws/*    → Mission Control WebSocket
"""

import argparse
import asyncio
import http.server
import json
import os
import socketserver
import sys
import threading
import urllib.request
from pathlib import Path


class UnifiedHandler(http.server.SimpleHTTPRequestHandler):
    """Serve static files, proxy API + Bifrost, handle WebSocket upgrade."""

    api_host = "127.0.0.1"
    api_port = 3004
    bifrost_host = "127.0.0.1"
    bifrost_port = 8001

    def log_message(self, fmt, *args):
        # Suppress routine logs; log errors only
        if "404" in args[0] or "500" in args[0]:
            print(f"[dashboard-server] {fmt % args}", file=sys.stderr)

    def do_GET(self):
        if self.path.startswith("/api/"):
            return self._proxy("http", self.api_host, self.api_port)
        if self.path.startswith("/bifrost/"):
            return self._proxy("http", self.bifrost_host, self.bifrost_port, strip_prefix="/bifrost")
        if self.path.startswith("/ws/"):
            self.send_response(426)
            self.end_headers()
            return
        # SPA fallback: serve index.html for unknown paths
        target = self.translate_path(self.path)
        if not os.path.exists(target) or os.path.isdir(target):
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/"):
            return self._proxy("http", self.api_host, self.api_port, method="POST")
        if self.path.startswith("/bifrost/"):
            return self._proxy("http", self.bifrost_host, self.bifrost_port, strip_prefix="/bifrost", method="POST")
        self.send_response(404)
        self.end_headers()

    def do_PUT(self):
        if self.path.startswith("/api/"):
            return self._proxy("http", self.api_host, self.api_port, method="PUT")
        self.send_response(404)
        self.end_headers()

    def do_DELETE(self):
        if self.path.startswith("/api/"):
            return self._proxy("http", self.api_host, self.api_port, method="DELETE")
        self.send_response(404)
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def _proxy(self, scheme, host, port, strip_prefix=None, method="GET"):
        path = self.path
        if strip_prefix and path.startswith(strip_prefix):
            path = path[len(strip_prefix):] or "/"
        url = f"{scheme}://{host}:{port}{path}"

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length else None

        try:
            req = urllib.request.Request(
                url,
                data=body,
                headers={k: v for k, v in self.headers.items() if k.lower() not in ("host", "content-length")},
                method=method,
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() not in ("transfer-encoding", "content-encoding"):
                        self.send_header(k, v)
                self.end_headers()
                self.wfile.write(resp.read())
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            for k, v in e.headers.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(e.read())
        except Exception as e:
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())


def run_server(static_dir: str, port: int, api_port: int, bifrost_port: int):
    UnifiedHandler.api_port = api_port
    UnifiedHandler.bifrost_port = bifrost_port

    os.chdir(static_dir)
    with socketserver.ThreadingTCPServer(("", port), UnifiedHandler) as httpd:
        print(f"[production-server] Serving {static_dir} on :{port}")
        print(f"[production-server] API proxy    → :{api_port}")
        print(f"[production-server] Bifrost proxy → :{bifrost_port}")
        httpd.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Unified production server for NLLM.ING")
    parser.add_argument("--static-dir", required=True, help="Path to dashboard static export")
    parser.add_argument("--port", type=int, default=3000, help="Dashboard port")
    parser.add_argument("--api-port", type=int, default=3004, help="Mission Control port")
    parser.add_argument("--bifrost-port", type=int, default=8001, help="Bifrost port")
    args = parser.parse_args()

    run_server(args.static_dir, args.port, args.api_port, args.bifrost_port)
