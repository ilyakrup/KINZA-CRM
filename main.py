import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import BOT_TOKEN
from database import init_db
from handlers import setup_routers
from scheduler import check_birthdays_and_notify

logging.basicConfig(level=logging.INFO)

async def main():
    # 1. Инициализация базы данных
    await init_db()

    # 2. Инициализация бота и диспетчера
    bot = Bot(token="8998815871:AAGYQGIzfW_Kws_VZj9TMTYx7sNPJBgm7Ro")
    dp = Dispatcher(storage=MemoryStorage())

    # 3. Подключение всех роутеров из папки handlers
    dp.include_router(setup_routers())

    # 4. Настройка планировщика утренних поздравлений (10:00)
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_birthdays_and_notify, "cron", hour=10, minute=0, args=[bot])
    scheduler.start()

    logging.info("🚀 Бот KinzaCRM успешно запущен в модульной архитектуре!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())