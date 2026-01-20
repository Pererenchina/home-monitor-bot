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
        'sources': ['Onliner', 'Kufar', 'Realt.by'],
        'address_keywords': []
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
        # Фильтр по количеству комнат
        if 'rooms' in self.filters and self.filters['rooms'] is not None:
            if listing.get('rooms') != self.filters['rooms']:
                return False
        
        # Фильтр по минимальной цене (USD)
        if 'min_price_usd' in self.filters and self.filters['min_price_usd'] is not None:
            listing_price = listing.get('price_usd')
            if listing_price is None or listing_price < self.filters['min_price_usd']:
                return False
        
        # Фильтр по максимальной цене (USD)
        if 'max_price_usd' in self.filters and self.filters['max_price_usd'] is not None:
            listing_price = listing.get('price_usd')
            if listing_price is None or listing_price > self.filters['max_price_usd']:
                return False
        
        # Фильтр по типу арендодателя
        if 'landlord' in self.filters and self.filters['landlord'] is not None:
            listing_landlord = listing.get('landlord', '').lower()
            filter_landlord = self.filters['landlord'].lower()
            if listing_landlord != filter_landlord:
                return False
        
        # Фильтр по источникам
        if 'sources' in self.filters and self.filters['sources']:
            listing_source = listing.get('source', '')
            if listing_source not in self.filters['sources']:
                return False
        
        # Фильтр по району/адресу (поиск подстроки)
        if 'address_keywords' in self.filters and self.filters['address_keywords']:
            address = listing.get('address', '').lower()
            keywords = [kw.lower() for kw in self.filters['address_keywords']]
            if not any(keyword in address for keyword in keywords):
                return False
        
        return True
