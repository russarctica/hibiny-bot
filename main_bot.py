import telebot
from telebot import types
import json
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import re

# Загружаем переменные окружения
load_dotenv()

# Настройки
TOKEN = os.getenv('TOKEN')
MANAGER_CHAT_ID = os.getenv('MANAGER_CHAT_ID', '')
INSTRUCTORS_CHAT_ID = os.getenv('INSTRUCTORS_CHAT_ID', '')
GUIDES_CHAT_ID = os.getenv('GUIDES_CHAT_ID', '')

print("=" * 50)
print("🚀 Запуск бота 'Хибины'...")
print(f"📋 Токен: {TOKEN[:10]}...")
print(f"👔 Менеджер: {MANAGER_CHAT_ID if MANAGER_CHAT_ID else 'не указан'}")
print(f"🎿 Чат инструкторов: {INSTRUCTORS_CHAT_ID if INSTRUCTORS_CHAT_ID else 'не указан'}")
print(f"🗺️ Чат гидов: {GUIDES_CHAT_ID if GUIDES_CHAT_ID else 'не указан'}")
print("=" * 50)

# Инициализация базы данных
from database import init_db, get_db, User, InstructorBooking, InstructorOffer, Setting, Excursion, ExcursionBooking, ExcursionOffer, Guide

