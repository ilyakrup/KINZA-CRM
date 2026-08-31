from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

def main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Мой профиль"), KeyboardButton(text="👨‍👩‍👧 Добавить праздник")],
            [KeyboardButton(text="🎁 Мои подарки"), KeyboardButton(text="🍷 Факт от шефа")],
            [KeyboardButton(text="🔍 Проверить / Погасить промокод"), KeyboardButton(text="📊 Статистика CRM")]
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

def contact_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Оформить карту гостя (поделиться контактом)", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )