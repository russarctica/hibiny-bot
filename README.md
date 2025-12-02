import telebot
from telebot import types
import json
import os
import re
import uuid

# ========== НАСТРОЙКИ ==========
# 🔧 ЗАМЕНИТЕ ЭТИ ЗНАЧЕНИЯ НА СВОИ!

# 1. ТОКЕН БОТА от Bot Father
TOKEN = '8534033828:AAHSPqujxmfLjcKw-551GrYEt2j8Hj92IzQ'

# 2. ID чата МЕНЕДЖЕРА (личный ID или группа менеджеров)
MANAGER_CHAT_ID = '6091836352'

# 3. ID чата ИНСТРУКТОРОВ (группа для инструкторов)
INSTRUCTORS_CHAT_ID = '-1003431251566'

# 4. ID чата ЭКСКУРСИЙ (группа для гидов по экскурсиям)
EXCURSIONS_CHAT_ID = '-1003489190945'

# Создаем объект бота
bot = telebot.TeleBot(TOKEN)

# ========== ПЕРЕМЕННЫЕ И ФАЙЛЫ ==========

# Путь к файлу данных
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BOOKINGS_FILE = os.path.join(SCRIPT_DIR, 'bookings.json')

# Словари для хранения состояний
user_states = {}       # Текущее состояние пользователя
temp_data = {}         # Временные данные при бронировании
editing_states = {}    # Состояния редактирования

# ========== КОМАНДА ДЛЯ ПОЛУЧЕНИЯ ID ==========

@bot.message_handler(commands=['getid'])
def get_chat_id(message):
    """
    Команда /getid - показывает ID текущего чата
    Используйте в каждом чате, чтобы получить его ID
    """
    user_id = message.from_user.id
    username = message.from_user.username
    chat_id = message.chat.id
    chat_type = message.chat.type
    
    # Определяем тип чата
    if chat_type == 'private':
        chat_type_ru = "личные сообщения"
        chat_title = f"@{username}" if username else f"ID: {user_id}"
    elif chat_type == 'group':
        chat_type_ru = "группа"
        chat_title = message.chat.title or "Группа без названия"
    elif chat_type == 'supergroup':
        chat_type_ru = "супергруппа"
        chat_title = message.chat.title or "Супергруппа без названия"
    elif chat_type == 'channel':
        chat_type_ru = "канал"
        chat_title = message.chat.title or "Канал без названия"
    else:
        chat_type_ru = chat_type
        chat_title = "Неизвестный чат"
    
    # Формируем ответ
    response = (
        f"🔍 <b>ИНФОРМАЦИЯ О ЧАТЕ</b>\n\n"
        f"🏷️ <b>Название:</b> {chat_title}\n"
        f"📝 <b>Тип:</b> {chat_type_ru}\n"
        f"🆔 <b>Chat ID:</b> <code>{chat_id}</code>\n"
    )
    
    # Добавляем инструкцию
    if chat_id < 0:  # Это группа/канал
        response += f"\n✅ <b>Это групповой чат/канал</b>\n"
        response += "📋 Скопируйте ID выше и вставьте в нужную переменную:\n"
        if "инструктор" in chat_title.lower():
            response += "<code>INSTRUCTORS_CHAT_ID = 'ваш_id'</code>"
        elif "экскурс" in chat_title.lower():
            response += "<code>EXCURSIONS_CHAT_ID = 'ваш_id'</code>"
        elif "менедж" in chat_title.lower():
            response += "<code>MANAGER_CHAT_ID = 'ваш_id'</code>"
    else:  # Это личные сообщения
        response += f"\n👤 <b>Это личные сообщения</b>\n"
        response += "📋 Этот ID можно использовать для MANAGER_CHAT_ID"
    
    # Отправляем ответ
    bot.send_message(chat_id, response, parse_mode='HTML')
    
    # Выводим в консоль для удобства
    print(f"\n{'='*60}")
    print(f"📱 ПОЛУЧЕН CHAT ID ЧАТА:")
    print(f"   Название: {chat_title}")
    print(f"   Тип: {chat_type_ru}")
    print(f"   ID: {chat_id}")
    print(f"{'='*60}\n")

# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ДАННЫМИ ==========

