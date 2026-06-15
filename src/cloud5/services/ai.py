"""ИИ-сервис на базе Anthropic Claude.

Используется модулем ai_assistant: собирает системный промпт из настроек тенанта
и базы знаний, добавляет историю диалога и возвращает ответ ассистента.
"""

from __future__ import annotations

from anthropic import AsyncAnthropic

from cloud5.config import settings
from cloud5.core.logging import get_logger

log = get_logger("ai")

_client: AsyncAnthropic | None = None

DEFAULT_SYSTEM = (
    "Ты — дружелюбный и профессиональный ассистент компании в Telegram. "
    "Отвечай кратко, по делу и вежливо, помогай клиенту и мягко подводи к покупке "
    "или целевому действию. Не выдумывай факты: если данных нет в контексте — "
    "честно скажи и предложи связаться с менеджером."
)

# Максимум сообщений истории, передаваемых модели
MAX_HISTORY = 20


def get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


def build_system_prompt(
    persona: str | None, knowledge: list[str] | None = None
) -> str:
    parts = [persona or DEFAULT_SYSTEM]
    if knowledge:
        joined = "\n\n".join(knowledge)
        parts.append(
            "Используй следующую информацию о компании как источник истины:\n"
            f"<knowledge>\n{joined}\n</knowledge>"
        )
    return "\n\n".join(parts)


async def generate_reply(
    *,
    system_prompt: str,
    history: list[dict[str, str]],
    model: str | None = None,
    max_tokens: int = 1024,
) -> str:
    """Сгенерировать ответ ассистента.

    history — список вида [{"role": "user"|"assistant", "content": "..."}].
    """
    client = get_client()
    trimmed = history[-MAX_HISTORY:]
    try:
        resp = await client.messages.create(
            model=model or settings.ai_model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=trimmed,
        )
    except Exception as exc:  # noqa: BLE001
        log.error("ai_generation_failed", error=str(exc))
        return (
            "Извините, не получилось обработать запрос прямо сейчас. "
            "Попробуйте ещё раз или напишите менеджеру."
        )

    chunks = [block.text for block in resp.content if block.type == "text"]
    return "\n".join(chunks).strip() or "…"
