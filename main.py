"""Точка входа в приложение."""
import logging
import os
from logging.handlers import RotatingFileHandler
from bot import create_application

# Создаем директорию для логов
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Настройка логирования в файл и консоль
log_file = os.path.join(log_dir, "bot.log")

# Создаем форматтер
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Обработчик для файла (с ротацией, максимум 10MB, 5 файлов)
file_handler = RotatingFileHandler(
    log_file,
    maxBytes=10*1024*1024,  # 10 MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)

# Обработчик для консоли
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)

# Настройка корневого логгера
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

logger = logging.getLogger(__name__)


def main() -> None:
    """Главная функция запуска бота."""
    try:
        application = create_application()
        logger.info("Бот запущен!")
        application.run_polling(allowed_updates=None)
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        raise


if __name__ == '__main__':
    main()
