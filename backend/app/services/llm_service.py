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
