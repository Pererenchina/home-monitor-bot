"""Парсер для Onliner.by."""
import re
import hashlib
import logging
from typing import List, Dict, Optional
from bs4 import BeautifulSoup

from .base import BaseParser
from .selenium_base import SeleniumBaseParser
from config import settings

logger = logging.getLogger(__name__)


class OnlinerParser(BaseParser):
    """Парсер для Onliner.by с использованием Chromium (общий браузер при передаче selenium_parser)."""
    
    def __init__(self, selenium_parser=None):
        """Инициализация парсера. Если передан selenium_parser — используется общий Chromium."""
        BaseParser.__init__(self, selenium_parser=selenium_parser)
        self.selenium_parser = selenium_parser or SeleniumBaseParser(shared=True)
        self._own_selenium = selenium_parser is None
    
    def __del__(self):
        """Деструктор — закрываем драйвер только если создавали сами."""
        if getattr(self, '_own_selenium', True) and hasattr(self, 'selenium_parser'):
            self.selenium_parser.close()
    
    async def parse_listings(self, url: str) -> List[Dict]:
        """
        Парсинг объявлений с Onliner.
        
        Args:
            url: URL страницы Onliner
        
        Returns:
            List[Dict]: Список объявлений
        """
        # Используем Selenium для получения HTML (динамическая загрузка)
        html = await self.selenium_parser.fetch_page_selenium(url, wait_time=10)
        if not html:
            # Пробуем обычный метод как fallback
            html = await self.fetch_page(url)
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'lxml')
        listings = []
        
        # Поиск объявлений на странице - Onliner использует класс "classified"
        # Но также можно искать по ссылкам напрямую
        listing_containers = soup.find_all('a', class_=re.compile(r'classified'))
        
        # Если не найдено, ищем по ссылкам на объявления
        if not listing_containers:
            # Ищем все ссылки на объявления, исключая служебные
            links = soup.find_all('a', href=re.compile(r'/ak/apartments/'))
            # Фильтруем ссылки - исключаем /create, /edit и другие служебные
            valid_links = [
                link for link in links 
                if link.get('href') and 
                '/create' not in link.get('href', '') and
                '/edit' not in link.get('href', '') and
                '/delete' not in link.get('href', '')
            ]
            for link in valid_links[:settings.max_listings_per_source]:
                listing_data = await self._parse_listing_from_link(link, url)
                if listing_data:
                    listings.append(listing_data)
        
        # Если нашли контейнеры, парсим их
        if listing_containers:
            for container in listing_containers[:settings.max_listings_per_source]:
                listing_data = await self._parse_listing_from_container(container, url)
                if listing_data:
                    listings.append(listing_data)
        
        # Если все еще не найдено, ищем по другим классам
        if not listing_containers and not listings:
            # Ищем все ссылки на объявления, исключая служебные
            links = soup.find_all('a', href=re.compile(r'/ak/apartments/'))
            # Фильтруем ссылки - исключаем /create, /edit и другие служебные
            valid_links = [
                link for link in links 
                if link.get('href') and 
                '/create' not in link.get('href', '') and
                '/edit' not in link.get('href', '') and
                '/delete' not in link.get('href', '')
            ]
            for link in valid_links[:settings.max_listings_per_source]:
                listing_data = await self._parse_listing_from_link(link, url)
                if listing_data:
                    listings.append(listing_data)
        else:
            for container in listing_containers[:settings.max_listings_per_source]:
                listing_data = await self._parse_listing_from_container(container, url)
                if listing_data:
                    listings.append(listing_data)
        
        # Если все еще нет объявлений, пробуем более агрессивный поиск
        if not listings:
            # Ищем любые ссылки, содержащие /ak/apartments/ с ID
            all_links = soup.find_all('a', href=True)
            for link in all_links:
                href = link.get('href', '')
                # Ищем ссылки вида /ak/apartments/123456 или подобные
                if '/ak/apartments/' in href and '/create' not in href:
                    # Проверяем, что после /apartments/ есть что-то похожее на ID
                    parts = href.split('/ak/apartments/')
                    if len(parts) > 1 and parts[1].split('/')[0].split('?')[0]:
                        listing_data = await self._parse_listing_from_link(link, url)
                        if listing_data and listing_data not in listings:
                            listings.append(listing_data)
                            if len(listings) >= settings.max_listings_per_source:
                                break
        
        return listings
    
    async def _parse_listing_from_link(
        self,
        link_element,
        base_url: str
    ) -> Optional[Dict]:
        """
        Парсинг объявления из ссылки.
        
        Args:
            link_element: Элемент ссылки BeautifulSoup
            base_url: Базовый URL
        
        Returns:
            Optional[Dict]: Данные объявления или None
        """
        try:
            href = link_element.get('href', '')
            if href:
                if not href.startswith('http'):
                    # Убираем дублирующие слеши
                    href = href.lstrip('/')
                    href = 'https://r.onliner.by/' + href
                # Убираем лишние параметры, оставляем только путь к объявлению
                if '/ak/apartments/' in href:
                    parts = href.split('/ak/apartments/')
                    if len(parts) > 1:
                        listing_path = parts[1].split('?')[0].split('#')[0]
                        href = f'https://r.onliner.by/ak/apartments/{listing_path}'
            else:
                return None
            
            # Пробуем загрузить страницу объявления для более точных данных
            listing_html = await self.selenium_parser.fetch_page_selenium(href, wait_time=8)
            if listing_html:
                listing_soup = BeautifulSoup(listing_html, 'lxml')
                text = listing_soup.get_text(' ', strip=True)
                
                # Извлекаем данные из страницы
                address = self._extract_address(text, listing_soup)
                rooms = None
                price_byn, price_usd = None, None
                landlord = None
                
                # Ищем комнаты в специальных элементах Onliner
                rooms_elems = listing_soup.find_all(class_=re.compile(r'apartment-info__item|classified__param|rooms|room'))
                for room_elem in rooms_elems:
                    room_text = room_elem.get_text(' ', strip=True)
                    rooms = self.extract_rooms(room_text)
                    if rooms:
                        break
                
                # Если не нашли, ищем в title
                if rooms is None:
                    title_elem = listing_soup.find('title')
                    if title_elem:
                        title_text = title_elem.get_text(' ', strip=True)
                        rooms = self.extract_rooms(title_text)
                
                # Если не нашли, ищем в тексте
                if rooms is None:
                    rooms = self.extract_rooms(text)
                
                # Ищем цену
                price_elems = listing_soup.find_all(class_=re.compile(r'apartment-info__item|classified__price|price'))
                for price_elem in price_elems:
                    price_text = price_elem.get_text(' ', strip=True)
                    price_byn, price_usd = self.extract_price(price_text)
                    if price_usd or price_byn:
                        break
                
                if not price_usd and not price_byn:
                    price_byn, price_usd = self.extract_price(text)
                
                # Onliner хранит цены в BYN в копейках - конвертируем в рубли
                if price_byn is not None and price_byn > 0:
                    # Проверяем соотношение с USD для определения формата
                    if price_usd and price_usd > 0:
                        ratio = price_byn / price_usd
                        # Если соотношение больше 10, вероятно цена в копейках
                        if ratio > 10:
                            price_byn = price_byn / 100
                    elif price_byn > 10000:
                        # Если цена очень большая и нет USD, вероятно в копейках
                        price_byn = price_byn / 100
                
                # Ищем арендодателя
                landlord_elems = listing_soup.find_all(class_=re.compile(r'classified__figure|owner|landlord|agent'))
                for landlord_elem in landlord_elems:
                    classes = landlord_elem.get('class', [])
                    if isinstance(classes, list):
                        if 'classified__figure_agent' in classes:
                            landlord = "Агентство"
                            break
                        else:
                            landlord_text = landlord_elem.get_text(' ', strip=True)
                            landlord = self._extract_landlord(landlord_text)
                            if landlord:
                                break
                
                if not landlord:
                    landlord = self._extract_landlord(text)
            else:
                # Fallback - используем данные из родительского элемента
                parent = link_element.find_parent(['div', 'article', 'li'])
                if not parent:
                    return None
                
                text = parent.get_text(' ', strip=True)
                
                address = self._extract_address(text, parent)
                rooms = self.extract_rooms(text) or self.extract_rooms(str(parent))
                price_byn, price_usd = self.extract_price(text)
                # Onliner хранит цены в BYN в копейках - конвертируем в рубли
                if price_byn is not None and price_byn > 0:
                    # Проверяем соотношение с USD для определения формата
                    if price_usd and price_usd > 0:
                        ratio = price_byn / price_usd
                        # Если соотношение больше 10, вероятно цена в копейках
                        if ratio > 10:
                            price_byn = price_byn / 100
                    elif price_byn > 10000:
                        # Если цена очень большая и нет USD, вероятно в копейках
                        price_byn = price_byn / 100
                landlord = self._extract_landlord(text)
            
            listing_id = hashlib.md5(href.encode()).hexdigest()
            
            # Если адрес не содержит "Минск", добавляем его
            if address and 'минск' not in address.lower():
                # Если адрес начинается с улицы, добавляем "Минск, "
                if address and len(address) > 3:
                    address = f"Минск, {address}"
                elif not address or address == 'Адрес не указан':
                    address = "Минск"
            
            return {
                'listing_id': listing_id,
                'source': 'Onliner',
                'address': address or 'Минск',
                'rooms': rooms,
                'price_byn': price_byn,
                'price_usd': price_usd,
                'landlord': landlord,
                'url': href
            }
        except Exception as e:
            logger.error(f"Ошибка парсинга объявления Onliner: {e}")
            return None
    
    async def _parse_listing_from_container(
        self,
        container,
        base_url: str
    ) -> Optional[Dict]:
        """
        Парсинг объявления из контейнера.
        
        Args:
            container: Контейнер BeautifulSoup
            base_url: Базовый URL
        
        Returns:
            Optional[Dict]: Данные объявления или None
        """
        try:
            # Если контейнер - это ссылка с классом 'classified', используем её напрямую
            if container.name == 'a' and 'classified' in container.get('class', []):
                href = container.get('href', '')
            else:
                text = container.get_text(' ', strip=True)
                
                # Улучшенный поиск ссылки на объявление
                href = ''
                
                # 1. Ищем прямую ссылку в контейнере
                link = container.find('a', href=re.compile(r'/ak/apartments/'))
                if link:
                    href = link.get('href', '')
                
                # 2. Если не нашли, ищем в дочерних элементах
                if not href:
                    links = container.find_all('a', href=re.compile(r'/ak/apartments/'))
                    if links:
                        href = links[0].get('href', '')
                
                # 3. Если не нашли, ищем data-атрибуты с URL
                if not href:
                    data_url = container.get('data-url') or container.get('data-href')
                    if data_url:
                        href = data_url
                
                # 4. Если не нашли, ищем в родительском элементе
                if not href:
                    parent = container.find_parent(['div', 'article', 'li'])
                    if parent:
                        parent_link = parent.find('a', href=re.compile(r'/ak/apartments/'))
                        if parent_link:
                            href = parent_link.get('href', '')
            
            # Формируем полный URL
            if href:
                if not href.startswith('http'):
                    # Убираем дублирующие слеши
                    href = href.lstrip('/')
                    href = 'https://r.onliner.by/' + href
                # Убираем лишние параметры и фрагменты, оставляем только путь к объявлению
                if '/ak/apartments/' in href:
                    # Берем только путь до объявления
                    parts = href.split('/ak/apartments/')
                    if len(parts) > 1:
                        listing_path = parts[1].split('?')[0].split('#')[0]
                        href = f'https://r.onliner.by/ak/apartments/{listing_path}'
            
            # Если ссылка все еще не найдена, пропускаем это объявление
            if not href or href == base_url or '/ak/apartments/' not in href:
                return None
            
            # Загружаем страницу объявления через Chromium (меньше блокировок)
            listing_html = await self.fetch_page_prefer_browser(href, wait_time=8)
            if listing_html:
                listing_soup = BeautifulSoup(listing_html, 'lxml')
                
                # Извлекаем цену из apartment-bar__price-value
                price_byn, price_usd = None, None
                price_usd_elem = listing_soup.find('span', class_='apartment-bar__price-value_complementary')
                if price_usd_elem:
                    price_usd_text = price_usd_elem.get_text(' ', strip=True)
                    _, price_usd = self.extract_price(price_usd_text)
                
                price_byn_elem = listing_soup.find('span', class_='apartment-bar__price-value_primary')
                if price_byn_elem:
                    price_byn_text = price_byn_elem.get_text(' ', strip=True)
                    price_byn, _ = self.extract_price(price_byn_text)
                    # Onliner хранит цены в BYN в копейках - конвертируем в рубли
                    if price_byn is not None and price_byn > 0:
                        # Проверяем соотношение с USD для определения формата
                        if price_usd and price_usd > 0:
                            ratio = price_byn / price_usd
                            # Если соотношение больше 10, вероятно цена в копейках
                            if ratio > 10:
                                price_byn = price_byn / 100
                        elif price_byn > 10000:
                            # Если цена очень большая и нет USD, вероятно в копейках
                            price_byn = price_byn / 100
                
                # Извлекаем комнаты из apartment-bar__value
                rooms = None
                bar_values = listing_soup.find_all('span', class_='apartment-bar__value')
                for bar_value in bar_values:
                    value_text = bar_value.get_text(' ', strip=True)
                    if 'комнатн' in value_text.lower() or 'комн' in value_text.lower():
                        rooms = self.extract_rooms(value_text)
                        if rooms is not None:
                            break
                
                # Извлекаем арендодателя из apartment-bar__value
                landlord = "Агентство"
                for bar_value in bar_values:
                    value_text = bar_value.get_text(' ', strip=True)
                    if 'собственник' in value_text.lower():
                        landlord = "Собственник"
                        break
                    elif 'агентство' in value_text.lower() or 'агент' in value_text.lower():
                        landlord = "Агентство"
                        break
                
                # Извлекаем адрес из apartment-info__sub-line_large
                address = ''
                address_elem = listing_soup.find('div', class_='apartment-info__sub-line_large')
                if address_elem:
                    address = address_elem.get_text(' ', strip=True)
                
                if not address:
                    address = self._extract_address(listing_soup.get_text(' ', strip=True), listing_soup)
            else:
                # Если не удалось загрузить страницу, используем данные из контейнера
                text = container.get_text(' ', strip=True)
                
                # Улучшенное извлечение цены - Onliner использует classified__price-value
                price_byn, price_usd = None, None
                price_elements = container.find_all(class_=re.compile(r'classified__price-value|price'))
                for price_elem in price_elements:
                    price_text = price_elem.get_text(' ', strip=True)
                    # Проверяем наличие валюты в родительском элементе
                    parent_price = price_elem.find_parent(class_=re.compile(r'classified__price'))
                    if parent_price:
                        parent_text = parent_price.get_text(' ', strip=True)
                        price_byn, price_usd = self.extract_price(parent_text)
                    else:
                        price_byn, price_usd = self.extract_price(price_text)
                    if price_usd or price_byn:
                        break
                
                # Если не нашли цену в специальных элементах, парсим весь текст
                if not price_usd and not price_byn:
                    price_byn, price_usd = self.extract_price(text)
                
                # Onliner хранит цены в BYN в копейках - конвертируем в рубли
                if price_byn is not None and price_byn > 0:
                    # Проверяем соотношение с USD для определения формата
                    if price_usd and price_usd > 0:
                        ratio = price_byn / price_usd
                        # Если соотношение больше 10, вероятно цена в копейках
                        if ratio > 10:
                            price_byn = price_byn / 100
                    elif price_byn > 10000:
                        # Если цена очень большая и нет USD, вероятно в копейках
                        price_byn = price_byn / 100
                
                # Улучшенное извлечение адреса - ищем в специальных элементах
                address = ''
                address_elem = container.find(class_=re.compile(r'classified__location|address|location'))
                if address_elem:
                    address = address_elem.get_text(' ', strip=True)
                
                if not address:
                    address = self._extract_address(text, container)
                
                # Улучшенное извлечение комнат - ищем в тексте и специальных элементах
                rooms = None
                rooms_elem = container.find(class_=re.compile(r'classified__param|rooms|room|classified__caption-item_type'))
                if rooms_elem:
                    rooms_text = rooms_elem.get_text(' ', strip=True)
                    rooms = self.extract_rooms(rooms_text)
                
                if rooms is None:
                    rooms = self.extract_rooms(text)
                
                # Улучшенное извлечение арендодателя - проверяем класс classified__figure_agent
                landlord = None
                figure_elem = container.find(class_=re.compile(r'classified__figure'))
                if figure_elem:
                    # Если есть класс classified__figure_agent, значит это агентство
                    # Если нет - возможно собственник
                    classes = figure_elem.get('class', [])
                    if isinstance(classes, list):
                        if 'classified__figure_agent' in classes:
                            landlord = "Агентство"
                        else:
                            # Нет класса agent - возможно собственник, проверяем текст
                            landlord = self._extract_landlord(text)
                    else:
                        landlord = self._extract_landlord(text)
                else:
                    landlord = self._extract_landlord(text)
                
                # Если не определили, по умолчанию считаем собственником
                if not landlord:
                    landlord = "Собственник"
            
            listing_id = hashlib.md5(href.encode()).hexdigest()
            
            # Если адрес не содержит "Минск", добавляем его
            if address and 'минск' not in address.lower():
                # Если адрес начинается с улицы, добавляем "Минск, "
                if address and len(address) > 3:
                    address = f"Минск, {address}"
                elif not address or address == 'Адрес не указан':
                    address = "Минск"
            
            return {
                'listing_id': listing_id,
                'source': 'Onliner',
                'address': address or 'Минск',
                'rooms': rooms,
                'price_byn': price_byn,
                'price_usd': price_usd,
                'landlord': landlord,
                'url': href
            }
        except Exception as e:
            logger.error(f"Ошибка парсинга контейнера Onliner: {e}")
            return None
    
    def _extract_address(self, text: str, element) -> str:
        """
        Извлечь адрес из текста или элемента.
        
        Args:
            text: Текст для поиска
            element: Элемент BeautifulSoup
        
        Returns:
            str: Адрес или пустая строка
        """
        # Поиск адреса в тексте (Минск, улица...)
        address_patterns = [
            r'Минск[,\s]+(?:ул\.|улица|пр\.|проспект|пер\.|переулок|бул\.|бульвар)?\s*([А-Яа-я\s\d,.-]+)',
            r'Минск[,\s]+([А-Яа-я\s\d,.-]{3,})',  # Более общий паттерн
            r'г\.?\s*Минск[,\s]+([А-Яа-я\s\d,.-]+)',
        ]
        
        for pattern in address_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                address_part = match.group(1).strip()
                # Ограничиваем длину адреса
                if len(address_part) > 100:
                    address_part = address_part[:100]
                return f"Минск, {address_part}"
        
        # Попробуем найти через data-атрибуты
        if hasattr(element, 'get'):
            address_attr = element.get('data-address') or element.get('data-location') or element.get('data-addr')
            if address_attr:
                return address_attr
        
        # Если просто упоминается Минск, возвращаем базовый адрес
        if 'минск' in text.lower():
            # Пытаемся найти что-то после Минска
            minsk_match = re.search(r'минск[,\s]+([а-яё\s\d,.-]{5,50})', text.lower())
            if minsk_match:
                return f"Минск, {minsk_match.group(1).strip().title()}"
            return "Минск"
        
        return ""
    
    def _extract_landlord(self, text: str) -> str:
        """
        Извлечь тип арендодателя из текста.
        
        Args:
            text: Текст для анализа
        
        Returns:
            str: "Собственник" или "Агентство"
        """
        text_lower = text.lower()
        if any(keyword in text_lower for keyword in [
            'собственник', 'от собственника', 'без посредников',
            'напрямую от собственника', 'хозяин', 'владелец',
            'от хозяина', 'напрямую', 'без агентств'
        ]):
            return "Собственник"
        return "Агентство"
