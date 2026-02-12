"""Парсер для Domovita.by."""
import re
import hashlib
import json
import logging
from typing import List, Dict, Optional
from bs4 import BeautifulSoup

from .base import BaseParser
from config import settings

logger = logging.getLogger(__name__)


class DomovitaParser(BaseParser):
    """Парсер для Domovita.by (загрузка через Chromium при передаче selenium_parser)."""
    
    def __init__(self, selenium_parser=None):
        super().__init__(selenium_parser=selenium_parser)
    
    async def parse_listings(self, url: str) -> List[Dict]:
        """
        Парсинг объявлений с Domovita.by.
        
        Args:
            url: URL страницы Domovita.by
        
        Returns:
            List[Dict]: Список объявлений
        """
        html = await self.fetch_page_prefer_browser(url, wait_time=10)
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'lxml')
        listings = []
        
        # Поиск объявлений на странице - Domovita использует класс "object-item"
        listing_containers = soup.find_all('div', class_=re.compile(r'object-item'))
        
        # Если не найдено, ищем по ссылкам на конкретные объявления
        if not listing_containers:
            # Ищем ссылки на конкретные объявления (исключаем категории)
            links = soup.find_all('a', href=re.compile(r'/minsk/flats/rent/|/object/|/flats/rent/|/flats-for-day/rent/'))
            # Фильтруем - исключаем категории и общие страницы
            valid_links = [
                link for link in links
                if link.get('href') and
                link.get('href') != url and
                '/1-room-flats/' not in link.get('href', '') and
                '/2-room-flats/' not in link.get('href', '') and
                '/3-room-flats/' not in link.get('href', '') and
                '/sale' not in link.get('href', '') and
                len(link.get('href', '').split('/')) > 5  # Конкретное объявление имеет больше сегментов в URL
            ]
            seen_urls = set()
            for link in valid_links[:settings.max_listings_per_source]:
                href = link.get('href', '')
                if href:
                    if not href.startswith('http'):
                        href = href.lstrip('/')
                        href = 'https://domovita.by/' + href
                    if '?' in href:
                        href = href.split('?')[0]
                    if '#' in href:
                        href = href.split('#')[0]
                    # Пропускаем дубликаты
                    if href in seen_urls:
                        continue
                    seen_urls.add(href)
                try:
                    listing_data = await self._parse_listing_from_link(link, url)
                    if listing_data:
                        # Проверяем дубликаты по URL
                        if listing_data['url'] not in [l['url'] for l in listings]:
                            listings.append(listing_data)
                except Exception as e:
                    logger.warning(f"Ошибка при парсинге объявления Domovita: {e}")
                    continue
        
        # Если нашли контейнеры, парсим их
        if listing_containers:
            for container in listing_containers[:settings.max_listings_per_source]:
                listing_data = self._parse_listing_from_container(container, url)
                if listing_data:
                    listings.append(listing_data)
        
        # Если все еще не найдено, ищем по другим классам
        if not listing_containers and not listings:
            listing_containers = soup.find_all(
                ['div', 'article'],
                class_=re.compile(r'listing|offer|ad|item|card')
            )
        
        # Если не найдено по классам, ищем по структуре
        if not listing_containers and not listings:
            listing_containers = soup.find_all('div', attrs={'data-id': True})
        
        # Альтернативный подход - поиск по ссылкам на объявления
        if not listing_containers and not listings:
            # Ищем ссылки на объявления (обычно содержат /minsk/flats/rent/ или /object/)
            links = soup.find_all('a', href=re.compile(r'/minsk/flats/rent/|/object/|/flats/rent/'))
            # Фильтруем служебные ссылки
            valid_links = [
                link for link in links 
                if link.get('href') and 
                '/create' not in link.get('href', '') and
                '/edit' not in link.get('href', '') and
                link.get('href') != url
            ]
            seen_urls = set()
            for link in valid_links[:settings.max_listings_per_source]:
                href = link.get('href', '')
                if href:
                    if not href.startswith('http'):
                        href = href.lstrip('/')
                        href = 'https://domovita.by/' + href
                    if '?' in href:
                        href = href.split('?')[0]
                    if '#' in href:
                        href = href.split('#')[0]
                    # Пропускаем дубликаты
                    if href in seen_urls:
                        continue
                    seen_urls.add(href)
                try:
                    listing_data = await self._parse_listing_from_link(link, url)
                    if listing_data:
                        # Проверяем дубликаты по URL
                        if listing_data['url'] not in [l['url'] for l in listings]:
                            listings.append(listing_data)
                except Exception as e:
                    logger.warning(f"Ошибка при парсинге объявления Domovita: {e}")
                    continue
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
                # Ищем ссылки на конкретные объявления
                if ('/flats/rent/' in href or '/object/' in href) and href != url:
                    # Нормализуем URL
                    if not href.startswith('http'):
                        href = href.lstrip('/')
                        href = 'https://domovita.by/' + href
                    if '?' in href:
                        href = href.split('?')[0]
                    if '#' in href:
                        href = href.split('#')[0]
                    # Проверяем дубликаты
                    if href in [l['url'] for l in listings]:
                        continue
                    try:
                        listing_data = await self._parse_listing_from_link(link, url)
                        if listing_data and listing_data['url'] not in [l['url'] for l in listings]:
                            listings.append(listing_data)
                            if len(listings) >= settings.max_listings_per_source:
                                break
                    except Exception as e:
                        logger.warning(f"Ошибка при парсинге объявления Domovita: {e}")
                        continue
        
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
                    href = href.lstrip('/')
                    href = 'https://domovita.by/' + href
                # Убираем лишние параметры
                if '?' in href:
                    href = href.split('?')[0]
                if '#' in href:
                    href = href.split('#')[0]
            else:
                return None
            
            # Загружаем страницу объявления через Chromium (меньше блокировок)
            try:
                listing_html = await self.fetch_page_prefer_browser(href, wait_time=8)
            except Exception as e:
                logger.warning(f"Не удалось загрузить страницу объявления Domovita {href}: {e}")
                listing_html = None
            
            if listing_html:
                listing_soup = BeautifulSoup(listing_html, 'lxml')
                text = listing_soup.get_text(' ', strip=True)
                
                # Извлекаем данные из title (Domovita использует title для основных данных)
                title_elem = listing_soup.find('title')
                if title_elem:
                    title_text = title_elem.get_text(' ', strip=True)
                    # Из title: "Сдается 1-комнатная квартира на пр-т Газеты Правда, д. 44, Минск, Московский район, 450USD"
                    rooms = self.extract_rooms(title_text)
                    address = self._extract_address(title_text, listing_soup)
                    price_byn, price_usd = self.extract_price(title_text)
                
                # Извлекаем цену из calculator__price-main (USD)
                if not price_usd:
                    price_usd_elems = listing_soup.find_all('div', class_='calculator__price-main')
                    for price_elem in price_usd_elems:
                        price_text = price_elem.get_text(' ', strip=True)
                        if '$' in price_text or 'USD' in price_text:
                            _, price_usd = self.extract_price(price_text)
                            if price_usd:
                                break
                
                # Извлекаем цену BYN из dropdown-pricechange_price-block
                if not price_byn:
                    price_byn_elem = listing_soup.find('div', class_='dropdown-pricechange_price-block')
                    if price_byn_elem:
                        price_byn_text = price_byn_elem.get_text(' ', strip=True)
                        price_byn, _ = self.extract_price(price_byn_text)
                
                # Извлекаем арендодателя из owner-info__status
                landlord = None
                landlord_elem = listing_soup.find('div', class_='owner-info__status')
                if landlord_elem:
                    landlord_text = landlord_elem.get_text(' ', strip=True)
                    if 'собственник' in landlord_text.lower() or 'от собственника' in landlord_text.lower():
                        landlord = "Собственник"
                    elif 'агент' in landlord_text.lower() or 'агентство' in landlord_text.lower():
                        landlord = "Агентство"
                
                # Если не нашли, ищем в других местах
                if not landlord:
                    landlord_elems = listing_soup.find_all(['div', 'span'], class_=re.compile(r'owner|landlord|agent|status'))
                    for landlord_elem in landlord_elems:
                        landlord_text = landlord_elem.get_text(' ', strip=True)
                        if 'собственник' in landlord_text.lower() or 'от собственника' in landlord_text.lower():
                            landlord = "Собственник"
                            break
                        elif 'агент' in landlord_text.lower() or 'агентство' in landlord_text.lower():
                            landlord = "Агентство"
                            break
                
                # Если не нашли, извлекаем из текста
                if not landlord:
                    landlord = self._extract_landlord(text)
                
                # По умолчанию - большинство объявлений от собственников
                if not landlord:
                    landlord = "Собственник"
                
                # Извлекаем комнаты из object-info__parametr
                if rooms is None:
                    rooms_elems = listing_soup.find_all('div', class_='object-info__parametr')
                    for room_elem in rooms_elems:
                        room_label = room_elem.find('span')
                        if room_label and 'Комнат' in room_label.get_text(' ', strip=True):
                            room_value = room_elem.find('span', class_=lambda x: x != 'object-info__parametr')
                            if room_value:
                                room_text = room_value.get_text(' ', strip=True)
                                try:
                                    rooms = int(room_text)
                                except ValueError:
                                    rooms = self.extract_rooms(room_text)
                            if rooms is not None:
                                break
                
                # Если не нашли комнаты, пробуем извлечь из URL
                if rooms is None:
                    # URL обычно содержит паттерн типа "2-komnatnaa-kvartira" или "1-komnatnaa"
                    url_match = re.search(r'/(\d+)-komnatnaa', href, re.IGNORECASE)
                    if url_match:
                        try:
                            rooms = int(url_match.group(1))
                        except ValueError:
                            pass
                
                # Если все еще не нашли, ищем в тексте страницы
                if rooms is None:
                    rooms = self.extract_rooms(text)
                
                # Извлекаем адрес из object-info__parametr
                if not address or address == 'Минск':
                    address_elems = listing_soup.find_all('div', class_='object-info__parametr')
                    for addr_elem in address_elems:
                        addr_label = addr_elem.find('span')
                        if addr_label and 'Адрес' in addr_label.get_text(' ', strip=True):
                            addr_value = addr_elem.find('span', class_=lambda x: x != 'object-info__parametr')
                            if addr_value:
                                address = addr_value.get_text(' ', strip=True)
                                if not address.startswith('Минск'):
                                    address = f"Минск, {address}"
                            break
                
                # Если не нашли адрес, пробуем извлечь из других элементов
                if not address or address == 'Минск' or address == 'Адрес не указан':
                    # Ищем в других местах
                    address_elems = listing_soup.find_all(['div', 'span'], class_=re.compile(r'address|location|place|object-info'))
                    for addr_elem in address_elems:
                        addr_text = addr_elem.get_text(' ', strip=True)
                        if 'минск' in addr_text.lower() and len(addr_text) > 10 and 'юридический' not in addr_text.lower():
                            address = self._extract_address(addr_text, addr_elem)
                            if address and address != 'Минск' and address != 'Адрес не указан':
                                break
                
                # Если все еще не нашли, пробуем извлечь из title
                if not address or address == 'Минск' or address == 'Адрес не указан':
                    if title_elem:
                        address = self._extract_address(title_text, listing_soup)
            else:
                # Если не удалось загрузить, используем данные из ссылки
                parent = link_element.find_parent(['div', 'article', 'li'])
                if not parent:
                    return None
                
                text = parent.get_text(' ', strip=True)
                
                address = self._extract_address(text, parent)
                
                # Пробуем извлечь комнаты из URL
                rooms = None
                if href:
                    room_match = re.search(r'/(\d+)-komnatnaa', href, re.IGNORECASE)
                    if room_match:
                        try:
                            rooms = int(room_match.group(1))
                        except ValueError:
                            pass
                
                if rooms is None:
                    rooms = self.extract_rooms(text) or self.extract_rooms(str(parent))
                
                price_byn, price_usd = self.extract_price(text)
                
                landlord = self._extract_landlord(text)
                # По умолчанию - большинство объявлений от собственников
                if not landlord:
                    landlord = "Собственник"
            
            listing_id = hashlib.md5(href.encode()).hexdigest()
            
            return {
                'listing_id': listing_id,
                'source': 'Domovita',
                'address': address or 'Адрес не указан',
                'rooms': rooms,
                'price_byn': price_byn,
                'price_usd': price_usd,
                'landlord': landlord,
                'url': href
            }
        except Exception as e:
            logger.error(f"Ошибка парсинга объявления Domovita: {e}")
            return None
    
    def _parse_listing_from_container(
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
            text = container.get_text(' ', strip=True)
            
            # Улучшенный поиск ссылки на объявление
            href = ''
            
            # 1. Ищем прямую ссылку в контейнере
            link = container.find('a', href=re.compile(r'/minsk/flats/rent/|/object/|/flats/rent/'))
            if link:
                href = link.get('href', '')
            
            # 2. Если не нашли, ищем в дочерних элементах
            if not href:
                links = container.find_all('a', href=re.compile(r'/minsk/flats/rent/|/object/|/flats/rent/'))
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
                    parent_link = parent.find('a', href=re.compile(r'/minsk/flats/rent/|/object/|/flats/rent/'))
                    if parent_link:
                        href = parent_link.get('href', '')
            
            # Формируем полный URL
            if href:
                if not href.startswith('http'):
                    href = href.lstrip('/')
                    href = 'https://domovita.by/' + href
                # Убираем лишние параметры
                if '?' in href:
                    href = href.split('?')[0]
                if '#' in href:
                    href = href.split('#')[0]
            
            # Если ссылка не найдена, пропускаем это объявление
            if not href or href == base_url or ('/flats/rent/' not in href and '/object/' not in href):
                return None
            
            # Извлечение адреса из специального элемента
            address = ''
            address_elem = container.find(class_=re.compile(r'object-item__address|address'))
            if address_elem:
                address_link = address_elem.find('a')
                if address_link:
                    address = address_link.get_text(' ', strip=True)
                else:
                    address = address_elem.get_text(' ', strip=True)
                # Исключаем служебные адреса
                if 'юридический' in address.lower():
                    address = ''
            
            # Если не нашли в специальном элементе, используем общий метод
            if not address:
                address = self._extract_address(text, container)
            
            # Если адрес содержит "юридический", очищаем его
            if address and 'юридический' in address.lower():
                address = ''
            
            # Извлечение цены из специального элемента
            price_byn, price_usd = None, None
            price_elem = container.find(class_=re.compile(r'object-item__price|price'))
            if price_elem:
                price_text = price_elem.get_text(' ', strip=True)
                # Domovita часто показывает цены в формате "247 р. за сутки" или "500 $"
                price_byn, price_usd = self.extract_price(price_text)
                # Если нашли только BYN и это аренда на длительный срок, конвертируем примерно
                # (но лучше не конвертировать автоматически, так как курс может меняться)
            
            # Если не нашли цену в специальном элементе, парсим весь текст
            if not price_usd and not price_byn:
                price_byn, price_usd = self.extract_price(text)
            
            # Извлечение комнат - проверяем alt текст изображений и ссылки
            rooms = None
            
            # 1. Проверяем alt текст всех изображений
            img_elems = container.find_all('img', alt=True)
            for img_elem in img_elems:
                alt_text = img_elem.get('alt', '')
                if 'комнатн' in alt_text.lower() or 'комн' in alt_text.lower():
                    rooms = self.extract_rooms(alt_text)
                    if rooms is not None:
                        break
            
            # 2. Проверяем ссылки - в URL может быть информация о комнатах
            if rooms is None:
                link = container.find('a', href=re.compile(r'/flats/rent/|/flats-for-day/rent/|/minsk/flats/rent/'))
                if link:
                    link_href = link.get('href', '')
                    # Ищем паттерны типа /1-room-flats/, /2-room-flats/ и т.д.
                    room_match = re.search(r'/(\d+)-room-flats/', link_href)
                    if room_match:
                        try:
                            rooms = int(room_match.group(1))
                        except ValueError:
                            pass
                    # Также проверяем паттерн типа "2-komnatnaa-kvartira" в URL
                    if rooms is None:
                        room_match = re.search(r'/(\d+)-komnatnaa', link_href, re.IGNORECASE)
                        if room_match:
                            try:
                                rooms = int(room_match.group(1))
                            except ValueError:
                                pass
                    # Также проверяем текст ссылки
                    if rooms is None:
                        link_text = link.get_text(' ', strip=True)
                        rooms = self.extract_rooms(link_text)
            
            # 3. Если не нашли, пробуем извлечь из href контейнера
            if rooms is None and href:
                room_match = re.search(r'/(\d+)-komnatnaa', href, re.IGNORECASE)
                if room_match:
                    try:
                        rooms = int(room_match.group(1))
                    except ValueError:
                        pass
            
            # 4. Если не нашли, используем общий метод
            if rooms is None:
                rooms = self.extract_rooms(text)
            
            # Извлекаем арендодателя
            landlord = self._extract_landlord(text)
            # По умолчанию - большинство объявлений от собственников
            if not landlord:
                landlord = "Собственник"
            
            listing_id = hashlib.md5(href.encode()).hexdigest()
            
            return {
                'listing_id': listing_id,
                'source': 'Domovita',
                'address': address or 'Адрес не указан',
                'rooms': rooms,
                'price_byn': price_byn,
                'price_usd': price_usd,
                'landlord': landlord,
                'url': href
            }
        except Exception as e:
            logger.error(f"Ошибка парсинга контейнера Domovita: {e}")
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
        # Поиск адреса в тексте (Минск, улица...) - улучшенные паттерны
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
        
        # Попробуем найти через data-атрибуты
        if hasattr(element, 'get'):
            address_attr = element.get('data-address') or element.get('data-location') or element.get('data-addr')
            if address_attr:
                return address_attr
        
        # Попробуем найти упоминание Минска
        if 'минск' in text.lower():
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
            'от собственника', 'собственник', 'без посредников', 
            'напрямую от собственника', 'хозяин', 'владелец',
            'от хозяина', 'напрямую', 'без агентств'
        ]):
            return "Собственник"
        return "Агентство"
