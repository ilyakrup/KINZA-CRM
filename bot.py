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
BOT_TOKEN = "8998815871:AAGYQGIzfW_Kws_VZj9TMTYx7sNPJBgm7Ro"  # <-- Вставьте ваш токен

# ВСТАВЬТЕ СЮДА ВАШ ТЕЛЕГРАМ ID (можно через запятую для нескольких сотрудников):
ADMIN_IDS = [5217847939]  

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
    admin_checking_promo = State()

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
def parse_and_validate_date(date_text: str) -> str | None:
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
    digits = "".join(random.choices(string.digits, k=4))
    return f"{prefix}-{digits}"

def is_date_in_next_days(bday_str: str, days_range: int = 7) -> bool:
    if not bday_str:
        return False
    try:
        day, month = map(int, bday_str.split("."))
        current_year = datetime.now().year
        bday_date = datetime(current_year, month, day).date()
        today = datetime.now().date()
        if bday_date < today:
            bday_date = datetime(current_year + 1, month, day).date()
        diff = (bday_date - today).days
        return 0 <= diff <= days_range
    except Exception:
        return False

# ==================== ИНИЦИАЛИЗАЦИЯ БАЗЫ ====================
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
                used_at TEXT,
                FOREIGN KEY (guest_id) REFERENCES guests(id)
            )
        """)
        await db.commit()

# ==================== КЛАВИАТУРЫ ====================
def main_kb(user_id: int):
    kb = [
        [KeyboardButton(text="👤 Мой профиль"), KeyboardButton(text="👨‍👩‍👧 Добавить праздник")],
        [KeyboardButton(text="🎁 Мои подарки"), KeyboardButton(text="🍷 Факт от шефа")],
    ]
    # Если это администратор / официант — добавляем кнопку админки
    if user_id in ADMIN_IDS:
        kb.append([KeyboardButton(text="⚙️ Панель Администратора")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def admin_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔍 Проверить / Погасить промокод")],
            [KeyboardButton(text="📊 Статистика CRM"), KeyboardButton(text="◀️ В главное меню")]
        ],
        resize_keyboard=True
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

# ==================== РЕГИСТРАЦИЯ И СТАРТ ====================
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT full_name FROM guests WHERE id = ?", (user_id,)) as cursor:
            guest = await cursor.fetchone()

    if guest:
        await message.answer(
            f"Рады видеть вас снова, {guest[0]}! 🌿\nЧем ресторан «Кинза» может вас порадовать?",
            reply_markup=main_kb(user_id)
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
        "Укажите **дату вашего рождения** в формате `ДД.ММ` (например, `15.04`):",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )
    await state.set_state(Form.waiting_for_bday)

@dp.message(Form.waiting_for_bday)
async def process_bday(message: types.Message, state: FSMContext):
    valid_bday = parse_and_validate_date(message.text)
    if not valid_bday:
        await message.answer("⚠️ Некорректный формат! Укажите дату цифрами в формате `ДД.ММ` (например, `15.04`):", parse_mode="Markdown")
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
        f"Покажите промокод официанту при визите!",
        reply_markup=main_kb(message.from_user.id),
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
    await callback.message.answer("Действие отменено.", reply_markup=main_kb(callback.from_user.id))

@dp.callback_query(F.data.startswith("rel_"))
async def process_relation(callback: types.CallbackQuery, state: FSMContext):
    relation = callback.data.split("_")[1]
    await state.update_data(relation=relation)
    prompt = "Напишите название события (например, *Годовщина*):" if relation == "Годовщина" else f"Вы выбрали: **{relation}**. Как зовут? (например, *Артем*):"
    await callback.message.edit_text(prompt, parse_mode="Markdown")
    await state.set_state(Form.waiting_family_name)

@dp.message(Form.waiting_family_name)
async def process_family_name(message: types.Message, state: FSMContext):
    name = message.text.strip()
    data = await state.get_data()
    relation = data['relation']

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id FROM family_members WHERE guest_id = ? AND LOWER(relation) = LOWER(?) AND LOWER(name) = LOWER(?)",
            (message.from_user.id, relation, name)
        ) as c:
            if await c.fetchone():
                await message.answer(f"⚠️ У вас уже добавлен(а) **{relation} {name}**! Введите другое имя или отмените:", parse_mode="Markdown")
                return

    await state.update_data(fam_name=name)
    await message.answer("Укажите дату рождения / события в формате `ДД.ММ` (например, `22.09`):", parse_mode="Markdown")
    await state.set_state(Form.waiting_family_bday)

@dp.message(Form.waiting_family_bday)
async def process_family_bday(message: types.Message, state: FSMContext):
    valid_bday = parse_and_validate_date(message.text)
    if not valid_bday:
        await message.answer("⚠️ Некорректная дата! Введите в формате `ДД.ММ` (например, `22.09`):", parse_mode="Markdown")
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
        f"✅ Сохранено: **{data['relation']} {data['fam_name']}** (📅 {valid_bday})\n"
        "Мы заранее пришлем вам персональную скидку 10% и подарок к этому дню!",
        reply_markup=main_kb(message.from_user.id),
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

@dp.callback_query(F.data.startswith("del_"))
async def delete_family_member(callback: types.CallbackQuery):
    mem_id = int(callback.data.split("_")[1])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM family_members WHERE id = ? AND guest_id = ?", (mem_id, callback.from_user.id))
        await db.commit()
    await callback.answer("Запись удалена!")
    await callback.message.delete()
    await callback.message.answer("✅ Запись удалена.", reply_markup=main_kb(callback.from_user.id))

# ==================== ПОДАРКИ ГОСТЯ ====================
@dp.message(F.text == "🎁 Мои подарки")
@dp.message(Command("gifts"))
async def show_gifts(message: types.Message):
    user_id = message.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT full_name, birthday FROM guests WHERE id = ?", (user_id,)) as c:
            guest = await c.fetchone()
        if not guest:
            await message.answer("Сначала зарегистрируйтесь через /start!")
            return

        guest_name, guest_bday = guest

        # Авто-выдача приветственного
        async with db.execute("SELECT id FROM promocodes WHERE guest_id = ? AND title LIKE '%Приветственный%'", (user_id,)) as c:
            if not await c.fetchone():
                w_code = generate_promo_code("KINZA-WELCOME")
                w_exp = (datetime.now() + timedelta(days=30)).strftime("%d.%m.%Y")
                await db.execute(
                    "INSERT INTO promocodes (guest_id, code, title, description, expires_at) VALUES (?, ?, ?, ?, ?)",
                    (user_id, w_code, "Приветственный подарок", "Скидка 10% и сладкий подарок от шефа", w_exp)
                )

        # Авто-выдача ДР гостя (если в пределах 7 дней)
        if is_date_in_next_days(guest_bday, days_range=7):
            current_year = datetime.now().year
            bday_title = f"День рождения {current_year} 🎉"
            async with db.execute("SELECT id FROM promocodes WHERE guest_id = ? AND title = ?", (user_id, bday_title)) as c:
                if not await c.fetchone():
                    b_code = generate_promo_code("KINZA-BDAY")
                    b_exp = (datetime.now() + timedelta(days=14)).strftime("%d.%m.%Y")
                    await db.execute(
                        "INSERT INTO promocodes (guest_id, code, title, description, expires_at) VALUES (?, ?, ?, ?, ?)",
                        (user_id, b_code, bday_title, "Скидка 10% и сладкий торт от шефа", b_exp)
                    )

        await db.commit()
        async with db.execute("SELECT code, title, description, expires_at, is_used FROM promocodes WHERE guest_id = ? ORDER BY id DESC", (user_id,)) as c:
            promos = await c.fetchall()

    text = "🎁 **Ваши персональные промокоды:**\n\n"
    for code, title, desc, expires, is_used in promos:
        status = "❌ Использован" if is_used else f"✅ Активен (до {expires})"
        text += f"🔹 **{title}**\nПромокод: `{code}`\nУсловия: **{desc}**\nСтатус: {status}\n\n"
    
    text += "📌 *Покажите промокод официанту перед закрытием счета.*"
    await message.answer(text, parse_mode="Markdown")

# ==================== ПАНЕЛЬ АДМИНИСТРАТОРА И ПОГАШЕНИЕ КОДОВ ====================
@dp.message(F.text == "⚙️ Панель Администратора")
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ У вас нет прав доступа к панели администратора.")
        return
    await message.answer("⚙️ **Панель администратора ресторана «Кинза»**\nВыберите действие:", reply_markup=admin_kb(), parse_mode="Markdown")

@dp.message(F.text == "◀️ В главное меню")
async def back_to_main(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Вы вернулись в главное меню.", reply_markup=main_kb(message.from_user.id))

@dp.message(F.text == "🔍 Проверить / Погасить промокод")
async def admin_check_promo_start(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("Введите промокод гостя (например: `KINZA-WELCOME-1234`):", parse_mode="Markdown")
    await state.set_state(Form.admin_checking_promo)

@dp.message(Form.admin_checking_promo)
async def admin_process_promo(message: types.Message, state: FSMContext):
    code = message.text.strip().upper()
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT p.id, p.code, p.title, p.description, p.expires_at, p.is_used, p.used_at, g.full_name, g.phone
            FROM promocodes p
            LEFT JOIN guests g ON p.guest_id = g.id
            WHERE UPPER(p.code) = ?
        """, (code,)) as c:
            promo = await c.fetchone()

    if not promo:
        await message.answer(
            f"❌ **Промокод `{code}` не найден!**\nПроверьте правильность написания и попробуйте снова:",
            parse_mode="Markdown"
        )
        return

    p_id, p_code, p_title, p_desc, p_exp, is_used, used_at, g_name, g_phone = promo

    if is_used:
        # ЗАЩИТА ОТ ДУБЛИКАТА ПОГАШЕНИЯ:
        await message.answer(
            f"⛔ **ВНИМАНИЕ! ПРОМОКОД УЖЕ ИСПОЛЬЗОВАН!**\n\n"
            f"Промокод: `{p_code}`\n"
            f"Гость: **{g_name}** (`{g_phone}`)\n"
            f"Подарок: {p_desc}\n"
            f"🕒 Был погашен: **{used_at}**\n\n"
            f"❌ *Повторное применение скидки запрещено!*",
            reply_markup=admin_kb(),
            parse_mode="Markdown"
        )
        await state.clear()
        return

    # Если промокод действителен:
    redeem_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Погасить промокод (Применить скидку)", callback_data=f"redeem_{p_id}")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action")]
        ]
    )

    await message.answer(
        f"✅ **ПРОМОКОД ДЕЙСТВИТЕЛЕН!**\n\n"
        f"Промокод: `{p_code}`\n"
        f"Тип: **{p_title}**\n"
        f"🎁 Подарок гостю: **{p_desc}**\n"
        f"👤 Гость: **{g_name}** (`{g_phone}`)\n"
        f"⏳ Срок действия: до {p_exp}\n\n"
        f"Нажмите кнопку ниже, чтобы списать подарок и зафиксировать скидку в чеке:",
        reply_markup=redeem_kb,
        parse_mode="Markdown"
    )
    await state.clear()

