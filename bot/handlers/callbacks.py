"""Обработчики callback запросов."""
import asyncio
import logging
from typing import Dict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler

from database import Database
from filters import ListingFilter, get_default_filters
from bot.utils.keyboard import get_main_keyboard
from bot.handlers.filters_manager import (
    show_filter_details,
    create_filters_list_keyboard,
    create_filter_actions_keyboard
)
from bot.handlers.filters_manager import (
    show_filter_details,
    create_filters_list_keyboard,
    create_filter_actions_keyboard
)

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
        [InlineKeyboardButton("🏙️ Город", callback_data="filter_city")],
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
        if 'temp_filters' not in context.user_data:
            context.user_data['temp_filters'] = get_default_filters()
        filters = context.user_data['temp_filters']
        if query.data == "set_rooms_none":
            filters['rooms'] = None
        else:
            filters['rooms'] = int(query.data.split("_")[-1])
        context.user_data['temp_filters'] = filters
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
        if 'temp_filters' not in context.user_data:
            context.user_data['temp_filters'] = get_default_filters()
        filters = context.user_data['temp_filters']
        if query.data == "set_landlord_none":
            filters['landlord'] = None
        else:
            filters['landlord'] = query.data.split("_", 2)[-1]
        context.user_data['temp_filters'] = filters
        await query.edit_message_text("✅ Тип арендодателя сохранен!")
        await asyncio.sleep(1)
        await show_filters_menu_from_query(query, context, db)
    
    elif query.data == "filter_city":
        await query.edit_message_text(
            "🏙️ Введите название города (например: Минск, Брест, Гомель) или отправьте 0 для сброса:"
        )
        context.user_data['waiting_for'] = 'city'
    
    elif query.data == "filter_save":
        # Сохраняем фильтр с именем
        if 'creating_filter' in context.user_data:
            filter_name = context.user_data.get('filter_name', 'Фильтр')
            current_filters = context.user_data.get('temp_filters', get_default_filters())
            
            filter_id = db.add_user_filter(user_id, filter_name, current_filters)
            context.user_data.pop('creating_filter', None)
            context.user_data.pop('temp_filters', None)
            context.user_data.pop('filter_name', None)
            
            await query.edit_message_text(
                f"✅ Фильтр '{filter_name}' создан! Начинаю сканирование..."
            )
            
            # Запускаем сканирование
            await scan_with_filter(query, context, db, filter_id, current_filters, user_id)
        else:
            # Редактирование существующего фильтра
            filter_id = context.user_data.get('editing_filter_id')
            if filter_id:
                current_filters = context.user_data.get('temp_filters', get_default_filters())
                db.update_user_filter(filter_id, user_id, filters=current_filters)
                context.user_data.pop('editing_filter_id', None)
                context.user_data.pop('temp_filters', None)
                
                await query.edit_message_text(
                    "✅ Фильтр обновлен! Начинаю сканирование..."
                )
                await scan_with_filter(query, context, db, filter_id, current_filters, user_id)
            else:
                await query.answer("Ошибка: фильтр не найден", show_alert=True)
    
    elif query.data == "create_new_filter":
        context.user_data['creating_filter'] = True
        context.user_data['temp_filters'] = get_default_filters()
        await query.edit_message_text(
            "📝 Создание нового фильтра\n\n"
            "Введите название для фильтра:"
        )
        context.user_data['waiting_for'] = 'filter_name'
    
    elif query.data == "back_to_filters_list":
        filters = db.get_user_filters(user_id)
        if filters:
            text = f"📋 Ваши фильтры ({len(filters)}):\n\n"
            for i, filter_item in enumerate(filters, 1):
                status = "✅ Активен" if filter_item.get('is_active', True) else "❌ Неактивен"
                text += f"{i}. {filter_item.get('filter_name', 'Фильтр')} - {status}\n"
            text += "\nВыберите фильтр:"
            keyboard = create_filters_list_keyboard(filters)
            await query.edit_message_text(text, reply_markup=keyboard)
        else:
            keyboard = get_main_keyboard()
            await query.edit_message_text(
                "📋 У вас пока нет фильтров.",
                reply_markup=keyboard
            )
    
    elif query.data.startswith("view_filter_"):
        filter_id = int(query.data.split("_")[-1])
        await show_filter_details(query, context, db, filter_id)
    
    elif query.data.startswith("edit_filter_"):
        filter_id = int(query.data.split("_")[-1])
        filter_data = db.get_user_filter_by_id(filter_id, user_id)
        if filter_data:
            context.user_data['editing_filter_id'] = filter_id
            context.user_data['temp_filters'] = filter_data['filters']
            await show_filters_menu_from_query(query, context, db)
        else:
            await query.answer("Фильтр не найден", show_alert=True)
    
    elif query.data.startswith("delete_filter_"):
        filter_id = int(query.data.split("_")[-1])
        if db.delete_user_filter(filter_id, user_id):
            await query.answer("✅ Фильтр удален", show_alert=True)
            filters = db.get_user_filters(user_id)
            if filters:
                text = f"📋 Ваши фильтры ({len(filters)}):\n\n"
                for i, filter_item in enumerate(filters, 1):
                    status = "✅ Активен" if filter_item.get('is_active', True) else "❌ Неактивен"
                    text += f"{i}. {filter_item.get('filter_name', 'Фильтр')} - {status}\n"
                text += "\nВыберите фильтр:"
                keyboard = create_filters_list_keyboard(filters)
                await query.edit_message_text(text, reply_markup=keyboard)
            else:
                keyboard = get_main_keyboard()
                await query.edit_message_text(
                    "📋 У вас больше нет фильтров.",
                    reply_markup=keyboard
                )
        else:
            await query.answer("❌ Ошибка при удалении", show_alert=True)
    
    elif query.data.startswith("toggle_filter_"):
        filter_id = int(query.data.split("_")[-1])
        filter_data = db.get_user_filter_by_id(filter_id, user_id)
        if filter_data:
            new_status = not filter_data.get('is_active', True)
            db.update_user_filter(filter_id, user_id, is_active=new_status)
            await query.answer(
                f"✅ Фильтр {'включен' if new_status else 'выключен'}",
                show_alert=True
            )
            await show_filter_details(query, context, db, filter_id)
        else:
            await query.answer("Фильтр не найден", show_alert=True)
    
    elif query.data == "back_to_main":
        keyboard = get_main_keyboard()
        await query.edit_message_text(
            "🏠 Главное меню",
            reply_markup=keyboard
        )
    
    elif query.data == "filter_reset":
        context.user_data['temp_filters'] = get_default_filters()
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
    
    # Используем временные фильтры если они есть (при создании/редактировании)
    if 'temp_filters' in context.user_data:
        current_filters = context.user_data['temp_filters']
    else:
        # При редактировании берем из БД
        if 'editing_filter_id' in context.user_data:
            filter_id = context.user_data['editing_filter_id']
            filter_data = db.get_user_filter_by_id(filter_id, user_id)
            if filter_data:
                current_filters = filter_data['filters']
                context.user_data['temp_filters'] = current_filters
            else:
                current_filters = get_default_filters()
        else:
            current_filters = get_default_filters()
    
    text = "⚙️ Настройка фильтров:\n\n"
    text += f"🏠 Комнаты: {current_filters.get('rooms', 'Не важно') or 'Не важно'}\n"
    text += f"💰 Мин. цена (USD): {current_filters.get('min_price_usd', 'Не важно') or 'Не важно'}\n"
    text += f"💰 Макс. цена (USD): {current_filters.get('max_price_usd', 'Не важно') or 'Не важно'}\n"
    text += f"👤 Арендодатель: {current_filters.get('landlord', 'Не важно') or 'Не важно'}\n"
    text += f"🏙️ Город: {current_filters.get('city', 'Не важно') or 'Не важно'}\n\n"
    text += "Выберите параметр для изменения:"
    
    keyboard = create_filters_keyboard(current_filters)
    await query.edit_message_text(text, reply_markup=keyboard)


