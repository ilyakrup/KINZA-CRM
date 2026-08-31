from aiogram import Router, F, types
from aiogram.filters import Command
import database as db
from keyboards import main_kb

router = Router()

@router.message(F.text == "🎁 Мои подарки")
@router.message(Command("gifts"))
async def show_gifts(message: types.Message):
    promos = await db.sync_and_get_promocodes(message.from_user.id)

    if promos is None:
        await message.answer("Сначала зарегистрируйтесь через /start!")
        return

    text = "🎁 **Ваши персональные промокоды:**\n\n"
    for code, title, desc, expires, is_used in promos:
        status = "❌ Использован" if is_used else f"✅ Активен (до {expires})"
        text += f"🔹 **{title}**\nПромокод: `{code}` *(нажмите для копирования)*\nУсловия: **{desc}**\nСтатус: {status}\n\n"
    
    text += "📌 *Покажите промокод официанту перед закрытием счета.*"
    await message.answer(text, parse_mode="Markdown")