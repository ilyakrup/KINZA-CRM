import random
from aiogram import Router, F, types
from aiogram.filters import Command

router = Router()

@router.message(F.text == "🍷 Факт от шефа")
@router.message(Command("fact"))
async def chef_fact(message: types.Message):
    facts = [
        "🌿 **Секрет вкуса:** Свежая кинза полностью раскрывает свой аромат, если добавлять ее в горячее блюдо за 30 секунд до подачи.",
        "🥩 **Сочный стейк:** После жарки мясу нужно «отдохнуть» 3-5 минут, чтобы сок равномерно разошелся по волокнам.",
        "🍰 **Сладкий секрет:** Щепотка морской соли в шоколадном десерте усиливает ощущение сладости на 30%!"
    ]
    await message.answer(random.choice(facts), parse_mode="Markdown")

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "🍽️ **Ресторан «Кинза»**\n\n"
        "📍 Ждем вас каждый день с 11:00 до 23:00.\n"
        "📞 Телефон: +7 (999) 000-00-00",
        parse_mode="Markdown"
    )