"""Обработчики текстовых сообщений."""
import logging
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters as tg_filters

from database import Database
from filters import ListingFilter, get_default_filters
from bot.utils.keyboard import get_main_keyboard
from bot.utils.listing_service import ListingService
from bot.utils.formatters import format_listing_message
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)


def setup_message_handlers(application, db: Database, listing_service: ListingService) -> None:
    """
    Настройка обработчиков сообщений.
    
    Args:
        application: Приложение Telegram бота
        db: Экземпляр базы данных
        listing_service: Сервис для работы с объявлениями
    """
    application.add_handler(
        MessageHandler(
            tg_filters.TEXT & ~tg_filters.COMMAND,
            lambda u, c: handle_message(u, c, db, listing_service)
        )
    )


async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db: Database,
    listing_service: ListingService
) -> None:
    """
    Обработка текстовых сообщений и кнопок.
    
    Args:
        update: Обновление от Telegram
        context: Контекст бота
        db: Экземпляр базы данных
        listing_service: Сервис для работы с объявлениями
    """
    user_id = update.effective_user.id
    text = update.message.text
    keyboard = get_main_keyboard()
    
    # Обработка нажатий кнопок
    if text == "➕ Создать фильтр":
        context.user_data['creating_filter'] = True
        context.user_data['temp_filters'] = get_default_filters()
        await update.message.reply_text(
            "📝 Создание нового фильтра\n\n"
            "Введите название для фильтра:",
            reply_markup=keyboard
        )
        context.user_data['waiting_for'] = 'filter_name'
        return
    
    elif text == "📋 Мои фильтры":
        from bot.handlers.filters_manager import show_filters_list
        await show_filters_list(update, context, db)
        return
    
    elif text == "🔍 Проверить объявления":
        await update.message.reply_text("🔍 Ищу новые объявления...", reply_markup=keyboard)
        
        active_filters = db.get_active_filters_for_user(user_id)
        if not active_filters:
            await update.message.reply_text(
                "⚠️ У вас нет активных фильтров! Создайте фильтр через кнопку '➕ Создать фильтр'",
                reply_markup=keyboard
            )
            return
        
        # Проверяем все активные фильтры
        all_listings = []
        for filter_item in active_filters:
            filter_obj = ListingFilter(filter_item['filters'])
            listings = await listing_service.fetch_and_filter_listings(filter_obj, user_id)
            all_listings.extend(listings)
        
        # Убираем дубликаты
        seen_ids = set()
        unique_listings = []
        for listing in all_listings:
            if listing['listing_id'] not in seen_ids:
                seen_ids.add(listing['listing_id'])
                unique_listings.append(listing)
        
        if unique_listings:
            # Ограничиваем до 15 объявлений
            listings_to_send = unique_listings[-15:] if len(unique_listings) > 15 else unique_listings
            await update.message.reply_text(
                f"✅ Найдено {len(unique_listings)} объявлений! Отправляю последние {len(listings_to_send)}...",
                reply_markup=keyboard
            )
            for listing in listings_to_send:
                try:
                    message_text = format_listing_message(listing)
                    await update.message.reply_text(
                        message_text,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=False,
                        reply_markup=keyboard
                    )
                    db.mark_listing_sent(listing['listing_id'], user_id)
                except Exception as e:
                    logger.error(f"Ошибка отправки объявления: {e}")
        else:
            await update.message.reply_text("😔 Новых объявлений не найдено.", reply_markup=keyboard)
        return
    
    
    elif text == "ℹ️ Помощь":
        help_text = (
            "ℹ️ Помощь по использованию бота:\n\n"
            "🏠 Бот ищет объявления об аренде квартир на сайтах:\n"
            "• Onliner.by\n"
            "• Kufar.by\n"
            "• Realt.by\n"
            "• Domovita.by\n\n"
            "⚙️ Настройте фильтры:\n"
            "• Количество комнат\n"
            "• Диапазон цен (USD)\n"
            "• Тип арендодателя\n"
            "• Город\n\n"
            "🔍 После настройки фильтров бот автоматически:\n"
            "• Сканирует сайты\n"
            "• Отправляет до 15 подходящих объявлений\n"
            "• Проверяет новые объявления каждые 5 минут\n\n"
            "Используйте кнопки внизу для управления!"
        )
        await update.message.reply_text(help_text, reply_markup=keyboard)
        return
    
    if context.user_data.get('waiting_for') == 'filter_name':
        filter_name = text.strip()
        if not filter_name:
            await update.message.reply_text("❌ Название не может быть пустым. Введите название:", reply_markup=keyboard)
            return
        
        context.user_data['filter_name'] = filter_name
        context.user_data['waiting_for'] = None
        
        # Показываем меню настройки фильтров
        from bot.handlers.callbacks import create_filters_keyboard
        temp_filters = context.user_data.get('temp_filters', get_default_filters())
        
        menu_text = f"⚙️ Настройка фильтра '{filter_name}':\n\n"
        menu_text += f"🏠 Комнаты: {temp_filters.get('rooms', 'Не важно') or 'Не важно'}\n"
        menu_text += f"💰 Мин. цена (USD): {temp_filters.get('min_price_usd', 'Не важно') or 'Не важно'}\n"
        menu_text += f"💰 Макс. цена (USD): {temp_filters.get('max_price_usd', 'Не важно') or 'Не важно'}\n"
        menu_text += f"👤 Арендодатель: {temp_filters.get('landlord', 'Не важно') or 'Не важно'}\n"
        menu_text += f"🏙️ Город: {temp_filters.get('city', 'Не важно') or 'Не важно'}\n\n"
        menu_text += "Выберите параметр для изменения:"
        
        filters_keyboard = create_filters_keyboard(temp_filters)
        await update.message.reply_text(menu_text, reply_markup=filters_keyboard)
        return
    
    elif context.user_data.get('waiting_for') == 'min_price':
        try:
            price = float(text)
            if 'temp_filters' not in context.user_data:
                context.user_data['temp_filters'] = get_default_filters()
            temp_filters = context.user_data['temp_filters']
            temp_filters['min_price_usd'] = None if price == 0 else price
            context.user_data['temp_filters'] = temp_filters
            await update.message.reply_text("✅ Минимальная цена сохранена!")
            from bot.handlers.callbacks import show_filters_menu_from_query
            class FakeQuery:
                def __init__(self, user, message):
                    self.from_user = user
                    self.message = message
                    self.edit_message_text = message.reply_text
            fake_query = FakeQuery(update.effective_user, update.message)
            await show_filters_menu_from_query(fake_query, context, db)
            context.user_data['waiting_for'] = None
        except ValueError:
            await update.message.reply_text("❌ Неверный формат. Введите число.", reply_markup=keyboard)
    
    elif context.user_data.get('waiting_for') == 'max_price':
        try:
            price = float(text)
            if 'temp_filters' not in context.user_data:
                context.user_data['temp_filters'] = get_default_filters()
            temp_filters = context.user_data['temp_filters']
            temp_filters['max_price_usd'] = None if price == 0 else price
            context.user_data['temp_filters'] = temp_filters
            await update.message.reply_text("✅ Максимальная цена сохранена!")
            from bot.handlers.callbacks import show_filters_menu_from_query
            class FakeQuery:
                def __init__(self, user, message):
                    self.from_user = user
                    self.message = message
                    self.edit_message_text = message.reply_text
            fake_query = FakeQuery(update.effective_user, update.message)
            await show_filters_menu_from_query(fake_query, context, db)
            context.user_data['waiting_for'] = None
        except ValueError:
            await update.message.reply_text("❌ Неверный формат. Введите число.", reply_markup=keyboard)
    
    elif context.user_data.get('waiting_for') == 'city':
        if 'temp_filters' not in context.user_data:
            context.user_data['temp_filters'] = get_default_filters()
        temp_filters = context.user_data['temp_filters']
        if text.strip().lower() == '0':
            temp_filters['city'] = None
            await update.message.reply_text("✅ Город сброшен!")
        else:
            temp_filters['city'] = text.strip()
            await update.message.reply_text(f"✅ Город '{text.strip()}' сохранен!")
        context.user_data['temp_filters'] = temp_filters
        from bot.handlers.callbacks import show_filters_menu_from_query
        class FakeQuery:
            def __init__(self, user, message):
                self.from_user = user
                self.message = message
                self.edit_message_text = message.reply_text
        fake_query = FakeQuery(update.effective_user, update.message)
        await show_filters_menu_from_query(fake_query, context, db)
        context.user_data['waiting_for'] = None
