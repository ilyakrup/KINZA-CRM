from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardRemove
import database as db
from keyboards import main_kb, contact_kb
from utils import parse_and_validate_date

router = Router()

class RegForm(StatesGroup):
    waiting_for_contact = State()
    waiting_for_bday = State()

@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    guest = await db.get_guest(message.from_user.id)
    if guest:
        await message.answer(
            f"Рады видеть вас снова, {guest[0]}! 🌿\nЧем ресторан «Кинза» может вас порадовать?",
            reply_markup=main_kb()
        )
    else:
        await message.answer(
            "Добро пожаловать в клуб гостей ресторана **«Кинза»**! 🍽️\n\n"
            "Оформите электронную карту гостя за 1 клик, чтобы получить **скидку 10% и сладкий подарок от шефа** к вашему визиту!",
            reply_markup=contact_kb(),
            parse_mode="Markdown"
        )
        await state.set_state(RegForm.waiting_for_contact)

@router.message(RegForm.waiting_for_contact, F.contact)
async def process_contact(message: types.Message, state: FSMContext):
    phone = message.contact.phone_number
    name = message.contact.first_name or message.from_user.first_name
    await state.update_data(phone=phone, full_name=name)

    await message.answer(
        f"Приятно познакомиться, {name}! 😊\n\n"
        "Укажите **дату вашего рождения** в формате `ДД.ММ` (например, `15.04`):",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )
    await state.set_state(RegForm.waiting_for_bday)

@router.message(RegForm.waiting_for_bday)
async def process_bday(message: types.Message, state: FSMContext):
    valid_bday = parse_and_validate_date(message.text)
    if not valid_bday:
        await message.answer("⚠️ Некорректный формат даты! Укажите дату цифрами в формате `ДД.ММ` (например, `15.04`):", parse_mode="Markdown")
        return

    data = await state.get_data()
    welcome_code, expires = await db.create_guest(
        user_id=message.from_user.id,
        username=message.from_user.username,
        full_name=data['full_name'],
        phone=data['phone'],
        birthday=valid_bday
    )

    await state.clear()
    await message.answer(
        f"🎉 **Ваша карта гостя успешно оформлена!**\n\n"
        f"🎁 **Ваш промокод:** `{welcome_code}`\n"
        f"📌 **Привилегия:** Скидка 10% и сладкий подарок от шефа\n"
        f"⏳ **Действует до:** {expires}\n\n"
        f"Покажите промокод официанту при визите в «Кинзу»!",
        reply_markup=main_kb(),
        parse_mode="Markdown"
    )