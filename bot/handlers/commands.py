"""Обработчики команд бота."""
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from database import Database
from filters import ListingFilter, get_default_filters
from bot.utils.listing_service import ListingService
from bot.utils.formatters import format_listing_message
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)


def setup_command_handlers(
    application,
    db: Database,
    listing_service: ListingService
) -> None:
    """
    Настройка обработчиков команд.
    
    Args:
        application: Приложение Telegram бота
        db: Экземпляр базы данных
        listing_service: Сервис для работы с объявлениями
    """
    application.add_handler(CommandHandler("start", lambda u, c: start(u, c, db)))
    application.add_handler(CommandHandler("filters", lambda u, c: show_filters_menu(u, c, db)))
    application.add_handler(CommandHandler("check", lambda u, c: check_listings(u, c, db, listing_service)))
    application.add_handler(CommandHandler("status", lambda u, c: show_status(u, c, db)))


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db: Database
) -> None:
    """
    Обработчик команды /start.
    
    Args:
        update: Обновление от Telegram
        context: Контекст бота
        db: Экземпляр базы данных
    """
    welcome_text = (
        "🏠 Добро пожаловать в бот для поиска квартир!\n\n"
        "Я помогу вам найти подходящие объявления об аренде квартир "
        "на сайтах Onliner, Kufar и Realt.by.\n\n"
        "Используйте команды:\n"
        "/filters - настроить фильтры поиска\n"
        "/check - проверить новые объявления сейчас\n"
        "/status - посмотреть текущие настройки"
    )
    await update.message.reply_text(welcome_text)


async def show_filters_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db: Database
) -> None:
    """
    Показать меню настройки фильтров.
    
    Args:
        update: Обновление от Telegram
        context: Контекст бота
        db: Экземпляр базы данных
    """
    from bot.handlers.callbacks import create_filters_keyboard
    
    user_id = update.effective_user.id
    current_filters = db.get_user_filters(user_id) or get_default_filters()
    
    text = "⚙️ Настройка фильтров:\n\n"
    text += f"🏠 Комнаты: {current_filters.get('rooms', 'Не важно') or 'Не важно'}\n"
    text += f"💰 Мин. цена (USD): {current_filters.get('min_price_usd', 'Не важно') or 'Не важно'}\n"
    text += f"💰 Макс. цена (USD): {current_filters.get('max_price_usd', 'Не важно') or 'Не важно'}\n"
    text += f"👤 Арендодатель: {current_filters.get('landlord', 'Не важно') or 'Не важно'}\n"
    text += f"📰 Источники: {', '.join(current_filters.get('sources', []))}\n\n"
    text += "Выберите параметр для изменения:"
    
    keyboard = create_filters_keyboard(current_filters)
    await update.message.reply_text(text, reply_markup=keyboard)


async def check_listings(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db: Database,
    listing_service: ListingService
) -> None:
    """
    Проверить новые объявления.
    
    Args:
        update: Обновление от Telegram
        context: Контекст бота
        db: Экземпляр базы данных
        listing_service: Сервис для работы с объявлениями
    """
    user_id = update.effective_user.id
    await update.message.reply_text("🔍 Ищу новые объявления...")
    
    user_filters = db.get_user_filters(user_id)
    if not user_filters:
        await update.message.reply_text(
            "⚠️ Сначала настройте фильтры с помощью команды /filters"
        )
        return
    
    filter_obj = ListingFilter(user_filters)
    new_listings = await listing_service.fetch_and_filter_listings(filter_obj, user_id)
    
    if new_listings:
        await update.message.reply_text(
            f"✅ Найдено {len(new_listings)} новых объявлений!"
        )
        for listing in new_listings:
            try:
                message_text = format_listing_message(listing)
                await update.message.reply_text(
                    message_text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=False
                )
                db.mark_listing_sent(listing['listing_id'], user_id)
            except Exception as e:
                logger.error(f"Ошибка отправки объявления: {e}")
    else:
        await update.message.reply_text("😔 Новых объявлений не найдено.")


async def show_status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db: Database
) -> None:
    """
    Показать текущие настройки.
    
    Args:
        update: Обновление от Telegram
        context: Контекст бота
        db: Экземпляр базы данных
    """
    user_id = update.effective_user.id
    current_filters = db.get_user_filters(user_id)
    
    if not current_filters:
        await update.message.reply_text(
            "⚠️ Фильтры не настроены. Используйте /filters"
        )
        return
    
    text = "📊 Текущие настройки:\n\n"
    text += f"🏠 Комнаты: {current_filters.get('rooms', 'Не важно') or 'Не важно'}\n"
    text += f"💰 Мин. цена (USD): {current_filters.get('min_price_usd', 'Не важно') or 'Не важно'}\n"
    text += f"💰 Макс. цена (USD): {current_filters.get('max_price_usd', 'Не важно') or 'Не важно'}\n"
    text += f"👤 Арендодатель: {current_filters.get('landlord', 'Не важно') or 'Не важно'}\n"
    text += f"📰 Источники: {', '.join(current_filters.get('sources', []))}\n"
    
    await update.message.reply_text(text)
