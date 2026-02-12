"""Парсер для Realt.by."""
import re
import hashlib
import logging
from typing import List, Dict, Optional
from bs4 import BeautifulSoup

from .base import BaseParser
from config import settings

logger = logging.getLogger(__name__)


class RealtParser(BaseParser):
    """Парсер для Realt.by (загрузка через Chromium при передаче selenium_parser)."""
    
    def __init__(self, selenium_parser=None):
        super().__init__(selenium_parser=selenium_parser)
    
    async def parse_listings(self, url: str) -> List[Dict]:
        """
        Парсинг объявлений с Realt.by.
        
        Args:
            url: Базовый URL Realt.by
        
        Returns:
            List[Dict]: Список объявлений
        """
        # URL для аренды квартир в Минске
        search_url = f"{url}rent/flat/minsk"
        
        html = await self.fetch_page_prefer_browser(search_url, wait_time=10)
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'lxml')
        listings = []
        
        # Поиск объявлений
        listing_containers = soup.find_all(
            ['div', 'article'],
            class_=re.compile(r'object|listing|offer|ad')
        )
        
        if not listing_containers:
            listing_containers = soup.find_all('div', attrs={'data-id': True})
        
        if not listing_containers:
            # Ищем ссылки на конкретные объявления (исключаем категории)
            # Realt использует формат /rent-flat-for-long/object/3105399/ или /object/3105399/
            links = soup.find_all('a', href=re.compile(r'/object/\d+|/rent-flat-for-long/object/\d+'))
            # Если не нашли по паттерну с ID, ищем любые ссылки на объекты
            if not links:
                all_links = soup.find_all('a', href=re.compile(r'/object/|/rent-flat-for-long/object/'))
                # Фильтруем категории и служебные ссылки - ищем только ссылки с ID объекта
                links = [
                    l for l in all_links 
                    if l.get('href') and
                    '/object/' in l.get('href', '') and  # Должна быть /object/
                    re.search(r'/object/\d+', l.get('href', '')) and  # Должен быть ID после /object/
                    '/rent/flat-for-long/' not in l.get('href', '') and  # Исключаем категории без ID
                    '/rent/offices/' not in l.get('href', '') and  # Исключаем офисы
                    '/rent/flat-for-long/' != l.get('href', '').rstrip('/') and  # Исключаем саму категорию
                    l.get('href', '').rstrip('/') not in ['/rent/flat-for-long', '/rent/offices']  # Исключаем категории
                ]
            
            # Дополнительная фильтрация: исключаем категории
            links = [
                l for l in links
                if l.get('href') and
                l.get('href', '').rstrip('/') not in [
                    'https://realt.by/rent/flat-for-long',
                    'https://realt.by/rent/flat-for-long/',
                    'https://realt.by/rent/offices',
                    'https://realt.by/rent/offices/',
                    '/rent/flat-for-long',
                    '/rent/flat-for-long/',
                    '/rent/offices',
                    '/rent/offices/'
                ] and
                not l.get('href', '').endswith('/rent/flat-for-long') and
                not l.get('href', '').endswith('/rent/flat-for-long/') and
                not l.get('href', '').endswith('/rent/offices') and
                not l.get('href', '').endswith('/rent/offices/')
            ]
            
            for link in links[:settings.max_listings_per_source]:
                listing_data = await self._parse_listing_from_link(link, url)
                if listing_data:
                    listings.append(listing_data)
        else:
            for container in listing_containers[:settings.max_listings_per_source]:
                listing_data = self._parse_listing_from_container(container, url)
                if listing_data:
                    listings.append(listing_data)
        
        # Если все еще нет объявлений, пробуем более широкий поиск
        if not listings:
            all_links = soup.find_all('a', href=True)
            for link in all_links:
                href = link.get('href', '')
                # Ищем ссылки с ID объекта (исключаем категории)
                if '/object/' in href and re.search(r'/object/\d+', href) and href != url:
                    # Проверяем, что это не категория
                    href_clean = href.rstrip('/')
                    if (href_clean not in [
                        'https://realt.by/rent/flat-for-long',
                        'https://realt.by/rent/flat-for-long/',
                        'https://realt.by/rent/offices',
                        'https://realt.by/rent/offices/',
                        '/rent/flat-for-long',
                        '/rent/flat-for-long/',
                        '/rent/offices',
                        '/rent/offices/'
                    ] and
                    not href.endswith('/rent/flat-for-long') and
                    not href.endswith('/rent/flat-for-long/') and
                    not href.endswith('/rent/offices') and
                    not href.endswith('/rent/offices/') and
                    '/rent/flat-for-long/' not in href and
                    '/rent/offices/' not in href):
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
        """Парсинг объявления из ссылки."""
        try:
            href = link_element.get('href', '')
            if href:
                if not href.startswith('http'):
                    href = href.lstrip('/')
                    href = 'https://realt.by/' + href
                # Убираем лишние параметры
                if '?' in href:
                    href = href.split('?')[0]
                if '#' in href:
                    href = href.split('#')[0]
            else:
                return None
            
            # Проверяем, что это конкретное объявление, а не категория
            if '/object/' not in href:
                return None
            
            # Проверяем, что есть ID объекта в URL
            if not re.search(r'/object/\d+', href):
                return None
            
            # Исключаем категории
            if href.rstrip('/') in ['https://realt.by/rent/flat-for-long', 'https://realt.by/rent/flat-for-long/']:
                return None
            if '/rent/offices/' in href:
                return None
            
            # Загружаем страницу объявления через Chromium (меньше блокировок)
            listing_html = await self.fetch_page_prefer_browser(href, wait_time=8)
            if listing_html:
                listing_soup = BeautifulSoup(listing_html, 'lxml')
                text = listing_soup.get_text(' ', strip=True)
                
                # Инициализируем переменные
                rooms = None
                address = None
                price_byn, price_usd = None, None
                landlord = None
                
                # Извлекаем данные из title (Realt часто использует title для основных данных)
                title_elem = listing_soup.find('title')
                if title_elem:
                    title_text = title_elem.get_text(' ', strip=True)
                    # Из title: "Снять 1-комнатную квартиру г. Минск ул. Репина 4"
                    rooms = self.extract_rooms(title_text)
                    address = self._extract_address(title_text, listing_soup)
                    price_byn, price_usd = self.extract_price(title_text)
                
                # Ищем цену в специальных элементах
                if not price_usd and not price_byn:
                    price_elems = listing_soup.find_all(class_=re.compile(r'price|cost|amount'))
                    for price_elem in price_elems:
                        price_text = price_elem.get_text(' ', strip=True)
                        price_byn, price_usd = self.extract_price(price_text)
                        if price_usd or price_byn:
                            break
                    # Если не нашли, ищем в тексте страницы
                    if not price_usd and not price_byn:
                        price_byn, price_usd = self.extract_price(text)
                
                # Ищем адрес в специальных элементах
                if not address:
                    address_elems = listing_soup.find_all(class_=re.compile(r'address|location|place'))
                    for addr_elem in address_elems:
                        addr_text = addr_elem.get_text(' ', strip=True)
                        if 'минск' in addr_text.lower() and len(addr_text) > 5:
                            address = self._extract_address(addr_text, addr_elem)
                            if address:
                                break
                    # Если не нашли, ищем в тексте страницы
                    if not address:
                        address = self._extract_address(text, listing_soup)
                
                # Ищем комнаты в специальных элементах
                if rooms is None:
                    rooms_elems = listing_soup.find_all(class_=re.compile(r'rooms|room|param'))
                    for room_elem in rooms_elems:
                        room_text = room_elem.get_text(' ', strip=True)
                        rooms = self.extract_rooms(room_text)
                        if rooms:
                            break
                    # Если не нашли, ищем в тексте страницы
                    if rooms is None:
                        rooms = self.extract_rooms(text)
                
                # Исключаем навигационные элементы (header, nav, footer, menu)
                excluded_tags = ['header', 'nav', 'footer', 'aside']
                excluded_classes = ['header', 'nav', 'footer', 'menu', 'navigation', 'sidebar']
                
                # Ищем арендодателя в специальных элементах - Realt.by использует разные классы
                landlord_elems = listing_soup.find_all(class_=re.compile(r'owner|landlord|agent|seller|contact|author|user|person'))
                for landlord_elem in landlord_elems:
                    # Пропускаем навигационные элементы
                    if landlord_elem.find_parent(excluded_tags):
                        continue
                    parent_classes = landlord_elem.find_parent(class_=re.compile('|'.join(excluded_classes)))
                    if parent_classes:
                        continue
                    
                    landlord_text = landlord_elem.get_text(' ', strip=True)
                    # Проверяем на собственника (приоритет)
                    if any(keyword in landlord_text.lower() for keyword in [
                        'собственник', 'от собственника', 'частное лицо', 
                        'без посредников', 'напрямую от собственника',
                        'хозяин', 'владелец', 'от хозяина', 'напрямую',
                        'без агентств', 'частное', 'физлицо'
                    ]):
                        landlord = "Собственник"
                        break
                    # Проверяем на агентство (только если явно указано в контексте объявления)
                    elif any(keyword in landlord_text.lower() for keyword in [
                        'агент', 'агентство', 'риэлтор', 'риелтор',
                        'компания', 'бюро', 'агентская'
                    ]) and len(landlord_text) < 200:  # Короткий текст - скорее всего это информация об арендодателе
                        landlord = "Агентство"
                        break
                
                # Также проверяем в title и мета-тегах
                if not landlord:
                    title_elem = listing_soup.find('title')
                    if title_elem:
                        title_text = title_elem.get_text(' ', strip=True)
                        if any(keyword in title_text.lower() for keyword in [
                            'собственник', 'от собственника', 'частное лицо',
                            'без посредников', 'напрямую от собственника'
                        ]):
                            landlord = "Собственник"
                        elif any(keyword in title_text.lower() for keyword in [
                            'агент', 'агентство', 'риэлтор'
                        ]):
                            landlord = "Агентство"
                
                # Ищем в мета-тегах и data-атрибутах
                if not landlord:
                    meta_elems = listing_soup.find_all(['meta', 'div', 'span'], attrs={
                        'property': re.compile(r'owner|landlord|agent'),
                        'itemprop': re.compile(r'owner|landlord|agent')
                    })
                    for meta_elem in meta_elems:
                        content = meta_elem.get('content') or meta_elem.get_text(' ', strip=True)
                        if content:
                            if any(keyword in content.lower() for keyword in [
                                'собственник', 'от собственника', 'частное лицо'
                            ]):
                                landlord = "Собственник"
                                break
                            elif any(keyword in content.lower() for keyword in [
                                'агент', 'агентство', 'риэлтор'
                            ]):
                                landlord = "Агентство"
                                break
                
                # Ищем в тексте страницы (более широкий поиск)
                if not landlord:
                    # Удаляем навигационные элементы из текста
                    main_content = listing_soup.find('main') or listing_soup.find('article') or listing_soup.find('div', class_=re.compile(r'content|main|object|listing'))
                    
                    if main_content:
                        # Извлекаем текст только из основного контента
                        content_text = main_content.get_text(' ', strip=True)
                        # Берем первые 3000 символов (основная информация)
                        text_sample = content_text[:3000] if len(content_text) > 3000 else content_text
                        landlord = self._extract_landlord(text_sample)
                    else:
                        # Если не нашли main content, ищем в первых 3000 символов всего текста
                        # (исключая начало, где обычно навигация)
                        text_sample = text[1000:4000] if len(text) > 4000 else text[1000:] if len(text) > 1000 else text
                        landlord = self._extract_landlord(text_sample)
                    
                    # Если не нашли, пробуем весь текст (но с приоритетом собственника)
                    if not landlord or landlord == "Агентство":
                        # Если не нашли явных указаний, считаем собственником
                        landlord = self._extract_landlord(text)
            else:
                # Если не удалось загрузить, используем данные из ссылки
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
                'source': 'Realt.by',
                'address': address or 'Адрес не указан',
                'rooms': rooms,
                'price_byn': price_byn,
                'price_usd': price_usd,
                'landlord': landlord,
                'url': href
            }
        except Exception as e:
            logger.error(f"Ошибка парсинга объявления Realt.by: {e}")
            return None
    
    def _parse_listing_from_container(
        self,
        container,
        base_url: str
    ) -> Optional[Dict]:
        """Парсинг объявления из контейнера."""
        try:
            text = container.get_text(' ', strip=True)
            
            # Улучшенный поиск ссылки на объявление
            href = ''
            
            # 1. Ищем прямую ссылку в контейнере
            link = container.find('a', href=re.compile(r'/object/|/rent/'))
            if link:
                href = link.get('href', '')
            
            # 2. Если не нашли, ищем в дочерних элементах
            if not href:
                links = container.find_all('a', href=re.compile(r'/object/|/rent/'))
                if links:
                    href = links[0].get('href', '')
            
            # 3. Если не нашли, ищем в родительском элементе
            if not href:
                parent = container.find_parent(['div', 'article', 'li'])
                if parent:
                    parent_link = parent.find('a', href=re.compile(r'/object/|/rent/'))
                    if parent_link:
                        href = parent_link.get('href', '')
            
            # Формируем полный URL
            if href:
                if not href.startswith('http'):
                    href = href.lstrip('/')
                    href = 'https://realt.by/' + href
                # Убираем лишние параметры
                if '/object/' in href or '/rent/' in href:
                    if '?' in href:
                        href = href.split('?')[0]
                    if '#' in href:
                        href = href.split('#')[0]
            
            # Если ссылка не найдена, пропускаем это объявление
            if not href or href == base_url:
                return None
            
            # Проверяем, что это конкретное объявление, а не категория
            if '/object/' not in href:
                return None
            
            # Проверяем, что есть ID объекта в URL
            if not re.search(r'/object/\d+', href):
                return None
            
            # Исключаем категории
            href_clean = href.rstrip('/')
            if href_clean in [
                'https://realt.by/rent/flat-for-long',
                'https://realt.by/rent/flat-for-long/',
                'https://realt.by/rent/offices',
                'https://realt.by/rent/offices/',
                '/rent/flat-for-long',
                '/rent/flat-for-long/',
                '/rent/offices',
                '/rent/offices/'
            ]:
                return None
            
            if href.endswith('/rent/flat-for-long') or href.endswith('/rent/flat-for-long/'):
                return None
            if href.endswith('/rent/offices') or href.endswith('/rent/offices/'):
                return None
            if '/rent/flat-for-long/' in href and '/object/' not in href:
                return None
            if '/rent/offices/' in href:
                return None
            
            # Улучшенное извлечение цены - ищем в специальных элементах
            price_byn, price_usd = None, None
            price_elements = container.find_all(class_=re.compile(r'price|cost|amount'))
            for price_elem in price_elements:
                price_text = price_elem.get_text(' ', strip=True)
                price_byn, price_usd = self.extract_price(price_text)
                if price_usd or price_byn:
                    break
            
            if not price_usd and not price_byn:
                price_byn, price_usd = self.extract_price(text)
            
            # Улучшенное извлечение адреса - исключаем служебные адреса
            address = ''
            address_elem = container.find(class_=re.compile(r'address|location|place'))
            if address_elem:
                address_text = address_elem.get_text(' ', strip=True)
                # Исключаем служебные адреса
                if 'юридический' not in address_text.lower() and len(address_text) > 5:
                    address = address_text
            
            if not address:
                address = self._extract_address(text, container)
            
            # Если адрес содержит "юридический", очищаем его
            if address and 'юридический' in address.lower():
                address = ''
            
            # Улучшенное извлечение комнат - ищем в разных местах
            rooms = None
            rooms_elem = container.find(class_=re.compile(r'rooms|room|param'))
            if rooms_elem:
                rooms_text = rooms_elem.get_text(' ', strip=True)
                rooms = self.extract_rooms(rooms_text)
            
            # Проверяем в ссылке - может быть /rent/flat/2/ или подобное
            if rooms is None:
                link = container.find('a', href=re.compile(r'/rent/|/object/'))
                if link:
                    href_text = link.get('href', '')
                    # Ищем паттерны типа /rent/flat/2/ или /2-room/
                    room_match = re.search(r'/(\d+)[-\s]?room|/rent/flat/(\d+)|/flat/(\d+)', href_text, re.IGNORECASE)
                    if room_match:
                        for group in room_match.groups():
                            if group:
                                try:
                                    rooms = int(group)
                                    break
                                except ValueError:
                                    pass
            
            if rooms is None:
                rooms = self.extract_rooms(text)
            
            # Улучшенное извлечение арендодателя
            landlord = self._extract_landlord(text)
            
            listing_id = hashlib.md5(href.encode()).hexdigest()
            
            return {
                'listing_id': listing_id,
                'source': 'Realt.by',
                'address': address or 'Адрес не указан',
                'rooms': rooms,
                'price_usd': price_usd,
                'price_byn': price_byn,
                'landlord': landlord,
                'url': href
            }
        except Exception as e:
            logger.error(f"Ошибка парсинга контейнера Realt.by: {e}")
            return None
    
    def _extract_address(self, text: str, element) -> str:
        """Извлечь адрес."""
        address_patterns = [
            r'Минск[,\s]+(?:ул\.|улица|пр\.|проспект|пер\.|переулок|бул\.|бульвар)?\s*([А-Яа-я\s\d,.-]+)',
            r'Минск[,\s]+([А-Яа-я\s\d,.-]{3,})',
            r'г\.?\s*Минск[,\s]+([А-Яа-я\s\d,.-]+)',
        ]
        
        for pattern in address_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                address_part = match.group(1).strip()
                if len(address_part) > 100:
                    address_part = address_part[:100]
                return f"Минск, {address_part}"
        
        if hasattr(element, 'get'):
            address_attr = element.get('data-address') or element.get('data-location') or element.get('data-addr')
            if address_attr:
                return address_attr
        
        if 'минск' in text.lower():
            minsk_match = re.search(r'минск[,\s]+([а-яё\s\d,.-]{5,50})', text.lower())
            if minsk_match:
                return f"Минск, {minsk_match.group(1).strip().title()}"
            return "Минск"
        
        # Исключаем служебные адреса
        if 'юридический адрес' in text.lower() or 'юридический' in text.lower():
            return ""
        
        return ""
    
    def _extract_landlord(self, text: str) -> str:
        """Извлечь тип арендодателя."""
        text_lower = text.lower()
        
        # Исключаем навигационные фразы, которые могут содержать "агент"
        # но не относятся к арендодателю
        nav_phrases = [
            'агент недвижимости', 'агентство недвижимости', 'риэлторское агентство',
            'офис недвижимости', 'бюро недвижимости', 'компания недвижимости',
            'риэлтор', 'риелтор', 'агент по недвижимости'
        ]
        
        # Проверяем, есть ли навигационные фразы (исключаем их из анализа)
        has_nav_phrase = any(phrase in text_lower for phrase in nav_phrases)
        
        # Ключевые слова для собственника (приоритет)
        owner_keywords = [
            'собственник', 'от собственника', 'без посредников', 
            'напрямую от собственника', 'хозяин', 'владелец',
            'от хозяина', 'напрямую', 'без агентств', 'частное лицо',
            'частное', 'физлицо', 'физическое лицо', 'от владельца',
            'напрямую от хозяина', 'без риэлторов',
            'собственник сдает', 'хозяин сдает', 'владелец сдает'
        ]
        
        # Ключевые слова для агентства (только в контексте объявления)
        agent_keywords = [
            'агент сдает', 'агентство сдает', 'риэлтор сдает',
            'компания сдает', 'бюро сдает', 'агентская сдает',
            'от агента', 'от агентства', 'от риэлтора',
            'через агента', 'через агентство', 'через риэлтора'
        ]
        
        # Проверяем на собственника (приоритет)
        for keyword in owner_keywords:
            if keyword in text_lower:
                return "Собственник"
        
        # Проверяем на агентство (только если явно указано в контексте объявления)
        # и нет навигационных фраз
        if not has_nav_phrase:
            for keyword in agent_keywords:
                if keyword in text_lower:
                    return "Агентство"
        
        # По умолчанию - если не нашли явных указаний, считаем собственником
        # (так как большинство объявлений от собственников)
        return "Собственник"
