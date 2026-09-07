import os
import sqlite3

# Проверяем, существует ли файл
if os.path.exists('hibiny.db'):
    print("✅ Файл hibiny.db существует!")
    
    # Проверяем, можно ли подключиться
    try:
        conn = sqlite3.connect('hibiny.db')
        cursor = conn.cursor()
        
        # Проверяем, есть ли таблицы
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print(f"✅ База данных работает. Таблиц найдено: {len(tables)}")
        
        for table in tables:
            print(f"   - {table[0]}")
        
        conn.close()
    except Exception as e:
        print(f"❌ Ошибка подключения к базе: {e}")
else:
    print("❌ Файл hibiny.db не найден!")
    print("Запустите бота командой: py bot.py")