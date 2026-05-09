import json
import re

import httpx

from app.config import GROQ_API_KEY, GROQ_BASE_URL, GROQ_MODEL


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

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(f"{GROQ_BASE_URL}/chat/completions", json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        return data["choices"][0]["message"]["content"].strip()

    async def answer_json(self, system_prompt: str, user_prompt: str) -> dict[str, object]:
        """Ask the model for a JSON object response (Groq `json_object` when available)."""
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
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(f"{GROQ_BASE_URL}/chat/completions", json=payload, headers=headers)
            if response.status_code >= 400:
                payload.pop("response_format", None)
                response = await client.post(f"{GROQ_BASE_URL}/chat/completions", json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        raw = data["choices"][0]["message"]["content"].strip()
        return self._parse_json_object(raw)

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
