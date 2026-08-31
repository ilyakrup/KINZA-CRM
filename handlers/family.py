from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import database as db
from keyboards import main_kb, family_types_kb
from utils import parse_and_validate_date

router = Router()

class FamilyForm(StatesGroup):
    waiting_family_name = State()
    waiting_family_bday = State()

@router.message(F.text == "👨‍👩‍👧 Добавить праздник")
async def add_family_start(message: types.Message):
    await message.answer("Кого из близких или какое событие вы хотите добавить?", reply_markup=family_types_kb())

@router.callback_query(F.data == "cancel_action")
async def cancel_callback(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.message.answer("Действие отменено.", reply_markup=main_kb())

@router.callback_query(F.data.startswith("rel_"))
async def process_relation(callback: types.CallbackQuery, state: FSMContext):
    relation = callback.data.split("_")[1]
    await state.update_data(relation=relation)
    prompt = "Напишите название события (например, *Годовщина*):" if relation == "Годовщина" else f"Вы выбрали: **{relation}**. Как зовут? (например, *Артем*):"
    await callback.message.edit_text(prompt, parse_mode="Markdown")
    await state.set_state(FamilyForm.waiting_family_name)

@router.message(FamilyForm.waiting_family_name)
async def process_family_name(message: types.Message, state: FSMContext):
    name = message.text.strip()
    await state.update_data(fam_name=name)
    await message.answer("Укажите дату рождения / события в формате `ДД.ММ` (например, `22.09`):", parse_mode="Markdown")
    await state.set_state(FamilyForm.waiting_family_bday)

@router.message(FamilyForm.waiting_family_bday)
async def process_family_bday(message: types.Message, state: FSMContext):
    valid_bday = parse_and_validate_date(message.text)
    if not valid_bday:
        await message.answer("⚠️ Некорректная дата! Введите в формате `ДД.ММ` (например, `22.09`):", parse_mode="Markdown")
        return

    data = await state.get_data()
    success = await db.add_family_member(message.from_user.id, data['relation'], data['fam_name'], valid_bday)
    
    if not success:
        await message.answer(
            f"⚠️ У вас уже добавлен(а) **{data['relation']} {data['fam_name']}**!\n"
            f"Нельзя добавить одного человека дважды.",
            reply_markup=main_kb(),
            parse_mode="Markdown"
        )
        await state.clear()
        return

    await state.clear()
    await message.answer(
        f"✅ Сохранено: **{data['relation']} {data['fam_name']}** (📅 {valid_bday})\n"
        "Мы заранее пришлем вам скидку 10% и подарок к этому дню!",
        reply_markup=main_kb(),
        parse_mode="Markdown"
    )

@router.message(F.text == "👤 Мой профиль")
async def show_profile(message: types.Message):
    guest = await db.get_guest(message.from_user.id)
    family = await db.get_family_members(message.from_user.id)

    if not guest:
        await message.answer("Вы еще не зарегистрированы. Нажмите /start")
        return

    text = f"👤 **Карта гостя «Кинза»**\n━━━━━━━━━━━━━━━━━━━━\n"
    text += f"Имя: **{guest[0]}**\nТелефон: `{guest[1]}`\nВаш день рождения: 🎂 **{guest[2]}**\n\n"
    
    inline_kb = None
    if family:
        text += "👨‍👩‍👧 **Праздники вашей семьи:**\n"
        buttons = []
        for mem_id, relation, name, bday in family:
            text += f"• {relation} **{name}** — 📅 {bday}\n"
            buttons.append([InlineKeyboardButton(text=f"🗑 Удалить {relation} {name}", callback_data=f"del_{mem_id}")])
        inline_kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    else:
        text += "👨‍👩‍👧 *Близкие пока не добавлены.* Нажмите «👨‍👩‍👧 Добавить праздник»."

    await message.answer(text, reply_markup=inline_kb, parse_mode="Markdown")

@router.callback_query(F.data.startswith("del_"))
async def delete_family_callback(callback: types.CallbackQuery):
    mem_id = int(callback.data.split("_")[1])
    await db.delete_family_member(mem_id, callback.from_user.id)
    await callback.answer("Запись удалена!")
    await callback.message.delete()
    await callback.message.answer("✅ Запись удалена.", reply_markup=main_kb())