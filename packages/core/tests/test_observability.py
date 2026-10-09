from __future__ import annotations

import sys
import types

from vigilo_core.observability import init_error_tracking, scrub_event


def test_does_nothing_without_a_dsn(monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    fake = types.SimpleNamespace(init=lambda **kw: (_ for _ in ()).throw(AssertionError("called")))
    monkeypatch.setitem(sys.modules, "sentry_sdk", fake)
    assert init_error_tracking("api") is False


def test_starts_with_privacy_preserving_settings_when_a_dsn_is_set(monkeypatch):
    seen: dict = {}
    tags: dict = {}
    fake = types.SimpleNamespace(
        init=lambda **kw: seen.update(kw), set_tag=lambda k, v: tags.update({k: v})
    )
    monkeypatch.setitem(sys.modules, "sentry_sdk", fake)
    monkeypatch.setenv("SENTRY_DSN", "https://key@example.ingest.sentry.io/1")
    monkeypatch.setenv("SENTRY_ENVIRONMENT", "staging")

    assert init_error_tracking("scanner") is True
    assert seen["send_default_pii"] is False
    assert seen["include_local_variables"] is False
    assert seen["max_request_body_size"] == "never"
    assert seen["traces_sample_rate"] == 0.0
    assert seen["environment"] == "staging"
    assert seen["before_send"] is scrub_event
    assert tags == {"service": "scanner"}


def test_a_missing_sdk_does_not_stop_startup(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "https://key@example.ingest.sentry.io/1")
    monkeypatch.setitem(sys.modules, "sentry_sdk", None)  # import raises ImportError
    assert init_error_tracking("api") is False


def test_events_lose_everything_that_could_hold_a_secret():
    event = {
        "message": "boom",
        "request": {
            "url": "https://api.example/v1/invites/nxi_secret/accept",
            "method": "POST",
            "data": {"token": "nxi_secret"},
            "headers": {"Authorization": "Bearer abc"},
            "cookies": {"__session": "x"},
            "query_string": "cursor=abc",
            "env": {"REMOTE_ADDR": "1.2.3.4"},
        },
        "user": {"email": "a@b.co"},
    }
    cleaned = scrub_event(event)
    assert set(cleaned["request"]) == {"url", "method"}
    assert cleaned["request"]["url"] == "https://api.example/v1/invites/[redacted]/accept"
    assert "user" not in cleaned


def test_one_time_links_are_redacted_wherever_they_appear():
    for url, expected in [
        ("https://app.example/invite/nxi_abc", "https://app.example/invite/[redacted]"),
        ("https://app.example/share/tok123", "https://app.example/share/[redacted]"),
        ("https://api.example/v1/share/tok123", "https://api.example/v1/share/[redacted]"),
        ("https://api.example/v1/targets", "https://api.example/v1/targets"),
    ]:
        assert scrub_event({"request": {"url": url}})["request"]["url"] == expected
