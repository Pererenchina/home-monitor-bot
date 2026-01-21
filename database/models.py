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
                
                # Таблица для хранения фильтров пользователей (поддержка нескольких фильтров)
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS user_filters (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        filter_name TEXT NOT NULL DEFAULT 'Фильтр',
                        filters TEXT NOT NULL,
                        is_active INTEGER DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Индекс для быстрого поиска фильтров пользователя
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_user_filters_user_id 
                    ON user_filters(user_id)
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
    
    def add_user_filter(
        self,
        user_id: int,
        filter_name: str,
        filters: Dict
    ) -> int:
        """
        Добавить новый фильтр пользователя.
        
        Args:
            user_id: ID пользователя
            filter_name: Название фильтра
            filters: Словарь с фильтрами
        
        Returns:
            int: ID созданного фильтра
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO user_filters (user_id, filter_name, filters, updated_at)
                    VALUES (?, ?, ?, ?)
                ''', (user_id, filter_name, json.dumps(filters), datetime.now()))
                conn.commit()
                return cursor.lastrowid
        except (sqlite3.Error, json.JSONEncodeError) as e:
            logger.error(f"Ошибка добавления фильтра: {e}")
            raise
    
    def get_user_filters(self, user_id: int) -> List[Dict]:
        """
        Получить все фильтры пользователя.
        
        Args:
            user_id: ID пользователя
        
        Returns:
            List[Dict]: Список фильтров с ключами: id, filter_name, filters, is_active
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, filter_name, filters, is_active, created_at, updated_at
                    FROM user_filters 
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                ''', (user_id,))
                
                results = cursor.fetchall()
                filters_list = []
                for row in results:
                    filters_list.append({
                        'id': row[0],
                        'filter_name': row[1],
                        'filters': json.loads(row[2]),
                        'is_active': bool(row[3]),
                        'created_at': row[4],
                        'updated_at': row[5]
                    })
                return filters_list
        except (sqlite3.Error, json.JSONDecodeError) as e:
            logger.error(f"Ошибка получения фильтров: {e}")
            return []
    
    def get_user_filter_by_id(self, filter_id: int, user_id: int) -> Optional[Dict]:
        """
        Получить фильтр по ID.
        
        Args:
            filter_id: ID фильтра
            user_id: ID пользователя (для проверки прав)
        
        Returns:
            Optional[Dict]: Фильтр или None
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, filter_name, filters, is_active
                    FROM user_filters 
                    WHERE id = ? AND user_id = ?
                ''', (filter_id, user_id))
                
                result = cursor.fetchone()
                if result:
                    return {
                        'id': result[0],
                        'filter_name': result[1],
                        'filters': json.loads(result[2]),
                        'is_active': bool(result[3])
                    }
                return None
        except (sqlite3.Error, json.JSONDecodeError) as e:
            logger.error(f"Ошибка получения фильтра: {e}")
            return None
    
    def update_user_filter(
        self,
        filter_id: int,
        user_id: int,
        filter_name: Optional[str] = None,
        filters: Optional[Dict] = None,
        is_active: Optional[bool] = None
    ) -> bool:
        """
        Обновить фильтр пользователя.
        
        Args:
            filter_id: ID фильтра
            user_id: ID пользователя
            filter_name: Новое название (опционально)
            filters: Новые фильтры (опционально)
            is_active: Статус активности (опционально)
        
        Returns:
            bool: True если обновлено успешно
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                updates = []
                params = []
                
                if filter_name is not None:
                    updates.append("filter_name = ?")
                    params.append(filter_name)
                
                if filters is not None:
                    updates.append("filters = ?")
                    params.append(json.dumps(filters))
                
                if is_active is not None:
                    updates.append("is_active = ?")
                    params.append(1 if is_active else 0)
                
                if not updates:
                    return False
                
                updates.append("updated_at = ?")
                params.append(datetime.now())
                params.extend([filter_id, user_id])
                
                query = f'''
                    UPDATE user_filters 
                    SET {', '.join(updates)}
                    WHERE id = ? AND user_id = ?
                '''
                cursor.execute(query, params)
                conn.commit()
                return cursor.rowcount > 0
        except (sqlite3.Error, json.JSONEncodeError) as e:
            logger.error(f"Ошибка обновления фильтра: {e}")
            return False
    
    def delete_user_filter(self, filter_id: int, user_id: int) -> bool:
        """
        Удалить фильтр пользователя.
        
        Args:
            filter_id: ID фильтра
            user_id: ID пользователя
        
        Returns:
            bool: True если удалено успешно
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM user_filters 
                    WHERE id = ? AND user_id = ?
                ''', (filter_id, user_id))
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Ошибка удаления фильтра: {e}")
            return False
    
    def get_all_users_with_filters(self) -> List[int]:
        """
        Получить список всех пользователей с активными фильтрами.
        
        Returns:
            List[int]: Список ID пользователей
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT DISTINCT user_id 
                    FROM user_filters 
                    WHERE is_active = 1
                ''')
                results = cursor.fetchall()
                return [row[0] for row in results]
        except sqlite3.Error as e:
            logger.error(f"Ошибка получения списка пользователей: {e}")
            return []
    
    def get_active_filters_for_user(self, user_id: int) -> List[Dict]:
        """
        Получить активные фильтры пользователя.
        
        Args:
            user_id: ID пользователя
        
        Returns:
            List[Dict]: Список активных фильтров
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, filter_name, filters
                    FROM user_filters 
                    WHERE user_id = ? AND is_active = 1
                    ORDER BY created_at DESC
                ''', (user_id,))
                
                results = cursor.fetchall()
                filters_list = []
                for row in results:
                    filters_list.append({
                        'id': row[0],
                        'filter_name': row[1],
                        'filters': json.loads(row[2])
                    })
                return filters_list
        except (sqlite3.Error, json.JSONDecodeError) as e:
            logger.error(f"Ошибка получения активных фильтров: {e}")
            return []
