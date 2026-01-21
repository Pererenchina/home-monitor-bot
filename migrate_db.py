"""Миграция базы данных для поддержки нескольких фильтров."""
import sqlite3
import sys
import os
os.environ['PYTHONIOENCODING'] = 'utf-8'

def migrate_database():
    """Обновить структуру БД."""
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    
    try:
        # Проверяем текущую структуру
        cursor.execute('PRAGMA table_info(user_filters)')
        columns = [row[1] for row in cursor.fetchall()]
        
        # Если таблица старого формата, пересоздаем
        if 'id' not in columns or 'is_active' not in columns:
            print("Обновление структуры таблицы user_filters...")
            
            # Создаем временную таблицу с новой структурой
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_filters_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    filter_name TEXT NOT NULL DEFAULT 'Фильтр',
                    filters TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Переносим данные если они есть
            if 'filters' in columns:
                cursor.execute('SELECT user_id, filters FROM user_filters')
                old_data = cursor.fetchall()
                for user_id, filters_json in old_data:
                    cursor.execute('''
                        INSERT INTO user_filters_new (user_id, filter_name, filters, is_active)
                        VALUES (?, ?, ?, 1)
                    ''', (user_id, 'Фильтр', filters_json))
            
            # Удаляем старую таблицу
            cursor.execute('DROP TABLE IF EXISTS user_filters')
            
            # Переименовываем новую таблицу
            cursor.execute('ALTER TABLE user_filters_new RENAME TO user_filters')
            
            # Создаем индекс
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_user_filters_user_id 
                ON user_filters(user_id)
            ''')
            
            conn.commit()
            print("OK: База данных успешно обновлена!")
        else:
            print("OK: Структура БД уже актуальна")
            
    except Exception as e:
        print(f"ERROR: Ошибка миграции: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()

if __name__ == '__main__':
    migrate_database()
