"""Сервис для работы с объявлениями."""
import logging
from typing import List, Dict

from parsers import OnlinerParser, KufarParser, RealtParser
from filters import ListingFilter
from database import Database
from config import settings

logger = logging.getLogger(__name__)


class ListingService:
    """Сервис для получения и фильтрации объявлений."""
    
    def __init__(self, db: Database) -> None:
        """
        Инициализация сервиса.
        
        Args:
            db: Экземпляр базы данных
        """
        self.db = db
        self.onliner_parser = OnlinerParser()
        self.kufar_parser = KufarParser()
        self.realt_parser = RealtParser()
    
    async def fetch_and_filter_listings(
        self,
        filter_obj: ListingFilter,
        user_id: int
    ) -> List[Dict]:
        """
        Получить и отфильтровать объявления.
        
        Args:
            filter_obj: Объект фильтра
            user_id: ID пользователя
        
        Returns:
            List[Dict]: Список новых отфильтрованных объявлений
        """
        all_listings: List[Dict] = []
        
        # Парсинг с разных сайтов
        sources = filter_obj.filters.get('sources', [])
        
        if 'Onliner' in sources:
            try:
                listings = await self.onliner_parser.parse_listings(settings.onliner_url)
                all_listings.extend(listings)
                logger.info(f"Получено {len(listings)} объявлений с Onliner")
            except Exception as e:
                logger.error(f"Ошибка парсинга Onliner: {e}")
        
        if 'Kufar' in sources:
            try:
                listings = await self.kufar_parser.parse_listings(settings.kufar_url)
                all_listings.extend(listings)
                logger.info(f"Получено {len(listings)} объявлений с Kufar")
            except Exception as e:
                logger.error(f"Ошибка парсинга Kufar: {e}")
        
        if 'Realt.by' in sources:
            try:
                listings = await self.realt_parser.parse_listings(settings.realt_url)
                all_listings.extend(listings)
                logger.info(f"Получено {len(listings)} объявлений с Realt.by")
            except Exception as e:
                logger.error(f"Ошибка парсинга Realt.by: {e}")
        
        # Фильтрация и проверка на новые объявления
        filtered_listings: List[Dict] = []
        for listing in all_listings:
            if filter_obj.matches(listing):
                # Проверяем, новое ли это объявление
                is_new = self.db.add_listing(
                    listing['listing_id'],
                    listing['source'],
                    listing['address'],
                    listing.get('rooms'),
                    listing.get('price_byn', 0),
                    listing.get('price_usd', 0),
                    listing.get('landlord', ''),
                    listing['url']
                )
                if is_new and not self.db.is_listing_sent_to_user(
                    listing['listing_id'],
                    user_id
                ):
                    filtered_listings.append(listing)
        
        logger.info(
            f"Найдено {len(filtered_listings)} новых объявлений "
            f"для пользователя {user_id}"
        )
        
        return filtered_listings
