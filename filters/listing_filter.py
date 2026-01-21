"""Фильтрация объявлений."""
from typing import Dict, Optional, List


def get_default_filters() -> Dict:
    """
    Получить фильтры по умолчанию.
    
    Returns:
        Dict: Словарь с фильтрами по умолчанию
    """
    return {
        'rooms': None,
        'min_price_usd': None,
        'max_price_usd': None,
        'landlord': None,
        'city': None
    }


class ListingFilter:
    """Класс для фильтрации объявлений по заданным критериям."""
    
    def __init__(self, filters: Dict) -> None:
        """
        Инициализация фильтра.
        
        Args:
            filters: Словарь с параметрами фильтрации
        """
        self.filters = filters
    
    def matches(self, listing: Dict) -> bool:
        """
        Проверить, соответствует ли объявление фильтрам.
        
        Args:
            listing: Словарь с данными объявления
        
        Returns:
            bool: True если объявление соответствует всем фильтрам
        """
        # Фильтр по количеству комнат (обязательный)
        if 'rooms' in self.filters and self.filters['rooms'] is not None:
            listing_rooms = listing.get('rooms')
            if listing_rooms != self.filters['rooms']:
                return False
        
        # Фильтр по минимальной цене (USD) - более мягкий
        if 'min_price_usd' in self.filters and self.filters['min_price_usd'] is not None:
            listing_price = listing.get('price_usd')
            # Если цена не указана, пропускаем фильтр (может быть указана в BYN)
            if listing_price is not None and listing_price < self.filters['min_price_usd']:
                return False
        
        # Фильтр по максимальной цене (USD) - более мягкий
        if 'max_price_usd' in self.filters and self.filters['max_price_usd'] is not None:
            listing_price = listing.get('price_usd')
            # Если цена не указана, пропускаем фильтр (может быть указана в BYN)
            if listing_price is not None and listing_price > self.filters['max_price_usd']:
                return False
        
        # Фильтр по типу арендодателя (обязательный)
        if 'landlord' in self.filters and self.filters['landlord'] is not None:
            listing_landlord = listing.get('landlord', '').lower()
            filter_landlord = self.filters['landlord'].lower()
            if listing_landlord != filter_landlord:
                return False
        
        # Фильтр по городу (более мягкий - если адрес не указан, пропускаем)
        if 'city' in self.filters and self.filters['city'] is not None:
            address = listing.get('address', '').lower()
            city = self.filters['city'].lower()
            # Если адрес не указан или "адрес не указан", пропускаем фильтр по городу
            if not address or 'адрес не указан' in address:
                # Пропускаем фильтр по городу, если адрес не указан
                pass
            elif city not in address:
                return False
        
        return True
