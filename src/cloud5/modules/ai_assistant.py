"""Модуль ИИ-ассистента: диалог с Claude, память и база знаний в БД."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cloud5.core.filters import ModuleEnabled
from cloud5.core.menu import back_to_menu_button
from cloud5.core.registry import TenantInfo
from cloud5.db.models import BotUser, ChatMessage, ChatRole, KnowledgeDoc
from cloud5.services import ai

router = Router(name="ai_assistant")
router.callback_query.filter(ModuleEnabled("ai_assistant"))
router.message.filter(ModuleEnabled("ai_assistant"))


class AIChat(StatesGroup):
    chatting = State()


def _exit_kb():
    builder = InlineKeyboardBuilder()
    builder.add(back_to_menu_button())
    return builder.as_markup()


async def _load_history(
    session: AsyncSession, tenant_id: int, user_id: int
) -> list[dict[str, str]]:
    rows = (
        await session.execute(
            select(ChatMessage)
            .where(
                ChatMessage.tenant_id == tenant_id,
                ChatMessage.user_id == user_id,
            )
            .order_by(ChatMessage.id.desc())
            .limit(ai.MAX_HISTORY)
        )
    ).scalars().all()
    rows.reverse()
    return [{"role": m.role.value, "content": m.content} for m in rows]


async def _load_knowledge(session: AsyncSession, tenant_id: int) -> list[str]:
    rows = (
        await session.execute(
            select(KnowledgeDoc).where(
                KnowledgeDoc.tenant_id == tenant_id,
                KnowledgeDoc.is_active.is_(True),
            )
        )
    ).scalars().all()
    return [f"{d.title}:\n{d.content}" for d in rows]


@router.callback_query(F.data == "ai:start")
async def ai_start(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AIChat.chatting)
    if isinstance(query.message, Message):
        await query.message.edit_text(
            "🧠 Я на связи! Напишите свой вопрос — отвечу сразу.",
            reply_markup=_exit_kb(),
        )
    await query.answer()


@router.message(AIChat.chatting, F.text)
async def ai_chat(
    message: Message,
    tenant: TenantInfo,
    user: BotUser,
    session: AsyncSession,
) -> None:
    text = (message.text or "").strip()
    if not text:
        return

    await message.bot.send_chat_action(message.chat.id, "typing")

    # сохранить вопрос пользователя
    session.add(
        ChatMessage(
            tenant_id=tenant.id,
            user_id=user.id,
            role=ChatRole.user,
            content=text,
        )
    )
    await session.flush()

    history = await _load_history(session, tenant.id, user.id)
    knowledge = await _load_knowledge(session, tenant.id)
    cfg = tenant.module_settings("ai_assistant")
    system_prompt = ai.build_system_prompt(cfg.get("persona"), knowledge)

    reply = await ai.generate_reply(
        system_prompt=system_prompt,
        history=history,
        model=cfg.get("model"),
        max_tokens=cfg.get("max_tokens", 1024),
    )

    # сохранить ответ ассистента
    session.add(
        ChatMessage(
            tenant_id=tenant.id,
            user_id=user.id,
            role=ChatRole.assistant,
            content=reply,
        )
    )
    await session.flush()

    await message.answer(reply, reply_markup=_exit_kb())
