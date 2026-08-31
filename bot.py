import asyncio
import logging
import random
import re
import string
from datetime import datetime, timedelta
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

# ==================== НАСТРОЙКИ ====================
BOT_TOKEN = "8998815871:AAGYQGIzfW_Kws_VZj9TMTYx7sNPJBgm7Ro"  # <-- ВСТАВЬТЕ СЮДА ВАШ ТОКЕН ИЗ BOTFATHER
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

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
def parse_and_validate_date(date_text: str) -> str | None:
    """Проверяет корректность даты (ДД.ММ) и исключает несуществующие дни."""
    cleaned = re.sub(r"[\/\-\s,]+", ".", date_text.strip())
    match = re.match(r"^(\d{1,2})\.(\d{1,2})(?:\.\d{2,4})?$", cleaned)
    if not match:
        return None
    
    day, month = int(match.group(1)), int(match.group(2))
    if not (1 <= month <= 12):
        return None
    
    days_in_months = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if not (1 <= day <= days_in_months[month - 1]):
        return None
    
    return f"{day:02d}.{month:02d}"

def generate_promo_code(prefix: str = "KINZA") -> str:
    """Генерирует уникальный красивый промокод: например KINZA-BDAY-7482"""
    digits = "".join(random.choices(string.digits, k=4))
    return f"{prefix}-{digits}"

def is_date_in_next_days(bday_str: str, days_range: int = 7) -> bool:
    """Проверяет, попадает ли день рождения в диапазон от сегодня до +N дней."""
    if not bday_str:
        return False
    try:
        day, month = map(int, bday_str.split("."))
        current_year = datetime.now().year
        bday_date = datetime(current_year, month, day).date()
        today = datetime.now().date()
        
        # Если праздник в этом году уже прошел, смотрим следующий год
        if bday_date < today:
            bday_date = datetime(current_year + 1, month, day).date()
            
        diff = (bday_date - today).days
        return 0 <= diff <= days_range
    except Exception:
        return False

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
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promocodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guest_id INTEGER,
                code TEXT UNIQUE,
                title TEXT,
                description TEXT,
                expires_at TEXT,
                is_used INTEGER DEFAULT 0,
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
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action")]
        ]
    )

# ==================== РЕГИСТРАЦИЯ ГОСТЯ ====================
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
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
            "Оформите электронную карту гостя за 1 клик, чтобы получить **скидку 10% и сладкий подарок от шефа** к вашему визиту!",
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
        "Мы приготовим для вас подарок к празднику!",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )
    await state.set_state(Form.waiting_for_bday)

@dp.message(Form.waiting_for_bday)
async def process_bday(message: types.Message, state: FSMContext):
    valid_bday = parse_and_validate_date(message.text)
    
    if not valid_bday:
        await message.answer(
            "⚠️ **Некорректный формат даты!**\n\n"
            "Пожалуйста, введите настоящую дату цифрами в формате `ДД.ММ` (например, `15.04`):",
            parse_mode="Markdown"
        )
        return

    data = await state.get_data()
    welcome_code = generate_promo_code("KINZA-WELCOME")
    expires = (datetime.now() + timedelta(days=30)).strftime("%d.%m.%Y")

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO guests (id, username, full_name, phone, birthday, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (message.from_user.id, message.from_user.username, data['full_name'], data['phone'], valid_bday, datetime.now().isoformat())
        )
        await db.execute(
            "INSERT INTO promocodes (guest_id, code, title, description, expires_at) VALUES (?, ?, ?, ?, ?)",
            (message.from_user.id, welcome_code, "Приветственный подарок", "Скидка 10% и сладкий подарок от шефа", expires)
        )
        await db.commit()

    await state.clear()
    await message.answer(
        f"🎉 **Ваша карта гостя успешно оформлена!**\n\n"
        f"🎁 **Ваш персональный промокод:** `{welcome_code}`\n"
        f"📌 **Привилегия:** Скидка 10% и сладкий подарок от шефа\n"
        f"⏳ **Действует до:** {expires}\n\n"
        f"Просто покажите этот промокод официанту при визите в «Кинзу»!\n\n"
        f"💡 Нажмите **«👨‍👩‍👧 Добавить праздник»**, чтобы мы дарили подарки и вашим близким.",
        reply_markup=main_kb(),
        parse_mode="Markdown"
    )

# ==================== ДОБАВЛЕНИЕ СЕМЬИ ====================
@dp.message(F.text == "👨‍👩‍👧 Добавить праздник")
async def add_family_start(message: types.Message):
    await message.answer("Кого из близких или какое событие вы хотите добавить?", reply_markup=family_types_kb())

