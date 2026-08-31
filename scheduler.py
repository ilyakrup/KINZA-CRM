import logging
from datetime import datetime, timedelta
import aiosqlite
from config import DB_PATH
from aiogram import Bot

async def check_birthdays_and_notify(bot: Bot):
    in_7_days = (datetime.now() + timedelta(days=7)).strftime("%d.%m")
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, full_name FROM guests WHERE birthday = ?", (in_7_days,)) as c:
            for g_id, name in await c.fetchall():
                try:
                    await bot.send_message(
                        g_id,
                        f"🎉 **{name}, совсем скоро ваш день рождения!**\n\n"
                        f"Мы в ресторане «Кинза» уже подготовили для вас подарок — **скидку 10% и торт от шефа**!\n"
                        f"Проверьте раздел **«🎁 Мои подарки»** и забронируйте столик ❤️",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logging.error(f"Ошибка отправки уведомления: {e}")