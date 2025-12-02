import telebot
from telebot import types
import json
import os
import re
import uuid
import time
import sys
import threading
from flask import Flask, request

# ========== КОНФИГУРАЦИЯ ==========
# 🔧 Для Render.com переменные берутся из окружения

# Получаем значения из переменных окружения
TOKEN = os.environ.get('TOKEN', '')
MANAGER_CHAT_ID = os.environ.get('MANAGER_CHAT_ID', '')
INSTRUCTORS_CHAT_ID = os.environ.get('INSTRUCTORS_CHAT_ID', '')
EXCURSIONS_CHAT_ID = os.environ.get('EXCURSIONS_CHAT_ID', '')

# 🔧 Для локальной работы (если не на Render):
# Раскомментируйте эти строки и вставьте свои значения:
# TOKEN = '8534033828:AAHSPqujxmfLjcKw-551GrYEt2j8Hj92IzQ'
# MANAGER_CHAT_ID = '6091836352'
# INSTRUCTORS_CHAT_ID = '-1003431251566'
# EXCURSIONS_CHAT_ID = '-1003489190945'

# ========== ПРОВЕРКА КОНФИГУРАЦИИ ==========

if not TOKEN:
    print("❌ ОШИБКА: Токен бота не задан!")
    print("Добавьте токен в переменную TOKEN в Render.com")
    print("Render: Dashboard → hibiny-bot → Environment")
    print("Локально: раскомментируйте TOKEN в коде")
    sys.exit(1)

# ========== СОЗДАНИЕ БОТА ==========

bot = telebot.TeleBot(TOKEN)

# Путь к файлу данных
if 'RENDER' in os.environ:
    # На Render
    DATA_DIR = '/var/data'
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
else:
    # На локальном компьютере
    DATA_DIR = os.path.dirname(os.path.abspath(__file__))

BOOKINGS_FILE = os.path.join(DATA_DIR, 'bookings.json')

# Словари для состояний
user_states = {}
temp_data = {}
editing_states = {}

print("=" * 60)
print("🏔️ БОТ ДЛЯ БРОНИРОВАНИЯ ХИБИНЫ")
print("=" * 60)
print(f"📁 Папка данных: {DATA_DIR}")
print(f"💾 Файл бронирований: {BOOKINGS_FILE}")
print(f"👔 Менеджер: {MANAGER_CHAT_ID}")
print(f"🎿 Инструкторы: {INSTRUCTORS_CHAT_ID}")
print(f"🗺️ Экскурсии: {EXCURSIONS_CHAT_ID}")
print("=" * 60)

# ========== ВЕБ-СЕРВЕР ДЛЯ RENDER ==========

# Render требует, чтобы приложение слушало порт
# Создаем простой Flask сервер для проверки здоровья
app = Flask(__name__)

@app.route('/')
def home():
    return "🏔️ Бот для бронирования Хибины работает! ✅"

@app.route('/health')
def health():
    return "OK", 200

def run_web_server():
    """Запуск веб-сервера для Render"""
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ДАННЫМИ ==========

