#!/usr/bin/env python3
"""
Скрипт для автоматической настройки .env файла
"""

import os
import sys
from pathlib import Path


def get_bot_token() -> str:
    """Запрашивает токен бота у пользователя"""
    print("\n🔑 Настройка токена бота")
    print("=" * 50)
    print("1. Откройте @BotFather в Telegram")
    print("2. Отправьте команду /newbot")
    print("3. Следуйте инструкциям для создания бота")
    print("4. Скопируйте полученный токен")
    print("=" * 50)
    
    while True:
        token = input("\nВведите токен бота: ").strip()
        if not token:
            print("❌ Токен не может быть пустым!")
            continue
        
        if not token.startswith("5") or len(token) < 40:
            print("❌ Неверный формат токена! Токен должен начинаться с '5' и быть длинным")
            continue
        
        print("✅ Токен принят!")
        return token


def get_admin_ids() -> list[int]:
    """Запрашивает ID администраторов"""
    print("\n👤 Настройка администраторов")
    print("=" * 50)
    print("1. Откройте @userinfobot в Telegram")
    print("2. Отправьте любое сообщение боту")
    print("3. Скопируйте ваш ID (число)")
    print("4. Можно добавить несколько администраторов через запятую")
    print("=" * 50)
    
    while True:
        admin_input = input("\nВведите ID администратора(ов) через запятую: ").strip()
        if not admin_input:
            print("❌ ID не может быть пустым!")
            continue
        
        try:
            admin_ids = []
            for part in admin_input.split(","):
                part = part.strip()
                if part:
                    admin_id = int(part)
                    if admin_id <= 0:
                        raise ValueError("ID должен быть положительным числом")
                    admin_ids.append(admin_id)
            
            if not admin_ids:
                print("❌ Не указан ни один ID!")
                continue
            
            print(f"✅ Добавлено администраторов: {len(admin_ids)}")
            return admin_ids
            
        except ValueError as e:
            print(f"❌ Ошибка: {e}")
            print("Убедитесь, что введены только числа, разделенные запятыми")


def get_timezone() -> str:
    """Запрашивает часовой пояс"""
    print("\n⏰ Настройка часового пояса")
    print("=" * 50)
    print("Введите часовой пояс в формате Continent/City")
    print("Примеры: Europe/Moscow, America/New_York, Asia/Tokyo")
    print("По умолчанию: Europe/Moscow")
    print("=" * 50)
    
    timezone = input("\nВведите часовой пояс (или Enter для пропуска): ").strip()
    if not timezone:
        timezone = "Europe/Moscow"
        print(f"✅ Используется часовой пояс по умолчанию: {timezone}")
    else:
        print(f"✅ Установлен часовой пояс: {timezone}")
    
    return timezone


def get_database_path() -> str:
    """Автоматически определяет путь к базе данных"""
    # Получаем текущую директорию скрипта
    current_dir = Path(__file__).parent.absolute()
    db_path = current_dir / "bot.db"
    
    print(f"\n🗄️ Путь к базе данных: {db_path}")
    print("✅ Путь определен автоматически")
    
    return str(db_path)


def create_env_file(bot_token: str, admin_ids: list[int], timezone: str, database_path: str):
    """Создает .env файл с указанными параметрами"""
    env_content = f"""# Telegram Bot Token (получите у @BotFather)
BOT_TOKEN={bot_token}

# ID администраторов (через запятую)
ADMIN_IDS={','.join(map(str, admin_ids))}

# Часовой пояс
TZ={timezone}

# Путь к базе данных (по умолчанию в текущей директории)
DATABASE_PATH={database_path}
"""
    
    env_path = Path(__file__).parent / ".env"
    
    try:
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(env_content)
        
        print(f"\n✅ Файл .env создан: {env_path}")
        return True
        
    except Exception as e:
        print(f"\n❌ Ошибка при создании .env файла: {e}")
        return False


def main():
    """Основная функция настройки"""
    print("🚀 Настройка Telegram Booking Bot")
    print("=" * 60)
    print("Этот скрипт поможет настроить конфигурацию бота")
    print("=" * 60)
    
    # Проверяем, существует ли уже .env файл
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        print(f"\n⚠️ Файл .env уже существует: {env_path}")
        overwrite = input("Перезаписать? (y/N): ").strip().lower()
        if overwrite != 'y':
            print("❌ Настройка отменена")
            return
    
    try:
        # Получаем все необходимые параметры
        bot_token = get_bot_token()
        admin_ids = get_admin_ids()
        timezone = get_timezone()
        database_path = get_database_path()
        
        # Создаем .env файл
        if create_env_file(bot_token, admin_ids, timezone, database_path):
            print("\n🎉 Настройка завершена успешно!")
            print("\n📋 Следующие шаги:")
            print("1. Установите зависимости: pip install -r requirements.txt")
            print("2. Протестируйте базу данных: python test_db.py")
            print("3. Запустите бота: python main.py")
            print("\n📖 Дополнительная информация в README.md")
        else:
            print("\n❌ Настройка не завершена из-за ошибки")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n❌ Настройка прервана пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Неожиданная ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
