import os
import shutil
from datetime import datetime

"""
Скрипт для очистки дубликатов и ненужных файлов в проекте Hibiny Bot
Все удаляемые файлы перемещаются в папку backup_old_files (не удаляются насовсем)
"""

# Папка проекта
PROJECT_DIR = r"C:\Users\masha\hibiny_bot"

# Папка для бэкапа
BACKUP_DIR = os.path.join(PROJECT_DIR, "backup_old_files")

# Файлы, которые НУЖНО ОСТАВИТЬ (рабочие)
KEEP_FILES_IN_ROOT = {
    "main_bot.py",
    "database.py",
    "state_manager.py",
    "states.py",
    "keyboards.py",
    "scheduler.py",
    "calendar_fixed.py",
    "config.py",
    "requirements.txt",
    ".env",
    "cleanup_bot.py",
}

# Папки, которые НУЖНО ОСТАВИТЬ
KEEP_DIRS = {
    "handlers",
    "data",
    "backup_old_files",
    "__pycache__",
}

# Файлы, которые НУЖНО ОСТАВИТЬ в папке handlers/
KEEP_FILES_IN_HANDLERS = {
    "__init__.py",
    "admin.py",
    "excursions.py",
    "expeditions.py",
    "hotel.py",
    "instructors.py",
    "main.py",
    "orders.py",
    "payment.py",
    "shop.py",
}

# Файлы-дубликаты для перемещения (из корня)
DUPLICATE_FILES_IN_ROOT = {
    "bot.py",
    "fixed_bot.py",
    "simple_bot.py",
    "simple_working_bot.py",
    "test_bot.py",
    "calendar_simple.py",
    "calendar_utils.py",
    "calendar_widget.py",
    "check_db.py",
    "check_token.py",
    "create_db.py",
    "migrate.py",
    "update_db.py",
    "make_admin.py",
    "add_admin.py",
    "instructors_chat.py",
    "keyboard.py",
    "orders.py",
    "utils.py",
    "simple_config.py",
    "simple_database.py",
    "requirements_simple.py",
    ".env.txt",
}

# Текстовые файлы-дубликаты для перемещения
DUPLICATE_TXT_FILES = {
    "Открыть cd CUsersmashahibiny_bot.txt",
    "Продолжаем создание чат бота из это.txt",
    "Р БОТ С МАГАЗИНОМ.txt",
    "Работающая версия с админкой статист. Те.txt",
    "Работающая версия ЭКСКУРСИИ инструктор отель. Те.txt",
    "Работающий БОТ ОСНОВНОЕ.txt",
    "Сейчас.txt",
    "ЧАТ БОТ С АДМИНКОЙ ПОЧТИ ПОЛНОЙ 2.txt",
    "ЧАТ БОТ С АДМИНКОЙ ПОЧТИ ПОЛНОЙ.txt",
    "# ТЕХНИЧЕСКАЯ ДОКУМЕНТАЦИЯ ЧАТ-БОТА.txt",
    "admin.txt",
}


def create_backup_dir():
    """Создаёт папку для бэкапа"""
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
        print(f"✅ Создана папка: {BACKUP_DIR}")
    else:
        print(f"📁 Папка для бэкапа уже существует: {BACKUP_DIR}")


def move_file(file_path, backup_path):
    """Перемещает файл в папку бэкапа"""
    try:
        shutil.move(file_path, backup_path)
        print(f"   📦 Перемещён: {os.path.basename(file_path)}")
        return True
    except Exception as e:
        print(f"   ❌ Ошибка при перемещении {file_path}: {e}")
        return False