def load_bookings():
    """Загружает все бронирования из файла"""
    try:
        if os.path.exists(BOOKINGS_FILE):
            with open(BOOKINGS_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                return json.loads(content) if content else {}
        return {}
    except Exception as e:
        print(f"❌ Ошибка загрузки бронирований: {e}")
        return {}

def save_bookings(bookings):
    """Сохраняет бронирования в файл"""
    try:
        with open(BOOKINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(bookings, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"❌ Ошибка сохранения бронирований: {e}")
        return False

# ========== ФУНКЦИИ УВЕДОМЛЕНИЙ ==========

def notify_manager(booking_data, user_id=None):
    """
    Отправляет полное уведомление менеджеру
    Со всеми контактами клиента
    """
    try:
        # Получаем информацию о пользователе
        user_info = ""
        if user_id:
            try:
                chat_info = bot.get_chat(user_id)
                username = chat_info.username
                if username:
                    user_info = f"https://t.me/{username}"
                else:
                    user_info = f"ID: {user_id}"
            except:
                user_info = f"ID: {user_id}"
        
        # Формируем сообщение
        message = "🔔 <b>НОВОЕ БРОНИРОВАНИЕ!</b>\n\n"
        message += f"👤 <b>Клиент:</b> {booking_data.get('name', 'Не указано')}\n"
        
        if user_info:
            message += f"📱 <b>Telegram:</b> {user_info}\n"
        
        message += f"📞 <b>Телефон:</b> {booking_data.get('contact', 'Не указано')}\n"
        message += f"📝 <b>Услуга:</b> {booking_data.get('service', 'Не указано')}\n"
        message += f"📅 <b>Дата:</b> {booking_data.get('date', 'Не указано')}\n"
        
        # Детали в зависимости от услуги
        if booking_data.get('service') == '🏨 Бабл Отель':
            message += f"🛏️ <b>Ночей:</b> {booking_data.get('nights', 'Не указано')}\n"
            # Расчет стоимости
            nights = int(booking_data.get('nights', 1))
            cost = nights * 5000  # 5000 руб за ночь
            message += f"💰 <b>Стоимость:</b> {cost} руб.\n"
            
        elif booking_data.get('service') == '🚗 Трансфер':
            message += f"👥 <b>Человек:</b> {booking_data.get('people', 'Не указано')}\n"
            message += f"📍 <b>Откуда:</b> {booking_data.get('from', 'Не указано')}\n"
            message += f"📍 <b>Куда:</b> {booking_data.get('to', 'Не указано')}\n"
            # Расчет стоимости
            people = int(booking_data.get('people', 1))
            cost = people * 1500  # 1500 руб с человека
            message += f"💰 <b>Стоимость:</b> {cost} руб.\n"
            
        elif booking_data.get('service') == '👨‍🏫 Инструктор':
            message += f"🎿 <b>Уровень:</b> {booking_data.get('level', 'Не указано')}\n"
            message += f"👥 <b>Тип:</b> {booking_data.get('group_type', 'Не указано')}\n"
            if booking_data.get('group_type') == '👥 Группа':
                message += f"👥 <b>Размер группы:</b> {booking_data.get('group_size', 'Не указано')}\n"
            message += f"⏱️ <b>Часов:</b> {booking_data.get('hours', 'Не указано')}\n"
            # Расчет стоимости
            hours = int(booking_data.get('hours', 2))
            cost = hours * 2000  # 2000 руб в час
            if booking_data.get('group_type') == '👥 Группа':
                cost *= 1.5  # Наценка 50% на группу
            message += f"💰 <b>Стоимость:</b> {cost} руб.\n"
            
        elif booking_data.get('service') == '🗺️ Экскурсия':
            message += f"🗺️ <b>Экскурсия:</b> {booking_data.get('excursion_type', 'Не указано')}\n"
            message += f"👥 <b>Человек:</b> {booking_data.get('people', 'Не указано')}\n"
            # Расчет стоимости
            people = int(booking_data.get('people', 1))
            cost = people * 2500  # 2500 руб с человека
            # Доплаты за разные экскурсии
            if booking_data.get('excursion_type') == 'Снегоход':
                cost += 5000
            elif booking_data.get('excursion_type') == 'Айсфлоатинг':
                cost += 3000
            elif booking_data.get('excursion_type') == 'Териберка':
                cost += 10000
            message += f"💰 <b>Стоимость:</b> {cost} руб.\n"
            
        elif booking_data.get('service') == '🧊 Экспедиция в Арктику':
            message += f"👥 <b>Человек:</b> {booking_data.get('people', 'Не указано')}\n"
            message += f"💵 <b>Стоимость:</b> от 150 000 руб./чел.\n"
        
        message += f"\n🆔 <b>ID бронирования:</b> {booking_data.get('id', 'Не указано')}"
        message += f"\n📊 <b>Статус оплаты:</b> {booking_data.get('payment_status', '❌ Не оплачено')}"
        
        # Отправляем менеджеру
        bot.send_message(MANAGER_CHAT_ID, message, parse_mode='HTML')
        print(f"✅ Уведомление отправлено менеджеру {MANAGER_CHAT_ID}")
        
    except Exception as e:
        print(f"❌ Ошибка уведомления менеджера: {e}")

def notify_instructors(booking_data):
    """
    Отправляет уведомление в чат инструкторов
    БЕЗ контактов клиента, но с расчетом стоимости
    """
    try:
        if booking_data.get('service') != '👨‍🏫 Инструктор':
            return
            
        message = "🎿 <b>НОВОЕ БРОНИРОВАНИЕ ИНСТРУКТОРА</b>\n\n"
        message += f"📅 <b>Дата:</b> {booking_data.get('date', 'Не указано')}\n"
        message += f"🎿 <b>Уровень катания:</b> {booking_data.get('level', 'Не указано')}\n"
        message += f"👥 <b>Тип занятия:</b> {booking_data.get('group_type', 'Не указано')}\n"
        
        if booking_data.get('group_type') == '👥 Группа':
            message += f"👥 <b>Размер группы:</b> {booking_data.get('group_size', 'Не указано')} чел.\n"
        
        message += f"⏱️ <b>Длительность:</b> {booking_data.get('hours', 'Не указано')} часов\n"
        
        # Расчет стоимости (без наценок для инструктора)
        hours = int(booking_data.get('hours', 2))
        cost = hours * 2000  # Базовая стоимость
        
        message += f"💰 <b>Стоимость для клиента:</b> {cost} руб.\n"
        
        if booking_data.get('group_type') == '👥 Группа':
            message += f"💵 <b>Наценка на группу:</b> 50%\n"
            message += f"💵 <b>Итоговая стоимость:</b> {cost * 1.5} руб.\n"
        
        message += f"\n🆔 <b>ID брони:</b> {booking_data.get('id', 'Не указано')}"
        message += f"\n📊 <b>Статус:</b> {booking_data.get('status', 'Ожидает')}"
        message += f"\n\n⚠️ <i>Контакты клиента у менеджера</i>"
        
        # Отправляем в чат инструкторов
        bot.send_message(INSTRUCTORS_CHAT_ID, message, parse_mode='HTML')
        print(f"✅ Уведомление отправлено инструкторам {INSTRUCTORS_CHAT_ID}")
        
    except Exception as e:
        print(f"❌ Ошибка уведомления инструкторов: {e}")

def notify_excursions(booking_data):
    """
    Отправляет уведомление в чат экскурсий
    БЕЗ контактов клиента, но с расчетом стоимости
    """
    try:
        if booking_data.get('service') != '🗺️ Экскурсия':
            return
            
        message = "🗺️ <b>НОВОЕ БРОНИРОВАНИЕ ЭКСКУРСИИ</b>\n\n"
        message += f"📅 <b>Дата:</b> {booking_data.get('date', 'Не указано')}\n"
        message += f"🗺️ <b>Тип экскурсии:</b> {booking_data.get('excursion_type', 'Не указано')}\n"
        message += f"👥 <b>Количество человек:</b> {booking_data.get('people', 'Не указано')}\n"
        
        # Расчет стоимости
        people = int(booking_data.get('people', 1))
        cost = people * 2500  # Базовая стоимость
        
        # Доплаты за разные экскурсии
        if booking_data.get('excursion_type') == 'Снегоход':
            cost += 5000
            message += f"🏍️ <b>Доплата за снегоход:</b> 5,000 руб.\n"
        elif booking_data.get('excursion_type') == 'Айсфлоатинг':
            cost += 3000
            message += f"🧊 <b>Доплата за айсфлоатинг:</b> 3,000 руб.\n"
        elif booking_data.get('excursion_type') == 'Териберка':
            cost += 10000
            message += f"🌊 <b>Доплата за Териберку:</b> 10,000 руб.\n"
        
        message += f"💰 <b>Стоимость для клиента:</b> {cost} руб.\n"
        message += f"\n🆔 <b>ID брони:</b> {booking_data.get('id', 'Не указано')}"
        message += f"\n📊 <b>Статус:</b> {booking_data.get('status', 'Ожидает')}"
        message += f"\n\n⚠️ <i>Контакты клиента у менеджера</i>"
        
        # Отправляем в чат экскурсий
        bot.send_message(EXCURSIONS_CHAT_ID, message, parse_mode='HTML')
        print(f"✅ Уведомление отправлено экскурсоводам {EXCURSIONS_CHAT_ID}")
        
    except Exception as e:
        print(f"❌ Ошибка уведомления экскурсоводов: {e}")

# ========== МЕНЮ И КНОПКИ ==========

def main_menu():
    """Главное меню с кнопками"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('🏨 Бабл Отель'),
        types.KeyboardButton('🚗 Трансфер'),
        types.KeyboardButton('👨‍🏫 Инструктор'),
        types.KeyboardButton('🗺️ Экскурсия'),
        types.KeyboardButton('🧊 Экспедиция в Арктику'),
        types.KeyboardButton('📋 Мои бронирования')
    )
    return markup

def ski_level_menu():
    """Меню выбора уровня катания"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎿 С 0 (новичок)", callback_data="level_beginner"),
        types.InlineKeyboardButton("⛷️ Продолжающий", callback_data="level_intermediate"),
        types.InlineKeyboardButton("🎯 Карвинг", callback_data="level_carving"),
        types.InlineKeyboardButton("🏔️ Фрирайд", callback_data="level_freeride")
    )
    return markup

