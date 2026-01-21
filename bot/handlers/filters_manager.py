"""Обработчики для управления фильтрами."""
import logging
from typing import List, Dict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import Database
from filters import get_default_filters
from bot.utils.keyboard import get_main_keyboard

logger = logging.getLogger(__name__)


def create_filters_list_keyboard(filters: List[Dict]) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру со списком фильтров.
    
    Args:
        filters: Список фильтров
    
    Returns:
        InlineKeyboardMarkup: Клавиатура
    """
    keyboard = []
    
    for filter_item in filters:
        status = "✅" if filter_item.get('is_active', True) else "❌"
        button_text = f"{status} {filter_item.get('filter_name', 'Фильтр')}"
        keyboard.append([
            InlineKeyboardButton(
                button_text,
                callback_data=f"view_filter_{filter_item['id']}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("➕ Создать новый фильтр", callback_data="create_new_filter")])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(keyboard)


def create_filter_actions_keyboard(filter_id: int) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру действий с фильтром.
    
    Args:
        filter_id: ID фильтра
    
    Returns:
        InlineKeyboardMarkup: Клавиатура
    """
    keyboard = [
        [InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_filter_{filter_id}")],
        [InlineKeyboardButton("🗑️ Удалить", callback_data=f"delete_filter_{filter_id}")],
        [InlineKeyboardButton("🔄 Включить/Выключить", callback_data=f"toggle_filter_{filter_id}")],
        [InlineKeyboardButton("◀️ Назад к списку", callback_data="back_to_filters_list")]
    ]
    return InlineKeyboardMarkup(keyboard)


async def show_filters_list(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db: Database
) -> None:
    """
    Показать список фильтров пользователя.
    
    Args:
        update: Обновление от Telegram
        context: Контекст бота
        db: Экземпляр базы данных
    """
    user_id = update.effective_user.id
    filters = db.get_user_filters(user_id)
    
    if not filters:
        keyboard = get_main_keyboard()
        await update.message.reply_text(
            "📋 У вас пока нет фильтров.\n\n"
            "Нажмите '➕ Создать фильтр' для создания первого фильтра.",
            reply_markup=keyboard
        )
        return
    
    text = f"📋 Ваши фильтры ({len(filters)}):\n\n"
    for i, filter_item in enumerate(filters, 1):
        status = "✅ Активен" if filter_item.get('is_active', True) else "❌ Неактивен"
        text += f"{i}. {filter_item.get('filter_name', 'Фильтр')} - {status}\n"
    
    text += "\nВыберите фильтр для просмотра или редактирования:"
    
    keyboard = create_filters_list_keyboard(filters)
    await update.message.reply_text(text, reply_markup=keyboard)


async def show_filter_details(
    query,
    context: ContextTypes.DEFAULT_TYPE,
    db: Database,
    filter_id: int
) -> None:
    """
    Показать детали фильтра.
    
    Args:
        query: Callback query
        context: Контекст бота
        db: Экземпляр базы данных
        filter_id: ID фильтра
    """
    user_id = query.from_user.id
    filter_data = db.get_user_filter_by_id(filter_id, user_id)
    
    if not filter_data:
        await query.answer("Фильтр не найден", show_alert=True)
        return
    
    filters = filter_data['filters']
    status = "✅ Активен" if filter_data.get('is_active', True) else "❌ Неактивен"
    
    text = f"📋 Фильтр: {filter_data['filter_name']}\n"
    text += f"Статус: {status}\n\n"
    text += "Параметры:\n"
    text += f"🏠 Комнаты: {filters.get('rooms', 'Не важно') or 'Не важно'}\n"
    text += f"💰 Мин. цена (USD): {filters.get('min_price_usd', 'Не важно') or 'Не важно'}\n"
    text += f"💰 Макс. цена (USD): {filters.get('max_price_usd', 'Не важно') or 'Не важно'}\n"
    text += f"👤 Арендодатель: {filters.get('landlord', 'Не важно') or 'Не важно'}\n"
    text += f"🏙️ Город: {filters.get('city', 'Не важно') or 'Не важно'}\n"
    
    keyboard = create_filter_actions_keyboard(filter_id)
    await query.edit_message_text(text, reply_markup=keyboard)
