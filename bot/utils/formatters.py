"""Форматирование сообщений."""
from typing import Dict


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
    text += f"<b>Ссылка на объявление:</b> <a href='{listing['url']}'>Ссылка</a>"
    
    return text
