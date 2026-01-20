"""Обработчики для Telegram бота."""
from .commands import setup_command_handlers
from .callbacks import setup_callback_handlers
from .messages import setup_message_handlers

__all__ = [
    'setup_command_handlers',
    'setup_callback_handlers',
    'setup_message_handlers'
]
