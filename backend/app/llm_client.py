"""
Shared Groq client, plus a small helper for getting strict JSON back.

Two things worth knowing about GPT-OSS models on Groq:

1. They're reasoning models - they spend some tokens "thinking" before
   producing the final answer, and those tokens count against
   max_tokens. reasoning_effort="low" keeps that overhead small so
   there's budget left for the actual output.

2. Free tier has a fairly tight per-minute token cap (e.g. 8,000 TPM
   for GPT-OSS 120B). A single research run fires several calls
   (planner, writer, critic, possibly revise+critique again) in quick
   succession, which can trip that cap even with reasonably-sized
   prompts. _call_with_retry backs off and retries once on a 429/413
   rate-limit response rather than crashing the whole pipeline.
"""

import json
import re
import time
import logging
from groq import Groq, APIStatusError
from app.config import settings

logger = logging.getLogger(__name__)

_client = Groq(api_key=settings.groq_api_key)

_RATE_LIMIT_STATUS_CODES = {413, 429}


def _call_with_retry(**kwargs):
    """Call the Groq chat completions endpoint, retrying once on a
    rate-limit response after a short wait."""
    try:
        return _client.chat.completions.create(**kwargs)
    except APIStatusError as e:
        if e.status_code in _RATE_LIMIT_STATUS_CODES:
            wait_seconds = 20
            logger.warning(
                "Groq rate limit hit (status %d) - waiting %ds and retrying once",
                e.status_code, wait_seconds,
            )
            time.sleep(wait_seconds)
            return _client.chat.completions.create(**kwargs)
        raise


def call_llm_json(system_prompt: str, user_prompt: str, max_tokens: int = 2000) -> dict:
    response = _call_with_retry(
        model=settings.groq_model,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
        reasoning_effort="low",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    raw_text = response.choices[0].message.content.strip()
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw_text, flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Groq did not return valid JSON.\nRaw response:\n{raw_text}") from e


def call_llm_text(system_prompt: str, user_prompt: str, max_tokens: int = 2000) -> str:
    response = _call_with_retry(
        model=settings.groq_model,
        max_tokens=max_tokens,
        reasoning_effort="low",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content.strip()