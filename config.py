import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('TOKEN')
MANAGER_CHAT_ID = os.getenv('MANAGER_CHAT_ID', '')
INSTRUCTORS_CHAT_ID = os.getenv('INSTRUCTORS_CHAT_ID', '')
GUIDES_CHAT_ID = os.getenv('GUIDES_CHAT_ID', '')

# Яндекс
YANDEX_API_KEY = os.getenv('YANDEX_API_KEY', '')
YANDEX_FOLDER_ID = os.getenv('YANDEX_FOLDER_ID', '')

# YooKassa
YOOKASSA_SHOP_ID = os.getenv('YOOKASSA_SHOP_ID', '')
YOOKASSA_SECRET_KEY = os.getenv('YOOKASSA_SECRET_KEY', '')

# Настройки оплаты
SBP_ACCOUNT = '40817810099910004312'
SBP_BANK_NAME = 'Сбербанк'
SBP_BIC = '044525225'
SBP_PAYMENT_URL = "https://qr.nspk.ru/AS1A00063410CST79ORB7PICRTTFK58P?type=01&bank=100000000111&crc=879D"

# Цены
HOTEL_PRICE_PER_NIGHT = 10000
INSTRUCTOR_COMMISSION = 10
GUIDE_COMMISSION = 10
EXCURSION_ACCESS_PRICE = 500
EXCURSION_COMMISSION = 5
EXCURSION_GROUP_DAYS_RANGE = 5

# Таймеры
OFFER_EXPIRATION_HOURS = 48

# AI настройки
AI_RESPONSE_TIMEOUT = 90

if not TOKEN:
    print("❌ Ошибка: Токен не найден!")
    print("Убедитесь, что файл .env существует и содержит переменную TOKEN")
    exit(1)

if not YANDEX_API_KEY:
    print("⚠️ Внимание: YANDEX_API_KEY не указан! Бот не будет отвечать на вопросы.")

if not YOOKASSA_SHOP_ID or not YOOKASSA_SECRET_KEY:
    print("⚠️ Внимание: YOOKASSA_SHOP_ID или YOOKASSA_SECRET_KEY не указаны! Оплата не будет работать.")

if not MANAGER_CHAT_ID:
    print("⚠️ Внимание: MANAGER_CHAT_ID не указан!")
    
if not INSTRUCTORS_CHAT_ID:
    print("⚠️ Внимание: INSTRUCTORS_CHAT_ID не указан!")
    
if not GUIDES_CHAT_ID:
    print("⚠️ Внимание: GUIDES_CHAT_ID не указан!")