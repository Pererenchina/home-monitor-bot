"""Базовый класс для парсеров объявлений."""
import re
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple
import aiohttp
from bs4 import BeautifulSoup

from config import settings

logger = logging.getLogger(__name__)


class BaseParser(ABC):
    """Базовый абстрактный класс для парсеров объявлений."""
    
    def __init__(self, selenium_parser=None) -> None:
        """
        Инициализация парсера.
        
        Args:
            selenium_parser: Опционально — общий парсер на Chromium для загрузки страниц (меньше блокировок).
        """
        self.headers = {
            'User-Agent': settings.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        }
        self.timeout = aiohttp.ClientTimeout(total=settings.http_timeout)
        self.selenium_parser = selenium_parser
    
    async def fetch_page(self, url: str) -> Optional[str]:
        """
        Получить HTML страницы.
        
        Args:
            url: URL страницы для получения
        
        Returns:
            Optional[str]: HTML содержимое страницы или None при ошибке
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=self.headers,
                    timeout=self.timeout
                ) as response:
                    if response.status == 200:
                        return await response.text()
                    else:
                        logger.warning(f"HTTP {response.status} для {url}")
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка при получении страницы {url}: {e}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении {url}: {e}")
        return None
    
    async def fetch_page_prefer_browser(self, url: str, wait_time: int = 8) -> Optional[str]:
        """
        Загрузить страницу: через Chromium, если передан selenium_parser, иначе через aiohttp.
        Использование браузера снижает количество блокировок.
        """
        if self.selenium_parser:
            return await self.selenium_parser.fetch_page_selenium(url, wait_time=wait_time)
        return await self.fetch_page(url)
    
    @abstractmethod
    async def parse_listings(self, url: str) -> List[Dict]:
        """
        Парсинг объявлений с сайта.
        
        Args:
            url: URL для парсинга
        
        Returns:
            List[Dict]: Список объявлений
        """
        pass
    
    def extract_price(self, text: str) -> Tuple[Optional[float], Optional[float]]:
        """
        Извлечь цены в BYN и USD из текста.
        
        Args:
            text: Текст для поиска цен
        
        Returns:
            Tuple[Optional[float], Optional[float]]: (цена_BYN, цена_USD)
        """
        price_byn: Optional[float] = None
        price_usd: Optional[float] = None
        
        # Нормализация текста - более агрессивная
        normalized_text = text.replace(',', '').replace('\xa0', ' ').replace('\u2009', ' ').replace('\u00a0', ' ')
        # Убираем множественные пробелы
        normalized_text = ' '.join(normalized_text.split())
        
        # Поиск USD - улучшенные паттерны
        usd_patterns = [
            r'(\d+(?:\s?\d+)*(?:\.\d+)?)\s*\$',  # 500 $ или 500$
            r'\$\s*(\d+(?:\s?\d+)*(?:\.\d+)?)',  # $ 500
            r'(\d+(?:\s?\d+)*(?:\.\d+)?)\s*USD',  # 500 USD
            r'USD\s*(\d+(?:\s?\d+)*(?:\.\d+)?)',  # USD 500
            r'(\d+(?:\s?\d+)*(?:\.\d+)?)\s*долл',  # 500 долл
        ]
        for pattern in usd_patterns:
            usd_match = re.search(pattern, normalized_text, re.IGNORECASE)
            if usd_match:
                try:
                    price_str = usd_match.group(1).replace(' ', '').replace('\xa0', '')
                    price_usd = float(price_str)
                    # Проверяем разумность цены (не больше 10000 для аренды)
                    if price_usd > 0 and price_usd < 10000:
                        break
                except ValueError:
                    continue
        
        # Поиск BYN - улучшенные паттерны
        byn_patterns = [
            r'(\d+(?:\s?\d+)*(?:\.\d+)?)\s*(?:BYN|р\.|руб|бел\.?\s*руб)',  # 500 BYN
            r'(\d+(?:\s?\d+)*(?:\.\d+)?)\s*р/мес',  # 500 р/мес
            r'(\d+(?:\s?\d+)*(?:\.\d+)?)\s*руб/мес',  # 500 руб/мес
        ]
        for pattern in byn_patterns:
            byn_match = re.search(pattern, normalized_text, re.IGNORECASE)
            if byn_match:
                try:
                    price_str = byn_match.group(1).replace(' ', '').replace('\xa0', '')
                    price_byn = float(price_str)
                    # Проверяем разумность цены (не больше 10000 для аренды)
                    if price_byn > 0 and price_byn < 10000:
                        break
                except ValueError:
                    continue
        
        return price_byn, price_usd
    
    def extract_rooms(self, text: str) -> Optional[int]:
        """
        Извлечь количество комнат из текста.
        
        Args:
            text: Текст для поиска
        
        Returns:
            Optional[int]: Количество комнат или None
        """
        # Поиск паттернов: "1-комнатная", "2 комнаты", "3-комн" и т.д.
        patterns = [
            r'(\d+)[-\s]?комнатн',  # 1-комнатная, 2 комнатная
            r'(\d+)[-\s]?комн',  # 1-комн, 2 комн
            r'(\d+)\s*комнат',  # 1 комнат, 2 комнаты
            r'(\d+)\s*к\.',  # 1 к., 2 к.
            r'(\d+)\s*к\b',  # 1к, 2к (отдельное слово)
            r'(\d+)[-\s]?к\.?\s*квартир',  # 1-к квартира, 2к квартира
            r'(\d+)[-\s]?комнатная',  # 1-комнатная (более точный паттерн)
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text.lower())
            if match:
                try:
                    rooms = int(match.group(1))
                    # Проверяем разумность (1-10 комнат)
                    if 1 <= rooms <= 10:
                        return rooms
                except ValueError:
                    continue
        
        return None