print("✅ Бот запущен и готов к работе!")
print("✅ Бот запущен и готов к работе!")
print(f"⏰ Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 50)

# Создаем бота
bot = telebot.TeleBot(TOKEN)

# Импортируем обработчики
from state_manager import StateManager
from states import UserStates, StateData
import keyboards

# Импортируем обработчики админки
from handlers.admin import handle_admin_start, handle_admin_states, handle_admin_callback

# Импортируем ИИ-консьержа
from services.ai_assistant import ask_deepseek

# Запускаем планировщик отчетов
try:
    from scheduler import start_scheduler_thread
    start_scheduler_thread(bot)
    print("✅ Планировщик отчетов запущен")
except Exception as e:
    print(f"⚠️ Ошибка запуска планировщика: {e}")

# ========== ОБРАБОТЧИКИ КОМАНД ==========

@bot.message_handler(commands=['start'])
def start_command(message):
    """Обработчик команды /start"""
    from handlers.main import handle_start
    handle_start(bot, message)

@bot.message_handler(commands=['guide'])
def guide_command(message):
    """Обработчик команды /guide для гидов"""
    from handlers.excursions import handle_guide_start
    handle_guide_start(bot, message)

@bot.message_handler(commands=['admin'])
def admin_command(message):
    """Обработчик команды /admin для входа в админку"""
    handle_admin_start(bot, message)

@bot.message_handler(commands=['assistant'])
def assistant_command(message):
    """Обработчик команды /assistant для ИИ-консьержа"""
    chat_id = message.chat.id
    bot.send_message(
        chat_id,
        "🤖 *Я ИИ-консьерж по Хибинам и Кольскому полуострову.*\n\n"
        "Просто напиши свой вопрос в свободной форме, и я постараюсь помочь.\n\n"
        "Например:\n"
        "• Какая сегодня погода в Кировске?\n"
        "• Будет ли северное сияние?\n"
        "• Как добраться до перевала Географов?\n"
        "• Где поесть недорого?\n"
        "• Что интересного происходит сейчас?\n\n"
        "Задавай любой вопрос — я отвечу!",
        parse_mode='Markdown'
    )

@bot.message_handler(func=lambda message: message.text == '🔙 Назад')
def handle_back(message):
    """Обработка кнопки 'Назад'"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    state = StateManager.get_state(user_id)
    if state.value.startswith('admin_'):
        handle_admin_states(bot, message)
        return
    
    if StateManager.go_back(user_id):
        state = StateManager.get_state(user_id)
        
        if state == UserStates.HOTEL_START:
            from handlers.hotel import handle_hotel_start
            handle_hotel_start(bot, message)
        elif state == UserStates.INSTRUCTORS_START:
            from handlers.instructors import handle_instructors_start
            handle_instructors_start(bot, message)
        elif state == UserStates.INSTRUCTORS_SELECT_SPORT:
            bot.send_message(chat_id, "🎿 *Выберите вид спорта:*", parse_mode='Markdown', reply_markup=keyboards.instructors_sport_keyboard())
        elif state == UserStates.INSTRUCTORS_SELECT_PROGRAM:
            bot.send_message(chat_id, "Выберите программу обучения:", reply_markup=keyboards.instructors_program_keyboard())
        elif state == UserStates.INSTRUCTORS_SELECT_PEOPLE:
            bot.send_message(chat_id, "👥 *Сколько человек?*", parse_mode='Markdown', reply_markup=keyboards.instructors_people_keyboard())
        elif state == UserStates.INSTRUCTORS_CHILDREN_INFO:
            bot.send_message(chat_id, "👶 *Есть ли дети?*", reply_markup=keyboards.instructors_children_keyboard())
        elif state == UserStates.INSTRUCTORS_SELECT_TYPE:
            bot.send_message(chat_id, "Выберите тип занятия:", reply_markup=keyboards.instructors_type_keyboard())
        elif state == UserStates.INSTRUCTORS_ENTER_GROUP_SIZE:
            bot.send_message(chat_id, "Сколько человек будет заниматься? (от 2 до 6 человек):", reply_markup=keyboards.instructors_group_size_keyboard())
        elif state == UserStates.INSTRUCTORS_FREERIDE_LEVEL:
            bot.send_message(chat_id, "🏔️ *Выберите ваш уровень фрирайда:*", parse_mode='Markdown', reply_markup=keyboards.instructors_freeride_level_keyboard())
        elif state == UserStates.INSTRUCTORS_SELECT_STUDENT:
            bot.send_message(chat_id, "Укажите, для кого занятие:", reply_markup=keyboards.instructors_student_type_keyboard())
        elif state == UserStates.INSTRUCTORS_SELECT_HOURS:
            bot.send_message(chat_id, "Выберите продолжительность занятия:", reply_markup=keyboards.instructors_hours_keyboard())
        elif state == UserStates.INSTRUCTORS_FREERIDE_DURATION:
            bot.send_message(chat_id, "⏱️ *Выберите формат занятия:*", parse_mode='Markdown', reply_markup=keyboards.instructors_freeride_duration_keyboard())
        elif state == UserStates.INSTRUCTORS_SELECT_GROUP_SLOT:
            data = StateManager.get_data(user_id)
            from handlers.instructors import show_group_slots
            show_group_slots(bot, chat_id, user_id, data.to_dict() if hasattr(data, 'to_dict') else {})
        elif state == UserStates.INSTRUCTORS_ENTER_DATE:
            bot.send_message(chat_id, "Введите дату занятия в формате ДД.ММ.ГГГГ:", reply_markup=keyboards.back_button())
        elif state == UserStates.INSTRUCTORS_ENTER_TIME:
            bot.send_message(chat_id, "Введите время занятия в формате ЧЧ:ММ:", reply_markup=keyboards.back_button())
        elif state == UserStates.INSTRUCTORS_ENTER_NAME:
            bot.send_message(chat_id, "Введите ваше имя и фамилию:", reply_markup=keyboards.back_button())
        elif state == UserStates.INSTRUCTORS_ENTER_PHONE:
            bot.send_message(chat_id, "Введите ваш номер телефона:", reply_markup=keyboards.back_button())
        elif state == UserStates.INSTRUCTORS_ENTER_NOTE:
            bot.send_message(chat_id, "📝 *Есть ли у вас особые пожелания?*", parse_mode='Markdown', reply_markup=keyboards.instructors_note_keyboard())
        elif state == UserStates.INSTRUCTORS_CONFIRMATION:
            data = StateManager.get_data(user_id)
            program_names = {'Новичок': '🎿 Новичок', 'Продолжающий': '⛷️ Продолжающий', 'Карвинг': '🏂 Карвинг', 'Фрирайд': '🏔️ Фрирайд'}
            student_icons = {'Взрослый': '👨', 'Ребенок': '👶'}
            program_display = program_names.get(getattr(data, 'program', ''), getattr(data, 'program', ''))
            student_icon = student_icons.get(getattr(data, 'student_type', ''), '👤')
            
            confirmation_text = f"""
✅ *Проверьте данные заявки:*

*Программа:* {program_display}
*Тип занятия:* {getattr(data, 'lesson_type', '')} {f"({getattr(data, 'group_size', 1)} чел.)" if getattr(data, 'lesson_type', '') == 'Группа' else ''}
*Ученик:* {student_icon} {getattr(data, 'student_type', '')}
*Продолжительность:* {getattr(data, 'hours', 1)} час(ов)
*Дата:* {getattr(data, 'lesson_date', '')}
*Время:* {getattr(data, 'lesson_time', '')}

*Контактные данные:*
👤 Имя: {getattr(data, 'client_name', '')}
📞 Телефон: {getattr(data, 'client_phone', '')}

💰 *Итоговая стоимость: {int(getattr(data, 'total_price', 0))} руб.*

Всё верно?
"""
            bot.send_message(chat_id, confirmation_text, parse_mode='Markdown', reply_markup=keyboards.instructors_confirmation_keyboard())
        elif state == UserStates.INSTRUCTOR_MODIFY_OFFER:
            data = StateManager.get_data(user_id)
            if hasattr(data, 'booking_id'):
                markup = types.InlineKeyboardMarkup(row_width=1)
                markup.add(
                    types.InlineKeyboardButton('💰 Изменить цену', callback_data=f'modify_price_{data.booking_id}'),
                    types.InlineKeyboardButton('📅 Изменить дату', callback_data=f'modify_date_{data.booking_id}'),
                    types.InlineKeyboardButton('🕒 Изменить время', callback_data=f'modify_time_{data.booking_id}'),
                    types.InlineKeyboardButton('✅ Завершить изменения', callback_data=f'modify_done_{data.booking_id}'),
                    types.InlineKeyboardButton('❌ Отменить', callback_data=f'modify_cancel_{data.booking_id}')
                )
                bot.send_message(chat_id, "✏️ *Что хотите изменить?*", parse_mode='Markdown', reply_markup=markup)
            else:
                StateManager.clear_state(user_id)
                bot.send_message(chat_id, "Возвращаемся в главное меню:", reply_markup=keyboards.main_menu())
        elif state == UserStates.INSTRUCTOR_MY_BOOKINGS:
            StateManager.clear_state(user_id)
            bot.send_message(chat_id, "Возвращаемся в меню инструктора:", reply_markup=keyboards.instructors_main_menu())
        elif state == UserStates.EXCURSIONS_START:
            from handlers.excursions import handle_excursions_start
            handle_excursions_start(bot, message)
        elif state == UserStates.EXCURSIONS_SELECT:
            bot.send_message(chat_id, "Выберите экскурсию:", reply_markup=keyboards.excursions_list_keyboard())
        elif state == UserStates.EXCURSIONS_ENTER_DATE:
            bot.send_message(chat_id, "Введите желаемую дату экскурсии в формате ДД.ММ.ГГГГ:", reply_markup=keyboards.back_button())
        elif state == UserStates.EXCURSIONS_ENTER_PEOPLE:
            bot.send_message(chat_id, "Сколько человек поедет на экскурсию?", reply_markup=keyboards.excursion_people_keyboard())
        elif state == UserStates.EXCURSIONS_ENTER_NAME:
            bot.send_message(chat_id, "Введите ваше имя и фамилию:", reply_markup=keyboards.back_button())
        elif state == UserStates.EXCURSIONS_ENTER_PHONE:
            bot.send_message(chat_id, "Введите ваш номер телефона:", reply_markup=keyboards.back_button())
        elif state == UserStates.EXCURSIONS_ENTER_NOTE:
            bot.send_message(chat_id, "📞 *Введите ваш номер телефона:*", parse_mode='Markdown', reply_markup=keyboards.back_button())
        elif state == UserStates.EXCURSIONS_CONFIRMATION:
            data = StateManager.get_data(user_id)
            if hasattr(data, 'excursion_id') or getattr(data, 'is_other_excursion', False):
                from handlers.excursions import show_excursion_confirmation
                show_excursion_confirmation(bot, message, data)
        elif state == UserStates.EXCURSIONS_OTHER:
            from handlers.excursions import handle_excursions_other
            handle_excursions_other(bot, message)
        elif state == UserStates.EXCURSIONS_OTHER_INPUT:
            from handlers.excursions import handle_excursions_other_input
            handle_excursions_other_input(bot, message)
        elif state == UserStates.EXCURSIONS_CHILDREN_INFO:
            from handlers.excursions import handle_excursions_children_info
            handle_excursions_children_info(bot, message)
        elif state == UserStates.EXCURSIONS_GROUP_SELECT:
            bot.send_message(chat_id, "📅 *Введите желаемую дату экскурсии в формате ДД.ММ.ГГГГ:*", parse_mode='Markdown', reply_markup=keyboards.back_button())
        elif state == UserStates.EXCURSIONS_VIEW_GROUP:
            bot.send_message(chat_id, "Выберите экскурсию:", reply_markup=keyboards.excursions_list_keyboard())
        elif state == UserStates.EXCURSIONS_JOIN_GROUP:
            bot.send_message(chat_id, "Выберите экскурсию:", reply_markup=keyboards.excursions_list_keyboard())
        elif state == UserStates.GUIDE_MODIFY_OFFER:
            data = StateManager.get_data(user_id)
            if hasattr(data, 'booking_id'):
                markup = types.InlineKeyboardMarkup(row_width=1)
                markup.add(
                    types.InlineKeyboardButton('💰 Изменить цену', callback_data=f'guide_modify_price_{data.booking_id}'),
                    types.InlineKeyboardButton('📅 Изменить дату', callback_data=f'guide_modify_date_{data.booking_id}'),
                    types.InlineKeyboardButton('🕒 Изменить время', callback_data=f'guide_modify_time_{data.booking_id}'),
                    types.InlineKeyboardButton('📍 Изменить место сбора', callback_data=f'guide_modify_location_{data.booking_id}'),
                    types.InlineKeyboardButton('👥 Изменить количество мест', callback_data=f'guide_modify_seats_{data.booking_id}'),
                    types.InlineKeyboardButton('📝 Добавить описание', callback_data=f'guide_modify_desc_{data.booking_id}'),
                    types.InlineKeyboardButton('✅ Отправить предложение', callback_data=f'guide_modify_done_{data.booking_id}'),
                    types.InlineKeyboardButton('❌ Отменить', callback_data=f'guide_modify_cancel_{data.booking_id}')
                )
                bot.send_message(chat_id, "✏️ *Что хотите изменить?*", parse_mode='Markdown', reply_markup=markup)
            else:
                StateManager.clear_state(user_id)
                bot.send_message(chat_id, "Возвращаемся в главное меню:", reply_markup=keyboards.main_menu())
        elif state == UserStates.GUIDE_MY_BOOKINGS:
            StateManager.clear_state(user_id)
            bot.send_message(chat_id, "Возвращаемся в меню гида:", reply_markup=keyboards.guide_menu_keyboard())
        elif state == UserStates.GUIDE_MODIFY_MIN_PEOPLE:
            bot.send_message(chat_id, "👥 *Введите минимальное количество человек:*", parse_mode='Markdown', reply_markup=keyboards.back_button())
        elif state == UserStates.GUIDE_MODIFY_MAX_PEOPLE:
            bot.send_message(chat_id, "👥 *Введите максимальное количество человек:*", parse_mode='Markdown', reply_markup=keyboards.back_button())
        elif state == UserStates.ORDERS_LIST:
            from handlers.orders import handle_orders_start
            handle_orders_start(bot, message)
        elif state == UserStates.ORDER_DETAILS:
            data = StateManager.get_data(user_id)
            if hasattr(data, 'orders'):
                from handlers.orders import show_orders_page
                show_orders_page(bot, chat_id, data.orders, data.current_page if hasattr(data, 'current_page') else 0)
            else:
                StateManager.clear_state(user_id)
                bot.send_message(chat_id, "Возвращаемся в главное меню:", reply_markup=keyboards.main_menu())
        elif state == UserStates.ORDER_RESCHEDULE_DATE:
            bot.send_message(chat_id, "📅 Введите новую дату в формате ДД.ММ.ГГГГ:", reply_markup=keyboards.back_button())
        elif state == UserStates.ORDER_RESCHEDULE_TIME:
            bot.send_message(chat_id, "🕒 Введите новое время в формате ЧЧ:ММ:", reply_markup=keyboards.back_button())
        elif state == UserStates.SHOP_START:
            from handlers.shop import handle_shop_start
            handle_shop_start(bot, message)
        elif state == UserStates.SHOP_CATEGORIES:
            from handlers.shop import handle_shop_categories
            handle_shop_categories(bot, message)
        elif state == UserStates.SHOP_PRODUCTS:
            from handlers.shop import handle_shop_products
            handle_shop_products(bot, message)
        elif state == UserStates.EXPEDITIONS_START:
            from handlers.expeditions import handle_expeditions_start
            handle_expeditions_start(bot, message)
        elif state == UserStates.GUIDE_CREATE_LOCATION:
            from handlers.excursions import handle_guide_create_location
            handle_guide_create_location(bot, message)
        elif state == UserStates.GUIDE_CREATE_RULES:
            from handlers.excursions import handle_guide_create_rules
            handle_guide_create_rules(bot, message)
        elif state == UserStates.GUIDE_CREATE_NOTE:
            from handlers.excursions import handle_guide_create_note
            handle_guide_create_note(bot, message)
        elif state.value.startswith('admin_'):
            handle_admin_states(bot, message)
        else:
            StateManager.clear_state(user_id)
            bot.send_message(chat_id, "Возвращаемся в главное меню:", reply_markup=keyboards.main_menu())
    else:
        StateManager.clear_state(user_id)
        bot.send_message(chat_id, "Возвращаемся в главное меню:", reply_markup=keyboards.main_menu())

@bot.message_handler(func=lambda message: message.text == '❌ Отмена')
def handle_cancel(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    state = StateManager.get_state(user_id)
    if state.value.startswith('admin_'):
        handle_admin_states(bot, message)
        return
    StateManager.clear_state(user_id)
    bot.send_message(chat_id, "Действие отменено. Возвращаемся в главное меню:", reply_markup=keyboards.main_menu())

# ========== ОБРАБОТКА СОСТОЯНИЙ ==========

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    state = StateManager.get_state(user_id)
    text = message.text
    
    print(f"DEBUG: user={user_id}, state={state}, text={text}")
    
    if state.value.startswith('admin_'):
        handle_admin_states(bot, message)
        return
    
    # Обработка кнопок главного меню
    if text == '🏨 Бабл Отель':
        from handlers.hotel import handle_hotel_start
        handle_hotel_start(bot, message)
        return
    elif text == '🎿 Инструкторы':
        from handlers.instructors import handle_instructors_start
        handle_instructors_start(bot, message)
        return
    elif text == '🗺️ Экскурсии':
        from handlers.excursions import handle_excursions_start
        handle_excursions_start(bot, message)
        return
    elif text == '🧊 Экспедиции':
        from handlers.expeditions import handle_expeditions_start
        handle_expeditions_start(bot, message)
        return
    elif text == '🛒 Магазин':
        from handlers.shop import handle_shop_start
        handle_shop_start(bot, message)
        return
    elif text == '📋 Мои заказы':
        with next(get_db()) as db:
            instructor_has = db.query(InstructorBooking).filter_by(instructor_id=user_id, status='accepted').first() is not None
            guide_has = db.query(ExcursionBooking).filter_by(guide_id=user_id, status='accepted').first() is not None
            
            print(f"DEBUG MAIN: user={user_id}, instructor_has={instructor_has}, guide_has={guide_has}")
            
            if instructor_has and guide_has:
                markup = types.InlineKeyboardMarkup(row_width=1)
                markup.add(
                    types.InlineKeyboardButton('🎿 Мои занятия (инструктор)', callback_data='show_instructor_bookings'),
                    types.InlineKeyboardButton('🗺️ Мои экскурсии (гид)', callback_data='show_guide_bookings'),
                    types.InlineKeyboardButton('📋 Мои заказы (клиент)', callback_data='show_client_orders')
                )
                bot.send_message(chat_id, "Выберите раздел:", reply_markup=markup)
            elif instructor_has:
                from handlers.orders import handle_instructor_my_bookings
                handle_instructor_my_bookings(bot, message)
            elif guide_has:
                from handlers.orders import handle_guide_my_bookings
                handle_guide_my_bookings(bot, message)
            else:
                from handlers.orders import handle_orders_start
                handle_orders_start(bot, message)
        return
    elif text == '✉️ Написать менеджеру':
        from handlers.main import handle_write_manager
        handle_write_manager(bot, message)
        return
    elif text == '👑 Админка':
        from handlers.main import handle_admin_access
        handle_admin_access(bot, message)
        return
    
    # Меню инструктора
    if text in ['📋 Мои заявки', '✅ Завершить занятие']:
        if text == '📋 Мои заявки':
            from handlers.orders import handle_instructor_my_bookings
            handle_instructor_my_bookings(bot, message)
        return
    
    # Меню гида
    if text in ['➕ Создать экскурсию', '📋 Мои заявки', '📊 Статистика']:
        if text == '📋 Мои заявки':
            from handlers.orders import handle_guide_my_bookings
            handle_guide_my_bookings(bot, message)
        elif text == '➕ Создать экскурсию':
            from handlers.excursions import handle_guide_menu
            handle_guide_menu(bot, message)
        elif text == '📊 Статистика':
            from handlers.excursions import handle_guide_menu
            handle_guide_menu(bot, message)
        return
    
    if state == UserStates.MAIN_MENU:
        main_menu_buttons = ['🏨 Бабл Отель', '🎿 Инструкторы', '🗺️ Экскурсии', 
                             '🧊 Экспедиции', '🛒 Магазин', '📋 Мои заказы',
                             '✉️ Написать менеджеру', '👑 Админка']
        if text in main_menu_buttons:
            from handlers.main import handle_main_menu
            handle_main_menu(bot, message)
        else:
            # Отправляем уведомление о поиске
            waiting_msg = bot.reply_to(message, "🔍 *Ищу информацию...* Обычно это занимает 30-60 секунд. Пожалуйста, подождите! ⏳", parse_mode='Markdown')
            try:
                answer = ask_deepseek(text)
                # Проверяем длину ответа
                if len(answer) > 4000:
                    answer = answer[:4000] + "\n\n📌 *Ответ слишком длинный, я его обрезал.* Если нужно больше деталей — уточните вопрос."
                bot.reply_to(message, answer, parse_mode='Markdown')
            except Exception as e:
                print(f"❌ Ошибка при получении ответа: {e}")
                bot.reply_to(message, "😔 *Извините, произошла ошибка при поиске информации.* Попробуйте переформулировать вопрос или напишите позже.", parse_mode='Markdown')
            finally:
                try:
                    bot.delete_message(chat_id, waiting_msg.message_id)
                except:
                    pass
        return
    
    # Отель
    if state == UserStates.HOTEL_ENTER_NAME:
        from handlers.hotel import handle_hotel_name
        handle_hotel_name(bot, message)
    elif state == UserStates.HOTEL_ENTER_PHONE:
        from handlers.hotel import handle_hotel_phone
        handle_hotel_phone(bot, message)
    elif state == UserStates.HOTEL_CONFIRMATION:
        from handlers.hotel import handle_hotel_confirmation
        handle_hotel_confirmation(bot, message)
    
    # Инструкторы (полная цепочка с новыми состояниями)
    elif state == UserStates.INSTRUCTORS_SELECT_SPORT:
        from handlers.instructors import handle_instructors_sport
        handle_instructors_sport(bot, message)
    elif state == UserStates.INSTRUCTORS_ENTER_OTHER_SPORT:
        from handlers.instructors import handle_instructors_other_sport
        handle_instructors_other_sport(bot, message)
    elif state == UserStates.INSTRUCTORS_PROGRAM_INFO:
        from handlers.instructors import handle_instructors_program
        handle_instructors_program(bot, message)
    elif state == UserStates.INSTRUCTORS_SELECT_PEOPLE:
        from handlers.instructors import handle_instructors_people
        handle_instructors_people(bot, message)
    elif state == UserStates.INSTRUCTORS_CHILDREN_INFO:
        from handlers.instructors import handle_instructors_children_info
        handle_instructors_children_info(bot, message)
    elif state == UserStates.INSTRUCTORS_SELECT_TYPE:
        from handlers.instructors import handle_instructors_type
        handle_instructors_type(bot, message)
    elif state == UserStates.INSTRUCTORS_ENTER_GROUP_SIZE:
        from handlers.instructors import handle_instructors_group_size
        handle_instructors_group_size(bot, message)
    elif state == UserStates.INSTRUCTORS_FREERIDE_LEVEL:
        from handlers.instructors import handle_instructors_freeride_level
        handle_instructors_freeride_level(bot, message)
    elif state == UserStates.INSTRUCTORS_SELECT_STUDENT:
        from handlers.instructors import handle_instructors_student
        handle_instructors_student(bot, message)
    elif state == UserStates.INSTRUCTORS_SELECT_HOURS:
        from handlers.instructors import handle_instructors_hours
        handle_instructors_hours(bot, message)
    elif state == UserStates.INSTRUCTORS_FREERIDE_DURATION:
        from handlers.instructors import handle_instructors_freeride_duration
        handle_instructors_freeride_duration(bot, message)
    elif state == UserStates.INSTRUCTORS_FREERIDE_DAYS:
        from handlers.instructors import handle_instructors_freeride_days
        handle_instructors_freeride_days(bot, message)
    elif state == UserStates.INSTRUCTORS_SELECT_GROUP_SLOT:
        from handlers.instructors import handle_instructors_group_slot
        handle_instructors_group_slot(bot, message)
    elif state == UserStates.INSTRUCTORS_ENTER_DATE:
        from handlers.instructors import handle_instructors_date
        handle_instructors_date(bot, message)
    elif state == UserStates.INSTRUCTORS_ENTER_TIME:
        from handlers.instructors import handle_instructors_time
        handle_instructors_time(bot, message)
    elif state == UserStates.INSTRUCTORS_ENTER_NAME:
        from handlers.instructors import handle_instructors_name
        handle_instructors_name(bot, message)
    elif state == UserStates.INSTRUCTORS_ENTER_PHONE:
        from handlers.instructors import handle_instructors_phone
        handle_instructors_phone(bot, message)
    elif state == UserStates.INSTRUCTORS_ENTER_NOTE:
        from handlers.instructors import handle_instructors_note
        handle_instructors_note(bot, message)
    elif state == UserStates.INSTRUCTORS_CONFIRMATION:
        from handlers.instructors import handle_instructors_confirmation
        handle_instructors_confirmation(bot, message)
    elif state == UserStates.INSTRUCTOR_MODIFY_OFFER:
        if message.text == '🔙 Назад':
            handle_back(message)
            return
        elif message.text == '❌ Отмена':
            StateManager.clear_state(user_id)
            bot.send_message(chat_id, "Действие отменено. Возвращаемся в главное меню:", reply_markup=keyboards.main_menu())
            return
        from handlers.instructors import handle_instructor_modify_input
        handle_instructor_modify_input(bot, message)
        return
    elif state == UserStates.INSTRUCTOR_MY_BOOKINGS:
        if message.text == '🔙 Назад':
            handle_back(message)
        return
    elif state == UserStates.INSTRUCTOR_RESCHEDULE_DATE:
        from handlers.orders import handle_instructor_reschedule_date
        handle_instructor_reschedule_date(bot, message)
        return
    elif state == UserStates.INSTRUCTOR_RESCHEDULE_TIME:
        from handlers.orders import handle_instructor_reschedule_time
        handle_instructor_reschedule_time(bot, message)
        return
    
    # Экскурсии (клиентские)
    elif state == UserStates.EXCURSIONS_START:
        from handlers.excursions import handle_excursions_list
        handle_excursions_list(bot, message)
    elif state == UserStates.EXCURSIONS_SELECT:
        from handlers.excursions import handle_excursion_select
        handle_excursion_select(bot, message)
    elif state == UserStates.EXCURSIONS_VIEW_DETAILS:
        from handlers.excursions import handle_excursion_book
        handle_excursion_book(bot, message)
    elif state == UserStates.EXCURSIONS_ENTER_DATE:
        from handlers.excursions import handle_excursion_date
        handle_excursion_date(bot, message)
    elif state == UserStates.EXCURSIONS_ENTER_PEOPLE:
        from handlers.excursions import handle_excursion_people
        handle_excursion_people(bot, message)
    elif state == UserStates.EXCURSIONS_ENTER_NAME:
        from handlers.excursions import handle_excursion_name
        handle_excursion_name(bot, message)
    elif state == UserStates.EXCURSIONS_ENTER_PHONE:
        from handlers.excursions import handle_excursion_phone
        handle_excursion_phone(bot, message)
    elif state == UserStates.EXCURSIONS_ENTER_NOTE:
        from handlers.excursions import handle_excursion_note
        handle_excursion_note(bot, message)
    elif state == UserStates.EXCURSIONS_CONFIRMATION:
        from handlers.excursions import handle_excursion_confirmation
        handle_excursion_confirmation(bot, message)
    elif state == UserStates.EXCURSIONS_OTHER:
        from handlers.excursions import handle_excursions_other
        handle_excursions_other(bot, message)
    elif state == UserStates.EXCURSIONS_OTHER_INPUT:
        from handlers.excursions import handle_excursions_other_input
        handle_excursions_other_input(bot, message)
    elif state == UserStates.EXCURSIONS_CHILDREN_INFO:
        from handlers.excursions import handle_excursions_children_info
        handle_excursions_children_info(bot, message)
    elif state == UserStates.EXCURSIONS_GROUP_SELECT:
        return
    elif state == UserStates.EXCURSIONS_VIEW_GROUP:
        if message.text == '✅ Забронировать':
            data = StateManager.get_data(user_id)
            data_dict = data.to_dict() if hasattr(data, 'to_dict') else {}
            data_dict['is_joining_group'] = True
            StateManager.set_state(user_id, UserStates.EXCURSIONS_ENTER_PEOPLE, StateData(**data_dict))
            bot.send_message(chat_id, "👥 *Сколько человек поедет?*", parse_mode='Markdown', reply_markup=keyboards.back_button())
        elif message.text == '🔙 Назад':
            handle_back(message)
        else:
            from handlers.excursions import handle_excursions_start
            handle_excursions_start(bot, message)
        return
    
    # Гиды - создание предложений
    elif state == UserStates.GUIDE_MODIFY_OFFER:
        if message.text == '🔙 Назад':
            handle_back(message)
            return
        elif message.text == '❌ Отмена':
            StateManager.clear_state(user_id)
            bot.send_message(chat_id, "Действие отменено. Возвращаемся в главное меню:", reply_markup=keyboards.main_menu())
            return
        from handlers.excursions import handle_guide_modify_input
        handle_guide_modify_input(bot, message)
        return
    elif state == UserStates.GUIDE_CREATE_NAME:
        from handlers.excursions import handle_guide_create_name
        handle_guide_create_name(bot, message)
        return
    elif state == UserStates.GUIDE_CREATE_DESCRIPTION:
        from handlers.excursions import handle_guide_create_description
        handle_guide_create_description(bot, message)
        return
    elif state == UserStates.GUIDE_CREATE_PHOTO:
        return
    elif state == UserStates.GUIDE_CREATE_PRICE:
        from handlers.excursions import handle_guide_create_price
        handle_guide_create_price(bot, message)
        return
    elif state == UserStates.GUIDE_CREATE_MIN_PEOPLE:
        from handlers.excursions import handle_guide_create_min_people
        handle_guide_create_min_people(bot, message)
        return
    elif state == UserStates.GUIDE_CREATE_MAX_PEOPLE:
        from handlers.excursions import handle_guide_create_max_people
        handle_guide_create_max_people(bot, message)
        return
    elif state == UserStates.GUIDE_CREATE_DATES:
        from handlers.excursions import handle_guide_create_dates
        handle_guide_create_dates(bot, message)
        return
    elif state == UserStates.GUIDE_CREATE_LOCATION:
        from handlers.excursions import handle_guide_create_location
        handle_guide_create_location(bot, message)
        return
    elif state == UserStates.GUIDE_CREATE_TIMES:
        from handlers.excursions import handle_guide_create_times
        handle_guide_create_times(bot, message)
        return
    elif state == UserStates.GUIDE_CREATE_RULES:
        from handlers.excursions import handle_guide_create_rules
        handle_guide_create_rules(bot, message)
        return
    elif state == UserStates.GUIDE_CREATE_NOTE:
        from handlers.excursions import handle_guide_create_note
        handle_guide_create_note(bot, message)
        return
    elif state == UserStates.GUIDE_CREATE_CONFIRMATION:
        from handlers.excursions import handle_guide_create_confirmation
        handle_guide_create_confirmation(bot, message)
        return
    elif state == UserStates.GUIDE_MY_BOOKINGS:
        if message.text == '🔙 Назад':
            handle_back(message)
        return
    elif state == UserStates.GUIDE_RESCHEDULE_DATE:
        from handlers.orders import handle_guide_reschedule_date
        handle_guide_reschedule_date(bot, message)
        return
    elif state == UserStates.GUIDE_RESCHEDULE_TIME:
        from handlers.orders import handle_guide_reschedule_time
        handle_guide_reschedule_time(bot, message)
        return
    elif state == UserStates.GUIDE_MODIFY_MIN_PEOPLE:
        from handlers.excursions import handle_guide_modify_input
        handle_guide_modify_input(bot, message)
        return
    elif state == UserStates.GUIDE_MODIFY_MAX_PEOPLE:
        from handlers.excursions import handle_guide_modify_input
        handle_guide_modify_input(bot, message)
        return
    
    # Магазин
    elif state == UserStates.SHOP_START:
        from handlers.shop import handle_shop_categories
        handle_shop_categories(bot, message)
    elif state == UserStates.SHOP_CATEGORIES:
        from handlers.shop import handle_shop_categories
        handle_shop_categories(bot, message)
    elif state == UserStates.SHOP_PRODUCTS:
        from handlers.shop import handle_shop_products
        handle_shop_products(bot, message)
    elif state == UserStates.SHOP_PRODUCT_DETAILS:
        from handlers.shop import handle_shop_product_details
        handle_shop_product_details(bot, message)
    elif state == UserStates.SHOP_ENTER_QUANTITY:
        from handlers.shop import handle_shop_product_details
        handle_shop_product_details(bot, message)
    elif state == UserStates.SHOP_ENTER_ADDRESS:
        from handlers.shop import handle_shop_address
        handle_shop_address(bot, message)
    elif state == UserStates.SHOP_CONFIRMATION:
        from handlers.shop import handle_shop_confirmation
        handle_shop_confirmation(bot, message)
    
    # Экспедиции
    elif state == UserStates.EXPEDITIONS_START:
        from handlers.expeditions import handle_expeditions_start
        handle_expeditions_start(bot, message)
    elif state == UserStates.EXPEDITIONS_SELECT:
        from handlers.expeditions import handle_expeditions_select
        handle_expeditions_select(bot, message)
    elif state == UserStates.EXPEDITIONS_ENTER_NAME:
        from handlers.expeditions import handle_expeditions_enter_name
        handle_expeditions_enter_name(bot, message)
    elif state == UserStates.EXPEDITIONS_ENTER_PEOPLE:
        from handlers.expeditions import handle_expeditions_enter_people
        handle_expeditions_enter_people(bot, message)
    elif state == UserStates.EXPEDITIONS_ENTER_PHONE:
        from handlers.expeditions import handle_expeditions_enter_phone
        handle_expeditions_enter_phone(bot, message)
    elif state == UserStates.EXPEDITIONS_ENTER_WISHES:
        from handlers.expeditions import handle_expeditions_enter_wishes
        handle_expeditions_enter_wishes(bot, message)
    elif state == UserStates.EXPEDITIONS_CONFIRMATION:
        from handlers.expeditions import handle_expeditions_confirmation
        handle_expeditions_confirmation(bot, message)
    
    # Мои заказы
    elif state == UserStates.ORDERS_LIST:
        from handlers.orders import handle_orders_list
        handle_orders_list(bot, message)
    elif state == UserStates.ORDER_DETAILS:
        from handlers.orders import handle_order_details
        handle_order_details(bot, message)
    elif state == UserStates.ORDER_RESCHEDULE_DATE:
        from handlers.orders import handle_reschedule_date
        handle_reschedule_date(bot, message)
    elif state == UserStates.ORDER_RESCHEDULE_TIME:
        from handlers.orders import handle_reschedule_time
        handle_reschedule_time(bot, message)
    
    elif state == UserStates.WRITE_MANAGER:
        from handlers.main import handle_manager_message
        handle_manager_message(bot, message)
    
    else:
        # Состояние None (теоретически возможно) → DeepSeek
        waiting_msg = bot.reply_to(message, "🔍 *Ищу информацию...* Обычно это занимает 30-60 секунд. Пожалуйста, подождите! ⏳", parse_mode='Markdown')
        try:
            answer = ask_deepseek(text)
            # Проверяем длину ответа
            if len(answer) > 4000:
                answer = answer[:4000] + "\n\n📌 *Ответ слишком длинный, я его обрезал.* Если нужно больше деталей — уточните вопрос."
            bot.reply_to(message, answer, parse_mode='Markdown')
        except Exception as e:
            print(f"❌ Ошибка при получении ответа: {e}")
            bot.reply_to(message, "😔 *Извините, произошла ошибка при поиске информации.* Попробуйте переформулировать вопрос или напишите позже.", parse_mode='Markdown')
        finally:
            try:
                bot.delete_message(chat_id, waiting_msg.message_id)
            except:
                pass

# ========== INLINE ОБРАБОТЧИКИ ==========

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    # === ОБРАБОТКА ЗАКАЗОВ (клиент) ===
    if call.data.startswith('orders_') or call.data.startswith('order_select_') or call.data.startswith('order_cancel_') or call.data.startswith('order_reschedule_') or call.data.startswith('order_contact_') or call.data == 'order_back_to_list':
        from handlers.orders import handle_orders_callback, handle_order_details_callback
        if call.data.startswith('order_cancel_') or call.data.startswith('order_reschedule_') or call.data.startswith('order_contact_') or call.data == 'order_back_to_list':
            handle_order_details_callback(bot, call)
        else:
            handle_orders_callback(bot, call)
        return
    
    # === ОБРАБОТКА ГРУПП (±5 ДНЕЙ) ===
    if call.data.startswith('join_existing_group_'):
        from handlers.excursions import handle_join_existing_group
        handle_join_existing_group(bot, call)
        return
    if call.data.startswith('keep_my_date_'):
        from handlers.excursions import handle_keep_my_date
        handle_keep_my_date(bot, call)
        return
    
    # === ОБРАБОТКА ПОДТВЕРЖДЕНИЯ ГИДА (НОВЫЙ УЧАСТНИК) ===
    if call.data.startswith('guide_confirm_join_'):
        from handlers.excursions import handle_guide_confirm_join
        handle_guide_confirm_join(bot, call)
        return
    if call.data.startswith('guide_reject_join_'):
        from handlers.excursions import handle_guide_reject_join
        handle_guide_reject_join(bot, call)
        return
    
    # === ОБРАБОТКА REBOOK (ЗАПИСАТЬСЯ СНОВА) ===
    if call.data.startswith('rebook_instructor_'):
        from handlers.orders import rebook_order
        booking_id = int(call.data.split('_')[-1])
        rebook_order(bot, call, 'instructor', booking_id)
        return
    if call.data.startswith('rebook_excursion_'):
        from handlers.orders import rebook_order
        booking_id = int(call.data.split('_')[-1])
        rebook_order(bot, call, 'excursion', booking_id)
        return
    # === КОНЕЦ ОБРАБОТКИ REBOOK ===
    
    if call.data.startswith('admin_'):
        handle_admin_callback(bot, call)
        return
    elif call.data.startswith('confirm_payment_'):
        from handlers.payment import handle_payment_confirmation
        handle_payment_confirmation(bot, call)
        return
    
    # === ОБРАБОТКА ТУРОВ ===
    if call.data.startswith('tour_select_'):
        from handlers.excursions import handle_tour_select
        handle_tour_select(bot, call)
        return
    if call.data == 'tour_back_to_excursions':
        from handlers.excursions import handle_tour_back
        handle_tour_back(bot, call)
        return
    
    # === ОБРАБОТКА ПРЕДОПЛАТЫ И КОМИССИИ ===
    if call.data.startswith('excursion_prepayment_'):
        from handlers.excursions import handle_excursion_prepayment
        handle_excursion_prepayment(bot, call)
        return
    if call.data.startswith('excursion_commission_paid_'):
        from handlers.excursions import handle_excursion_commission_paid
        handle_excursion_commission_paid(bot, call)
        return
    if call.data.startswith('guide_access_paid_'):
        from handlers.excursions import handle_guide_access_paid
        handle_guide_access_paid(bot, call)
        return
    
    # Выбор раздела для пользователя с несколькими ролями
    if call.data == 'show_instructor_bookings':
        from handlers.orders import handle_instructor_my_bookings
        fake_msg = types.Message(
            message_id=call.message.message_id, from_user=call.from_user, chat=call.message.chat,
            date=call.message.date, content_type='text', options={}, json_string='')
        fake_msg.text = '📋 Мои заявки'
        handle_instructor_my_bookings(bot, fake_msg)
        bot.answer_callback_query(call.id)
        return
    elif call.data == 'show_guide_bookings':
        from handlers.orders import handle_guide_my_bookings
        fake_msg = types.Message(
            message_id=call.message.message_id, from_user=call.from_user, chat=call.message.chat,
            date=call.message.date, content_type='text', options={}, json_string='')
        fake_msg.text = '📋 Мои заявки'
        handle_guide_my_bookings(bot, fake_msg)
        bot.answer_callback_query(call.id)
        return
    elif call.data == 'show_client_orders':
        from handlers.orders import handle_orders_start
        fake_msg = types.Message(
            message_id=call.message.message_id, from_user=call.from_user, chat=call.message.chat,
            date=call.message.date, content_type='text', options={}, json_string='')
        fake_msg.text = '📋 Мои заказы'
        handle_orders_start(bot, fake_msg)
        bot.answer_callback_query(call.id)
        return
    
    # Календарь отеля
    if call.data.startswith('date_'):
        from handlers.hotel import handle_date_select
        handle_date_select(bot, call)
    elif call.data.startswith('prev_') or call.data.startswith('next_'):
        from handlers.hotel import handle_calendar_navigate
        handle_calendar_navigate(bot, call)
    elif call.data == 'cancel_calendar':
        from handlers.hotel import handle_calendar_cancel
        handle_calendar_cancel(bot, call)
    elif call.data.startswith('blocked_'):
        bot.answer_callback_query(call.id, "❌ Эта дата недоступна для бронирования", show_alert=True)
    
    # Инструкторы
    elif call.data.startswith('instructor_take_'):
        from handlers.instructors import handle_instructor_take
        handle_instructor_take(bot, call)
    elif call.data.startswith('instructor_modify_'):
        from handlers.instructors import handle_instructor_modify_start
        handle_instructor_modify_start(bot, call)
    elif call.data.startswith('modify_price_'):
        from handlers.instructors import handle_modify_price
        handle_modify_price(bot, call)
    elif call.data.startswith('modify_date_'):
        from handlers.instructors import handle_modify_date
        handle_modify_date(bot, call)
    elif call.data.startswith('modify_time_'):
        from handlers.instructors import handle_modify_time
        handle_modify_time(bot, call)
    elif call.data.startswith('modify_done_'):
        from handlers.instructors import handle_modify_done
        handle_modify_done(bot, call)
    elif call.data.startswith('modify_cancel_'):
        from handlers.instructors import handle_modify_cancel
        handle_modify_cancel(bot, call)
    elif call.data.startswith('accept_offer_'):
        from handlers.instructors import handle_accept_offer
        handle_accept_offer(bot, call)
    elif call.data.startswith('reject_offer_'):
        from handlers.instructors import handle_reject_offer
        handle_reject_offer(bot, call)
    elif call.data.startswith('wait_offer_'):
        from handlers.instructors import handle_wait_offer
        handle_wait_offer(bot, call)
    elif call.data.startswith('end_lesson_'):
        from handlers.instructors import handle_end_lesson
        handle_end_lesson(bot, call)
    elif call.data.startswith('extend_lesson_'):
        from handlers.instructors import handle_extend_lesson
        handle_extend_lesson(bot, call)
    elif call.data.startswith('client_paid_'):
        from handlers.instructors import handle_client_paid
        handle_client_paid(bot, call)
    elif call.data.startswith('group_slot_'):
        from handlers.instructors import handle_group_slot_callback
        handle_group_slot_callback(bot, call)
    elif call.data.startswith('instructor_paid_commission_'):
        from handlers.instructors import handle_instructor_paid_commission
        handle_instructor_paid_commission(bot, call)
    elif call.data.startswith('instructor_reject_'):
        from handlers.instructors import handle_instructor_reject
        handle_instructor_reject(bot, call)
    
    # Гиды
    elif call.data.startswith('guide_offer_'):
        from handlers.excursions import handle_guide_offer_start
        handle_guide_offer_start(bot, call)
    elif call.data.startswith('guide_modify_price_'):
        from handlers.excursions import handle_guide_modify_price
        handle_guide_modify_price(bot, call)
    elif call.data.startswith('guide_modify_date_'):
        from handlers.excursions import handle_guide_modify_date
        handle_guide_modify_date(bot, call)
    elif call.data.startswith('guide_modify_time_'):
        from handlers.excursions import handle_guide_modify_time
        handle_guide_modify_time(bot, call)
    elif call.data.startswith('guide_modify_location_'):
        from handlers.excursions import handle_guide_modify_location
        handle_guide_modify_location(bot, call)
    elif call.data.startswith('guide_modify_seats_'):
        from handlers.excursions import handle_guide_modify_seats
        handle_guide_modify_seats(bot, call)
    elif call.data.startswith('guide_modify_desc_'):
        from handlers.excursions import handle_guide_modify_desc
        handle_guide_modify_desc(bot, call)
    elif call.data.startswith('guide_modify_done_'):
        from handlers.excursions import handle_guide_modify_done
        handle_guide_modify_done(bot, call)
    elif call.data.startswith('guide_modify_cancel_'):
        from handlers.excursions import handle_guide_modify_cancel
        handle_guide_modify_cancel(bot, call)
    elif call.data.startswith('guide_modify_min_people_'):
        from handlers.excursions import handle_guide_modify_min_people
        handle_guide_modify_min_people(bot, call)
    elif call.data.startswith('guide_modify_max_people_'):
        from handlers.excursions import handle_guide_modify_max_people
        handle_guide_modify_max_people(bot, call)
    elif call.data.startswith('guide_accept_offer_'):
        from handlers.excursions import handle_accept_offer
        handle_accept_offer(bot, call)
    elif call.data.startswith('guide_reject_offer_'):
        from handlers.excursions import handle_reject_offer
        handle_reject_offer(bot, call)
    elif call.data.startswith('guide_wait_offer_'):
        from handlers.excursions import handle_wait_offer
        handle_wait_offer(bot, call)
    
    # Экскурсии (старые callback'и)
    elif call.data.startswith('exc_accept_'):
        from handlers.excursions import handle_accept_offer
        handle_accept_offer(bot, call)
    elif call.data.startswith('exc_reject_'):
        from handlers.excursions import handle_reject_offer
        handle_reject_offer(bot, call)
    elif call.data.startswith('exc_wait_'):
        from handlers.excursions import handle_wait_offer
        handle_wait_offer(bot, call)
    elif call.data.startswith('exc_client_paid_'):
        from handlers.excursions import handle_excursion_client_paid
        handle_excursion_client_paid(bot, call)
    elif call.data.startswith('guide_paid_commission_'):
        from handlers.excursions import handle_guide_paid_commission
        handle_guide_paid_commission(bot, call)
    
    # Управление заказами (инструктор)
    elif call.data.startswith('instr_cancel_'):
        from handlers.orders import handle_instructor_cancel
        booking_id = int(call.data.split('_')[-1])
        handle_instructor_cancel(bot, call, booking_id)
    elif call.data.startswith('instr_reschedule_') and not call.data.startswith('instr_reschedule_accept_') and not call.data.startswith('instr_reschedule_reject_'):
        from handlers.orders import handle_instructor_reschedule_start
        booking_id = int(call.data.split('_')[-1])
        handle_instructor_reschedule_start(bot, call, booking_id)
    elif call.data.startswith('instr_reschedule_accept_'):
        from handlers.orders import handle_instructor_reschedule_accept
        parts = call.data.split('_')
        booking_id = int(parts[3])
        new_date = parts[4]
        new_time = parts[5]
        handle_instructor_reschedule_accept(bot, call, booking_id, new_date, new_time)
    elif call.data.startswith('instr_reschedule_reject_'):
        from handlers.orders import handle_instructor_reschedule_reject
        booking_id = int(call.data.split('_')[-1])
        handle_instructor_reschedule_reject(bot, call, booking_id)
    
    # Управление заказами (гид)
    elif call.data.startswith('guide_cancel_'):
        from handlers.orders import handle_guide_cancel
        booking_id = int(call.data.split('_')[-1])
        handle_guide_cancel(bot, call, booking_id)
    elif call.data.startswith('guide_reschedule_') and not call.data.startswith('guide_reschedule_accept_') and not call.data.startswith('guide_reschedule_reject_'):
        from handlers.orders import handle_guide_reschedule_start
        booking_id = int(call.data.split('_')[-1])
        handle_guide_reschedule_start(bot, call, booking_id)
    elif call.data.startswith('guide_reschedule_accept_'):
        from handlers.orders import handle_guide_reschedule_accept
        parts = call.data.split('_')
        booking_id = int(parts[3])
        new_date = parts[4]
        new_time = parts[5]
        handle_guide_reschedule_accept(bot, call, booking_id, new_date, new_time)
    elif call.data.startswith('guide_reschedule_reject_'):
        from handlers.orders import handle_guide_reschedule_reject
        booking_id = int(call.data.split('_')[-1])
        handle_guide_reschedule_reject(bot, call, booking_id)
    
    # Детали заказа для инструктора
    elif call.data.startswith('instr_booking_detail_'):
        from handlers.orders import show_instructor_booking_detail
        booking_id = int(call.data.split('_')[-1])
        show_instructor_booking_detail(bot, call, booking_id)
    elif call.data == 'instr_back_to_list':
        from handlers.orders import handle_instructor_my_bookings
        fake_msg = types.Message(
            message_id=call.message.message_id,
            from_user=call.from_user,
            chat=call.message.chat,
            date=call.message.date,
            content_type='text',
            options={},
            json_string=''
        )
        fake_msg.text = '📋 Мои заявки'
        handle_instructor_my_bookings(bot, fake_msg)
        bot.answer_callback_query(call.id)
    
    # Детали заказа для гида
    elif call.data.startswith('guide_booking_detail_'):
        from handlers.orders import show_guide_booking_detail
        booking_id = int(call.data.split('_')[-1])
        show_guide_booking_detail(bot, call, booking_id)
    elif call.data == 'guide_back_to_list':
        from handlers.orders import handle_guide_my_bookings
        fake_msg = types.Message(
            message_id=call.message.message_id,
            from_user=call.from_user,
            chat=call.message.chat,
            date=call.message.date,
            content_type='text',
            options={},
            json_string=''
        )
        fake_msg.text = '📋 Мои заявки'
        handle_guide_my_bookings(bot, fake_msg)
        bot.answer_callback_query(call.id)
    
    elif call.data == 'ignore':
        bot.answer_callback_query(call.id)
    else:
        from handlers.hotel import handle_hotel_callback
        handle_hotel_callback(bot, call)

# ========== ОБРАБОТКА ФОТО ==========

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    state = StateManager.get_state(user_id)
    
    if state == UserStates.GUIDE_CREATE_PHOTO:
        from handlers.excursions import handle_guide_create_photo_input
        handle_guide_create_photo_input(bot, message)
        return
    elif state == UserStates.EXCURSIONS_VIEW_DETAILS:
        return
    else:
        bot.send_message(chat_id, "Фото получено, но не в том контексте. Возвращаемся в главное меню:", reply_markup=keyboards.main_menu())

# ========== ЗАПУСК ==========

if __name__ == '__main__':
    import threading
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class HealthCheckHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'ok')

        def log_message(self, format, *args):
            pass

    def run_health_server():
        server = HTTPServer(('0.0.0.0', 10000), HealthCheckHandler)
        server.serve_forever()

    threading.Thread(target=run_health_server, daemon=True).start()
    
    print("🤖 Бот запущен и готов к работе!")
    print("⏰ Для остановки нажмите Ctrl+C")
    try:
        bot.polling(none_stop=True, interval=0, timeout=90)
    except Exception as e:
        print(f"❌ Ошибка при работе бота: {e}")
