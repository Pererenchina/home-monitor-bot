"""Основной модуль бота."""
import asyncio
import logging
from telegram import Update
from telegram.ext import Application, ContextTypes
from telegram.constants import ParseMode

from config import settings
from database import Database
from filters import ListingFilter
from bot.handlers import (
    setup_command_handlers,
    setup_callback_handlers,
    setup_message_handlers
)
from bot.utils.listing_service import ListingService
from bot.utils.formatters import format_listing_message

# Логирование уже настроено в main.py
logger = logging.getLogger(__name__)


async def periodic_check(context) -> None:
    """
    Периодическая проверка новых объявлений.
    
    Args:
        context: Контекст бота
    """
    db = Database(settings.db_path)
    listing_service = ListingService(db)
    users = db.get_all_users_with_filters()
    
    for user_id in users:
        # Получаем все активные фильтры пользователя
        active_filters = db.get_active_filters_for_user(user_id)
        if not active_filters:
            continue
        
        # Проверяем все активные фильтры
        all_listings = []
        for filter_item in active_filters:
            filter_obj = ListingFilter(filter_item['filters'])
            listings = await listing_service.fetch_and_filter_listings(
                filter_obj,
                user_id
            )
            all_listings.extend(listings)
        
        # Убираем дубликаты
        seen_ids = set()
        unique_listings = []
        for listing in all_listings:
            if listing['listing_id'] not in seen_ids:
                seen_ids.add(listing['listing_id'])
                unique_listings.append(listing)
        
        # Ограничиваем до 15 объявлений
        listings_to_send = unique_listings[-15:] if len(unique_listings) > 15 else unique_listings
        
        if listings_to_send:
            for listing in listings_to_send:
                try:
                    message_text = format_listing_message(listing)
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=message_text,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=False
                    )
                    db.mark_listing_sent(listing['listing_id'], user_id)
                    await asyncio.sleep(1)  # Задержка между сообщениями
                except Exception as e:
                    logger.error(f"Ошибка отправки сообщения пользователю {user_id}: {e}")


def create_application() -> Application:
    """
    Создать и настроить приложение бота.
    
    Returns:
        Application: Настроенное приложение Telegram бота
    """
    if not settings.validate():
        raise ValueError("TELEGRAM_BOT_TOKEN не установлен! Создайте файл .env")
    
    # Создание приложения
    application = Application.builder().token(settings.telegram_bot_token).build()
    
    # Инициализация сервисов
    db = Database(settings.db_path)
    listing_service = ListingService(db)
    
    # Регистрация обработчиков
    setup_command_handlers(application, db, listing_service)
    setup_callback_handlers(application, db)
    setup_message_handlers(application, db, listing_service)
    
    # Обработчик ошибок
    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик ошибок."""
        logger.error(
            f"Exception while handling an update: {context.error}",
            exc_info=context.error
        )
        if update and isinstance(update, Update) and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "❌ Произошла ошибка. Попробуйте позже или обратитесь к администратору."
                )
            except Exception:
                pass
    
    application.add_error_handler(error_handler)
    
    # Периодическая проверка
    job_queue = application.job_queue
    if job_queue:
        job_queue.run_repeating(
            periodic_check,
            interval=settings.check_interval,
            first=10
        )
    
    logger.info("Бот инициализирован")
    return application
