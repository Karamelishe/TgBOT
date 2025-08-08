#!/usr/bin/env python3
"""
Скрипт для тестирования подключения к базе данных
"""

import asyncio
import os
from config import load_settings
from db import Database


async def test_database():
    """Тестирует подключение к базе данных"""
    try:
        settings = load_settings()
        print(f"Путь к базе данных: {settings.database_path}")
        
        # Проверяем права доступа к директории
        db_dir = os.path.dirname(settings.database_path)
        if db_dir:
            print(f"Директория базы данных: {db_dir}")
            if os.access(db_dir, os.W_OK):
                print("✅ Права на запись в директорию есть")
            else:
                print("❌ Нет прав на запись в директорию")
        
        # Тестируем подключение к базе данных
        db = Database(settings.database_path)
        await db.init()
        print("✅ Подключение к базе данных успешно")
        
        # Тестируем создание таблиц
        print("✅ Таблицы созданы/проверены")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False
    
    return True


if __name__ == "__main__":
    success = asyncio.run(test_database())
    if success:
        print("\n🎉 База данных готова к работе!")
    else:
        print("\n💥 Проблемы с базой данных")
        print("\nВозможные решения:")
        print("1. Создайте файл .env с правильными настройками")
        print("2. Убедитесь, что у процесса есть права на запись")
        print("3. Измените DATABASE_PATH в .env на доступную директорию")