def group_type_menu():
    """Меню выбора типа группы"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("👤 Взрослый", callback_data="type_adult"),
        types.InlineKeyboardButton("🧒 Ребенок", callback_data="type_child"),
        types.InlineKeyboardButton("👥 Группа", callback_data="type_group")
    )
    return markup

def excursion_menu():
    """Меню выбора экскурсии"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    excursions = [
        "Северное Сияние", "Прогулка в горы", "Снегоход", "Айсфлоатинг",
        "Териберка", "Кандалакша", "Мончегорск", "Полярные Зори"
    ]
    for excursion in excursions:
        markup.add(types.InlineKeyboardButton(excursion, callback_data=f"exc_{excursion}"))
    return markup

def booking_management_menu(booking_index, user_id):
    """Меню управления бронированием"""
    bookings = load_bookings()
    user_bookings = bookings.get(str(user_id), [])
    if not user_bookings or booking_index >= len(user_bookings):
        return None
    
    booking = user_bookings[booking_index]
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # Кнопки редактирования
    buttons = [
        types.InlineKeyboardButton("📅 Дата", callback_data=f"edit_date_{booking_index}"),
        types.InlineKeyboardButton("👤 Имя", callback_data=f"edit_name_{booking_index}"),
        types.InlineKeyboardButton("📞 Телефон", callback_data=f"edit_contact_{booking_index}")
    ]
    
    # Специфические поля
    if booking['service'] == '🏨 Бабл Отель':
        buttons.append(types.InlineKeyboardButton("🛏️ Ночи", callback_data=f"edit_nights_{booking_index}"))
    elif booking['service'] == '🚗 Трансфер':
        buttons.append(types.InlineKeyboardButton("👥 Люди", callback_data=f"edit_people_{booking_index}"))
        buttons.append(types.InlineKeyboardButton("📍 Откуда", callback_data=f"edit_from_{booking_index}"))
        buttons.append(types.InlineKeyboardButton("📍 Куда", callback_data=f"edit_to_{booking_index}"))
    elif booking['service'] == '👨‍🏫 Инструктор':
        buttons.append(types.InlineKeyboardButton("🎿 Уровень", callback_data=f"edit_level_{booking_index}"))
        buttons.append(types.InlineKeyboardButton("👥 Тип", callback_data=f"edit_group_type_{booking_index}"))
        if booking.get('group_type') == '👥 Группа':
            buttons.append(types.InlineKeyboardButton("👥 Размер", callback_data=f"edit_group_size_{booking_index}"))
        buttons.append(types.InlineKeyboardButton("⏱️ Часы", callback_data=f"edit_hours_{booking_index}"))
    elif booking['service'] == '🗺️ Экскурсия':
        buttons.append(types.InlineKeyboardButton("👥 Люди", callback_data=f"edit_people_{booking_index}"))
        buttons.append(types.InlineKeyboardButton("🗺️ Тип", callback_data=f"edit_excursion_{booking_index}"))
    
    # Кнопки управления
    buttons.extend([
        types.InlineKeyboardButton("⏱️ Продлить", callback_data=f"extend_{booking_index}"),
        types.InlineKeyboardButton("💳 Оплатить", callback_data=f"pay_{booking_index}"),
        types.InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_{booking_index}")
    ])
    
    # Распределяем кнопки по 2 в ряд
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            markup.add(buttons[i], buttons[i+1])
        else:
            markup.add(buttons[i])
    
    return markup

