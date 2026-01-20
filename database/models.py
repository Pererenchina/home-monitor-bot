"""Модели и работа с базой данных."""
import sqlite3
import json
import logging
from datetime import datetime
from typing import Optional, Dict, List
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class Database:
    """Класс для работы с базой данных SQLite."""
    
    def __init__(self, db_path: str = "bot_database.db") -> None:
        """
        Инициализация подключения к базе данных.
        
        Args:
            db_path: Путь к файлу базы данных
        """
        self.db_path = db_path
        self.init_database()
    
    @contextmanager
    def get_connection(self):
        """
        Контекстный менеджер для работы с подключением к БД.
        
        Yields:
            sqlite3.Connection: Подключение к базе данных
        """
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()
    
    def init_database(self) -> None:
        """Инициализация структуры базы данных."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Таблица для хранения объявлений
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS listings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        listing_id TEXT UNIQUE NOT NULL,
                        source TEXT NOT NULL,
                        address TEXT,
                        rooms INTEGER,
                        price_byn REAL,
                        price_usd REAL,
                        landlord TEXT,
                        url TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        sent_to_users TEXT DEFAULT '[]'
                    )
                ''')
                
                # Таблица для хранения настроек пользователей
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS user_filters (
                        user_id INTEGER PRIMARY KEY,
                        filters TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                conn.commit()
                logger.info("База данных инициализирована")
        except sqlite3.Error as e:
            logger.error(f"Ошибка инициализации базы данных: {e}")
            raise
    
    def add_listing(
        self,
        listing_id: str,
        source: str,
        address: str,
        rooms: Optional[int],
        price_byn: Optional[float],
        price_usd: Optional[float],
        landlord: str,
        url: str
    ) -> bool:
        """
        Добавить объявление в БД.
        
        Args:
            listing_id: Уникальный идентификатор объявления
            source: Источник объявления
            address: Адрес
            rooms: Количество комнат
            price_byn: Цена в BYN
            price_usd: Цена в USD
            landlord: Тип арендодателя
            url: Ссылка на объявление
        
        Returns:
            bool: True если объявление новое, False если уже существует
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO listings (
                        listing_id, source, address, rooms,
                        price_byn, price_usd, landlord, url
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    listing_id, source, address, rooms,
                    price_byn, price_usd, landlord, url
                ))
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            # Объявление уже существует
            return False
        except sqlite3.Error as e:
            logger.error(f"Ошибка добавления объявления: {e}")
            return False
    
    def is_listing_sent_to_user(self, listing_id: str, user_id: int) -> bool:
        """
        Проверить, было ли объявление отправлено пользователю.
        
        Args:
            listing_id: Идентификатор объявления
            user_id: ID пользователя
        
        Returns:
            bool: True если объявление уже отправлено пользователю
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT sent_to_users FROM listings WHERE listing_id = ?
                ''', (listing_id,))
                
                result = cursor.fetchone()
                if result:
                    sent_users = json.loads(result[0])
                    return user_id in sent_users
                return False
        except (sqlite3.Error, json.JSONDecodeError) as e:
            logger.error(f"Ошибка проверки отправки объявления: {e}")
            return False
    
    def mark_listing_sent(self, listing_id: str, user_id: int) -> None:
        """
        Отметить, что объявление отправлено пользователю.
        
        Args:
            listing_id: Идентификатор объявления
            user_id: ID пользователя
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT sent_to_users FROM listings WHERE listing_id = ?
                ''', (listing_id,))
                
                result = cursor.fetchone()
                if result:
                    sent_users = json.loads(result[0])
                    if user_id not in sent_users:
                        sent_users.append(user_id)
                        cursor.execute('''
                            UPDATE listings SET sent_to_users = ? WHERE listing_id = ?
                        ''', (json.dumps(sent_users), listing_id))
                        conn.commit()
        except (sqlite3.Error, json.JSONDecodeError) as e:
            logger.error(f"Ошибка отметки объявления как отправленного: {e}")
    
    def save_user_filters(self, user_id: int, filters: Dict) -> None:
        """
        Сохранить фильтры пользователя.
        
        Args:
            user_id: ID пользователя
            filters: Словарь с фильтрами
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO user_filters (user_id, filters, updated_at)
                    VALUES (?, ?, ?)
                ''', (user_id, json.dumps(filters), datetime.now()))
                conn.commit()
        except (sqlite3.Error, json.JSONEncodeError) as e:
            logger.error(f"Ошибка сохранения фильтров: {e}")
            raise
    
    def get_user_filters(self, user_id: int) -> Optional[Dict]:
        """
        Получить фильтры пользователя.
        
        Args:
            user_id: ID пользователя
        
        Returns:
            Optional[Dict]: Словарь с фильтрами или None
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT filters FROM user_filters WHERE user_id = ?
                ''', (user_id,))
                
                result = cursor.fetchone()
                if result:
                    return json.loads(result[0])
                return None
        except (sqlite3.Error, json.JSONDecodeError) as e:
            logger.error(f"Ошибка получения фильтров: {e}")
            return None
    
    def get_all_users_with_filters(self) -> List[int]:
        """
        Получить список всех пользователей с настроенными фильтрами.
        
        Returns:
            List[int]: Список ID пользователей
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT user_id FROM user_filters')
                results = cursor.fetchall()
                return [row[0] for row in results]
        except sqlite3.Error as e:
            logger.error(f"Ошибка получения списка пользователей: {e}")
            return []
