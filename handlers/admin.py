from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import database as db
from keyboards import main_kb

router = Router()

class AdminForm(StatesGroup):
    waiting_promo_to_check = State()

@router.message(F.text == "🔍 Проверить / Погасить промокод")
async def check_promo_btn(message: types.Message, state: FSMContext):
    await message.answer("Введите промокод гостя (например: `KINZA-WELCOME-1234`):", parse_mode="Markdown")
    await state.set_state(AdminForm.waiting_promo_to_check)

@router.message(AdminForm.waiting_promo_to_check)
@router.message(F.text.startswith("KINZA-"))
@router.message(F.text.startswith("kinza-"))
async def check_and_redeem_promo(message: types.Message, state: FSMContext):
    code = message.text.strip().upper()
    await state.clear()

    promo = await db.get_promo_details(code)
    if not promo:
        await message.answer(f"❌ **Промокод `{code}` не существует!**", reply_markup=main_kb(), parse_mode="Markdown")
        return

    p_id, p_code, p_title, p_desc, p_exp, is_used, used_at, g_name, g_phone = promo

    # Защита от дублей
    if is_used:
        await message.answer(
            f"⛔ **ВНИМАНИЕ! ПРОМОКОД УЖЕ БЫЛ ПОГАШЕН РАНЕЕ!**\n\n"
            f"Код: `{p_code}`\n"
            f"Гость: **{g_name or 'Гость'}** (`{g_phone or '-'}`)\n"
            f"Подарок: {p_desc}\n"
            f"🕒 Был использован: **{used_at}**\n\n"
            f"❌ *Повторное предоставление скидки строго запрещено!*",
            reply_markup=main_kb(),
            parse_mode="Markdown"
        )
        return

    redeem_btn = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Погасить (Применить скидку)", callback_data=f"redeem_{p_id}")],
            [InlineKeyboardButton(text="❌ Не погашать", callback_data="cancel_action")]
        ]
    )

    await message.answer(
        f"✅ **ПРОМОКОД ДЕЙСТВИТЕЛЕН!**\n\n"
        f"Промокод: `{p_code}`\n"
        f"Акция: **{p_title}**\n"
        f"🎁 Подарок: **{p_desc}**\n"
        f"👤 Гость: **{g_name}** (`{g_phone}`)\n"
        f"⏳ Срок действия: до {p_exp}\n\n"
        f"Нажмите кнопку ниже, чтобы применить скидку в счете:",
        reply_markup=redeem_btn,
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("redeem_"))
async def redeem_callback(callback: types.CallbackQuery):
    p_id = int(callback.data.split("_")[1])
    success, code_name, used_time = await db.redeem_promo(p_id)

    if not success:
        await callback.message.edit_text("⛔ Этот промокод уже был погашен!")
        return

    await callback.message.edit_text(
        f"🎉 **ПРОМОКОД УСПЕШНО ПОГАШЕН!**\n\n"
        f"Код: `{code_name}`\n"
        f"Время погашения: **{used_time}**\n"
        f"Скидка 10% и подарок зафиксированы в чеке.",
        parse_mode="Markdown"
    )
    await callback.message.answer("Готово! Промокод списан из базы.", reply_markup=main_kb())

@router.message(F.text == "📊 Статистика CRM")
async def stats_handler(message: types.Message):
    total_guests, total_family, active_promos, used_promos = await db.get_crm_stats()
    text = (
        "📊 **Статистика CRM «Кинза»:**\n━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Всего гостей в базе: **{total_guests}**\n"
        f"👨‍👩‍👧 Праздников семьи в базе: **{total_family}**\n"
        f"🎁 Активных промокодов у гостей: **{active_promos}**\n"
        f"✅ Использовано промокодов: **{used_promos}**\n"
    )
    await message.answer(text, reply_markup=main_kb(), parse_mode="Markdown")