import httpx
import pytest

from app.core.exceptions import LLMUnavailableError
from app.core.llm import GroqGateway, load_groq_keys


def ok_transport(payload: str, status: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"choices": [{"message": {"content": payload}}]})
    return httpx.MockTransport(handler)


def test_no_keys_rejected():
    with pytest.raises(LLMUnavailableError):
        GroqGateway(api_keys=[])


def test_chat_json_parses_response():
    gateway = GroqGateway(
        api_keys=["key-a"], transport=ok_transport('{"spf": 30}')
    )
    assert gateway.chat_json([{"role": "user", "content": "hi"}]) == {"spf": 30}


def test_round_robin_across_keys():
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["authorization"])
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "{}"}}]}
        )

    gateway = GroqGateway(
        api_keys=["key-a", "key-b"], transport=httpx.MockTransport(handler)
    )
    messages = [{"role": "user", "content": "hi"}]
    gateway.chat_json(messages)
    gateway.chat_json(messages)
    assert seen == ["Bearer key-a", "Bearer key-b"]


def test_429_fails_over_to_next_key():
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        auth = request.headers["authorization"]
        calls.append(auth)
        if auth == "Bearer key-a":
            return httpx.Response(429, json={"error": {"message": "limit"}})
        return httpx.Response(
            200, json={"choices": [{"message": {"content": '{"ok": true}'}}]}
        )

    gateway = GroqGateway(
        api_keys=["key-a", "key-b"], transport=httpx.MockTransport(handler)
    )
    result = gateway.chat_json([{"role": "user", "content": "hi"}])
    assert result == {"ok": True}
    assert calls == ["Bearer key-a", "Bearer key-b"]


def test_all_keys_limited_raises_without_leaking_key():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "limit"}})

    gateway = GroqGateway(
        api_keys=["key-a", "key-b"], transport=httpx.MockTransport(handler)
    )
    with pytest.raises(LLMUnavailableError) as exc_info:
        gateway.chat_json([{"role": "user", "content": "hi"}])
    assert "key-a" not in str(exc_info.value)
    assert "key-b" not in str(exc_info.value)


def test_unparseable_json_raises():
    gateway = GroqGateway(api_keys=["key-a"], transport=ok_transport("not json"))
    with pytest.raises(LLMUnavailableError):
        gateway.chat_json([{"role": "user", "content": "hi"}])


def test_load_keys_dedupes_and_skips_empty(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    for i in range(1, 21):
        monkeypatch.delenv(f"GROQ_API_KEY_{i}", raising=False)
    monkeypatch.setenv("GROQ_API_KEY_1", "key-a")
    monkeypatch.setenv("GROQ_API_KEY_2", "key-a")
    assert load_groq_keys() == ["key-a"]