# ========== ОСНОВНЫЕ КОМАНДЫ ==========

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """Обработчик команд /start и /help"""
    user_id = str(message.chat.id)
    user_states[user_id] = None
    temp_data[user_id] = {}
    
    welcome_text = (
        "🏔️ <b>Добро пожаловать в сервис бронирования Хибины!</b>\n\n"
        "Я помогу вам забронировать:\n"
        "🏨 Бабл Отель - уютное размещение\n"
        "🚗 Трансфер - комфортная дорога\n"
        "👨‍🏫 Инструктор - обучение катанию\n"
        "🗺️ Экскурсии - интересные маршруты\n"
        "🧊 Экспедиции - приключения в Арктике\n\n"
        "<i>Выберите услугу или посмотрите ваши бронирования:</i>"
    )
    
    bot.send_message(
        message.chat.id,
        welcome_text,
        reply_markup=main_menu(),
        parse_mode='HTML'
    )

@bot.message_handler(commands=['admin'])
def admin_info(message):
    """Показывает информацию о настройках (для администратора)"""
    admin_text = (
        "⚙️ <b>ТЕКУЩИЕ НАСТРОЙКИ БОТА</b>\n\n"
        f"🆔 <b>Ваш ID:</b> <code>{message.chat.id}</code>\n"
        f"👔 <b>Чат менеджера:</b> <code>{MANAGER_CHAT_ID}</code>\n"
        f"🎿 <b>Чат инструкторов:</b> <code>{INSTRUCTORS_CHAT_ID}</code>\n"
        f"🗺️ <b>Чат экскурсий:</b> <code>{EXCURSIONS_CHAT_ID}</code>\n\n"
        f"📁 <b>Файл данных:</b> {BOOKINGS_FILE}\n"
        f"📊 <b>Всего бронирований:</b> {sum(len(v) for v in load_bookings().values())}"
    )
    
    bot.send_message(message.chat.id, admin_text, parse_mode='HTML')

# ========== ОБРАБОТКА КНОПОК УСЛУГ ==========

@bot.message_handler(func=lambda message: message.text == '🏨 Бабл Отель')
def start_hotel_booking(message):
    """Начало бронирования отеля"""
    user_id = str(message.chat.id)
    user_states[user_id] = 'hotel_date'
    temp_data[user_id] = {'service': '🏨 Бабл Отель'}
    
    remove_keyboard = types.ReplyKeyboardRemove()
    bot.send_message(
        message.chat.id,
        "🏨 <b>Бабл Отель</b>\n\nВведите дату заезда (например: 15.12.2024):",
        reply_markup=remove_keyboard,
        parse_mode='HTML'
    )

@bot.message_handler(func=lambda message: message.text == '🚗 Трансфер')
def start_transfer_booking(message):
    """Начало бронирования трансфера"""
    user_id = str(message.chat.id)
    user_states[user_id] = 'transfer_date'
    temp_data[user_id] = {'service': '🚗 Трансфер'}
    
    remove_keyboard = types.ReplyKeyboardRemove()
    bot.send_message(
        message.chat.id,
        "🚗 <b>Трансфер</b>\n\nВведите дату трансфера (например: 15.12.2024):",
        reply_markup=remove_keyboard,
        parse_mode='HTML'
    )

@bot.message_handler(func=lambda message: message.text == '👨‍🏫 Инструктор')
def start_instructor_booking(message):
    """Начало бронирования инструктора"""
    user_id = str(message.chat.id)
    user_states[user_id] = 'instructor_date'
    temp_data[user_id] = {'service': '👨‍🏫 Инструктор'}
    
    remove_keyboard = types.ReplyKeyboardRemove()
    bot.send_message(
        message.chat.id,
        "👨‍🏫 <b>Инструктор</b>\n\nВведите дату занятия (например: 15.12.2024):",
        reply_markup=remove_keyboard,
        parse_mode='HTML'
    )

@bot.message_handler(func=lambda message: message.text == '🗺️ Экскурсия')
def start_excursion_booking(message):
    """Начало бронирования экскурсии"""
    user_id = str(message.chat.id)
    user_states[user_id] = 'excursion_date'
    temp_data[user_id] = {'service': '🗺️ Экскурсия'}
    
    remove_keyboard = types.ReplyKeyboardRemove()
    bot.send_message(
        message.chat.id,
        "🗺️ <b>Экскурсия</b>\n\nВведите дату экскурсии (например: 15.12.2024):",
        reply_markup=remove_keyboard,
        parse_mode='HTML'
    )

@bot.message_handler(func=lambda message: message.text == '🧊 Экспедиция в Арктику')
def start_expedition(message):
    """Начало заявки на экспедицию"""
    user_id = str(message.chat.id)
    user_states[user_id] = 'expedition_name'
    temp_data[user_id] = {'service': '🧊 Экспедиция в Арктику'}
    
    remove_keyboard = types.ReplyKeyboardRemove()
    bot.send_message(
        message.chat.id,
        "🧊 <b>Экспедиция в Арктику</b>\n\n"
        "Профессиональные экспедиции по Арктике проходят 2 раза в год.\n"
        "Оставьте свои контакты и наш менеджер вышлет информацию о предстоящем путешествии.\n\n"
        "Введите ваше имя:",
        reply_markup=remove_keyboard,
        parse_mode='HTML'
    )

@bot.message_handler(func=lambda message: message.text == '📋 Мои бронирования')
def show_my_bookings(message):
    """Показывает список бронирований пользователя"""
    user_id = str(message.chat.id)
    bookings = load_bookings()
    user_bookings = bookings.get(user_id, [])
    
    if not user_bookings:
        bot.send_message(message.chat.id, "📭 У вас пока нет бронирований.")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    for i, booking in enumerate(user_bookings):
        # Создаем короткое описание
        service_icon = booking['service'][:2]  # Берем эмодзи
        date = booking.get('date', 'дата не указана')
        text = f"{service_icon} #{i+1} - {date}"
        callback_data = f"view_{i}"
        markup.add(types.InlineKeyboardButton(text, callback_data=callback_data))
    
    bot.send_message(
        message.chat.id,
        "📋 <b>Ваши бронирования:</b>\n\nВыберите бронирование для управления:",
        reply_markup=markup,
        parse_mode='HTML'
    )

