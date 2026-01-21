"""Настройки приложения."""
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Класс для хранения настроек приложения."""
    
    def __init__(self):
        """Инициализация настроек из переменных окружения."""
        self.telegram_bot_token: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
        
        # URLs для парсинга
        self.onliner_url: str = "https://r.onliner.by/ak/"
        self.kufar_url: str = "https://re.kufar.by/"
        self.realt_url: str = "https://realt.by/"
        self.domovita_url: str = "https://domovita.by/minsk/flats/rent"
        
        # Интервал проверки новых объявлений (в секундах)
        self.check_interval: int = int(os.getenv('CHECK_INTERVAL', '300'))  # 5 минут
        
        # Настройки парсинга
        self.user_agent: str = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        
        # Настройки базы данных
        self.db_path: str = os.getenv('DB_PATH', 'bot_database.db')
        
        # Таймаут для HTTP запросов
        self.http_timeout: int = int(os.getenv('HTTP_TIMEOUT', '10'))
        
        # Максимальное количество объявлений для парсинга за раз
        self.max_listings_per_source: int = int(os.getenv('MAX_LISTINGS_PER_SOURCE', '20'))
    
    def validate(self) -> bool:
        """
        Проверка валидности настроек.
        
        Returns:
            bool: True если настройки валидны, иначе False
        """
        if not self.telegram_bot_token:
            return False
        return True
