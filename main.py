"""Точка входа в приложение."""
import logging
from bot import create_application

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
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