# ========== ОБРАБОТКА ШАГОВ БРОНИРОВАНИЯ ==========

@bot.message_handler(func=lambda message: user_states.get(str(message.chat.id)) in [
    'hotel_date', 'transfer_date', 'instructor_date', 'excursion_date'
])
def process_date(message):
    """Обработка ввода даты"""
    user_id = str(message.chat.id)
    state = user_states[user_id]
    
    # Проверяем формат даты
    if not re.match(r'\d{2}\.\d{2}\.\d{4}', message.text):
        bot.send_message(message.chat.id, "❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ")
        return
    
    temp_data[user_id]['date'] = message.text
    
    # Переходим к следующему шагу
    if state == 'hotel_date':
        user_states[user_id] = 'hotel_name'
        bot.send_message(message.chat.id, "Введите ваше имя:")
    elif state == 'transfer_date':
        user_states[user_id] = 'transfer_name'
        bot.send_message(message.chat.id, "Введите ваше имя:")
    elif state == 'instructor_date':
        user_states[user_id] = 'instructor_name'
        bot.send_message(message.chat.id, "Введите ваше имя:")
    elif state == 'excursion_date':
        user_states[user_id] = 'excursion_name'
        bot.send_message(message.chat.id, "Введите ваше имя:")

@bot.message_handler(func=lambda message: user_states.get(str(message.chat.id)) in [
    'hotel_name', 'transfer_name', 'instructor_name', 'excursion_name', 'expedition_name'
])
def process_name(message):
    """Обработка ввода имени"""
    user_id = str(message.chat.id)
    state = user_states[user_id]
    
    temp_data[user_id]['name'] = message.text
    
    if state == 'hotel_name':
        user_states[user_id] = 'hotel_contact'
        bot.send_message(message.chat.id, "Введите ваш номер телефона:")
    elif state == 'transfer_name':
        user_states[user_id] = 'transfer_contact'
        bot.send_message(message.chat.id, "Введите ваш номер телефона:")
    elif state == 'instructor_name':
        user_states[user_id] = 'instructor_contact'
        bot.send_message(message.chat.id, "Введите ваш номер телефона:")
    elif state == 'excursion_name':
        user_states[user_id] = 'excursion_contact'
        bot.send_message(message.chat.id, "Введите ваш номер телефона:")
    elif state == 'expedition_name':
        user_states[user_id] = 'expedition_contact'
        bot.send_message(message.chat.id, "Введите ваш номер телефона:")

@bot.message_handler(func=lambda message: user_states.get(str(message.chat.id)) in [
    'hotel_contact', 'transfer_contact', 'instructor_contact', 
    'excursion_contact', 'expedition_contact'
])
def process_contact(message):
    """Обработка ввода контактов"""
    user_id = str(message.chat.id)
    state = user_states[user_id]
    
    temp_data[user_id]['contact'] = message.text
    
    if state == 'hotel_contact':
        user_states[user_id] = 'hotel_nights'
        bot.send_message(message.chat.id, "Введите количество суток:")
    elif state == 'transfer_contact':
        user_states[user_id] = 'transfer_people'
        bot.send_message(message.chat.id, "Введите количество человек:")
    elif state == 'instructor_contact':
        user_states[user_id] = 'instructor_level'
        bot.send_message(message.chat.id, "Выберите уровень катания:", reply_markup=ski_level_menu())
    elif state == 'excursion_contact':
        user_states[user_id] = 'excursion_people'
        bot.send_message(message.chat.id, "Введите количество человек:")
    elif state == 'expedition_contact':
        user_states[user_id] = 'expedition_people'
        bot.send_message(message.chat.id, "Введите количество человек:")

# Дополнительные шаги для разных услуг
@bot.message_handler(func=lambda message: user_states.get(str(message.chat.id)) == 'hotel_nights')
def process_hotel_nights(message):
    """Обработка ввода количества ночей"""
    user_id = str(message.chat.id)
    if not message.text.isdigit():
        bot.send_message(message.chat.id, "❌ Введите число")
        return
    
    temp_data[user_id]['nights'] = message.text
    save_booking(user_id)

@bot.message_handler(func=lambda message: user_states.get(str(message.chat.id)) == 'transfer_people')
def process_transfer_people(message):
    """Обработка ввода количества человек для трансфера"""
    user_id = str(message.chat.id)
    if not message.text.isdigit():
        bot.send_message(message.chat.id, "❌ Введите число")
        return
    
    temp_data[user_id]['people'] = message.text
    user_states[user_id] = 'transfer_from'
    bot.send_message(message.chat.id, "Откуда забрать? (адрес или место):")

@bot.message_handler(func=lambda message: user_states.get(str(message.chat.id)) == 'transfer_from')
def process_transfer_from(message):
    """Обработка ввода места отправления"""
    user_id = str(message.chat.id)
    temp_data[user_id]['from'] = message.text
    user_states[user_id] = 'transfer_to'
    bot.send_message(message.chat.id, "Куда отвезти? (адрес или место):")

@bot.message_handler(func=lambda message: user_states.get(str(message.chat.id)) == 'transfer_to')
def process_transfer_to(message):
    """Обработка ввода места назначения"""
    user_id = str(message.chat.id)
    temp_data[user_id]['to'] = message.text
    save_booking(user_id)

@bot.message_handler(func=lambda message: user_states.get(str(message.chat.id)) == 'excursion_people')
def process_excursion_people(message):
    """Обработка ввода количества человек для экскурсии"""
    user_id = str(message.chat.id)
    if not message.text.isdigit():
        bot.send_message(message.chat.id, "❌ Введите число")
        return
    
    temp_data[user_id]['people'] = message.text
    bot.send_message(message.chat.id, "Выберите тип экскурсии:", reply_markup=excursion_menu())

