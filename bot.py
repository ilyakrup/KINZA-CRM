import asyncio
import logging
from datetime import datetime, timedelta
import random
import aiosqlite

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ВСТАВЬТЕ СЮДА ВАШ ТОКЕН ИЗ BOTFATHER:
BOT_TOKEN = "8998815871:AAGYQGIzfW_Kws_VZj9TMTYx7sNPJBgm7Ro"
DB_PATH = "kinza_crm.db"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
scheduler = AsyncIOScheduler()

# ==================== СОСТОЯНИЯ (FSM) ====================
class Form(StatesGroup):
    waiting_for_contact = State()
    waiting_for_bday = State()
    waiting_family_type = State()
    waiting_family_name = State()
    waiting_family_bday = State()

# ==================== БАЗА ДАННЫХ ====================
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS guests (
                id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                phone TEXT,
                birthday TEXT,
                created_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS family_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guest_id INTEGER,
                relation TEXT,
                name TEXT,
                birthday TEXT,
                FOREIGN KEY (guest_id) REFERENCES guests(id)
            )
        """)
        await db.commit()

# ==================== КЛАВИАТУРЫ ====================
def main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Мой профиль"), KeyboardButton(text="👨‍👩‍👧 Добавить праздник")],
            [KeyboardButton(text="🎁 Мои подарки"), KeyboardButton(text="🍷 Факт от шефа")],
        ],
        resize_keyboard=True,
    )

def family_types_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Сын 👦", callback_data="rel_Сын"),
             InlineKeyboardButton(text="Дочь 👧", callback_data="rel_Дочь")],
            [InlineKeyboardButton(text="Супруг(а) ❤️", callback_data="rel_Супруг(а)"),
             InlineKeyboardButton(text="Годовщина 💍", callback_data="rel_Годовщина")],
        ]
    )

# ==================== ХЭНДЛЕРЫ: СТАРТ И РЕГИСТРАЦИЯ ====================
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT full_name FROM guests WHERE id = ?", (message.from_user.id,)) as cursor:
            guest = await cursor.fetchone()

    if guest:
        await message.answer(
            f"Рады видеть вас снова, {guest[0]}! 🌿\n"
            "Чем ресторан «Кинза» может вас порадовать сегодня?",
            reply_markup=main_kb()
        )
    else:
        contact_btn = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="📱 Оформить карту гостя (поделиться контактом)", request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await message.answer(
            "Добро пожаловать в клуб гостей ресторана **«Кинза»**! 🍽️\n\n"
            "Оформите электронную карту гостя за 1 клик, чтобы получать подарки к семейным праздникам и комплименты от шефа.",
            reply_markup=contact_btn,
            parse_mode="Markdown"
        )
        await state.set_state(Form.waiting_for_contact)

@dp.message(Form.waiting_for_contact, F.contact)
async def process_contact(message: types.Message, state: FSMContext):
    phone = message.contact.phone_number
    name = message.contact.first_name or message.from_user.first_name
    await state.update_data(phone=phone, full_name=name)

    await message.answer(
        f"Приятно познакомиться, {name}! 😊\n\n"
        "Укажите **дату вашего рождения** в формате `ДД.ММ` (например, `15.04`):\n"
        "Мы приготовим для вас особенный подарок к празднику!",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )
    await state.set_state(Form.waiting_for_bday)

@dp.message(Form.waiting_for_bday)
async def process_bday(message: types.Message, state: FSMContext):
    bday = message.text.strip()
    data = await state.get_data()

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO guests (id, username, full_name, phone, birthday, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (message.from_user.id, message.from_user.username, data['full_name'], data['phone'], bday, datetime.now().isoformat())
        )
        await db.commit()

    await state.clear()
    await message.answer(
        "🎉 **Поздравляем! Ваша карта гостя активирована.**\n\n"
        "🍰 Вам начислен приветственный комплимент от шефа к следующему визиту!\n\n"
        "💡 *Совет:* Нажмите **«👨‍👩‍👧 Добавить праздник»**, чтобы мы не забыли поздравить ваших детей и вторую половинку.",
        reply_markup=main_kb(),
        parse_mode="Markdown"
    )

# ==================== ДОБАВЛЕНИЕ СЕМЬИ ====================
@dp.message(F.text == "👨‍👩‍👧 Добавить праздник")
async def add_family_start(message: types.Message):
    await message.answer("Какой праздник или кого из близких вы хотите добавить?", reply_markup=family_types_kb())

@dp.callback_query(F.data.startswith("rel_"))
async def process_relation(callback: types.CallbackQuery, state: FSMContext):
    relation = callback.data.split("_")[1]
    await state.update_data(relation=relation)
    
    if relation == "Годовщина":
        prompt_text = "Напишите название события (например, *Годовщина свадьбы*):"
    else:
        prompt_text = f"Вы выбрали: **{relation}**. Как зовут? (например, *Артем*):"
        
    await callback.message.edit_text(prompt_text, parse_mode="Markdown")
    await state.set_state(Form.waiting_family_name)

@dp.message(Form.waiting_family_name)
async def process_family_name(message: types.Message, state: FSMContext):
    await state.update_data(fam_name=message.text.strip())
    await message.answer("Укажите дату в формате `ДД.ММ` (например, `22.09`):", parse_mode="Markdown")
    await state.set_state(Form.waiting_family_bday)

@dp.message(Form.waiting_family_bday)
async def process_family_bday(message: types.Message, state: FSMContext):
    fam_bday = message.text.strip()
    data = await state.get_data()

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO family_members (guest_id, relation, name, birthday) VALUES (?, ?, ?, ?)",
            (message.from_user.id, data['relation'], data['fam_name'], fam_bday)
        )
        await db.commit()

    await state.clear()
    await message.answer(
        f"✅ Сохранено: **{data['relation']} {data['fam_name']}** ({fam_bday})\n\n"
        "Мы заранее напомним о приближении праздника и приготовим специальный подарок для вашей семьи!",
        reply_markup=main_kb(),
        parse_mode="Markdown"
    )

# ==================== ПРОФИЛЬ ГОСТЯ ====================
@dp.message(F.text == "👤 Мой профиль")
@dp.message(Command("profile"))
async def show_profile(message: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT full_name, phone, birthday FROM guests WHERE id = ?", (message.from_user.id,)) as c:
            guest = await c.fetchone()
        async with db.execute("SELECT relation, name, birthday FROM family_members WHERE guest_id = ?", (message.from_user.id,)) as c:
            family = await c.fetchall()

    if not guest:
        await message.answer("Вы еще не зарегистрированы. Нажмите /start")
        return

    text = f"👤 **Карта гостя «Кинза»**\n"
    text += f"━━━━━━━━━━━━━━━━━━━━\n"
    text += f"Имя: **{guest[0]}**\n"
    text += f"Телефон: `{guest[1]}`\n"
    text += f"Ваш день рождения: 🎂 **{guest[2]}**\n\n"
    
    if family:
        text += "👨‍👩‍👧 **Праздники вашей семьи:**\n"
        for member in family:
            text += f"• {member[0]} **{member[1]}** — 📅 {member[2]}\n"
    else:
        text += "👨‍👩‍👧 *Праздники близких пока не добавлены.* Нажмите «👨‍👩‍👧 Добавить праздник»."

    await message.answer(text, parse_mode="Markdown")

# ==================== ПОДАРКИ И ПРОМОКОДЫ ====================
@dp.message(F.text == "🎁 Мои подарки")
@dp.message(Command("gifts"))
async def show_gifts(message: types.Message):
    text = (
        "🎁 **Ваши привилегии и подарки в «Кинза»:**\n\n"
        "1. **Приветственный десерт** — покажите это сообщение официанту при следующем визите.\n"
        "2. **Скидка 15% и торт** на все дни рождения вашей семьи (промокод активируется автоматически за 7 дней до праздника).\n"
        "3. **Комплимент от шефа** на каждую вашу годовщину."
    )
    await message.answer(text, parse_mode="Markdown")

# ==================== ФАКТ ИЛИ ШУТКА ОТ ШЕФА ====================
@dp.message(F.text == "🍷 Факт от шефа")
@dp.message(Command("fact"))
async def chef_fact(message: types.Message):
    facts = [
        "🌿 **Секрет от шефа:** Свежая кинза полностью раскрывает свой аромат, если добавлять ее в горячее блюдо за 30 секунд до подачи, а не во время долгой варки!",
        "🥩 **Гастро-факт:** Идеальный стейк после жарки должен «отдохнуть» на теплой тарелке 3-5 минут. За это время мясные соки равномерно распределяются от центра к краям.",
        "🍷 **Вино и сыр:** Чем тверже и старше сыр, тем более насыщенное и танинное красное вино к нему подходит.",
        "😄 **Шутка от шефа:** Самый точный кухонный таймер — это вопрос гостя «А скоро ли будет готово?» каждые две минуты!"
    ]
    await message.answer(random.choice(facts), parse_mode="Markdown")

# ==================== ПОМОЩЬ / СВЯЗЬ ====================
@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "🍽️ **Ресторан «Кинза»**\n\n"
        "📍 Ждем вас в гости каждый день с 11:00 до 23:00.\n"
        "📞 Телефон для бронирования столов: +7 (999) 000-00-00\n"
        "💬 Вопросы и пожелания: @kinza_admin",
        parse_mode="Markdown"
    )

# ==================== ТРИГГЕРНЫЕ НАПОМИНАНИЯ (КАЖДОЕ УТРО В 10:00) ====================
async def check_birthdays_and_notify():
    today = datetime.now().strftime("%d.%m")
    in_7_days = (datetime.now() + timedelta(days=7)).strftime("%d.%m")
    in_14_days = (datetime.now() + timedelta(days=14)).strftime("%d.%m")

    async with aiosqlite.connect(DB_PATH) as db:
        # 1. За 14 дней до ДР ребенка (предложение банкета)
        async with db.execute("SELECT guest_id, relation, name FROM family_members WHERE birthday = ? AND relation IN ('Сын', 'Дочь')", (in_14_days,)) as c:
            for g_id, rel, name in await c.fetchall():
                try:
                    await bot.send_message(
                        g_id,
                        f"🎂 **Приближается праздник!**\n\n"
                        f"Через 2 недели день рождения у вашего {rel.lower()}а **{name}**!\n"
                        f"В «Кинзе» мы с радостью организуем незабываемый детский праздник: дарим праздничный торт и скидку 15% на меню.\n\n"
                        f"📞 Забронировать столик заранее: +7 (999) 000-00-00",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logging.error(f"Ошибка отправки: {e}")

        # 2. За 7 дней до ДР самого гостя
        async with db.execute("SELECT id, full_name FROM guests WHERE birthday = ?", (in_7_days,)) as c:
            for g_id, name in await c.fetchall():
                try:
                    await bot.send_message(
                        g_id,
                        f"🎉 **{name}, совсем скоро ваш день рождения!**\n\n"
                        f"Мы подготовили для вас фирменный подарок и бутылку вина к праздничному ужину.\n"
                        f"Будем счастливы разделить этот день с вами в «Кинзе»!",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logging.error(f"Ошибка отправки: {e}")

# ==================== ТОЧКА ВХОДА ====================
async def main():
    await init_db()
    # Запуск проверки дат каждое утро в 10:00
    scheduler.add_job(check_birthdays_and_notify, "cron", hour=10, minute=0)
    scheduler.start()
    logging.info("Бот KinzaCRM успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())