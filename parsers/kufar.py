"""Парсер для Kufar.by."""
import re
import hashlib
import logging
from typing import List, Dict, Optional
from bs4 import BeautifulSoup

from .base import BaseParser
from config import settings

logger = logging.getLogger(__name__)


class KufarParser(BaseParser):
    """Парсер для Kufar.by."""
    
    async def parse_listings(self, url: str) -> List[Dict]:
        """
        Парсинг объявлений с Kufar.
        
        Args:
            url: Базовый URL Kufar
        
        Returns:
            List[Dict]: Список объявлений
        """
        # Добавляем параметры для аренды квартир в Минске
        search_url = f"{url}listings?cat=1010&sort=lst.d&cur=USD&rgn=7&prc=r%3A0%2C1000"
        
        html = await self.fetch_page(search_url)
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'lxml')
        listings = []
        
        # Kufar использует структуру с data-id
        listing_containers = soup.find_all(
            ['div', 'article'],
            attrs={'data-id': True}
        )
        
        # Альтернативный поиск по классам
        if not listing_containers:
            listing_containers = soup.find_all(
                'div',
                class_=re.compile(r'styles_item|listing|ad')
            )
        
        # Поиск по ссылкам
        if not listing_containers:
            links = soup.find_all('a', href=re.compile(r'/v/'))
            for link in links[:settings.max_listings_per_source]:
                listing_data = await self._parse_listing_from_link(link, url)
                if listing_data:
                    listings.append(listing_data)
        else:
            for container in listing_containers[:settings.max_listings_per_source]:
                listing_data = self._parse_listing_from_container(container, url)
                if listing_data:
                    listings.append(listing_data)
        
        return listings
    
    async def _parse_listing_from_link(
        self,
        link_element,
        base_url: str
    ) -> Optional[Dict]:
        """Парсинг объявления из ссылки."""
        try:
            href = link_element.get('href', '')
            if not href.startswith('http'):
                href = 'https://re.kufar.by' + href
            
            parent = link_element.find_parent(['div', 'article', 'li'])
            if not parent:
                return None
            
            text = parent.get_text(' ', strip=True)
            
            address = self._extract_address(text, parent)
            rooms = self.extract_rooms(text) or self.extract_rooms(str(parent))
            price_byn, price_usd = self.extract_price(text)
            landlord = self._extract_landlord(text)
            
            listing_id = hashlib.md5(href.encode()).hexdigest()
            
            return {
                'listing_id': listing_id,
                'source': 'Kufar',
                'address': address or 'Адрес не указан',
                'rooms': rooms,
                'price_byn': price_byn,
                'price_usd': price_usd,
                'landlord': landlord,
                'url': href
            }
        except Exception as e:
            logger.error(f"Ошибка парсинга объявления Kufar: {e}")
            return None
    
    def _parse_listing_from_container(
        self,
        container,
        base_url: str
    ) -> Optional[Dict]:
        """Парсинг объявления из контейнера."""
        try:
            text = container.get_text(' ', strip=True)
            
            link = container.find('a', href=re.compile(r'/v/'))
            href = link.get('href', '') if link else ''
            if href and not href.startswith('http'):
                href = 'https://re.kufar.by' + href
            
            address = self._extract_address(text, container)
            rooms = self.extract_rooms(text)
            price_byn, price_usd = self.extract_price(text)
            landlord = self._extract_landlord(text)
            
            listing_id = hashlib.md5((href or text[:100]).encode()).hexdigest()
            
            return {
                'listing_id': listing_id,
                'source': 'Kufar',
                'address': address or 'Адрес не указан',
                'rooms': rooms,
                'price_byn': price_byn,
                'price_usd': price_usd,
                'landlord': landlord,
                'url': href or base_url
            }
        except Exception as e:
            logger.error(f"Ошибка парсинга контейнера Kufar: {e}")
            return None
    
    def _extract_address(self, text: str, element) -> str:
        """Извлечь адрес."""
        address_pattern = re.compile(
            r'Минск[,\s]+(?:ул\.|улица|пр\.|проспект|пер\.|переулок|бул\.|бульвар)?\s*([А-Яа-я\s\d,.-]+)'
        )
        match = address_pattern.search(text)
        if match:
            return f"Минск, {match.group(1).strip()}"
        
        if hasattr(element, 'get'):
            address_attr = element.get('data-address') or element.get('data-location')
            if address_attr:
                return address_attr
        
        return ""
    
    def _extract_landlord(self, text: str) -> str:
        """Извлечь тип арендодателя."""
        text_lower = text.lower()
        if any(keyword in text_lower for keyword in ['собственник', 'без посредников']):
            return "Собственник"
        return "Агентство"