@bot.message_handler(func=lambda message: user_states.get(str(message.chat.id)) == 'expedition_people')
def process_expedition_people(message):
    """Обработка ввода количества человек для экспедиции"""
    user_id = str(message.chat.id)
    if not message.text.isdigit():
        bot.send_message(message.chat.id, "❌ Введите число")
        return
    
    temp_data[user_id]['people'] = message.text
    save_booking(user_id)

# ========== INLINE КНОПКИ ==========

@bot.callback_query_handler(func=lambda call: call.data.startswith('level_'))
def handle_ski_level(call):
    """Обработка выбора уровня катания"""
    user_id = str(call.message.chat.id)
    level_map = {
        'level_beginner': '🎿 С 0 (новичок)',
        'level_intermediate': '⛷️ Продолжающий',
        'level_carving': '🎯 Карвинг',
        'level_freeride': '🏔️ Фрирайд'
    }
    
    temp_data[user_id]['level'] = level_map[call.data]
    user_states[user_id] = 'instructor_group_type'
    
    bot.edit_message_text(
        "Выберите тип занятия:",
        call.message.chat.id,
        call.message.message_id
    )
    bot.send_message(call.message.chat.id, "Выберите тип:", reply_markup=group_type_menu())

@bot.callback_query_handler(func=lambda call: call.data.startswith('type_'))
def handle_group_type(call):
    """Обработка выбора типа группы"""
    user_id = str(call.message.chat.id)
    type_map = {
        'type_adult': '👤 Взрослый',
        'type_child': '🧒 Ребенок',
        'type_group': '👥 Группа'
    }
    
    temp_data[user_id]['group_type'] = type_map[call.data]
    
    if call.data == 'type_group':
        user_states[user_id] = 'instructor_group_size'
        bot.send_message(call.message.chat.id, "Введите количество человек в группе:")
    else:
        user_states[user_id] = 'instructor_hours'
        bot.send_message(call.message.chat.id, "Введите количество часов (минимум 2):")

@bot.callback_query_handler(func=lambda call: call.data.startswith('exc_'))
def handle_excursion_type(call):
    """Обработка выбора типа экскурсии"""
    user_id = str(call.message.chat.id)
    excursion_type = call.data.replace('exc_', '')
    temp_data[user_id]['excursion_type'] = excursion_type
    
    bot.edit_message_text(
        f"Выбрана экскурсия: {excursion_type}",
        call.message.chat.id,
        call.message.message_id
    )
    save_booking(user_id)

@bot.message_handler(func=lambda message: user_states.get(str(message.chat.id)) == 'instructor_group_size')
def process_group_size(message):
    """Обработка ввода размера группы"""
    user_id = str(message.chat.id)
    if not message.text.isdigit():
        bot.send_message(message.chat.id, "❌ Введите число")
        return
    
    temp_data[user_id]['group_size'] = message.text
    user_states[user_id] = 'instructor_hours'
    bot.send_message(message.chat.id, "Введите количество часов (минимум 2):")

@bot.message_handler(func=lambda message: user_states.get(str(message.chat.id)) == 'instructor_hours')
def process_instructor_hours(message):
    """Обработка ввода количества часов"""
    user_id = str(message.chat.id)
    if not message.text.isdigit() or int(message.text) < 2:
        bot.send_message(message.chat.id, "❌ Минимальное бронирование - 2 часа")
        return
    
    temp_data[user_id]['hours'] = message.text
    save_booking(user_id)

# ========== УПРАВЛЕНИЕ БРОНИРОВАНИЯМИ ==========

@bot.callback_query_handler(func=lambda call: call.data.startswith('view_'))
def show_booking_details(call):
    """Показывает детали бронирования"""
    user_id = str(call.message.chat.id)
    booking_index = int(call.data.split('_')[1])
    
    bookings = load_bookings()
    user_bookings = bookings.get(user_id, [])
    
    if booking_index >= len(user_bookings):
        bot.answer_callback_query(call.id, "Бронирование не найдено")
        return
    
    booking = user_bookings[booking_index]
    
    # Форматируем детали
    details = f"<b>📋 Бронирование #{booking_index + 1}</b>\n\n"
    details += f"📝 Услуга: {booking['service']}\n"
    details += f"📅 Дата: {booking.get('date', 'Не указано')}\n"
    details += f"👤 Имя: {booking.get('name', 'Не указано')}\n"
    details += f"📞 Контакты: {booking.get('contact', 'Не указано')}\n"
    
    if booking['service'] == '🏨 Бабл Отель':
        details += f"🛏️ Ночей: {booking.get('nights', 'Не указано')}\n"
    elif booking['service'] == '🚗 Трансфер':
        details += f"👥 Человек: {booking.get('people', 'Не указано')}\n"
        details += f"📍 Откуда: {booking.get('from', 'Не указано')}\n"
        details += f"📍 Куда: {booking.get('to', 'Не указано')}\n"
    elif booking['service'] == '👨‍🏫 Инструктор':
        details += f"🎿 Уровень: {booking.get('level', 'Не указано')}\n"
        details += f"👥 Тип: {booking.get('group_type', 'Не указано')}\n"
        if booking.get('group_type') == '👥 Группа':
            details += f"👥 Размер группы: {booking.get('group_size', 'Не указано')}\n"
        details += f"⏱️ Часов: {booking.get('hours', 'Не указано')}\n"
    elif booking['service'] == '🗺️ Экскурсия':
        details += f"🗺️ Тип: {booking.get('excursion_type', 'Не указано')}\n"
        details += f"👥 Человек: {booking.get('people', 'Не указано')}\n"
    
    details += f"\n💰 Статус оплаты: {booking.get('payment_status', '❌ Не оплачено')}\n"
    details += f"📊 Статус: {booking.get('status', '🟡 Ожидает')}\n"
    details += f"🆔 ID: {booking.get('id', 'Не указано')}"
    
    bot.edit_message_text(
        details,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=booking_management_menu(booking_index, user_id),
        parse_mode='HTML'
    )

