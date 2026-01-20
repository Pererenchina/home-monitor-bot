"""Основной модуль бота."""
import asyncio
import logging
from telegram.ext import Application
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

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
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
        user_filters = db.get_user_filters(user_id)
        if not user_filters:
            continue
        
        filter_obj = ListingFilter(user_filters)
        new_listings = await listing_service.fetch_and_filter_listings(
            filter_obj,
            user_id
        )
        
        if new_listings:
            for listing in new_listings:
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
    setup_message_handlers(application, db)
    
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
