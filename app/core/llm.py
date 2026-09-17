"""Groq LPU gateway with multi-key rotation.

Keys are read from GROQ_API_KEY, GROQ_API_KEY_1..N environment entries.
Rotation is round-robin, a key that answers 429 or 401 is cooled down
and the request fails over to the next key within the same call.
Key material never appears in logs, errors, or responses, only key indexes.
"""

import json
import os
import threading
import time

import httpx

from app.core.config import settings
from app.core.exceptions import LLMUnavailableError

JSON_RETRYABLE_CODE = "json_validate_failed"

def load_groq_keys() -> list[str]:
    candidates = [os.environ.get("GROQ_API_KEY", "")]
    candidates += [os.environ.get(f"GROQ_API_KEY_{i}", "") for i in range(1, 21)]
    seen: list[str] = []
    for key in candidates:
        key = key.strip()
        if key and key not in seen:
            seen.append(key)
    return seen

class GroqGateway:
    def __init__(
        self,
        api_keys: list[str] | None = None,
        transport: httpx.BaseTransport | None = None,
    ):
        keys = api_keys if api_keys is not None else load_groq_keys()
        if not keys:
            raise LLMUnavailableError("groq api keys not configured")
        self._keys = keys
        self._index = 0
        self._lock = threading.Lock()
        self._cooldown_until = {i: 0.0 for i in range(len(keys))}
        self._client = httpx.Client(
            base_url=settings.groq_base_url,
            timeout=settings.groq_timeout_s,
            transport=transport,
        )

    def key_count(self) -> int:
        return len(self._keys)

    def _pick(self) -> int | None:
        now = time.monotonic()
        with self._lock:
            for _ in range(len(self._keys)):
                candidate = self._index
                self._index = (self._index + 1) % len(self._keys)
                if self._cooldown_until[candidate] <= now:
                    return candidate
        return None

    def _cool(self, index: int) -> None:
        with self._lock:
            self._cooldown_until[index] = (
                time.monotonic() + settings.groq_key_cooldown_s
            )

    def chat_json(
        self,
        messages: list[dict],
        model: str | None = None,
        max_tokens: int = 1024,
    ) -> dict:
        attempts = 0
        payload_messages = [
            {"role": "system", "content": "Return valid JSON only."},
            *messages,
        ]
        while attempts < len(self._keys):
            index = self._pick()
            if index is None:
                break
            attempts += 1
            try:
                response = self._client.post(
                    "/chat/completions",
                    headers={"Authorization": f"Bearer {self._keys[index]}"},
                    json={
                        "model": model or settings.groq_model_agent,
                        "messages": payload_messages,
                        "response_format": {"type": "json_object"},
                        "max_tokens": max_tokens,
                    },
                )
            except httpx.HTTPError:
                self._cool(index)
                continue
            if response.status_code == 200:
                try:
                    content = response.json()["choices"][0]["message"]["content"]
                    return json.loads(content)
                except (KeyError, IndexError, ValueError) as exc:
                    raise LLMUnavailableError(
                        f"groq key at position {index} returned unparseable json"
                    ) from exc
            if response.status_code in (401, 429):
                self._cool(index)
                continue
            if response.status_code == 400 and JSON_RETRYABLE_CODE in response.text:
                self._cool(index)
                continue
            if 500 <= response.status_code < 600:
                self._cool(index)
                continue
            raise LLMUnavailableError(
                f"groq request rejected with status {response.status_code}"
            )
        raise LLMUnavailableError("all groq keys cooling down or unreachable")

    def chat_stream(
        self,
        messages: list[dict],
        model: str | None = None,
        max_tokens: int = 1024,
    ):
        attempts = 0
        while attempts < len(self._keys):
            index = self._pick()
            if index is None:
                break
            attempts += 1
            try:
                stream = self._client.stream(
                    "POST",
                    "/chat/completions",
                    headers={"Authorization": f"Bearer {self._keys[index]}"},
                    json={
                        "model": model or settings.groq_model_agent,
                        "messages": messages,
                        "max_tokens": max_tokens,
                        "stream": True,
                    },
                )
            except httpx.HTTPError:
                self._cool(index)
                continue
            with stream as response:
                if response.status_code != 200:
                    if response.status_code in (401, 429) or (
                        500 <= response.status_code < 600
                    ):
                        self._cool(index)
                        continue
                    raise LLMUnavailableError(
                        f"groq request rejected with status {response.status_code}"
                    )
                for line in response.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[len("data:"):].strip()
                    if data == "[DONE]":
                        return
                    try:
                        delta = json.loads(data)["choices"][0]["delta"].get(
                            "content"
                        )
                    except (KeyError, IndexError, ValueError):
                        continue
                    if delta:
                        yield delta
                return
        raise LLMUnavailableError("all groq keys cooling down or unreachable")

_gateway: GroqGateway | None = None
_gateway_lock = threading.Lock()

def get_groq_gateway() -> GroqGateway:
    global _gateway
    if _gateway is None:
        with _gateway_lock:
            if _gateway is None:
                _gateway = GroqGateway()
    return _gateway