# ========== РЕДАКТИРОВАНИЕ БРОНИРОВАНИЙ ==========

@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_'))
def handle_edit_request(call):
    """Обработка запроса на редактирование"""
    user_id = str(call.message.chat.id)
    parts = call.data.split('_')
    
    if len(parts) < 3:
        bot.answer_callback_query(call.id, "Ошибка запроса")
        return
    
    action = parts[1]
    booking_index = int(parts[2])
    
    # Сохраняем состояние редактирования
    editing_states[user_id] = {
        'action': action,
        'booking_index': booking_index
    }
    
    # Запрашиваем новое значение
    questions = {
        'date': "Введите новую дату (например: 15.12.2024):",
        'name': "Введите новое имя:",
        'contact': "Введите новый телефон:",
        'nights': "Введите новое количество ночей:",
        'people': "Введите новое количество человек:",
        'from': "Введите новый пункт отправления:",
        'to': "Введите новый пункт назначения:",
        'level': "Выберите новый уровень катания:",
        'group_type': "Выберите новый тип занятия:",
        'group_size': "Введите новый размер группы:",
        'hours': "Введите новое количество часов (минимум 2):",
        'excursion': "Выберите новую экскурсию:"
    }
    
    if action in questions:
        question = questions[action]
        
        # Если нужно показать меню
        if action == 'level':
            bot.send_message(call.message.chat.id, question, reply_markup=ski_level_menu())
        elif action == 'group_type':
            bot.send_message(call.message.chat.id, question, reply_markup=group_type_menu())
        elif action == 'excursion':
            bot.send_message(call.message.chat.id, question, reply_markup=excursion_menu())
        else:
            bot.send_message(call.message.chat.id, question)
        
        bot.answer_callback_query(call.id)
    else:
        bot.answer_callback_query(call.id, "Неизвестное действие")

@bot.message_handler(func=lambda message: editing_states.get(str(message.chat.id)))
def handle_edit_input(message):
    """Обработка ввода новых данных для редактирования"""
    user_id = str(message.chat.id)
    
    if user_id not in editing_states:
        return
    
    edit_data = editing_states[user_id]
    action = edit_data['action']
    booking_index = edit_data['booking_index']
    
    # Загружаем бронирования
    bookings = load_bookings()
    user_bookings = bookings.get(user_id, [])
    
    if booking_index >= len(user_bookings):
        bot.send_message(message.chat.id, "❌ Бронирование не найдено")
        del editing_states[user_id]
        return
    
    booking = user_bookings[booking_index]
    
    # Проверяем и обновляем данные
    if action in ['date', 'name', 'contact', 'from', 'to']:
        booking[action] = message.text
    
    elif action in ['nights', 'people', 'group_size', 'hours']:
        if not message.text.isdigit():
            bot.send_message(message.chat.id, "❌ Введите число")
            return
        
        if action == 'hours' and int(message.text) < 2:
            bot.send_message(message.chat.id, "❌ Минимум 2 часа")
            return
        
        booking[action] = message.text
    
    # Сохраняем изменения
    user_bookings[booking_index] = booking
    bookings[user_id] = user_bookings
    save_bookings(bookings)
    
    # Показываем обновленное бронирование
    details = f"<b>✅ Изменения сохранены!</b>\n\n"
    details += f"📝 Услуга: {booking['service']}\n"
    details += f"📅 Дата: {booking.get('date', 'Не указано')}\n"
    details += f"👤 Имя: {booking.get('name', 'Не указано')}\n"
    details += f"📞 Контакты: {booking.get('contact', 'Не указано')}\n"
    
    bot.send_message(
        message.chat.id,
        details,
        reply_markup=booking_management_menu(booking_index, user_id),
        parse_mode='HTML'
    )
    
    # Удаляем состояние редактирования
    del editing_states[user_id]

# ========== ПРОДЛЕНИЕ, ОПЛАТА, ОТМЕНА ==========

@bot.callback_query_handler(func=lambda call: call.data.startswith('extend_'))
def handle_extend(call):
    """Обработка продления бронирования"""
    booking_index = int(call.data.split('_')[1])
    bot.answer_callback_query(call.id, "Для продления свяжитесь с менеджером")
    bot.send_message(
        call.message.chat.id,
        "📞 Для продления бронирования свяжитесь с менеджером:\n"
        "Телефон: +7 (911) 123-45-67\n"
        "Telegram: @manager_hb"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('pay_'))
def handle_payment(call):
    """Обработка оплаты"""
    booking_index = int(call.data.split('_')[1])
    bot.answer_callback_query(call.id, "Оплата временно недоступна")
    bot.send_message(
        call.message.chat.id,
        "💳 <b>Информация об оплате</b>\n\n"
        "В настоящее время оплата через бота временно недоступна.\n"
        "Для оплаты свяжитесь с менеджером:\n\n"
        "📞 Телефон: +7 (911) 123-45-67\n"
        "📱 Telegram: @manager_hb\n"
        "📧 Email: booking@hibiny.ru",
        parse_mode='HTML'
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('cancel_'))
def handle_cancel(call):
    """Обработка отмены бронирования"""
    user_id = str(call.message.chat.id)
    booking_index = int(call.data.split('_')[1])
    
    # Меню подтверждения
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Да, отменить", callback_data=f"confirm_cancel_{booking_index}"),
        types.InlineKeyboardButton("❌ Нет, оставить", callback_data="keep_booking")
    )
    
    bot.send_message(
        call.message.chat.id,
        "⚠️ Вы уверены, что хотите отменить бронирование?\n"
        "Это действие нельзя отменить.",
        reply_markup=markup
    )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_cancel_'))
def confirm_cancel(call):
    """Подтверждение отмены бронирования"""
    user_id = str(call.message.chat.id)
    booking_index = int(call.data.split('_')[2])
    
    bookings = load_bookings()
    user_bookings = bookings.get(user_id, [])
    
    if booking_index >= len(user_bookings):
        bot.answer_callback_query(call.id, "Бронирование не найдено")
        return
    
    # Удаляем бронирование
    cancelled_booking = user_bookings.pop(booking_index)
    
    if not user_bookings:
        del bookings[user_id]
    else:
        bookings[user_id] = user_bookings
    
    save_bookings(bookings)
    
    bot.send_message(call.message.chat.id, "✅ Бронирование отменено.")
    bot.answer_callback_query(call.id, "✅ Бронирование отменено")

