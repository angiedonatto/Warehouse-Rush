import time

import pytest

from api._cloud import CloudAPI, SignedSessions
from api._viewer import ViewerSession

TEST_SECRET = "local-unit-test-key-32-characters-minimum"


def test_signed_roundtrip_retains_mission_and_rejects_tampering():
    sessions = SignedSessions(TEST_SECRET)
    session = ViewerSession(settings={"orders": 1, "blocked": True})
    for _ in range(12):
        session.step()
    token = sessions.dump(session)
    restored = sessions.load(token)
    assert restored.payload() == session.payload()
    with pytest.raises(ValueError, match="Firma"):
        sessions.load(token[:-1] + ("0" if token[-1] != "0" else "1"))
    assert len(token) < 3800


def test_visitor_sessions_are_isolated_across_api_instances():
    api = CloudAPI(TEST_SECRET)
    a, token_a = api.handle("POST", "reset", {"orders": 1, "policy": "manual"})
    b, token_b = api.handle("POST", "reset", {"orders": 2, "policy": "heuristic"})
    for _ in range(3):
        a, token_a = CloudAPI(TEST_SECRET).handle("POST", "step", {"action": 2}, token_a)
    b, _ = CloudAPI(TEST_SECRET).handle("GET", "state", token=token_b)
    assert a["state"]["tiempo"] == 3 and a["orders"] == 1
    assert b["state"]["tiempo"] == 0 and b["orders"] == 2
    assert b["state"]["theta"] == 0


def test_random_policy_sequence_survives_stateless_restoration():
    api = CloudAPI(TEST_SECRET)
    direct = ViewerSession(settings={"orders": 1, "policy": "random", "seed": 847})
    payload, token = api.handle("POST", "reset", {"orders": 1, "policy": "random", "seed": 847})
    for _ in range(35):
        expected = direct.step()
        payload, token = CloudAPI(TEST_SECRET).handle("POST", "step", {}, token)
        assert payload["last_action"] == expected["last_action"]
        assert payload["state"] == expected["state"]
        assert payload["observation"] == expected["observation"]


def test_full_blocked_mission_completes_through_stateless_requests():
    api = CloudAPI(TEST_SECRET)
    payload, token = api.handle("POST", "reset", {"orders": 2, "blocked": True})
    while not payload["done"]:
        payload, token = CloudAPI(TEST_SECRET).handle("POST", "step", {}, token)
        assert len(token) < 3800
    assert payload["info"]["success"] and payload["state"]["entregas"] == 2
    assert payload["state"]["tiempo"] == 91
    restored, _ = CloudAPI(TEST_SECRET).handle("GET", "state", token=token)
    assert restored["done"] and restored["state"] == payload["state"]


def test_expired_or_invalid_cookie_cannot_inject_state(monkeypatch):
    api = CloudAPI(TEST_SECRET)
    payload, token = api.handle("GET", "state")
    monkeypatch.setattr(time, "time", lambda: 9_999_999_999)
    with pytest.raises(ValueError, match="expirada"):
        api.handle("POST", "step", {}, token)
    fresh, _ = api.handle("GET", "state", token=token)
    assert fresh["state"]["tiempo"] == 0
    fresh, _ = api.handle("GET", "state", token="forged.cookie")
    assert fresh["state"]["carga"] is None and fresh["state"]["entregas"] == 0


def test_missing_or_short_secret_is_rejected():
    for secret in (None, "short"):
        with pytest.raises(RuntimeError, match="WAREHOUSE_SESSION_SECRET"):
            CloudAPI(secret)


def test_read_only_state_does_not_overwrite_newer_browser_cookie():
    api = CloudAPI(TEST_SECRET)
    _, original = api.handle("POST", "reset", {"blocked": True})
    _, updated = api.handle("POST", "reset", {"blocked": False})
    older_read, replacement = api.handle("GET", "state", token=original)
    assert older_read["state"]["pasillo_bloqueado"] is True
    assert replacement is None  # Sin Set-Cookie que pueda revertir el POST.
    current, replacement = api.handle("GET", "state", token=updated)
    assert current["state"]["pasillo_bloqueado"] is False and replacement is None