@dp.callback_query(F.data == "cancel_action")
async def cancel_callback(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.message.answer("Действие отменено.", reply_markup=main_kb())

@dp.callback_query(F.data.startswith("rel_"))
async def process_relation(callback: types.CallbackQuery, state: FSMContext):
    relation = callback.data.split("_")[1]
    await state.update_data(relation=relation)
    
    if relation == "Годовщина":
        prompt = "Напишите название памятного события (например, *Свадьба*):"
    else:
        prompt = f"Вы выбрали: **{relation}**. Как зовут? (например, *Артем*):"
        
    await callback.message.edit_text(prompt, parse_mode="Markdown")
    await state.set_state(Form.waiting_family_name)

@dp.message(Form.waiting_family_name)
async def process_family_name(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("Имя слишком короткое. Напишите корректное имя:")
        return

    data = await state.get_data()
    relation = data['relation']

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id FROM family_members WHERE guest_id = ? AND LOWER(relation) = LOWER(?) AND LOWER(name) = LOWER(?)",
            (message.from_user.id, relation, name)
        ) as c:
            existing = await c.fetchone()

    if existing:
        await message.answer(
            f"⚠️ У вас уже добавлен(а) **{relation} {name}**!\n"
            f"Введите другое имя или нажмите /start:",
            parse_mode="Markdown"
        )
        return

    await state.update_data(fam_name=name)
    await message.answer("Укажите дату рождения / события в формате `ДД.ММ` (например, `22.09`):", parse_mode="Markdown")
    await state.set_state(Form.waiting_family_bday)

@dp.message(Form.waiting_family_bday)
async def process_family_bday(message: types.Message, state: FSMContext):
    valid_bday = parse_and_validate_date(message.text)
    
    if not valid_bday:
        await message.answer(
            "⚠️ **Некорректная дата!**\n\n"
            "Пожалуйста, введите настоящую дату в формате `ДД.ММ` (например, `22.09`):",
            parse_mode="Markdown"
        )
        return

    data = await state.get_data()

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO family_members (guest_id, relation, name, birthday) VALUES (?, ?, ?, ?)",
            (message.from_user.id, data['relation'], data['fam_name'], valid_bday)
        )
        await db.commit()

    await state.clear()
    await message.answer(
        f"✅ **Успешно сохранено:** {data['relation']} **{data['fam_name']}** (📅 {valid_bday})\n\n"
        "Мы заранее напомним вам о празднике и подарим персональную скидку 10% и сладкий подарок от шефа!",
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
        async with db.execute("SELECT id, relation, name, birthday FROM family_members WHERE guest_id = ?", (message.from_user.id,)) as c:
            family = await c.fetchall()

    if not guest:
        await message.answer("Вы еще не зарегистрированы. Нажмите /start")
        return

    text = f"👤 **Карта гостя «Кинза»**\n"
    text += f"━━━━━━━━━━━━━━━━━━━━\n"
    text += f"Имя: **{guest[0]}**\n"
    text += f"Телефон: `{guest[1]}`\n"
    text += f"Ваш день рождения: 🎂 **{guest[2]}**\n\n"
    
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

@dp.callback_query(F.data.startswith("del_"))
async def delete_family_member(callback: types.CallbackQuery):
    mem_id = int(callback.data.split("_")[1])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM family_members WHERE id = ? AND guest_id = ?", (mem_id, callback.from_user.id))
        await db.commit()
    
    await callback.answer("Запись удалена!")
    await callback.message.delete()
    await callback.message.answer("✅ Запись о празднике успешно удалена.", reply_markup=main_kb())

# ==================== УМНЫЙ РАЗДЕЛ ПОДАРКОВ (АВТОМАТИЧЕСКАЯ ГЕНЕРАЦИЯ ДР) ====================
@dp.message(F.text == "🎁 Мои подарки")
@dp.message(Command("gifts"))
async def show_gifts(message: types.Message):
    user_id = message.from_user.id
    
    async with aiosqlite.connect(DB_PATH) as db:
        # Проверяем гостя
        async with db.execute("SELECT full_name, birthday FROM guests WHERE id = ?", (user_id,)) as c:
            guest = await c.fetchone()
            
        if not guest:
            await message.answer("Сначала зарегистрируйтесь через /start, чтобы получить подарки!")
            return

        guest_name, guest_bday = guest

        # 1. Если нет приветственного промокода — выдаем его
        async with db.execute("SELECT id FROM promocodes WHERE guest_id = ? AND title LIKE '%Приветственный%'", (user_id,)) as c:
            has_welcome = await c.fetchone()

        if not has_welcome:
            w_code = generate_promo_code("KINZA-WELCOME")
            w_exp = (datetime.now() + timedelta(days=30)).strftime("%d.%m.%Y")
            await db.execute(
                "INSERT INTO promocodes (guest_id, code, title, description, expires_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, w_code, "Приветственный подарок", "Скидка 10% и сладкий десерт от шефа", w_exp)
            )

        # 2. Если у гостя ДР в ближайшие 7 дней (или сегодня) — генерируем подарок на ДР!
        if is_date_in_next_days(guest_bday, days_range=7):
            current_year = datetime.now().year
            bday_title = f"День рождения {current_year} 🎉"
            async with db.execute("SELECT id FROM promocodes WHERE guest_id = ? AND title = ?", (user_id, bday_title)) as c:
                has_bday_promo = await c.fetchone()
                
            if not has_bday_promo:
                bday_code = generate_promo_code("KINZA-BDAY")
                bday_exp = (datetime.now() + timedelta(days=14)).strftime("%d.%m.%Y")
                await db.execute(
                    "INSERT INTO promocodes (guest_id, code, title, description, expires_at) VALUES (?, ?, ?, ?, ?)",
                    (user_id, bday_code, bday_title, "Скидка 10% и сладкий торт от шефа", bday_exp)
                )

        # 3. Проверяем семью на ближайшие ДР
        async with db.execute("SELECT relation, name, birthday FROM family_members WHERE guest_id = ?", (user_id,)) as c:
            family = await c.fetchall()

        for rel, name, fam_bday in family:
            if is_date_in_next_days(fam_bday, days_range=7):
                current_year = datetime.now().year
                fam_title = f"Праздник: {rel} {name} ({current_year})"
                async with db.execute("SELECT id FROM promocodes WHERE guest_id = ? AND title = ?", (user_id, fam_title)) as c:
                    has_fam_promo = await c.fetchone()
                if not has_fam_promo:
                    fam_code = generate_promo_code("KINZA-FAMILY")
                    fam_exp = (datetime.now() + timedelta(days=14)).strftime("%d.%m.%Y")
                    await db.execute(
                        "INSERT INTO promocodes (guest_id, code, title, description, expires_at) VALUES (?, ?, ?, ?, ?)",
                        (user_id, fam_code, fam_title, "Скидка 10% и сладкий подарок от шефа", fam_exp)
                    )

        await db.commit()

        # Загружаем актуальные промокоды
        async with db.execute(
            "SELECT code, title, description, expires_at, is_used FROM promocodes WHERE guest_id = ? ORDER BY id DESC",
            (user_id,)
        ) as c:
            promos = await c.fetchall()

    text = "🎁 **Ваши персональные промокоды и подарки:**\n\n"
    for code, title, desc, expires, is_used in promos:
        status = "❌ Использован" if is_used else f"✅ Активен (до {expires})"
        text += (
            f"🔹 **{title}**\n"
            f"Промокод: `{code}` *(нажмите, чтобы скопировать)*\n"
            f"Условия: **{desc}**\n"
            f"Статус: {status}\n\n"
        )
    
    text += "📌 *Покажите промокод официанту перед закрытием счета в ресторане «Кинза».*"
    await message.answer(text, parse_mode="Markdown")

# ==================== ФАКТ ИЛИ ШУТКА ОТ ШЕФА ====================
@dp.message(F.text == "🍷 Факт от шефа")
@dp.message(Command("fact"))
async def chef_fact(message: types.Message):
    facts = [
        "🌿 **Секрет вкуса:** Свежая кинза полностью раскрывает свой аромат, если добавлять ее в горячее блюдо за 30 секунд до подачи, а не в процессе долгой варки.",
        "🥩 **Сочный стейк:** После жарки мясу обязательно нужно «отдохнуть» 3-5 минут, чтобы температура и сок равномерно разошлись по волокнам.",
        "🍷 **Вино и сыр:** Твердые выдержанные сыры идеально раскрываются с танинными плотными красными винами, а мягкие сыры — с легкими белыми.",
        "🍰 **Сладкий секрет:** Щепотка морской соли в шоколадном десерте усиливает ощущение сладости на 30%!"
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

# ==================== ТРИГГЕРНЫЙ ПЛАНИРОВЩИК (УТРОМ В 10:00) ====================
async def check_birthdays_and_notify():
    in_7_days = (datetime.now() + timedelta(days=7)).strftime("%d.%m")
    async with aiosqlite.connect(DB_PATH) as db:
        # Уведомление о ДР гостя
        async with db.execute("SELECT id, full_name FROM guests WHERE birthday = ?", (in_7_days,)) as c:
            for g_id, name in await c.fetchall():
                try:
                    await bot.send_message(
                        g_id,
                        f"🎉 **{name}, совсем скоро ваш день рождения!**\n\n"
                        f"Мы в ресторане «Кинза» уже подготовили для вас подарок — **скидку 10% и торт от шефа**!\n"
                        f"Проверьте раздел **«🎁 Мои подарки»** и забронируйте столик заранее ❤️",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logging.error(f"Ошибка отправки: {e}")

# ==================== ЗАПУСК ====================
async def main():
    await init_db()
    scheduler.add_job(check_birthdays_and_notify, "cron", hour=10, minute=0)
    scheduler.start()
    logging.info("Бот KinzaCRM успешно обновлен и запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())