@bot.callback_query_handler(func=lambda call: call.data == 'keep_booking')
def keep_booking(call):
    """Отказ от отмены"""
    bot.send_message(call.message.chat.id, "✅ Бронирование сохранено.")
    bot.answer_callback_query(call.id)

# ========== СОХРАНЕНИЕ НОВОГО БРОНИРОВАНИЯ ==========

def save_booking(user_id):
    """Сохранение нового бронирования и отправка уведомлений"""
    bookings = load_bookings()
    
    if user_id not in bookings:
        bookings[user_id] = []
    
    booking_data = temp_data[user_id].copy()
    booking_data['id'] = str(uuid.uuid4())[:8]
    booking_data['status'] = '🟡 Ожидает подтверждения'
    booking_data['payment_status'] = '❌ Не оплачено'
    
    bookings[user_id].append(booking_data)
    
    if save_bookings(bookings):
        # Формируем подтверждение для клиента
        service = booking_data['service']
        confirmation = f"✅ <b>{service} - бронирование создано!</b>\n\n"
        
        if service == '🏨 Бабл Отель':
            confirmation += f"📅 Дата: {booking_data.get('date')}\n"
            confirmation += f"👤 Имя: {booking_data.get('name')}\n"
            confirmation += f"📞 Телефон: {booking_data.get('contact')}\n"
            confirmation += f"🛏️ Ночей: {booking_data.get('nights')}\n"
            confirmation += f"⏰ Заезд: 14:00, Выезд: 12:00\n"
        elif service == '🚗 Трансфер':
            confirmation += f"📅 Дата: {booking_data.get('date')}\n"
            confirmation += f"👤 Имя: {booking_data.get('name')}\n"
            confirmation += f"📞 Телефон: {booking_data.get('contact')}\n"
            confirmation += f"👥 Человек: {booking_data.get('people')}\n"
            confirmation += f"📍 Откуда: {booking_data.get('from')}\n"
            confirmation += f"📍 Куда: {booking_data.get('to')}\n"
        elif service == '👨‍🏫 Инструктор':
            confirmation += f"📅 Дата: {booking_data.get('date')}\n"
            confirmation += f"👤 Имя: {booking_data.get('name')}\n"
            confirmation += f"📞 Телефон: {booking_data.get('contact')}\n"
            confirmation += f"🎿 Уровень: {booking_data.get('level')}\n"
            confirmation += f"👥 Тип: {booking_data.get('group_type')}\n"
            if booking_data.get('group_type') == '👥 Группа':
                confirmation += f"👥 Размер группы: {booking_data.get('group_size')}\n"
            confirmation += f"⏱️ Часов: {booking_data.get('hours')}\n"
            confirmation += f"ℹ️ Мин. бронирование: 2 часа\n"
        elif service == '🗺️ Экскурсия':
            confirmation += f"📅 Дата: {booking_data.get('date')}\n"
            confirmation += f"👤 Имя: {booking_data.get('name')}\n"
            confirmation += f"📞 Телефон: {booking_data.get('contact')}\n"
            confirmation += f"👥 Человек: {booking_data.get('people')}\n"
            confirmation += f"🗺️ Экскурсия: {booking_data.get('excursion_type')}\n"
        elif service == '🧊 Экспедиция в Арктику':
            confirmation += f"🧊 Экспедиция в Арктику\n\n"
            confirmation += f"👤 Имя: {booking_data.get('name')}\n"
            confirmation += f"📞 Телефон: {booking_data.get('contact')}\n"
            confirmation += f"👥 Человек: {booking_data.get('people')}\n\n"
            confirmation += f"Профессиональные экспедиции по Арктике проходят 2 раза в год.\n"
            confirmation += f"Наш менеджер свяжется с вами и вышлет информацию о предстоящем путешествии.\n\n"
            confirmation += f"Спасибо за интерес к экспедициям!"
        
        confirmation += f"\n🆔 ID бронирования: {booking_data['id']}\n"
        confirmation += f"📞 Мы свяжемся с вами для подтверждения!"
        
        # Сбрасываем состояние
        user_states[user_id] = None
        temp_data[user_id] = {}
        
        # Отправляем подтверждение клиенту
        bot.send_message(int(user_id), confirmation, reply_markup=main_menu(), parse_mode='HTML')
        
        # Отправляем уведомления
        notify_manager(booking_data, user_id=int(user_id))
        
        if service == '👨‍🏫 Инструктор':
            notify_instructors(booking_data)
        elif service == '🗺️ Экскурсия':
            notify_excursions(booking_data)
        
    else:
        bot.send_message(int(user_id), "❌ Ошибка при сохранении бронирования.", reply_markup=main_menu())

# ========== ЗАПУСК БОТА ==========

if __name__ == "__main__":
    print("=" * 60)
    print("🏔️ БОТ ДЛЯ БРОНИРОВАНИЯ ХИБИНЫ ЗАПУЩЕН!")
    print("=" * 60)
    print(f"📁 Файл данных: {BOOKINGS_FILE}")
    print(f"👔 Чат менеджера: {MANAGER_CHAT_ID}")
    print(f"🎿 Чат инструкторов: {INSTRUCTORS_CHAT_ID}")
    print(f"🗺️ Чат экскурсий: {EXCURSIONS_CHAT_ID}")
    print("=" * 60)
    print("🚀 Бот запущен и готов к работе!")
    print("👉 Используйте /start для начала")
    print("👉 Используйте /getid в чате, чтобы получить его ID")
    print("=" * 60)
    
    try:
        bot.polling(none_stop=True, interval=0)
    except Exception as e:
        print(f"❌ Ошибка при запуске бота: {e}")
