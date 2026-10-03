from __future__ import annotations

import httpx
import pytest

from vigilo_core.config import config
from vigilo_integrations.errors import LlmProviderError
from vigilo_integrations.llm import generate_remediation_text


@pytest.fixture(autouse=True)
def _anthropic_configured(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-haiku-4-5")
    config.cache_clear()
    yield
    config.cache_clear()


async def test_sends_a_well_formed_request_and_extracts_text():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["api_key"] = request.headers["x-api-key"]
        return httpx.Response(200, json={"content": [{"type": "text", "text": "hello"}]})

    result = await generate_remediation_text(
        prompt="fix this", transport=httpx.MockTransport(handler)
    )

    assert result == "hello"
    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    assert captured["api_key"] == "test-key"


async def test_concatenates_multiple_text_blocks():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"content": [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]},
        )

    result = await generate_remediation_text(
        prompt="fix this", transport=httpx.MockTransport(handler)
    )

    assert result == "ab"


async def test_raises_on_a_rejection():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "invalid api key"}})

    with pytest.raises(LlmProviderError):
        await generate_remediation_text(prompt="fix this", transport=httpx.MockTransport(handler))


async def test_raises_on_a_transport_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated connection failure")

    with pytest.raises(LlmProviderError):
        await generate_remediation_text(prompt="fix this", transport=httpx.MockTransport(handler))


async def test_raises_when_response_has_no_text_content():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"content": []})

    with pytest.raises(LlmProviderError):
        await generate_remediation_text(prompt="fix this", transport=httpx.MockTransport(handler))


async def test_raises_when_not_configured(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    config.cache_clear()

    with pytest.raises(LlmProviderError):
        await generate_remediation_text(prompt="fix this")


async def test_sends_workspace_header_when_configured(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_WORKSPACE_ID", "wrkspc_123")
    config.cache_clear()
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(request.headers)
        return httpx.Response(200, json={"content": [{"type": "text", "text": "ok"}]})

    await generate_remediation_text(prompt="p", transport=httpx.MockTransport(handler))
    assert captured["anthropic-workspace-id"] == "wrkspc_123"


async def test_no_workspace_header_by_default():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(request.headers)
        return httpx.Response(200, json={"content": [{"type": "text", "text": "ok"}]})

    await generate_remediation_text(prompt="p", transport=httpx.MockTransport(handler))
    assert "anthropic-workspace-id" not in captured


async def test_empty_model_env_falls_back_to_default(monkeypatch):
    """Compose passes an unset ANTHROPIC_MODEL as "", which must not become the model."""
    monkeypatch.setenv("ANTHROPIC_MODEL", "")
    config.cache_clear()
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured.update(json.loads(request.content))
        return httpx.Response(200, json={"content": [{"type": "text", "text": "ok"}]})

    await generate_remediation_text(prompt="p", transport=httpx.MockTransport(handler))
    assert captured["model"] == "claude-haiku-4-5"