def cleanup_root():
    """Очищает корневую папку от дубликатов"""
    print("\n" + "=" * 60)
    print("🗂️  ПРОВЕРКА КОРНЕВОЙ ПАПКИ")
    print("=" * 60)
    
    moved_count = 0
    
    for filename in os.listdir(PROJECT_DIR):
        file_path = os.path.join(PROJECT_DIR, filename)
        
        if os.path.isdir(file_path):
            continue
        
        if filename in KEEP_FILES_IN_ROOT:
            continue
        
        if filename.endswith(".pyc"):
            continue
        
        if filename in DUPLICATE_FILES_IN_ROOT:
            backup_path = os.path.join(BACKUP_DIR, filename)
            if move_file(file_path, backup_path):
                moved_count += 1
            continue
        
        if filename in DUPLICATE_TXT_FILES:
            backup_path = os.path.join(BACKUP_DIR, filename)
            if move_file(file_path, backup_path):
                moved_count += 1
            continue
        
        if filename.endswith(".py") or filename.endswith(".txt"):
            print(f"   ⚠️ НЕИЗВЕСТНЫЙ ФАЙЛ: {filename}")
    
    print(f"\n📊 Перемещено файлов из корня: {moved_count}")


def cleanup_handlers():
    """Очищает папку handlers/ от дубликатов"""
    print("\n" + "=" * 60)
    print("🗂️  ПРОВЕРКА ПАПКИ HANDLERS")
    print("=" * 60)
    
    handlers_dir = os.path.join(PROJECT_DIR, "handlers")
    
    if not os.path.exists(handlers_dir):
        print("❌ Папка handlers не найдена!")
        return
    
    moved_count = 0
    
    for filename in os.listdir(handlers_dir):
        file_path = os.path.join(handlers_dir, filename)
        
        if os.path.isdir(file_path):
            continue
        
        if filename in KEEP_FILES_IN_HANDLERS:
            continue
        
        if filename.endswith(".py"):
            if filename == "scheduler.py":
                print(f"   ⚠️ НЕПРАВИЛЬНЫЙ ФАЙЛ: {filename} (должен быть в корне, не в handlers!)")
            
            backup_path = os.path.join(BACKUP_DIR, filename)
            if move_file(file_path, backup_path):
                moved_count += 1
    
    print(f"\n📊 Перемещено файлов из handlers: {moved_count}")


def show_remaining_files():
    """Показывает, какие файлы остались в проекте"""
    print("\n" + "=" * 60)
    print("📋 ОСТАВШИЕСЯ ФАЙЛЫ В ПРОЕКТЕ")
    print("=" * 60)
    
    print("\n📁 Корневая папка:")
    for filename in sorted(os.listdir(PROJECT_DIR)):
        file_path = os.path.join(PROJECT_DIR, filename)
        if os.path.isfile(file_path) and not filename.startswith("cleanup"):
            if filename.endswith(".py") or filename == ".env" or filename.endswith(".txt"):
                if filename not in DUPLICATE_FILES_IN_ROOT and filename not in DUPLICATE_TXT_FILES:
                    print(f"   ✅ {filename}")
    
    handlers_dir = os.path.join(PROJECT_DIR, "handlers")
    if os.path.exists(handlers_dir):
        print("\n📁 Папка handlers/:")
        for filename in sorted(os.listdir(handlers_dir)):
            file_path = os.path.join(handlers_dir, filename)
            if os.path.isfile(file_path) and filename.endswith(".py"):
                print(f"   ✅ {filename}")


def main():
    """Главная функция"""
    print("=" * 60)
    print("🧹 СКРИПТ ОЧИСТКИ ПРОЕКТА HIBINY BOT")
    print("=" * 60)
    print(f"📂 Папка проекта: {PROJECT_DIR}")
    print(f"📦 Папка бэкапа: {BACKUP_DIR}")
    print("\n⚠️  ВНИМАНИЕ: Файлы будут ПЕРЕМЕЩЕНЫ в папку бэкапа, а не удалены.")
    print("   При необходимости их можно вернуть обратно.")
    print("\n" + "=" * 60)
    
    create_backup_dir()
    cleanup_root()
    cleanup_handlers()
    show_remaining_files()
    
    print("\n" + "=" * 60)
    print("✅ ОЧИСТКА ЗАВЕРШЕНА!")
    print("=" * 60)
    print("\n💡 Чтобы проверить работу бота, выполните:")
    print("   cd C:\\Users\\masha\\hibiny_bot")
    print("   python main_bot.py")
    print("\n💡 Если что-то пошло не так, файлы можно вернуть из папки:")
    print(f"   {BACKUP_DIR}")


if __name__ == "__main__":
    main()