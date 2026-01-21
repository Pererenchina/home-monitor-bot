"""Форматирование сообщений."""
from typing import Dict
from urllib.parse import urlparse


def _is_valid_url(url: str) -> bool:
    """
    Проверить, является ли строка валидным URL.
    
    Args:
        url: Строка для проверки
    
    Returns:
        bool: True если валидный URL
    """
    if not url or not isinstance(url, str):
        return False
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def format_listing_message(listing: Dict) -> str:
    """
    Форматировать сообщение об объявлении в HTML.
    
    Args:
        listing: Словарь с данными объявления
    
    Returns:
        str: Отформатированное HTML сообщение
    """
    text = f"<b>Адрес:</b> {listing['address']}\n"
    
    if listing.get('rooms'):
        text += f"<b>Комнаты:</b> {listing['rooms']}-комнатная квартира\n"
    else:
        text += "<b>Комнаты:</b> Не указано\n"
    
    if listing.get('price_byn'):
        text += f"<b>Цена:</b> {int(listing['price_byn'])} BYN\n"
    if listing.get('price_usd'):
        text += f"<b>Цена:</b> {int(listing['price_usd'])} $\n"
    
    text += f"<b>Арендодатель:</b> {listing.get('landlord', 'Не указано')}\n"
    text += f"<b>Источник:</b> {listing['source']}\n"
    
    # Форматирование ссылки - всегда показываем конкретную ссылку на объявление
    url = listing.get('url', '')
    if url and _is_valid_url(url):
        # Проверяем, что это ссылка на конкретное объявление, а не на главную страницу
        source = listing.get('source', '')
        is_listing_url = False
        
        if source == 'Onliner' and '/ak/apartments/' in url:
            is_listing_url = True
        elif source == 'Kufar' and '/v/' in url:
            is_listing_url = True
        elif source == 'Realt.by' and ('/object/' in url or '/rent/' in url):
            is_listing_url = True
        elif source == 'Domovita' and ('/flats/rent/' in url or '/object/' in url):
            is_listing_url = True
        
        if is_listing_url:
            # Обрезаем длинные URL для отображения
            display_url = url
            if len(display_url) > 60:
                # Показываем только домен и последнюю часть пути
                parts = display_url.split('/')
                if len(parts) > 2:
                    display_url = '/'.join(parts[:3]) + '/.../' + parts[-1]
            text += f"<b>Ссылка:</b> <a href='{url}'>Открыть объявление</a>"
        else:
            # Если URL не на конкретное объявление, показываем общую ссылку
            if source == 'Onliner':
                text += "<b>Ссылка:</b> <a href='https://r.onliner.by/ak/'>r.onliner.by/ak/</a>"
            elif source == 'Kufar':
                text += "<b>Ссылка:</b> <a href='https://re.kufar.by/'>re.kufar.by</a>"
            elif source == 'Realt.by':
                text += "<b>Ссылка:</b> <a href='https://realt.by/'>realt.by</a>"
            elif source == 'Domovita':
                text += "<b>Ссылка:</b> <a href='https://domovita.by/minsk/flats/rent'>domovita.by</a>"
            else:
                text += "<b>Ссылка:</b> Недоступна"
    else:
        # Если URL невалидный, показываем источник
        source = listing.get('source', 'Неизвестно')
        if source == 'Onliner':
            text += "<b>Ссылка:</b> <a href='https://r.onliner.by/ak/'>r.onliner.by/ak/</a>"
        elif source == 'Kufar':
            text += "<b>Ссылка:</b> <a href='https://re.kufar.by/'>re.kufar.by</a>"
        elif source == 'Realt.by':
            text += "<b>Ссылка:</b> <a href='https://realt.by/'>realt.by</a>"
        elif source == 'Domovita':
            text += "<b>Ссылка:</b> <a href='https://domovita.by/minsk/flats/rent'>domovita.by</a>"
        else:
            text += "<b>Ссылка:</b> Недоступна"
    
    return text
