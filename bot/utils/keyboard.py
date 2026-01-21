"""Утилиты для создания клавиатур."""
from telegram import ReplyKeyboardMarkup, KeyboardButton


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """
    Создать основную клавиатуру с кнопками.
    
    Returns:
        ReplyKeyboardMarkup: Клавиатура с основными кнопками
    """
    keyboard = [
        [
            KeyboardButton("➕ Создать фильтр"),
            KeyboardButton("📋 Мои фильтры")
        ],
        [
            KeyboardButton("🔍 Проверить объявления"),
            KeyboardButton("ℹ️ Помощь")
        ]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
