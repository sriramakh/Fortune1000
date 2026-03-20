import json
import logging
import re
from typing import Optional

import aiohttp
from openai import AsyncOpenAI

from config import (
    MINIMAX_API_TOKEN,
    MINIMAX_MODEL,
    OPENAI_API_KEY,
    OPENAI_MODEL,
)

logger = logging.getLogger(__name__)

MINIMAX_ENDPOINT = "https://api.minimax.io/v1/text/chatcompletion_v2"


class LLMClient:
    def __init__(self):
        self.openai = AsyncOpenAI(api_key=OPENAI_API_KEY)
        self._minimax_session: Optional[aiohttp.ClientSession] = None

    async def _get_minimax_session(self) -> aiohttp.ClientSession:
        if self._minimax_session is None or self._minimax_session.closed:
            self._minimax_session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {MINIMAX_API_TOKEN}",
                    "Content-Type": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=60),
            )
        return self._minimax_session

    async def complete_minimax(
        self, system: str, user: str, temperature: float = 1.0
    ) -> str:
        session = await self._get_minimax_session()
        payload = {
            "model": MINIMAX_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_completion_tokens": 8192,
            "temperature": temperature,
            "top_p": 0.95,
            "stream": False,
        }

        async with session.post(MINIMAX_ENDPOINT, json=payload) as resp:
            data = await resp.json()
            if resp.status != 200:
                error_msg = data.get("base_resp", {}).get("status_msg", str(data))
                raise RuntimeError(f"MiniMax API error ({resp.status}): {error_msg}")

            # Check for API-level errors
            base_resp = data.get("base_resp", {})
            if base_resp.get("status_code", 0) != 0:
                raise RuntimeError(f"MiniMax error: {base_resp.get('status_msg', str(data))}")

            choices = data.get("choices", [])
            if not choices:
                raise RuntimeError(f"MiniMax returned no choices: {data}")

            return choices[0]["message"]["content"]

    async def complete_openai(
        self, system: str, user: str, temperature: float = 0.3
    ) -> str:
        resp = await self.openai.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=8192,
        )
        return resp.choices[0].message.content

    async def complete_openai_json(
        self, system: str, user: str, temperature: float = 0.3
    ) -> dict:
        raw = await self.complete_openai(system, user, temperature)
        return parse_llm_json(raw)

    async def complete_minimax_json(
        self, system: str, user: str, temperature: float = 1.0
    ) -> dict | list:
        try:
            raw = await self.complete_minimax(system, user, temperature)
        except Exception as e:
            logger.warning(f"MiniMax failed ({e}), falling back to OpenAI")
            raw = await self.complete_openai(system, user, 0.3)
        return parse_llm_json(raw)

    async def close(self):
        if self._minimax_session and not self._minimax_session.closed:
            await self._minimax_session.close()
        await self.openai.close()


def parse_llm_json(text: str) -> dict | list:
    """Parse JSON from LLM output, handling markdown fences."""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        text = match.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        for pattern in [r"\{[\s\S]*\}", r"\[[\s\S]*\]"]:
            match = re.search(pattern, text)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    continue
        logger.error(f"Failed to parse JSON from LLM output: {text[:200]}")
        raise ValueError(f"Could not parse JSON from LLM response")
