# ==============================================================================
# service.py - local HTTP service for the Chrome extension
#
#   GET  /health    {"ok": true}
#   POST /analyze   body: {league, pro_schedule?, free_agents?, swid?, team_id?}
#                   -> pipeline.analyze() result (numbers only, no AI)
#   POST /explain   body: {result, ai: {provider, api_key, model, base_url}}
#                   -> {"text", "source": "ai"|"template", "error"}
#
# Safety rules (the service holds no secrets of its own, but it must not be a
# door for other web pages):
#   * binds to 127.0.0.1 only, never 0.0.0.0
#   * the Host header must be 127.0.0.1 / localhost (stops DNS rebinding)
#   * a request that carries an Origin must come from a chrome-extension://
#     page (pinned to EXTENSION_ID when set). Browsers always send Origin on a
#     cross-origin POST, so a web page cannot get through. curl sends none.
#   * POST bodies must be application/json, which forces a CORS preflight
#   * bodies are size-limited, and are never logged (they hold the AI key)
#
# stdlib http.server on purpose: no new dependency for three small endpoints.
# ==============================================================================
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from loguru import logger

from ffai.ai import AiSettings, explain
from ffai.config import settings
from ffai.parser import EspnParseError
from ffai.pipeline import analyze

HOST = "127.0.0.1"
# A real league response with player stats for every team can be several MB.
MAX_BODY_BYTES = 16 * 1024 * 1024
EXTENSION_ORIGIN_PREFIX = "chrome-extension://"


class _Handler(BaseHTTPRequestHandler):
    server_version = "ffai"
    protocol_version = "HTTP/1.1"

    # --- plumbing ---

    def log_message(self, format, *args):  # noqa: A002 - signature fixed by the base class
        logger.debug("http " + format % args)  # request line only, never the body

    def _origin_allowed(self) -> bool:
        origin = self.headers.get("Origin")
        if origin is None:
            return True  # not a browser (curl, tests)
        if not origin.startswith(EXTENSION_ORIGIN_PREFIX):
            return False
        return not settings.extension_id or origin == EXTENSION_ORIGIN_PREFIX + settings.extension_id

    def _host_allowed(self) -> bool:
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]").lower()
        return host in ("127.0.0.1", "localhost")

    def _send_json(self, status: int, body: dict) -> None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        origin = self.headers.get("Origin")
        if origin and self._origin_allowed():
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.end_headers()
        self.wfile.write(data)

    def _error(self, status: int, message: str, kind: str = "request") -> None:
        self._send_json(status, {"error": message, "kind": kind})

    def _guard(self) -> bool:
        """False (after answering) when the request must not go further."""
        if not self._host_allowed():
            self._error(403, "bad Host header")
            return False
        if not self._origin_allowed():
            self._error(403, "origin not allowed")
            return False
        return True

    # --- routes ---

    def do_OPTIONS(self):  # CORS preflight
        if not self._guard():
            return
        self.send_response(204)
        origin = self.headers.get("Origin")
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Private-Network", "true")
            self.send_header("Access-Control-Max-Age", "600")
            self.send_header("Vary", "Origin")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        if not self._guard():
            return
        if self.path == "/health":
            self._send_json(200, {"ok": True})
        else:
            self._error(404, "not found")

    def do_POST(self):
        if not self._guard():
            return
        if self.path not in ("/analyze", "/explain"):
            self._error(404, "not found")
            return
        if not (self.headers.get("Content-Type") or "").startswith("application/json"):
            self._error(415, "Content-Type must be application/json")
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self._error(400, "bad Content-Length")
            return
        if length > MAX_BODY_BYTES:
            self._error(413, f"body is larger than {MAX_BODY_BYTES // (1024 * 1024)} MB")
            # The body is not read, so the connection cannot be reused safely.
            self.close_connection = True
            return
        try:
            body = json.loads(self.rfile.read(length) or b"null")
        except ValueError:
            self._error(400, "body is not valid JSON")
            return

        try:
            if self.path == "/analyze":
                self._send_json(200, analyze(body))
            else:
                self._explain(body)
        except EspnParseError as e:
            self._error(422, str(e), kind="parse")
        except Exception:  # noqa: BLE001 - never crash the server on one request
            # No exception text in the answer or the log line: a message could
            # echo part of the body. The traceback goes to the log only.
            logger.exception("request failed")
            self._error(500, "internal error, see the service log", kind="internal")

    def _explain(self, body) -> None:
        if not isinstance(body, dict) or not isinstance(body.get("result"), dict):
            self._error(400, "expected {\"result\": {...}, \"ai\": {...}}")
            return
        outcome = explain(body["result"], AiSettings.from_request(body.get("ai")))
        self._send_json(200, {"text": outcome.text, "source": outcome.source, "error": outcome.error})


def make_server(port: int | None = None) -> ThreadingHTTPServer:
    """Port 0 picks a free port (used by tests)."""
    return ThreadingHTTPServer((HOST, settings.service_port if port is None else port), _Handler)


def serve(port: int | None = None) -> None:
    server = make_server(port)
    logger.info(f"ffai service listening on http://{HOST}:{server.server_address[1]} (Ctrl+C to stop)")
    try:
        server.serve_forever()
    finally:
        server.server_close()
