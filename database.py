from datetime import datetime, timedelta
import aiosqlite
from config import DB_PATH
from utils import generate_promo_code, is_date_in_next_days

async def init_db():
    """Создание всех таблиц при первом запуске"""
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

async def get_guest(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT full_name, phone, birthday FROM guests WHERE id = ?", (user_id,)) as c:
            return await c.fetchone()

async def create_guest(user_id: int, username: str, full_name: str, phone: str, birthday: str):
    welcome_code = generate_promo_code("KINZA-WELCOME")
    expires = (datetime.now() + timedelta(days=30)).strftime("%d.%m.%Y")
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO guests (id, username, full_name, phone, birthday, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, username, full_name, phone, birthday, datetime.now().isoformat())
        )
        await db.execute(
            "INSERT INTO promocodes (guest_id, code, title, description, expires_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, welcome_code, "Приветственный подарок", "Скидка 10% и сладкий подарок от шефа", expires)
        )
        await db.commit()
    return welcome_code, expires

async def add_family_member(guest_id: int, relation: str, name: str, birthday: str):
    async with aiosqlite.connect(DB_PATH) as db:
        # Проверка на дубликат
        async with db.execute(
            "SELECT id FROM family_members WHERE guest_id = ? AND LOWER(relation) = LOWER(?) AND LOWER(name) = LOWER(?)",
            (guest_id, relation, name)
        ) as c:
            if await c.fetchone():
                return False  # Дубликат найден
        
        await db.execute(
            "INSERT INTO family_members (guest_id, relation, name, birthday) VALUES (?, ?, ?, ?)",
            (guest_id, relation, name, birthday)
        )
        await db.commit()
        return True

async def get_family_members(guest_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, relation, name, birthday FROM family_members WHERE guest_id = ?", (guest_id,)) as c:
            return await c.fetchall()

async def delete_family_member(mem_id: int, guest_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM family_members WHERE id = ? AND guest_id = ?", (mem_id, guest_id))
        await db.commit()

async def sync_and_get_promocodes(user_id: int):
    """Синхронизирует промокоды к ближайшим праздникам и возвращает список всех промокодов"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT full_name, birthday FROM guests WHERE id = ?", (user_id,)) as c:
            guest = await c.fetchone()
        if not guest:
            return None

        guest_name, guest_bday = guest

        # Проверка приветственного
        async with db.execute("SELECT id FROM promocodes WHERE guest_id = ? AND title LIKE '%Приветственный%'", (user_id,)) as c:
            if not await c.fetchone():
                w_code = generate_promo_code("KINZA-WELCOME")
                w_exp = (datetime.now() + timedelta(days=30)).strftime("%d.%m.%Y")
                await db.execute(
                    "INSERT INTO promocodes (guest_id, code, title, description, expires_at) VALUES (?, ?, ?, ?, ?)",
                    (user_id, w_code, "Приветственный подарок", "Скидка 10% и десерт от шефа", w_exp)
                )

        # Проверка ДР гостя (в пределах 7 дней)
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
            return await c.fetchall()

async def get_promo_details(code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT p.id, p.code, p.title, p.description, p.expires_at, p.is_used, p.used_at, g.full_name, g.phone
            FROM promocodes p
            LEFT JOIN guests g ON p.guest_id = g.id
            WHERE UPPER(p.code) = ?
        """, (code.upper(),)) as c:
            return await c.fetchone()

async def redeem_promo(p_id: int):
    used_time = datetime.now().strftime("%d.%m.%Y в %H:%M")
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT is_used, code FROM promocodes WHERE id = ?", (p_id,)) as c:
            row = await c.fetchone()
            if not row or row[0] == 1:
                return False, None, None
            code_name = row[1]

        await db.execute("UPDATE promocodes SET is_used = 1, used_at = ? WHERE id = ?", (used_time, p_id))
        await db.commit()
        return True, code_name, used_time

async def get_crm_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM guests") as c:
            total_guests = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM family_members") as c:
            total_family = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM promocodes WHERE is_used = 0") as c:
            active_promos = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM promocodes WHERE is_used = 1") as c:
            used_promos = (await c.fetchone())[0]
        return total_guests, total_family, active_promos, used_promos