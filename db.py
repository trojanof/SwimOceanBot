# db.py
import sqlite3
import os
from settings import DATA_DIR

DB_PATH = os.path.join(DATA_DIR, 'messages_ledger.db')


def get_connection():
    """Создает подключение с таймаутом ожидания и авто-созданием папки"""
    os.makedirs(DATA_DIR, exist_ok=True)
    # timeout=20.0 заставляет SQLite ждать освобождения файла до 20 секунд вместо краша
    return sqlite3.connect(DB_PATH, timeout=20.0)


def init_db():
    """Инициализация базы и включение многопоточного режима WAL"""
    with get_connection() as conn:
        cursor = conn.cursor()
        # Включаем режим WAL (Write-Ahead Logging) для защиты от конфликтов потоков
        cursor.execute('PRAGMA journal_mode=WAL;')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                message_id INTEGER PRIMARY KEY,
                chat_id INTEGER,
                user_id TEXT,
                date_str TEXT,
                meters INTEGER
            )
        ''')
        conn.commit()
    print("✅ База данных SQLite успешно инициализирована в режиме WAL.")


def save_message(message_id, chat_id, user_id, date_str, meters):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO messages (message_id, chat_id, user_id, date_str, meters)
            VALUES (?, ?, ?, ?, ?)
        ''', (message_id, chat_id, str(user_id), date_str, int(meters)))
        conn.commit()


def get_old_meters(message_id, chat_id):
    """Возвращает старое количество метров или None"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT meters FROM messages WHERE message_id = ? AND chat_id = ?',
                       (message_id, chat_id))
        row = cursor.fetchone()
        return row[0] if row else None


def get_workouts_count(user_id, date_str):
    """Считает количество тренировок пользователя за конкретную дату"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM messages WHERE user_id = ? AND date_str = ?',
                       (str(user_id), date_str))
        row = cursor.fetchone()
        return row[0] if row else 0
