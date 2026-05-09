import asyncio
import json
import re
from typing import Any

import httpx

from app.config import (
    GROQ_API_KEY,
    GROQ_BASE_URL,
    GROQ_HTTP_CONNECT_TIMEOUT,
    GROQ_HTTP_READ_TIMEOUT,
    GROQ_MAX_ATTEMPTS,
    GROQ_MODEL,
    GROQ_RETRY_BACKOFF_MS,
)


def _retryable_status(code: int) -> bool:
    return code in {408, 409, 425, 429} or code >= 500


class LLMService:
    async def answer(self, system_prompt: str, user_prompt: str) -> str:
        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is not configured.")

        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
            "top_p": 1,
        }
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}

        timeout = httpx.Timeout(GROQ_HTTP_READ_TIMEOUT, connect=GROQ_HTTP_CONNECT_TIMEOUT)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"{GROQ_BASE_URL}/chat/completions", json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        return data["choices"][0]["message"]["content"].strip()

    async def answer_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, object]:
        """Ask the model for a JSON object response (Groq `json_object` when available)."""
        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is not configured.")

        payload: dict[str, Any] = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
            "top_p": 1,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        timeout = httpx.Timeout(GROQ_HTTP_READ_TIMEOUT, connect=GROQ_HTTP_CONNECT_TIMEOUT)

        last_error: Exception | None = None
        for attempt in range(1, GROQ_MAX_ATTEMPTS + 1):
            if meta is not None:
                meta["llm_attempts"] = attempt
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(f"{GROQ_BASE_URL}/chat/completions", json=payload, headers=headers)
                    if response.status_code >= 400:
                        fallback_payload = dict(payload)
                        fallback_payload.pop("response_format", None)
                        response = await client.post(
                            f"{GROQ_BASE_URL}/chat/completions",
                            json=fallback_payload,
                            headers=headers,
                        )
                    response.raise_for_status()
                    data = response.json()

                    usage = data.get("usage")
                    if isinstance(usage, dict) and meta is not None:
                        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                            if usage.get(key) is not None:
                                meta[key] = usage[key]

                raw = data["choices"][0]["message"]["content"].strip()
                return self._parse_json_object(raw)
            except httpx.HTTPStatusError as exc:
                last_error = exc
                code = exc.response.status_code if exc.response is not None else 0
                if attempt < GROQ_MAX_ATTEMPTS and _retryable_status(code):
                    await asyncio.sleep((GROQ_RETRY_BACKOFF_MS / 1000.0) * (2 ** (attempt - 1)))
                    continue
                raise
            except httpx.RequestError as exc:
                last_error = exc
                if attempt < GROQ_MAX_ATTEMPTS:
                    await asyncio.sleep((GROQ_RETRY_BACKOFF_MS / 1000.0) * (2 ** (attempt - 1)))
                    continue
                raise
            except (ValueError, KeyError, TypeError, json.JSONDecodeError):
                raise

        assert last_error is not None
        raise last_error

    @staticmethod
    def _parse_json_object(raw: str) -> dict[str, object]:
        cleaned = raw.strip()
        fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
        if fence:
            cleaned = fence.group(1).strip()
        parsed = json.loads(cleaned)
        if not isinstance(parsed, dict):
            raise ValueError("LLM JSON root must be an object.")
        return parsed
