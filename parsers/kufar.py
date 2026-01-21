"""Парсер для Kufar.by."""
import re
import hashlib
import logging
from typing import List, Dict, Optional
from bs4 import BeautifulSoup, Tag

from .base import BaseParser
from .selenium_base import SeleniumBaseParser
from config import settings

logger = logging.getLogger(__name__)


class KufarParser(BaseParser):
    """Парсер для Kufar.by с использованием Selenium."""
    
    def __init__(self):
        """Инициализация парсера."""
        BaseParser.__init__(self)
        self.selenium_parser = SeleniumBaseParser()
    
    def __del__(self):
        """Деструктор - закрываем Selenium драйвер."""
        if hasattr(self, 'selenium_parser'):
            self.selenium_parser.close()
    
    async def parse_listings(self, url: str) -> List[Dict]:
        """
        Парсинг объявлений с Kufar.
        
        Args:
            url: Базовый URL Kufar
        
        Returns:
            List[Dict]: Список объявлений
        """
        # Используем правильный URL для аренды квартир в Минске
        # cat=1010 - категория квартиры, typ=sell - продажа, но нам нужна аренда
        # Для аренды используем другой URL формат
        search_url = f"{url}l/minsk/snyat/kvartiru"
        
        # Используем Selenium для получения HTML (динамическая загрузка)
        # Увеличиваем время ожидания для Kufar, так как он загружает объявления динамически
        html = await self.selenium_parser.fetch_page_selenium(search_url, wait_time=20)
        if not html:
            # Пробуем обычный метод как fallback
            html = await self.fetch_page(search_url)
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'lxml')
        listings = []
        
        # Kufar загружает объявления через JavaScript, их ID находятся в скриптах
        # Ищем ad_id в скриптах и извлекаем данные из JSON
        import json
        scripts = soup.find_all('script')
        
        # Ищем скрипт с __NEXT_DATA__
        next_data_script = soup.find('script', id='__NEXT_DATA__', type='application/json')
        if next_data_script and next_data_script.string:
            try:
                data = json.loads(next_data_script.string)
                # Ищем объявления в структуре данных
                if 'props' in data and 'initialState' in data.get('props', {}):
                    listing_state = data['props']['initialState'].get('listing', {})
                    ads = listing_state.get('ads', [])
                    if ads:
                        logger.info(f"Найдено {len(ads)} объявлений в JSON данных")
                        for ad in ads[:settings.max_listings_per_source]:
                            try:
                                listing_data = self._parse_listing_from_json(ad)
                                if listing_data:
                                    listings.append(listing_data)
                            except Exception as e:
                                logger.warning(f"Ошибка при парсинге объявления из JSON: {e}")
                                continue
            except Exception as e:
                logger.debug(f"Не удалось извлечь JSON из __NEXT_DATA__: {e}")
        
        # Если не нашли в __NEXT_DATA__, ищем в других скриптах
        if not listings:
            for script in scripts:
                if script.string and ('"ads"' in script.string or '"listing"' in script.string):
                    try:
                        # Ищем JSON объект в скрипте
                        json_match = re.search(r'\{.*"ads".*\}', script.string, re.DOTALL)
                        if json_match:
                            try:
                                data = json.loads(json_match.group(0))
                                # Ищем объявления в разных местах структуры
                                ads = []
                                if isinstance(data, dict):
                                    if 'ads' in data:
                                        ads = data['ads'] if isinstance(data['ads'], list) else []
                                    elif 'listing' in data and 'ads' in data['listing']:
                                        ads = data['listing']['ads'] if isinstance(data['listing']['ads'], list) else []
                                    elif 'initialState' in data and 'listing' in data['initialState']:
                                        listing_state = data['initialState']['listing']
                                        ads = listing_state.get('ads', []) if isinstance(listing_state, dict) else []
                                
                                if ads:
                                    logger.info(f"Найдено {len(ads)} объявлений в JSON данных (альтернативный поиск)")
                                    for ad in ads[:settings.max_listings_per_source]:
                                        try:
                                            listing_data = self._parse_listing_from_json(ad)
                                            if listing_data:
                                                listings.append(listing_data)
                                        except Exception as e:
                                            logger.warning(f"Ошибка при парсинге объявления из JSON: {e}")
                                            continue
                                    break
                            except json.JSONDecodeError:
                                continue
                    except Exception as e:
                        logger.debug(f"Ошибка при поиске JSON в скрипте: {e}")
                        continue
        
        # Если не нашли в JSON, ищем ad_id в скриптах
        if not listings:
            ad_ids = set()
            for script in scripts:
                if script.string:
                    # Ищем паттерн "ad_id":число
                    matches = re.findall(r'"ad_id"\s*:\s*(\d+)', script.string)
                    for match in matches:
                        ad_ids.add(match)
            
            # Если нашли ID в скриптах, извлекаем данные из контейнеров на странице
            if ad_ids:
                logger.info(f"Найдено {len(ad_ids)} объявлений через ad_id в скриптах")
                # Ищем контейнеры с этими ID
                for ad_id in list(ad_ids)[:settings.max_listings_per_source]:
                    container = soup.find(attrs={'data-id': ad_id})
                    if container:
                        listing_data = await self._parse_listing_from_container(container, url)
                        if listing_data:
                            listings.append(listing_data)
                    else:
                        # Если контейнер не найден, ищем данные в тексте страницы по ID
                        # Пробуем найти упоминание этого ID в тексте или скриптах
                        href = f'https://re.kufar.by/v/{ad_id}'
                        # Ищем в тексте страницы данные об этом объявлении
                        # (Kufar может хранить данные в JSON в скриптах)
                        listing_data = None
                        for script in scripts:
                            if script.string and str(ad_id) in script.string:
                                # Пробуем извлечь данные из JSON
                                try:
                                    import json
                                    # Ищем объект с этим ad_id
                                    pattern = r'\{[^{}]*"ad_id"\s*:\s*' + str(ad_id) + r'[^{}]*\}'
                                    json_match = re.search(pattern, script.string, re.DOTALL)
                                    if json_match:
                                        ad_json = json.loads(json_match.group(0))
                                        listing_data = self._parse_listing_from_json(ad_json)
                                        break
                                except:
                                    pass
                        
                        # Если не нашли в JSON, создаем базовое объявление
                        if not listing_data:
                            listing_id = hashlib.md5(href.encode()).hexdigest()
                            listing_data = {
                                'listing_id': listing_id,
                                'source': 'Kufar',
                                'address': 'Адрес не указан',
                                'rooms': None,
                                'price_byn': None,
                                'price_usd': None,
                                'landlord': None,
                                'url': href
                            }
                        listings.append(listing_data)
        
        # Также ищем в HTML структуре (на случай, если объявления уже загружены)
        listing_containers = []
        if not listings:
            # Kufar использует структуру с data-id (только числовые ID)
            listing_containers = soup.find_all(
                ['div', 'article'],
                attrs={'data-id': re.compile(r'^\d+$')}  # Только числовые ID
            )
            
            # Альтернативный поиск по классам
            if not listing_containers:
                listing_containers = soup.find_all(
                    'div',
                    class_=re.compile(r'styles_item|listing|ad|item|card')
                )
            
            # Поиск по ссылкам
            if not listing_containers:
                # Ищем ссылки на объявления (обычно содержат /v/ с ID)
                links = soup.find_all('a', href=re.compile(r'/v/\d+'))
                # Если не нашли с ID, ищем любые ссылки /v/
                if not links:
                    links = soup.find_all('a', href=re.compile(r'/v/'))
                
                seen_urls = set()
                for link in links[:settings.max_listings_per_source]:
                    href = link.get('href', '')
                    if href:
                        if not href.startswith('http'):
                            href = href.lstrip('/')
                            href = 'https://re.kufar.by/' + href
                        if '?' in href:
                            href = href.split('?')[0]
                        if '#' in href:
                            href = href.split('#')[0]
                        if href in seen_urls:
                            continue
                        seen_urls.add(href)
                    try:
                        listing_data = await self._parse_listing_from_link(link, url)
                        if listing_data and listing_data['url'] not in [l['url'] for l in listings]:
                            listings.append(listing_data)
                    except Exception as e:
                        logger.warning(f"Ошибка при парсинге объявления Kufar: {e}")
                        continue
            else:
                seen_urls = set()
                for container in listing_containers[:settings.max_listings_per_source]:
                    try:
                        listing_data = await self._parse_listing_from_container(container, url)
                        if listing_data and listing_data['url'] not in [l['url'] for l in listings]:
                            listings.append(listing_data)
                    except Exception as e:
                        logger.warning(f"Ошибка при парсинге контейнера Kufar: {e}")
                        continue
        
        # Если все еще нет объявлений, пробуем более широкий поиск
        if not listings:
            all_links = soup.find_all('a', href=True)
            for link in all_links:
                href = link.get('href', '')
                # Ищем ссылки с ID объявления
                if '/v/' in href and href != url:
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
                    href = 'https://re.kufar.by/' + href
                # Убираем лишние параметры и очищаем ID
                if '/v/' in href:
                    parts = href.split('/v/')
                    if len(parts) > 1:
                        listing_path = parts[1].split('?')[0].split('#')[0]
                        # Очищаем ID от лишних символов (оставляем только цифры)
                        listing_id_clean = ''.join(c for c in listing_path if c.isdigit())
                        if listing_id_clean:
                            href = f'https://re.kufar.by/v/{listing_id_clean}'
                        else:
                            return None
            else:
                return None
            
            # Загружаем страницу объявления для извлечения данных через Selenium
            # (Kufar может блокировать обычные HTTP запросы)
            listing_html = await self.selenium_parser.fetch_page_selenium(href, wait_time=8)
            if not listing_html:
                # Fallback на обычный метод
                listing_html = await self.fetch_page(href)
            if listing_html:
                listing_soup = BeautifulSoup(listing_html, 'lxml')
                text = listing_soup.get_text(' ', strip=True)
                
                # Инициализируем переменные
                rooms = None
                address = None
                price_byn, price_usd = None, None
                landlord = None
                
                # Извлекаем данные из title (Kufar использует title для основных данных)
                title_elem = listing_soup.find('title')
                if title_elem:
                    title_text = title_elem.get_text(' ', strip=True)
                    # Из title: "1-к квартира 33.6 м² по адресу Николы Теслы ул, Минск, по цене 1 393 р. / мес."
                    rooms = self.extract_rooms(title_text)
                    address = self._extract_address(title_text, listing_soup)
                    price_byn, price_usd = self.extract_price(title_text)
                
                # Ищем цену в специальных элементах
                if not price_usd and not price_byn:
                    # Ищем элементы с ценой
                    price_elems = listing_soup.find_all(class_=re.compile(r'price|cost|amount|styles_price'))
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
                    address_elems = listing_soup.find_all(class_=re.compile(r'address|location|place|styles_address'))
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
                    rooms_elems = listing_soup.find_all(class_=re.compile(r'rooms|room|param|styles_rooms'))
                    for room_elem in rooms_elems:
                        room_text = room_elem.get_text(' ', strip=True)
                        rooms = self.extract_rooms(room_text)
                        if rooms:
                            break
                    # Если не нашли, ищем в тексте страницы
                    if rooms is None:
                        rooms = self.extract_rooms(text)
                
                # Ищем арендодателя в специальных элементах
                landlord_elems = listing_soup.find_all(class_=re.compile(r'owner|landlord|agent|styles_owner'))
                for landlord_elem in landlord_elems:
                    landlord_text = landlord_elem.get_text(' ', strip=True)
                    if 'собственник' in landlord_text.lower() or 'от собственника' in landlord_text.lower():
                        landlord = "Собственник"
                        break
                    elif 'агент' in landlord_text.lower() or 'агентство' in landlord_text.lower():
                        landlord = "Агентство"
                        break
                # Если не нашли, ищем в тексте страницы
                if not landlord:
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
    
    async def _parse_listing_from_container(
        self,
        container,
        base_url: str
    ) -> Optional[Dict]:
        """Парсинг объявления из контейнера."""
        try:
            text = container.get_text(' ', strip=True)
            
            # Улучшенный поиск ссылки на объявление
            href = ''
            
            # 1. Ищем data-id и формируем ссылку (только если это число)
            data_id = container.get('data-id')
            if data_id:
                # Проверяем, что data-id является числом (ID объявления)
                try:
                    # Очищаем data-id от лишних символов
                    data_id_clean = str(data_id).strip()
                    data_id_clean = ''.join(c for c in data_id_clean if c.isdigit())
                    if data_id_clean:
                        int(data_id_clean)  # Проверяем, что это число
                        href = f'https://re.kufar.by/v/{data_id_clean}'
                        data_id = data_id_clean
                    else:
                        data_id = None
                except (ValueError, TypeError):
                    # Если data-id не число, это служебная ссылка, пропускаем
                    data_id = None
            
            # 2. Ищем прямую ссылку в контейнере
            if not href:
                link = container.find('a', href=re.compile(r'/v/'))
                if link:
                    href = link.get('href', '')
            
            # 3. Если не нашли, ищем в дочерних элементах
            if not href:
                links = container.find_all('a', href=re.compile(r'/v/'))
                if links:
                    href = links[0].get('href', '')
            
            # 4. Если не нашли, ищем в родительском элементе
            if not href:
                parent = container.find_parent(['div', 'article', 'li'])
                if parent:
                    parent_link = parent.find('a', href=re.compile(r'/v/'))
                    if parent_link:
                        href = parent_link.get('href', '')
            
            # 5. Ищем data-href или другие data-атрибуты
            if not href:
                href = container.get('data-href') or container.get('data-url') or container.get('href')
            
            # Формируем полный URL
            if href:
                if not href.startswith('http'):
                    href = href.lstrip('/')
                    href = 'https://re.kufar.by/' + href
                # Убираем лишние параметры и очищаем ID
                if '/v/' in href:
                    parts = href.split('/v/')
                    if len(parts) > 1:
                        listing_path = parts[1].split('?')[0].split('#')[0]
                        # Очищаем ID от лишних символов (оставляем только цифры)
                        listing_id_clean = ''.join(c for c in listing_path if c.isdigit())
                        if listing_id_clean:
                            href = f'https://re.kufar.by/v/{listing_id_clean}'
                        else:
                            return None
            
            # Если ссылка не найдена, но есть data-id (число), формируем ссылку
            if not href and data_id:
                try:
                    # Очищаем data-id от лишних символов
                    data_id_clean = str(data_id).strip()
                    data_id_clean = ''.join(c for c in data_id_clean if c.isdigit())
                    if data_id_clean:
                        int(data_id_clean)  # Проверяем, что это число
                        href = f'https://re.kufar.by/v/{data_id_clean}'
                    else:
                        return None
                except (ValueError, TypeError):
                    # Если data-id не число, это служебная ссылка, пропускаем
                    return None
            
            # Если ссылка все еще не найдена, пропускаем это объявление
            if not href or href == base_url:
                return None
            
            # Исключаем служебные ссылки
            if any(excluded in href.lower() for excluded in [
                'about_kufar', 'for_business', 'usefully', 'safety',
                'help', 'support', 'contact', 'terms', 'privacy'
            ]):
                return None
            
            # Извлекаем данные из контейнера на главной странице (не загружаем отдельную страницу)
            # Это быстрее и надежнее, так как многие объявления могут быть недоступны
            text = container.get_text(' ', strip=True)
            
            # Инициализируем переменные
            rooms = None
            address = None
            price_byn, price_usd = None, None
            landlord = None
            
            # Ищем цену в контейнере - пробуем разные селекторы
            price_elems = container.find_all(class_=re.compile(r'price|cost|amount|styles_price|styles_cost'))
            for price_elem in price_elems:
                price_text = price_elem.get_text(' ', strip=True)
                price_byn, price_usd = self.extract_price(price_text)
                if price_usd or price_byn:
                    break
            # Если не нашли в элементах, ищем в тексте контейнера
            if not price_usd and not price_byn:
                price_byn, price_usd = self.extract_price(text)
            
            # Ищем адрес в контейнере - пробуем разные селекторы
            address_elems = container.find_all(class_=re.compile(r'address|location|place|styles_address|styles_location'))
            for addr_elem in address_elems:
                addr_text = addr_elem.get_text(' ', strip=True)
                if 'минск' in addr_text.lower() and len(addr_text) > 5:
                    address = self._extract_address(addr_text, addr_elem)
                    if address:
                        break
            # Если не нашли в элементах, ищем в тексте контейнера
            if not address:
                address = self._extract_address(text, container)
            
            # Ищем комнаты в контейнере - пробуем разные селекторы
            rooms_elems = container.find_all(class_=re.compile(r'rooms|room|param|styles_rooms|styles_param'))
            for room_elem in rooms_elems:
                room_text = room_elem.get_text(' ', strip=True)
                rooms = self.extract_rooms(room_text)
                if rooms:
                    break
            # Если не нашли в элементах, ищем в тексте контейнера
            if rooms is None:
                rooms = self.extract_rooms(text)
            
            # Ищем арендодателя в контейнере - пробуем разные селекторы
            landlord_elems = container.find_all(class_=re.compile(r'owner|landlord|agent|styles_owner|styles_agent'))
            for landlord_elem in landlord_elems:
                landlord_text = landlord_elem.get_text(' ', strip=True)
                if 'собственник' in landlord_text.lower() or 'от собственника' in landlord_text.lower():
                    landlord = "Собственник"
                    break
                elif 'агент' in landlord_text.lower() or 'агентство' in landlord_text.lower():
                    landlord = "Агентство"
                    break
            # Если не нашли в элементах, ищем в тексте контейнера
            if not landlord:
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
            logger.error(f"Ошибка парсинга контейнера Kufar: {e}")
            return None
    
    def _parse_listing_from_json(self, ad_data: Dict) -> Optional[Dict]:
        """Парсинг объявления из JSON данных."""
        try:
            ad_id = ad_data.get('ad_id') or ad_data.get('id') or ad_data.get('adId')
            if not ad_id:
                return None
            
            # Очищаем ad_id от лишних символов и приводим к строке
            ad_id = str(ad_id).strip()
            # Убираем все нецифровые символы, кроме дефиса (если есть)
            ad_id_clean = ''.join(c for c in ad_id if c.isdigit())
            if not ad_id_clean:
                return None
            
            # Формируем правильную ссылку
            href = f'https://re.kufar.by/v/{ad_id_clean}'
            
            # Извлекаем данные из JSON
            subject = ad_data.get('subject', '') or ad_data.get('title', '') or ad_data.get('name', '')
            
            # Ищем комнаты - сначала в ad_parameters, потом в subject
            rooms = None
            ad_parameters = ad_data.get('ad_parameters', [])
            if isinstance(ad_parameters, list):
                for param in ad_parameters:
                    if isinstance(param, dict) and param.get('p') == 'rooms':
                        rooms_str = param.get('v', '')
                        if rooms_str:
                            try:
                                rooms = int(rooms_str)
                            except (ValueError, TypeError):
                                rooms = self.extract_rooms(str(rooms_str))
                        break
            
            # Если не нашли в параметрах, извлекаем из subject
            if rooms is None:
                rooms = self.extract_rooms(subject)
            
            # Ищем цену - Kufar хранит price_byn и price_usd напрямую
            price_byn = ad_data.get('price_byn')
            price_usd = ad_data.get('price_usd')
            
            # Конвертируем в числа, если нужно
            try:
                if price_byn is not None:
                    price_byn = float(price_byn) if not isinstance(price_byn, (int, float)) else price_byn
                if price_usd is not None:
                    price_usd = float(price_usd) if not isinstance(price_usd, (int, float)) else price_usd
                    
                    # Если цены в неправильном формате (слишком большие числа), конвертируем
                    # Kufar может хранить цены в копейках/центах
                    # Проверяем: если цена USD больше 1000, вероятно это в центах (делим на 100)
                    if isinstance(price_usd, (int, float)):
                        if price_usd > 1000:
                            # Вероятно, цена в центах - делим на 100
                            price_usd = price_usd / 100
                        elif price_usd > 5000:
                            # Если очень большая, точно в центах
                            price_usd = price_usd / 100
                    
                    if isinstance(price_byn, (int, float)):
                        # BYN может быть в копейках - проверяем по разумности
                        # Если цена больше 10000 BYN (для аренды это очень много), возможно в копейках
                        # Также проверяем соотношение с USD: если BYN/USD > 10, вероятно в копейках
                        if price_byn > 10000:
                            # Проверяем соотношение с USD
                            if price_usd and price_usd > 0:
                                ratio = price_byn / price_usd
                                # Нормальный курс ~2.9-3.0, если больше 10 - точно в копейках
                                if ratio > 10:
                                    price_byn = price_byn / 100
                            else:
                                # Если USD нет, но BYN очень большая, делим на 100
                                if price_byn > 100000:
                                    price_byn = price_byn / 100
            except (ValueError, TypeError):
                price_byn = None
                price_usd = None
            
            # Ищем адрес - в account_parameters с p='address'
            address = ''
            account_parameters = ad_data.get('account_parameters', [])
            if isinstance(account_parameters, list):
                for param in account_parameters:
                    if isinstance(param, dict) and param.get('p') == 'address':
                        address = param.get('v', '')
                        if address:
                            break
            
            # Если не нашли в account_parameters, ищем в ad_parameters
            if not address:
                if isinstance(ad_parameters, list):
                    for param in ad_parameters:
                        if isinstance(param, dict) and param.get('p') in ['address', 'region', 'area']:
                            addr_value = param.get('v', '')
                            if addr_value and 'минск' in str(addr_value).lower():
                                if not address:
                                    address = str(addr_value)
                                else:
                                    address = f"{address}, {addr_value}"
            
            # Если не нашли адрес, пробуем извлечь из subject
            if not address or address == '':
                if subject:
                    address = self._extract_address(subject, None)
            
            # Ищем арендодателя - company_ad=False обычно означает собственника
            landlord = None
            company_ad = ad_data.get('company_ad', None)
            
            # Приоритет 1: company_ad - самый надежный индикатор
            if company_ad is False:
                # Не компания, скорее всего собственник
                landlord = "Собственник"
            elif company_ad is True:
                # Компания = агентство
                landlord = "Агентство"
            
            # Приоритет 2: account_type
            if not landlord:
                account_type = ad_data.get('account_type', '') or ad_data.get('accountType', '')
                if account_type:
                    account_type_lower = str(account_type).lower()
                    if any(keyword in account_type_lower for keyword in ['owner', 'собственник', 'private', 'частное']):
                        landlord = "Собственник"
                    elif any(keyword in account_type_lower for keyword in ['agent', 'агент', 'company', 'компания']):
                        landlord = "Агентство"
            
            # Приоритет 3: ad_parameters - ищем параметр flat_rent_for_whom
            if not landlord:
                if isinstance(ad_parameters, list):
                    for param in ad_parameters:
                        if isinstance(param, dict):
                            param_p = param.get('p', '')
                            param_vl = param.get('vl', '') or param.get('v', '')
                            if param_p == 'flat_rent_for_whom' and param_vl:
                                param_vl_lower = str(param_vl).lower()
                                if any(keyword in param_vl_lower for keyword in ['собственник', 'от собственника', 'частное']):
                                    landlord = "Собственник"
                                    break
                                elif any(keyword in param_vl_lower for keyword in ['агент', 'агентство', 'компания']):
                                    landlord = "Агентство"
                                    break
            
            # Приоритет 4: извлекаем из subject
            if not landlord and subject:
                landlord = self._extract_landlord(subject)
            
            # Приоритет 5: по умолчанию - большинство объявлений от собственников
            if not landlord:
                landlord = "Собственник"  # По умолчанию - собственник
            
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
            logger.error(f"Ошибка парсинга объявления из JSON: {e}")
            import traceback
            logger.debug(traceback.format_exc())
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
        if any(keyword in text_lower for keyword in [
            'собственник', 'от собственника', 'без посредников', 
            'напрямую от собственника', 'хозяин', 'владелец',
            'от хозяина', 'напрямую', 'без агентств'
        ]):
            return "Собственник"
        return "Агентство"
