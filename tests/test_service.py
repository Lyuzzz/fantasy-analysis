import http.client
import json
import threading
from pathlib import Path

import pytest

from ffai import ai, service
from ffai.config import settings

FIXTURES = Path(__file__).parent / "fixtures"
EXT_ORIGIN = "chrome-extension://abcdefghijklmnopabcdefghijklmnop"
MY_SWID = "{AAAAAAAA-0000-4000-8000-000000000001}"


def _load(name):
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def server():
    srv = service.make_server(0)  # Port 0 lets the OS pick a free port.
    # A short poll interval makes shutdown() fast. The default interval waits up to 0.5 s.
    thread = threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
    thread.start()
    yield srv
    srv.shutdown()
    srv.server_close()


def call(server, method, path, body=None, headers=None, raw=None):
    """Send one real HTTP request over a local socket. Return (status, headers, json)."""
    conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=10)
    send_headers = {} if headers is None else dict(headers)
    data = raw
    if body is not None:
        data = json.dumps(body).encode()
        send_headers.setdefault("Content-Type", "application/json")
    conn.request(method, path, body=data, headers=send_headers)
    response = conn.getresponse()
    payload = response.read()
    conn.close()
    return response.status, response, (json.loads(payload) if payload else None)


@pytest.fixture
def payload():
    return {
        "league": _load("league_view.json"),
        "pro_schedule": _load("pro_schedule.json"),
        "free_agents": _load("free_agents.json"),
        "swid": MY_SWID,
    }


# Basics


def test_health(server):
    status, _, body = call(server, "GET", "/health")
    assert (status, body) == (200, {"ok": True})


def test_it_listens_on_loopback_only(server):
    assert server.server_address[0] == "127.0.0.1"


def test_unknown_path_is_404(server):
    assert call(server, "GET", "/nope")[0] == 404
    assert call(server, "POST", "/nope", {})[0] == 404


def test_analyze_round_trip(server, payload):
    status, _, body = call(server, "POST", "/analyze", payload)
    assert status == 200
    assert body["team"]["id"] == 2
    assert body["starters"] and "pending" in body


# Request checks


def test_bad_json_is_400(server):
    status, _, body = call(server, "POST", "/analyze", raw=b"{not json", headers={"Content-Type": "application/json"})
    assert status == 400 and "JSON" in body["error"]


def test_wrong_content_type_is_415(server):
    status, *_ = call(server, "POST", "/analyze", raw=b"{}", headers={"Content-Type": "text/plain"})
    assert status == 415


def test_oversized_body_is_413(server, monkeypatch):
    monkeypatch.setattr(service, "MAX_BODY_BYTES", 100)
    status, _, body = call(server, "POST", "/analyze", raw=b"x" * 500, headers={"Content-Type": "application/json"})
    assert status == 413


def test_espn_format_problem_is_422_with_a_readable_message(server, payload):
    del payload["league"]["settings"]["rosterSettings"]["lineupSlotCounts"]
    status, _, body = call(server, "POST", "/analyze", payload)
    assert status == 422 and body["kind"] == "parse" and "lineupSlotCounts" in body["error"]


def test_unknown_swid_is_422(server, payload):
    payload["swid"] = "{NOT-ME}"
    assert call(server, "POST", "/analyze", payload)[0] == 422


def test_internal_error_is_500_and_the_server_keeps_running(server, payload, monkeypatch):
    def boom(_):
        raise RuntimeError("secret detail from the body")

    monkeypatch.setattr(service, "analyze", boom)
    status, _, body = call(server, "POST", "/analyze", payload)
    assert status == 500
    assert "secret detail" not in json.dumps(body)
    assert call(server, "GET", "/health")[0] == 200


# Who may call


def test_foreign_web_page_origin_is_rejected(server, payload):
    status, *_ = call(server, "POST", "/analyze", payload, headers={"Origin": "https://evil.example"})
    assert status == 403


def test_foreign_origin_cannot_read_health_either(server):
    assert call(server, "GET", "/health", headers={"Origin": "https://evil.example"})[0] == 403


def test_extension_origin_is_allowed_and_echoed(server, payload):
    status, response, _ = call(server, "POST", "/analyze", payload, headers={"Origin": EXT_ORIGIN})
    assert status == 200
    assert response.getheader("Access-Control-Allow-Origin") == EXT_ORIGIN


def test_pinned_extension_id_rejects_other_extensions(server, payload, monkeypatch):
    monkeypatch.setattr(settings, "extension_id", "abcdefghijklmnopabcdefghijklmnop")
    assert call(server, "POST", "/analyze", payload, headers={"Origin": EXT_ORIGIN})[0] == 200
    other = "chrome-extension://zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"
    assert call(server, "POST", "/analyze", payload, headers={"Origin": other})[0] == 403


def test_other_host_header_is_rejected(server):
    # This is DNS rebinding. A page on evil.example resolves to 127.0.0.1 and sends this Host.
    status, *_ = call(server, "GET", "/health", headers={"Host": "evil.example"})
    assert status == 403


def test_preflight(server):
    status, response, _ = call(
        server, "OPTIONS", "/analyze", headers={"Origin": EXT_ORIGIN, "Access-Control-Request-Method": "POST"}
    )
    assert status == 204
    assert response.getheader("Access-Control-Allow-Origin") == EXT_ORIGIN
    assert "POST" in response.getheader("Access-Control-Allow-Methods")
    assert "Content-Type" in response.getheader("Access-Control-Allow-Headers")


def test_preflight_from_a_web_page_is_rejected(server):
    status, *_ = call(server, "OPTIONS", "/analyze", headers={"Origin": "https://evil.example"})
    assert status == 403


# Explain


def test_explain_without_a_key_returns_the_template(server, payload, monkeypatch):
    for name in ("ai_api_key", "ai_model"):
        monkeypatch.setattr(settings, name, "")
    result = call(server, "POST", "/analyze", payload)[2]
    status, _, body = call(server, "POST", "/explain", {"result": result, "ai": {}})
    assert status == 200
    assert body["source"] == "template" and body["text"] and "key" in body["error"]


def test_explain_passes_the_panel_settings_to_the_model(server, payload, monkeypatch):
    seen = {}

    def fake_explain(result, ai_settings):
        seen["ai"] = ai_settings
        return ai.Explanation("advice", "ai")

    monkeypatch.setattr(service, "explain", fake_explain)
    result = call(server, "POST", "/analyze", payload)[2]
    ai_body = {"provider": "anthropic", "api_key": "k-1", "model": "claude-sonnet-5-5"}
    status, _, body = call(server, "POST", "/explain", {"result": result, "ai": ai_body})
    assert (status, body["text"], body["source"]) == (200, "advice", "ai")
    assert (seen["ai"].api_key, seen["ai"].model) == ("k-1", "claude-sonnet-5-5")


def test_explain_needs_a_result(server):
    assert call(server, "POST", "/explain", {"ai": {}})[0] == 400
    assert call(server, "POST", "/explain", [])[0] == 400


def test_the_api_key_never_reaches_the_service_log(server, payload, monkeypatch):
    from loguru import logger

    monkeypatch.setattr(ai.requests, "post", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom sk-live-key")))
    lines = []
    sink = logger.add(lines.append, level="DEBUG")
    try:
        result = call(server, "POST", "/analyze", payload)[2]
        call(server, "POST", "/explain", {"result": result, "ai": {"api_key": "sk-live-key", "model": "m"}})
    finally:
        logger.remove(sink)
    assert not any("sk-live-key" in str(line) for line in lines)