def load_bookings():
    """Загружает все бронирования из файла"""
    try:
        if os.path.exists(BOOKINGS_FILE):
            with open(BOOKINGS_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    return json.loads(content)
        return {}
    except Exception as e:
        print(f"❌ Ошибка загрузки: {e}")
        return {}

def save_bookings(bookings):
    """Сохраняет бронирования в файл"""
    try:
        with open(BOOKINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(bookings, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")
        return False

def log(message, level="INFO"):
    """Логирование с временной меткой"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")

# ========== ФУНКЦИИ УВЕДОМЛЕНИЙ ==========

def notify_manager(booking_data, user_id=None):
    """Отправляет полное уведомление менеджеру"""
    try:
        user_link = f"tg://user?id={user_id}" if user_id else "Неизвестно"
        
        message = "🔔 <b>НОВОЕ БРОНИРОВАНИЕ!</b>\n\n"
        message += f"👤 <b>Клиент:</b> {booking_data.get('name', 'Не указано')}\n"
        message += f"🔗 <b>Ссылка:</b> <a href='{user_link}'>Написать в Telegram</a>\n"
        message += f"📞 <b>Телефон:</b> {booking_data.get('contact', 'Не указано')}\n"
        message += f"📝 <b>Услуга:</b> {booking_data.get('service', 'Не указано')}\n"
        message += f"📅 <b>Дата:</b> {booking_data.get('date', 'Не указано')}\n"
        
        # Детали услуги
        if booking_data.get('service') == '🏨 Бабл Отель':
            message += f"🛏️ <b>Ночей:</b> {booking_data.get('nights', 'Не указано')}\n"
            message += f"💰 <b>Примерная стоимость:</b> {int(booking_data.get('nights', 1)) * 5000} руб.\n"
        
        elif booking_data.get('service') == '🚗 Трансфер':
            message += f"👥 <b>Человек:</b> {booking_data.get('people', 'Не указано')}\n"
            message += f"📍 <b>Маршрут:</b> {booking_data.get('from', '?')} → {booking_data.get('to', '?')}\n"
            message += f"💰 <b>Примерная стоимость:</b> {int(booking_data.get('people', 1)) * 1500} руб.\n"
        
        elif booking_data.get('service') == '👨‍🏫 Инструктор':
            message += f"🎿 <b>Уровень:</b> {booking_data.get('level', 'Не указано')}\n"
            message += f"👥 <b>Тип:</b> {booking_data.get('group_type', 'Не указано')}\n"
            if booking_data.get('group_type') == '👥 Группа':
                message += f"👥 <b>Размер группы:</b> {booking_data.get('group_size', 'Не указано')}\n"
            message += f"⏱️ <b>Часов:</b> {booking_data.get('hours', 'Не указано')}\n"
            hours = int(booking_data.get('hours', 2))
            cost = hours * 2000
            if booking_data.get('group_type') == '👥 Группа':
                cost *= 1.5
            message += f"💰 <b>Примерная стоимость:</b> {cost} руб.\n"
        
        elif booking_data.get('service') == '🗺️ Экскурсия':
            message += f"🗺️ <b>Тип:</b> {booking_data.get('excursion_type', 'Не указано')}\n"
            message += f"👥 <b>Человек:</b> {booking_data.get('people', 'Не указано')}\n"
            people = int(booking_data.get('people', 1))
            cost = people * 2500
            if booking_data.get('excursion_type') == 'Снегоход':
                cost += 5000
            elif booking_data.get('excursion_type') == 'Айсфлоатинг':
                cost += 3000
            elif booking_data.get('excursion_type') == 'Териберка':
                cost += 10000
            message += f"💰 <b>Примерная стоимость:</b> {cost} руб.\n"
        
        elif booking_data.get('service') == '🧊 Экспедиция в Арктику':
            message += f"👥 <b>Человек:</b> {booking_data.get('people', 'Не указано')}\n"
            message += f"💰 <b>Примерная стоимость:</b> от 150,000 руб./чел.\n"
        
        message += f"\n🆔 <b>ID бронирования:</b> {booking_data.get('id', 'Не указано')}"
        message += f"\n📊 <b>Статус:</b> {booking_data.get('payment_status', '❌ Не оплачено')}"
        
        bot.send_message(MANAGER_CHAT_ID, message, parse_mode='HTML')
        log(f"Уведомление отправлено менеджеру")
        
    except Exception as e:
        log(f"Ошибка уведомления менеджера: {e}", "ERROR")

def notify_instructors(booking_data):
    """Уведомление для чата инструкторов (без контактов)"""
    try:
        if booking_data.get('service') != '👨‍🏫 Инструктор':
            return
            
        message = "🎿 <b>НОВОЕ БРОНИРОВАНИЕ ИНСТРУКТОРА</b>\n\n"
        message += f"📅 <b>Дата:</b> {booking_data.get('date', 'Не указано')}\n"
        message += f"🎿 <b>Уровень:</b> {booking_data.get('level', 'Не указано')}\n"
        message += f"👥 <b>Тип:</b> {booking_data.get('group_type', 'Не указано')}\n"
        
        if booking_data.get('group_type') == '👥 Группа':
            message += f"👥 <b>Размер группы:</b> {booking_data.get('group_size', 'Не указано')}\n"
        
        message += f"⏱️ <b>Часов:</b> {booking_data.get('hours', 'Не указано')}\n"
        
        # Расчет стоимости для инструктора
        hours = int(booking_data.get('hours', 2))
        cost_per_hour = 2000
        total = hours * cost_per_hour
        
        if booking_data.get('group_type') == '👥 Группа':
            total *= 1.5
        
        message += f"💰 <b>Стоимость для клиента:</b> {total} руб.\n"
        message += f"🆔 <b>ID:</b> {booking_data.get('id', 'Не указано')}\n"
        message += f"📊 <b>Статус:</b> {booking_data.get('status', 'Ожидает')}\n"
        message += "\n⚠️ <i>Контакты клиента доступны только менеджеру</i>"
        
        bot.send_message(INSTRUCTORS_CHAT_ID, message, parse_mode='HTML')
        log(f"Уведомление отправлено инструкторам")
        
    except Exception as e:
        log(f"Ошибка уведомления инструкторов: {e}", "ERROR")

def notify_excursions(booking_data):
    """Уведомление для чата экскурсий (без контактов)"""
    try:
        if booking_data.get('service') != '🗺️ Экскурсия':
            return
            
        message = "🗺️ <b>НОВОЕ БРОНИРОВАНИЕ ЭКСКУРСИИ</b>\n\n"
        message += f"📅 <b>Дата:</b> {booking_data.get('date', 'Не указано')}\n"
        message += f"🗺️ <b>Тип:</b> {booking_data.get('excursion_type', 'Не указано')}\n"
        message += f"👥 <b>Человек:</b> {booking_data.get('people', 'Не указано')}\n"
        
        # Расчет стоимости
        people = int(booking_data.get('people', 1))
        cost_per_person = 2500
        total = people * cost_per_person
        
        # Доплаты
        if booking_data.get('excursion_type') == 'Снегоход':
            total += 5000
            message += f"🏍️ <b>Доплата за снегоход:</b> 5,000 руб.\n"
        elif booking_data.get('excursion_type') == 'Айсфлоатинг':
            total += 3000
            message += f"🧊 <b>Доплата за айсфлоатинг:</b> 3,000 руб.\n"
        elif booking_data.get('excursion_type') == 'Териберка':
            total += 10000
            message += f"🌊 <b>Доплата за Териберку:</b> 10,000 руб.\n"
        
        message += f"💰 <b>Стоимость для клиента:</b> {total} руб.\n"
        message += f"🆔 <b>ID:</b> {booking_data.get('id', 'Не указано')}\n"
        message += f"📊 <b>Статус:</b> {booking_data.get('status', 'Ожидает')}\n"
        message += "\n⚠️ <i>Контакты клиента доступны только менеджеру</i>"
        
        bot.send_message(EXCURSIONS_CHAT_ID, message, parse_mode='HTML')
        log(f"Уведомление отправлено экскурсоводам")
        
    except Exception as e:
        log(f"Ошибка уведомления экскурсоводов: {e}", "ERROR")

# ========== КОМАНДЫ БОТА ==========

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """Главное меню бота"""
    user_id = str(message.chat.id)
    user_states[user_id] = None
    temp_data[user_id] = {}
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('🏨 Бабл Отель'),
        types.KeyboardButton('🚗 Трансфер'),
        types.KeyboardButton('👨‍🏫 Инструктор'),
        types.KeyboardButton('🗺️ Экскурсия'),
        types.KeyboardButton('🧊 Экспедиция в Арктику'),
        types.KeyboardButton('📋 Мои бронирования')
    )
    
    welcome_text = (
        "🏔️ <b>Добро пожаловать в сервис бронирования Хибины!</b>\n\n"
        "Я помогу вам забронировать:\n"
        "• 🏨 Бабл Отель - уютное размещение\n"
        "• 🚗 Трансфер - комфортная дорога\n"
        "• 👨‍🏫 Инструктор - обучение катанию\n"
        "• 🗺️ Экскурсии - интересные маршруты\n"
        "• 🧊 Экспедиции - приключения в Арктике\n\n"
        "<i>Выберите услугу или посмотрите ваши бронирования:</i>"
    )
    
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup, parse_mode='HTML')
    log(f"Новый пользователь: {user_id}")

@bot.message_handler(commands=['getid'])
def get_chat_id(message):
    """Получение ID чата"""
    chat_id = message.chat.id
    chat_title = message.chat.title or "Личные сообщения"
    
    response = (
        f"🔍 <b>ИНФОРМАЦИЯ О ЧАТЕ</b>\n\n"
        f"🏷️ <b>Название:</b> {chat_title}\n"
        f"🆔 <b>Chat ID:</b> <code>{chat_id}</code>\n\n"
    )
    
    if chat_id < 0:
        response += "✅ <b>Это групповой чат/канал</b>\n"
        if "инструктор" in chat_title.lower():
            response += "📋 Скопируйте ID и вставьте в: INSTRUCTORS_CHAT_ID"
        elif "экскурс" in chat_title.lower():
            response += "📋 Скопируйте ID и вставьте в: EXCURSIONS_CHAT_ID"
        else:
            response += "📋 Скопируйте ID и используйте как MANAGER_CHAT_ID"
    else:
        response += "👤 <b>Это личные сообщения</b>\n"
        response += "📋 Этот ID можно использовать как MANAGER_CHAT_ID"
    
    bot.send_message(chat_id, response, parse_mode='HTML')
    log(f"Пользователь запросил ID чата: {chat_id}")

@bot.message_handler(commands=['admin'])
def admin_info(message):
    """Информация для администратора"""
    bookings = load_bookings()
    total_bookings = sum(len(v) for v in bookings.values())
    
    info = (
        f"⚙️ <b>СТАТУС БОТА</b>\n\n"
        f"📊 <b>Всего бронирований:</b> {total_bookings}\n"
        f"👥 <b>Уникальных пользователей:</b> {len(bookings)}\n"
        f"📁 <b>Файл данных:</b> {BOOKINGS_FILE}\n\n"
        f"🔧 <b>Настройки:</b>\n"
        f"• Менеджер: {MANAGER_CHAT_ID if MANAGER_CHAT_ID else 'Не задан'}\n"
        f"• Инструкторы: {INSTRUCTORS_CHAT_ID if INSTRUCTORS_CHAT_ID else 'Не задан'}\n"
        f"• Экскурсии: {EXCURSIONS_CHAT_ID if EXCURSIONS_CHAT_ID else 'Не задан'}\n\n"
        f"🔄 <b>Бот работает с:</b>\n"
        f"{time.strftime('%d.%m.%Y %H:%M:%S')}"
    )
    
    bot.send_message(message.chat.id, info, parse_mode='HTML')

# ========== ОБРАБОТКА КНОПОК УСЛУГ ==========

services = {
    '🏨 Бабл Отель': {'state': 'hotel_date', 'service': '🏨 Бабл Отель'},
    '🚗 Трансфер': {'state': 'transfer_date', 'service': '🚗 Трансфер'},
    '👨‍🏫 Инструктор': {'state': 'instructor_date', 'service': '👨‍🏫 Инструктор'},
    '🗺️ Экскурсия': {'state': 'excursion_date', 'service': '🗺️ Экскурсия'},
    '🧊 Экспедиция в Арктику': {'state': 'expedition_name', 'service': '🧊 Экспедиция в Арктику'},
}

for service_text, data in services.items():
    @bot.message_handler(func=lambda msg, st=service_text: msg.text == st)
    def handle_service(message, service_text=service_text, data=data):
        user_id = str(message.chat.id)
        user_states[user_id] = data['state']
        temp_data[user_id] = {'service': data['service']}
        
        remove_keyboard = types.ReplyKeyboardRemove()
        
        questions = {
            'hotel_date': "🏨 <b>Бабл Отель</b>\n\nВведите дату заезда (например: 15.12.2024):",
            'transfer_date': "🚗 <b>Трансфер</b>\n\nВведите дату трансфера (например: 15.12.2024):",
            'instructor_date': "👨‍🏫 <b>Инструктор</b>\n\nВведите дату занятия (например: 15.12.2024):",
            'excursion_date': "🗺️ <b>Экскурсия</b>\n\nВведите дату экскурсии (например: 15.12.2024):",
            'expedition_name': "🧊 <b>Экспедиция в Арктику</b>\n\nПрофессиональные экспедиции по Арктике проходят 2 раза в год.\nОставьте свои контакты и наш менеджер вышлет информацию о предстоящем путешествии.\n\nВведите ваше имя:"
        }
        
        bot.send_message(message.chat.id, questions[data['state']], 
                        reply_markup=remove_keyboard, parse_mode='HTML')
        log(f"Пользователь {user_id} начал бронирование: {data['service']}")

# ========== ОБРАБОТКА "МОИ БРОНИРОВАНИЯ" ==========

@bot.message_handler(func=lambda message: message.text == '📋 Мои бронирования')
def show_bookings(message):
    """Показать бронирования пользователя"""
    user_id = str(message.chat.id)
    bookings = load_bookings()
    user_bookings = bookings.get(user_id, [])
    
    if not user_bookings:
        bot.send_message(message.chat.id, "📭 У вас пока нет бронирований.")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    for i, booking in enumerate(user_bookings):
        btn_text = f"{i+1}. {booking['service']} - {booking.get('date', 'дата?')}"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"view_{i}"))
    
    bot.send_message(
        message.chat.id,
        f"📋 <b>Ваши бронирования ({len(user_bookings)}):</b>\n\nВыберите для управления:",
        reply_markup=markup,
        parse_mode='HTML'
    )

# ========== СОХРАНЕНИЕ БРОНИРОВАНИЯ ==========

def save_booking(user_id):
    """Сохранение нового бронирования"""
    bookings = load_bookings()
    
    if user_id not in bookings:
        bookings[user_id] = []
    
    booking_data = temp_data[user_id].copy()
    booking_data['id'] = str(uuid.uuid4())[:8]
    booking_data['status'] = '🟡 Ожидает подтверждения'
    booking_data['payment_status'] = '❌ Не оплачено'
    booking_data['created_at'] = time.strftime("%d.%m.%Y %H:%M")
    
    bookings[user_id].append(booking_data)
    
    if save_bookings(bookings):
        # Подтверждение для клиента
        confirmation = format_confirmation(booking_data)
        
        # Сбрасываем состояние
        user_states[user_id] = None
        temp_data[user_id] = {}
        
        # Главное меню
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(
            types.KeyboardButton('🏨 Бабл Отель'),
            types.KeyboardButton('🚗 Трансфер'),
            types.KeyboardButton('👨‍🏫 Инструктор'),
            types.KeyboardButton('🗺️ Экскурсия'),
            types.KeyboardButton('🧊 Экспедиция в Арктику'),
            types.KeyboardButton('📋 Мои бронирования')
        )
        
        bot.send_message(int(user_id), confirmation, reply_markup=markup, parse_mode='HTML')
        
        # Отправляем уведомления
        notify_manager(booking_data, int(user_id))
        
        if booking_data['service'] == '👨‍🏫 Инструктор':
            notify_instructors(booking_data)
        elif booking_data['service'] == '🗺️ Экскурсия':
            notify_excursions(booking_data)
        
        log(f"Создано бронирование: {booking_data['service']} для {user_id}")
        
    else:
        bot.send_message(int(user_id), "❌ Ошибка при сохранении бронирования.")

def format_confirmation(booking_data):
    """Форматирование подтверждения бронирования"""
    service = booking_data['service']
    
    templates = {
        '🏨 Бабл Отель': (
            f"✅ <b>Бабл Отель - бронирование создано!</b>\n\n"
            f"📅 Дата: {booking_data.get('date')}\n"
            f"👤 Имя: {booking_data.get('name')}\n"
            f"📞 Телефон: {booking_data.get('contact')}\n"
            f"🛏️ Ночей: {booking_data.get('nights')}\n"
            f"⏰ Заезд: 14:00, Выезд: 12:00\n"
        ),
        '🚗 Трансфер': (
            f"✅ <b>Трансфер - бронирование создано!</b>\n\n"
            f"📅 Дата: {booking_data.get('date')}\n"
            f"👤 Имя: {booking_data.get('name')}\n"
            f"📞 Телефон: {booking_data.get('contact')}\n"
            f"👥 Человек: {booking_data.get('people')}\n"
            f"📍 Маршрут: {booking_data.get('from')} → {booking_data.get('to')}\n"
        ),
        '👨‍🏫 Инструктор': (
            f"✅ <b>Инструктор - бронирование создано!</b>\n\n"
            f"📅 Дата: {booking_data.get('date')}\n"
            f"👤 Имя: {booking_data.get('name')}\n"
            f"📞 Телефон: {booking_data.get('contact')}\n"
            f"🎿 Уровень: {booking_data.get('level')}\n"
            f"👥 Тип: {booking_data.get('group_type')}\n"
            f"⏱️ Часов: {booking_data.get('hours')}\n"
        ),
        '🗺️ Экскурсия': (
            f"✅ <b>Экскурсия - бронирование создано!</b>\n\n"
            f"📅 Дата: {booking_data.get('date')}\n"
            f"👤 Имя: {booking_data.get('name')}\n"
            f"📞 Телефон: {booking_data.get('contact')}\n"
            f"👥 Человек: {booking_data.get('people')}\n"
            f"🗺️ Экскурсия: {booking_data.get('excursion_type')}\n"
        ),
        '🧊 Экспедиция в Арктику': (
            f"✅ <b>Заявка на экспедицию принята!</b>\n\n"
            f"👤 Имя: {booking_data.get('name')}\n"
            f"📞 Телефон: {booking_data.get('contact')}\n"
            f"👥 Человек: {booking_data.get('people')}\n\n"
            f"🧊 Профессиональные экспедиции по Арктике проходят 2 раза в год.\n"
            f"Наш менеджер свяжется с вами и вышлет информацию о предстоящем путешествии.\n"
        )
    }
    
    confirmation = templates.get(service, "✅ Бронирование создано!")
    confirmation += f"\n🆔 ID бронирования: {booking_data['id']}"
    confirmation += f"\n📞 Мы свяжемся с вами для подтверждения!"
    
    return confirmation

# ========== ЗАПУСК БОТА ==========

def run_bot():
    """Запуск Telegram бота"""
    log("🚀 Запуск Telegram бота...")
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        log(f"❌ Ошибка в работе бота: {e}", "ERROR")
        log("🔄 Перезапуск через 5 секунд...")
        time.sleep(5)
        run_bot()

def main():
    """Основная функция запуска"""
    log("=" * 60)
    log("🏔️ БОТ ДЛЯ БРОНИРОВАНИЯ ХИБИНЫ")
    log("=" * 60)
    
    # Проверка конфигурации
    if TOKEN == 'ВАШ_ТОКЕН_ЗДЕСЬ':
        log("❌ ОШИБКА: Токен бота не установлен!", "ERROR")
        log("Добавьте TOKEN в переменные окружения на Render.com")
        log("Render: Dashboard → hibiny-bot → Environment")
        return
    
    log("✅ Конфигурация проверена")
    log(f"👔 Уведомления менеджеру: {MANAGER_CHAT_ID if MANAGER_CHAT_ID else 'Не задано'}")
    log(f"🎿 Уведомления инструкторам: {INSTRUCTORS_CHAT_ID if INSTRUCTORS_CHAT_ID else 'Не задано'}")
    log(f"🗺️ Уведомления экскурсоводам: {EXCURSIONS_CHAT_ID if EXCURSIONS_CHAT_ID else 'Не задано'}")
    log("=" * 60)
    
    # Запуск веб-сервера в отдельном потоке (для Render)
    if 'RENDER' in os.environ or 'PORT' in os.environ:
        log("🌐 Запуск веб-сервера для Render...")
        web_thread = threading.Thread(target=run_web_server, daemon=True)
        web_thread.start()
    
    # Запуск Telegram бота
    run_bot()

if __name__ == "__main__":
    main()
