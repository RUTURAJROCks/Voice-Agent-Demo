"""Multi-provider client (OpenRouter, Gemini, ChatGPT, Claude) used to polish speech."""
import logging
import httpx
from .config import get_settings

logger = logging.getLogger(__name__)


def ensure_question_preserved(reply: str, text: str) -> str:
    if not text:
        return reply
    if "?" in reply and "?" not in text:
        return reply
    return text


async def polish_spoken_reply(
    reply: str,
    *,
    state: str,
    provider: str = "openrouter",
    api_key: str = ""
) -> tuple[str, str | None]:
    settings = get_settings()
    if state in ("booked", "escalated"):
        return reply, None

    provider = (provider or "openrouter").lower().strip()
    key = api_key.strip() or settings.openrouter_api_key

    if not key:
        return reply, None

    system_prompt = "You polish phone-agent replies for speech. You MUST keep every question asked in the input. Do NOT remove questions or truncate instructions."
    user_prompt = f"Conversation state: {state}\nPolish this for phone speech without removing any questions:\n{reply}"

    try:
        async with httpx.AsyncClient(timeout=8) as client:
            if provider == "gemini":
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}"
                payload = {"contents": [{"parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}]}
                res = await client.post(url, json=payload)
                res.raise_for_status()
                data = res.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                return ensure_question_preserved(reply, text), "gemini-2.5-flash"

            elif provider == "chatgpt":
                url = "https://api.openai.com/v1/chat/completions"
                payload = {
                    "model": "gpt-4o-mini",
                    "temperature": 0.2,
                    "max_tokens": 100,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                }
                headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
                res = await client.post(url, json=payload, headers=headers)
                res.raise_for_status()
                data = res.json()
                text = data["choices"][0]["message"]["content"].strip()
                return ensure_question_preserved(reply, text), "gpt-4o-mini"

            elif provider == "claude":
                url = "https://api.anthropic.com/v1/messages"
                payload = {
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": 100,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_prompt}],
                }
                headers = {
                    "x-api-key": key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                }
                res = await client.post(url, json=payload, headers=headers)
                res.raise_for_status()
                data = res.json()
                text = data["content"][0]["text"].strip()
                return ensure_question_preserved(reply, text), "claude-3-5-sonnet"

            else:
                url = "https://openrouter.ai/api/v1/chat/completions"
                payload = {
                    "model": settings.openrouter_primary_model,
                    "models": settings.openrouter_models,
                    "temperature": 0.2,
                    "max_tokens": 100,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                }
                headers = {
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "X-Title": "Voice AI Lead Agent",
                }
                res = await client.post(url, json=payload, headers=headers)
                res.raise_for_status()
                data = res.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content")
                if not content or not isinstance(content, str):
                    return reply, None
                text = content.strip()
                return ensure_question_preserved(reply, text), data.get("model", settings.openrouter_primary_model)


    except Exception as exc:
        logger.warning("%s provider error; using fallback reply: %s", provider, exc)
        return reply, None

