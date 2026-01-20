"""Обработчики callback запросов."""
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler

from database import Database
from filters import ListingFilter, get_default_filters

logger = logging.getLogger(__name__)


def setup_callback_handlers(application, db: Database) -> None:
    """
    Настройка обработчиков callback.
    
    Args:
        application: Приложение Telegram бота
        db: Экземпляр базы данных
    """
    application.add_handler(
        CallbackQueryHandler(lambda u, c: button_callback(u, c, db))
    )


def create_filters_keyboard(current_filters: dict) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру для меню фильтров.
    
    Args:
        current_filters: Текущие фильтры пользователя
    
    Returns:
        InlineKeyboardMarkup: Клавиатура
    """
    keyboard = [
        [InlineKeyboardButton("🏠 Количество комнат", callback_data="filter_rooms")],
        [InlineKeyboardButton("💰 Минимальная цена (USD)", callback_data="filter_min_price")],
        [InlineKeyboardButton("💰 Максимальная цена (USD)", callback_data="filter_max_price")],
        [InlineKeyboardButton("👤 Арендодатель", callback_data="filter_landlord")],
        [InlineKeyboardButton("📰 Источники", callback_data="filter_sources")],
        [InlineKeyboardButton("✅ Сохранить и начать поиск", callback_data="filter_save")],
        [InlineKeyboardButton("❌ Сбросить фильтры", callback_data="filter_reset")]
    ]
    return InlineKeyboardMarkup(keyboard)


async def button_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db: Database
) -> None:
    """
    Обработка нажатий на кнопки.
    
    Args:
        update: Обновление от Telegram
        context: Контекст бота
        db: Экземпляр базы данных
    """
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if query.data == "filter_rooms":
        keyboard = [
            [InlineKeyboardButton("1 комната", callback_data="set_rooms_1")],
            [InlineKeyboardButton("2 комнаты", callback_data="set_rooms_2")],
            [InlineKeyboardButton("3 комнаты", callback_data="set_rooms_3")],
            [InlineKeyboardButton("4+ комнат", callback_data="set_rooms_4")],
            [InlineKeyboardButton("Не важно", callback_data="set_rooms_none")],
            [InlineKeyboardButton("◀️ Назад", callback_data="back_to_filters")]
        ]
        await query.edit_message_text(
            "Выберите количество комнат:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data.startswith("set_rooms_"):
        filters = db.get_user_filters(user_id) or get_default_filters()
        if query.data == "set_rooms_none":
            filters['rooms'] = None
        else:
            filters['rooms'] = int(query.data.split("_")[-1])
        db.save_user_filters(user_id, filters)
        await query.edit_message_text("✅ Количество комнат сохранено!")
        await asyncio.sleep(1)
        await show_filters_menu_from_query(query, context, db)
    
    elif query.data == "filter_min_price":
        await query.edit_message_text(
            "💰 Введите минимальную цену в USD (или отправьте 0 для сброса):"
        )
        context.user_data['waiting_for'] = 'min_price'
    
    elif query.data == "filter_max_price":
        await query.edit_message_text(
            "💰 Введите максимальную цену в USD (или отправьте 0 для сброса):"
        )
        context.user_data['waiting_for'] = 'max_price'
    
    elif query.data == "filter_landlord":
        keyboard = [
            [InlineKeyboardButton("Собственник", callback_data="set_landlord_Собственник")],
            [InlineKeyboardButton("Агентство", callback_data="set_landlord_Агентство")],
            [InlineKeyboardButton("Не важно", callback_data="set_landlord_none")],
            [InlineKeyboardButton("◀️ Назад", callback_data="back_to_filters")]
        ]
        await query.edit_message_text(
            "Выберите тип арендодателя:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data.startswith("set_landlord_"):
        filters = db.get_user_filters(user_id) or get_default_filters()
        if query.data == "set_landlord_none":
            filters['landlord'] = None
        else:
            filters['landlord'] = query.data.split("_", 2)[-1]
        db.save_user_filters(user_id, filters)
        await query.edit_message_text("✅ Тип арендодателя сохранен!")
        await asyncio.sleep(1)
        await show_filters_menu_from_query(query, context, db)
    
    elif query.data == "filter_sources":
        current_filters = db.get_user_filters(user_id) or get_default_filters()
        sources = current_filters.get('sources', ['Onliner', 'Kufar', 'Realt.by'])
        
        keyboard = [
            [
                InlineKeyboardButton(
                    "✅ Onliner" if "Onliner" in sources else "Onliner",
                    callback_data="toggle_source_Onliner"
                )
            ],
            [
                InlineKeyboardButton(
                    "✅ Kufar" if "Kufar" in sources else "Kufar",
                    callback_data="toggle_source_Kufar"
                )
            ],
            [
                InlineKeyboardButton(
                    "✅ Realt.by" if "Realt.by" in sources else "Realt.by",
                    callback_data="toggle_source_Realt.by"
                )
            ],
            [InlineKeyboardButton("◀️ Назад", callback_data="back_to_filters")]
        ]
        await query.edit_message_text(
            "Выберите источники (можно несколько):",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data.startswith("toggle_source_"):
        filters = db.get_user_filters(user_id) or get_default_filters()
        source = query.data.split("_", 2)[-1]
        sources = filters.get('sources', [])
        if source in sources:
            sources.remove(source)
        else:
            sources.append(source)
        filters['sources'] = sources
        db.save_user_filters(user_id, filters)
        # Обновляем меню
        await button_callback(update, context, db)
    
    elif query.data == "filter_save":
        await query.edit_message_text(
            "✅ Фильтры сохранены! Используйте /check для проверки объявлений."
        )
    
    elif query.data == "filter_reset":
        db.save_user_filters(user_id, get_default_filters())
        await query.edit_message_text("✅ Фильтры сброшены!")
        await asyncio.sleep(1)
        await show_filters_menu_from_query(query, context, db)
    
    elif query.data == "back_to_filters":
        await show_filters_menu_from_query(query, context, db)


async def show_filters_menu_from_query(
    query,
    context: ContextTypes.DEFAULT_TYPE,
    db: Database
) -> None:
    """
    Показать меню фильтров из callback query.
    
    Args:
        query: Callback query
        context: Контекст бота
        db: Экземпляр базы данных
    """
    user_id = query.from_user.id
    current_filters = db.get_user_filters(user_id) or get_default_filters()
    
    text = "⚙️ Настройка фильтров:\n\n"
    text += f"🏠 Комнаты: {current_filters.get('rooms', 'Не важно') or 'Не важно'}\n"
    text += f"💰 Мин. цена (USD): {current_filters.get('min_price_usd', 'Не важно') or 'Не важно'}\n"
    text += f"💰 Макс. цена (USD): {current_filters.get('max_price_usd', 'Не важно') or 'Не важно'}\n"
    text += f"👤 Арендодатель: {current_filters.get('landlord', 'Не важно') or 'Не важно'}\n"
    text += f"📰 Источники: {', '.join(current_filters.get('sources', []))}\n\n"
    text += "Выберите параметр для изменения:"
    
    keyboard = create_filters_keyboard(current_filters)
    await query.edit_message_text(text, reply_markup=keyboard)