async def scan_with_filter(
    query,
    context: ContextTypes.DEFAULT_TYPE,
    db: Database,
    filter_id: int,
    filters: Dict,
    user_id: int
) -> None:
    """
    Выполнить сканирование с фильтром.
    
    Args:
        query: Callback query
        context: Контекст бота
        db: Экземпляр базы данных
        filter_id: ID фильтра
        filters: Словарь с фильтрами
        user_id: ID пользователя
    """
    from bot.utils.listing_service import ListingService
    from filters import ListingFilter
    from bot.utils.formatters import format_listing_message
    from telegram.constants import ParseMode
    
    listing_service = ListingService(db)
    filter_obj = ListingFilter(filters)
    main_keyboard = get_main_keyboard()
    
    try:
        new_listings = await listing_service.fetch_and_filter_listings(filter_obj, user_id)
        
        if new_listings:
            # Ограничиваем до 15 объявлений
            listings_to_send = new_listings[-15:] if len(new_listings) > 15 else new_listings
            
            await query.message.reply_text(
                f"✅ Найдено {len(new_listings)} объявлений! Отправляю последние {len(listings_to_send)}...",
                reply_markup=main_keyboard
            )
            for listing in listings_to_send:
                try:
                    message_text = format_listing_message(listing)
                    await query.message.reply_text(
                        message_text,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=False,
                        reply_markup=main_keyboard
                    )
                    db.mark_listing_sent(listing['listing_id'], user_id)
                except Exception as e:
                    logger.error(f"Ошибка отправки объявления: {e}")
        else:
            await query.message.reply_text(
                "😔 Объявлений по вашим фильтрам не найдено.",
                reply_markup=main_keyboard
            )
    except Exception as e:
        logger.error(f"Ошибка при сканировании: {e}")
        await query.message.reply_text(
            f"❌ Ошибка при сканировании: {e}",
            reply_markup=main_keyboard
        )