@dp.callback_query(F.data.startswith("redeem_"))
async def redeem_promo_callback(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("У вас нет прав!", show_alert=True)
        return

    p_id = int(callback.data.split("_")[1])
    used_time = datetime.now().strftime("%d.%m.%Y в %H:%M")

    async with aiosqlite.connect(DB_PATH) as db:
        # Проверяем ещё раз перед погашением
        async with db.execute("SELECT is_used, code FROM promocodes WHERE id = ?", (p_id,)) as c:
            res = await c.fetchone()
            if not res or res[0] == 1:
                await callback.message.edit_text("⛔ Этот промокод уже был погашен ранее!")
                return
            code_name = res[1]

        # Фиксируем погашение
        await db.execute("UPDATE promocodes SET is_used = 1, used_at = ? WHERE id = ?", (used_time, p_id))
        await db.commit()

    await callback.message.edit_text(
        f"🎉 **УСПЕШНО ПОГАШЕН!**\n\n"
        f"Промокод `{code_name}` закрыт.\n"
        f"Время погашения: {used_time}\n"
        f"Скидка 10% и десерт применены к столу.",
        parse_mode="Markdown"
    )
    await callback.message.answer("Выберите следующее действие:", reply_markup=admin_kb())

# ==================== СТАТИСТИКА CRM ====================
@dp.message(F.text == "📊 Статистика CRM")
async def admin_stats(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM guests") as c:
            total_guests = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM family_members") as c:
            total_family = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM promocodes WHERE is_used = 0") as c:
            active_promos = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM promocodes WHERE is_used = 1") as c:
            used_promos = (await c.fetchone())[0]

    text = (
        "📊 **Статистика CRM «Кинза»:**\n━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Всего гостей в базе: **{total_guests}**\n"
        f"👨‍👩‍👧 Добавлено праздников семьи: **{total_family}**\n"
        f"🎁 Активных промокодов на руках: **{active_promos}**\n"
        f"✅ Использовано промокодов (визитов): **{used_promos}**\n"
    )
    await message.answer(text, parse_mode="Markdown")

# ==================== РАЗВЛЕКАТЕЛЬНЫЙ БЛОК И ПОМОЩЬ ====================
@dp.message(F.text == "🍷 Факт от шефа")
@dp.message(Command("fact"))
async def chef_fact(message: types.Message):
    facts = [
        "🌿 **Секрет вкуса:** Свежая кинза полностью раскрывает свой аромат, если добавлять ее в горячее блюдо за 30 секунд до подачи.",
        "🥩 **Сочный стейк:** После жарки мясу нужно «отдохнуть» 3-5 минут, чтобы сок равномерно разошелся по волокнам.",
        "🍰 **Сладкий секрет:** Щепотка морской соли в шоколадном десерте усиливает ощущение сладости на 30%!"
    ]
    await message.answer(random.choice(facts), parse_mode="Markdown")

# ==================== ЗАПУСК ====================
async def main():
    await init_db()
    logging.info("Бот KinzaCRM с панелью администратора успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())