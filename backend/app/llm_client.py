"""
Shared Groq client, plus a small helper for getting strict JSON back.

Every agent (planner, writer, critic later) calls through
`call_llm_json` / `call_llm_text` so the JSON contract and error
handling live in exactly one place. Swapping providers later (e.g.
back to Claude, or to Gemini) means editing only this file.
"""

import json
import re
from groq import Groq
from app.config import settings

_client = Groq(api_key=settings.groq_api_key)


def call_llm_json(system_prompt: str, user_prompt: str, max_tokens: int = 1500) -> dict:
    """
    Call Groq and parse the response as JSON.

    Groq's OpenAI-compatible API supports native JSON mode via
    response_format — more reliable than asking nicely in the prompt,
    but we still keep the fence-stripping as a safety net.
    """
    response = _client.chat.completions.create(
        model=settings.groq_model,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
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
        raise ValueError(
            f"Groq did not return valid JSON.\nRaw response:\n{raw_text}"
        ) from e


def call_llm_text(system_prompt: str, user_prompt: str, max_tokens: int = 2000) -> str:
    """Call Groq and return plain text (used by the Writer stage)."""
    response = _client.chat.completions.create(
        model=settings.groq_model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content.strip()
