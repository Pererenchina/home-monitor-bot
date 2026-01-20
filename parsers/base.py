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
    
    def __init__(self) -> None:
        """Инициализация парсера."""
        self.headers = {
            'User-Agent': settings.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        }
        self.timeout = aiohttp.ClientTimeout(total=settings.http_timeout)
    
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
        
        # Нормализация текста
        normalized_text = text.replace(',', '').replace('\xa0', ' ')
        
        # Поиск USD
        usd_pattern = r'(\d+(?:\s?\d+)*(?:\.\d+)?)\s*\$'
        usd_match = re.search(usd_pattern, normalized_text)
        if usd_match:
            try:
                price_usd = float(usd_match.group(1).replace(' ', ''))
            except ValueError:
                logger.debug(f"Не удалось распарсить USD цену: {usd_match.group(1)}")
        
        # Поиск BYN
        byn_pattern = r'(\d+(?:\s?\d+)*(?:\.\d+)?)\s*(?:BYN|р\.|руб|бел\.?\s*руб)'
        byn_match = re.search(byn_pattern, normalized_text, re.IGNORECASE)
        if byn_match:
            try:
                price_byn = float(byn_match.group(1).replace(' ', ''))
            except ValueError:
                logger.debug(f"Не удалось распарсить BYN цену: {byn_match.group(1)}")
        
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
            r'(\d+)[-\s]?комнатн',
            r'(\d+)[-\s]?комн',
            r'(\d+)\s*комнат',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text.lower())
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    continue
        
        return None
