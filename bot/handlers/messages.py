"""Обработчики текстовых сообщений."""
import logging
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters as tg_filters

from database import Database
from filters import get_default_filters

logger = logging.getLogger(__name__)


def setup_message_handlers(application, db: Database) -> None:
    """
    Настройка обработчиков сообщений.
    
    Args:
        application: Приложение Telegram бота
        db: Экземпляр базы данных
    """
    application.add_handler(
        MessageHandler(
            tg_filters.TEXT & ~tg_filters.COMMAND,
            lambda u, c: handle_message(u, c, db)
        )
    )


async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db: Database
) -> None:
    """
    Обработка текстовых сообщений.
    
    Args:
        update: Обновление от Telegram
        context: Контекст бота
        db: Экземпляр базы данных
    """
    user_id = update.effective_user.id
    text = update.message.text
    
    if context.user_data.get('waiting_for') == 'min_price':
        try:
            price = float(text)
            user_filters = db.get_user_filters(user_id) or get_default_filters()
            user_filters['min_price_usd'] = None if price == 0 else price
            db.save_user_filters(user_id, user_filters)
            await update.message.reply_text("✅ Минимальная цена сохранена!")
            context.user_data['waiting_for'] = None
        except ValueError:
            await update.message.reply_text("❌ Неверный формат. Введите число.")
    
    elif context.user_data.get('waiting_for') == 'max_price':
        try:
            price = float(text)
            user_filters = db.get_user_filters(user_id) or get_default_filters()
            user_filters['max_price_usd'] = None if price == 0 else price
            db.save_user_filters(user_id, user_filters)
            await update.message.reply_text("✅ Максимальная цена сохранена!")
            context.user_data['waiting_for'] = None
        except ValueError:
            await update.message.reply_text("❌ Неверный формат. Введите число.")
