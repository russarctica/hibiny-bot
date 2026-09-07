import telebot
from telebot import types
import json
from datetime import datetime, timedelta
import re
from database import get_db, User, HotelBooking, BlockedDate
from state_manager import StateManager
from states import UserStates, StateData
import keyboards
from calendar_fixed import create_calendar, format_date, calculate_nights, get_blocked_dates
from config import HOTEL_PRICE_PER_NIGHT, MANAGER_CHAT_ID
from handlers.payment import send_payment_link

def handle_hotel_start(bot, message):
    """Начало бронирования отеля"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Устанавливаем состояние
    StateManager.set_state(user_id, UserStates.HOTEL_START, StateData(step=1))
    
    # Отправляем описание отеля
    hotel_text = f"""
🏨 *БАБЛ ОТЕЛЬ*

*Описание:*
Уютный отель в самом сердце Хибин.
Все номера с панорамным видом на горы.

*Условия:*
• Цена: {HOTEL_PRICE_PER_NIGHT} руб./сутки
• Заезд: с 14:00
• Выезд: до 12:00
• Минимальное бронирование: 1 ночь
• Максимальное бронирование: 14 ночей

*Выберите дату заезда:*
"""
    
    # Получаем заблокированные даты
    blocked_dates = get_blocked_dates()
    
    # Создаем календарь
    calendar_markup = create_calendar(blocked_dates=blocked_dates)
    
    bot.send_message(
        chat_id,
        hotel_text,
        parse_mode='Markdown',
        reply_markup=calendar_markup
    )

def handle_date_select(bot, call):
    """Обработка выбора даты"""
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    # Извлекаем дату из callback
    date_str = call.data.replace('date_', '')
    
    # Получаем текущие данные
    data = StateManager.get_data(user_id)
    if not hasattr(data, 'step'):
        data = StateData(step=1)
    
    try:
        if data.step == 1:  # Выбор даты заезда
            # Сохраняем дату заезда
            StateManager.set_state(
                user_id,
                UserStates.HOTEL_SELECT_CHECKIN,
                StateData(
                    step=2,
                    checkin_date=date_str,
                    checkin_display=format_date(date_str)
                )
            )
            
            # Получаем заблокированные даты
            blocked_dates = get_blocked_dates()
            
            # Создаем календарь
            calendar_markup = create_calendar(blocked_dates=blocked_dates)
            
            # Пробуем отредактировать сообщение
            try:
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=call.message.message_id,
                    text=f"✅ *Дата заезда выбрана:* {format_date(date_str)}\n\n"
                         f"*Теперь выберите дату выезда:*\n"
                         f"Дата выезда должна быть позже даты заезда.",
                    parse_mode='Markdown',
                    reply_markup=calendar_markup
                )
            except Exception as e:
                # Если не удалось отредактировать, отправляем новое сообщение
                bot.send_message(
                    chat_id,
                    f"✅ *Дата заезда выбрана:* {format_date(date_str)}\n\n"
                    f"*Теперь выберите дату выезда:*\n"
                    f"Дата выезда должна быть позже даты заезда.",
                    parse_mode='Markdown',
                    reply_markup=calendar_markup
                )
            
        elif data.step == 2:  # Выбор даты выезда
            checkin_date = datetime.strptime(data.checkin_date, '%Y-%m-%d')
            checkout_date = datetime.strptime(date_str, '%Y-%m-%d')
            
            # Проверяем, что дата выезда позже заезда
            if checkout_date <= checkin_date:
                bot.answer_callback_query(
                    call.id,
                    "❌ Дата выезда должна быть позже даты заезда!",
                    show_alert=True
                )
                return
            
            # Проверяем доступность всех дат в периоде
            blocked_dates = get_blocked_dates()
            current_date = checkin_date
            all_dates_available = True
            blocked_dates_in_period = []
            
            while current_date < checkout_date:
                date_str_check = current_date.strftime('%Y-%m-%d')
                if date_str_check in blocked_dates:
                    all_dates_available = False
                    blocked_dates_in_period.append(format_date(date_str_check))
                current_date += timedelta(days=1)
            
            if not all_dates_available:
                blocked_dates_text = "\n".join(blocked_dates_in_period)
                bot.answer_callback_query(
                    call.id,
                    f"❌ В выбранном периоде есть занятые даты:\n{blocked_dates_text}",
                    show_alert=True
                )
                return
            
            # Рассчитываем количество ночей
            nights = calculate_nights(data.checkin_date, date_str)
            if nights > 14:
                bot.answer_callback_query(
                    call.id,
                    "❌ Максимальное количество ночей - 14!",
                    show_alert=True
                )
                return
            
            # Сохраняем данные
            StateManager.set_state(
                user_id,
                UserStates.HOTEL_ENTER_NAME,
                StateData(
                    step=3,
                    checkin_date=data.checkin_date,
                    checkin_display=data.checkin_display,
                    checkout_date=date_str,
                    checkout_display=format_date(date_str),
                    nights=nights,
                    total_price=nights * HOTEL_PRICE_PER_NIGHT
                )
            )
            
            # Удаляем сообщение с календарем
            try:
                bot.delete_message(chat_id, call.message.message_id)
            except:
                pass  # Игнорируем ошибку удаления
            
            # Запрашиваем имя
            bot.send_message(
                chat_id,
                f"✅ *Даты выбраны:*\n"
                f"📅 Заезд: {data.checkin_display}\n"
                f"📅 Выезд: {format_date(date_str)}\n"
                f"🌙 Ночей: {nights}\n"
                f"💰 Стоимость: {nights * HOTEL_PRICE_PER_NIGHT} руб.\n\n"
                f"*Теперь введите ваше имя и фамилию:*",
                parse_mode='Markdown',
                reply_markup=keyboards.back_button()
            )
    except Exception as e:
        print(f"Ошибка в handle_date_select: {e}")
        bot.answer_callback_query(
            call.id,
            "❌ Произошла ошибка. Попробуйте еще раз.",
            show_alert=True
        )

def handle_calendar_navigate(bot, call):
    """Навигация по календарю"""
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    # Получаем данные
    data = StateManager.get_data(user_id)
    
    if call.data.startswith('prev_'):
        # Предыдущий месяц
        _, year, month = call.data.split('_')
        year = int(year)
        month = int(month)
    elif call.data.startswith('next_'):
        # Следующий месяц
        _, year, month = call.data.split('_')
        year = int(year)
        month = int(month)
    else:
        return
    
    # Получаем заблокированные даты
    blocked_dates = get_blocked_dates()
    
    # Создаем новый календарь
    calendar_markup = create_calendar(year=year, month=month, blocked_dates=blocked_dates)
    
    # Обновляем сообщение
    if hasattr(data, 'step'):
        if data.step == 1:
            text = "🏨 *Выберите дату заезда:*"
        elif data.step == 2:
            text = f"✅ *Дата заезда выбрана:* {data.checkin_display}\n\n*Теперь выберите дату выезда:*"
        else:
            text = "🏨 *Выберите дату:*"
    else:
        text = "🏨 *Выберите дату:*"
    
    try:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text=text,
            parse_mode='Markdown',
            reply_markup=calendar_markup
        )
    except Exception as e:
        # Если не удалось отредактировать, отправляем новое сообщение
        bot.send_message(
            chat_id,
            text,
            parse_mode='Markdown',
            reply_markup=calendar_markup
        )

def handle_calendar_cancel(bot, call):
    """Отмена выбора даты"""
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    # Очищаем состояние
    StateManager.clear_state(user_id)
    
    # Удаляем сообщение с календарем
    try:
        bot.delete_message(chat_id, call.message.message_id)
    except:
        pass
    
    # Возвращаем в главное меню
    bot.send_message(
        chat_id,
        "Бронирование отеля отменено. Возвращаемся в главное меню:",
        reply_markup=keyboards.main_menu()
    )

def handle_hotel_callback(bot, call):
    """Обработка callback для отеля"""
    if call.data == 'ignore':
        bot.answer_callback_query(call.id)
    elif call.data.startswith('blocked_'):
        bot.answer_callback_query(
            call.id,
            "❌ Эта дата недоступна для бронирования",
            show_alert=True
        )

def handle_hotel_name(bot, message):
    """Обработка ввода имени для отеля"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверка на кнопку "Назад"
    if message.text == '🔙 Назад':
        # Возвращаем к выбору даты выезда
        data = StateManager.get_data(user_id)
        if hasattr(data, 'checkin_date'):
            StateManager.set_state(
                user_id,
                UserStates.HOTEL_SELECT_CHECKOUT,
                StateData(
                    step=2,
                    checkin_date=data.checkin_date,
                    checkin_display=data.checkin_display
                )
            )
            
            # Получаем заблокированные даты
            blocked_dates = get_blocked_dates()
            
            # Создаем календарь
            calendar_markup = create_calendar(blocked_dates=blocked_dates)
            
            bot.send_message(
                chat_id,
                f"✅ *Дата заезда выбрана:* {data.checkin_display}\n\n"
                f"*Теперь выберите дату выезда:*",
                parse_mode='Markdown',
                reply_markup=calendar_markup
            )
        else:
            handle_hotel_start(bot, message)
        return
    
    name = message.text.strip()
    
    # Простая валидация имени
    if len(name) < 2:
        bot.send_message(
            chat_id,
            "❌ Имя слишком короткое. Введите имя и фамилию (минимум 2 символа):",
            reply_markup=keyboards.back_button()
        )
        return
    
    # Сохраняем имя и переходим к вводу телефона
    data = StateManager.get_data(user_id)
    data_dict = data.to_dict() if hasattr(data, 'to_dict') else {}
    data_dict['name'] = name
    
    StateManager.set_state(user_id, UserStates.HOTEL_ENTER_PHONE, StateData(**data_dict))
    
    bot.send_message(
        chat_id,
        "📞 *Введите ваш номер телефона:*\n\n"
        "Можно вводить в любом формате, главное - чтобы были цифры\n"
        "Пример: 8-900-123-45-67 или +7 900 123 45 67",
        parse_mode='Markdown',
        reply_markup=keyboards.back_button()
    )

def handle_hotel_phone(bot, message):
    """Обработка ввода телефона для отеля"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверка на кнопку "Назад"
    if message.text == '🔙 Назад':
        # Возвращаем к вводу имени
        StateManager.set_state(user_id, UserStates.HOTEL_ENTER_NAME, StateManager.get_data(user_id))
        bot.send_message(
            chat_id,
            "👤 *Введите ваше имя и фамилию:*",
            parse_mode='Markdown',
            reply_markup=keyboards.back_button()
        )
        return
    
    phone = message.text.strip()
    
    # Извлекаем все цифры из строки
    digits = re.findall(r'\d', phone)
    if not digits:
        bot.send_message(
            chat_id,
            "❌ Номер телефона должен содержать цифры. Введите номер телефона:",
            reply_markup=keyboards.back_button()
        )
        return
    
    # Формируем номер из найденных цифр
    phone_number = ''.join(digits)
    
    # Если цифр меньше 10, считаем некорректным
    if len(phone_number) < 10:
        bot.send_message(
            chat_id,
            "❌ Номер телефона слишком короткий. Введите номер телефона:",
            reply_markup=keyboards.back_button()
        )
        return
    
    # Берем последние 10 цифр (или все, если меньше)
    if len(phone_number) > 10:
        phone_number = phone_number[-10:]
    
    # Форматируем как +7XXXXXXXXXX
    formatted_phone = f"+7{phone_number}"
    
    # Сохраняем телефон и переходим к подтверждению
    data = StateManager.get_data(user_id)
    data_dict = data.to_dict() if hasattr(data, 'to_dict') else {}
    data_dict['phone'] = formatted_phone
    
    StateManager.set_state(user_id, UserStates.HOTEL_CONFIRMATION, StateData(**data_dict))
    
    # Формируем текст подтверждения
    confirmation_text = f"""
✅ *ПРОВЕРЬТЕ ДАННЫЕ БРОНИРОВАНИЯ:*

*Даты:*
📅 Заезд: {data_dict.get('checkin_display', '')}
📅 Выезд: {data_dict.get('checkout_display', '')}
🌙 Ночей: {data_dict.get('nights', 0)}

*Стоимость:*
💰 {data_dict.get('nights', 0)} ночей × {HOTEL_PRICE_PER_NIGHT} руб. = {data_dict.get('total_price', 0)} руб.

*Контактные данные:*
👤 Имя: {data_dict.get('name', '')}
📞 Телефон: {formatted_phone}

*Условия бронирования:*
• Предоплата 30% в течение 24 часов
• Полная оплата за 7 дней до заезда
• Бесплатная отмена за 7 дней до заезда
• При отмене позже - удерживается 30%

Всё верно?
"""
    
    bot.send_message(
        chat_id,
        confirmation_text,
        parse_mode='Markdown',
        reply_markup=keyboards.confirmation_buttons()
    )

def handle_hotel_confirmation(bot, message):
    """Обработка подтверждения бронирования отеля"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '✅ Подтвердить бронирование':
        # Получаем данные
        data = StateManager.get_data(user_id)
        
        # Проверяем наличие всех необходимых данных
        required_fields = ['checkin_date', 'checkout_date', 'nights', 'total_price', 'name', 'phone']
        missing_fields = []
        
        for field in required_fields:
            if not hasattr(data, field):
                missing_fields.append(field)
        
        if missing_fields:
            bot.send_message(
                chat_id,
                f"❌ Не хватает данных: {', '.join(missing_fields)}. Начните бронирование заново.",
                reply_markup=keyboards.main_menu()
            )
            StateManager.clear_state(user_id)
            return
        
        # Создаем бронирование в базе данных
        with next(get_db()) as db:
            try:
                # Получаем или создаем пользователя
                user = db.query(User).filter_by(user_id=user_id).first()
                if not user:
                    user = User(
                        user_id=user_id,
                        username=message.from_user.username,
                        first_name=message.from_user.first_name,
                        last_name=message.from_user.last_name,
                        phone=data.phone
                    )
                    db.add(user)
                    db.commit()
                    db.refresh(user)
                
                # Генерируем ID бронирования
                import random
                import string
                booking_id = 'HOT' + ''.join(random.choices(string.digits, k=8))
                
                # Создаем бронирование
                checkin_date = datetime.strptime(data.checkin_date, '%Y-%m-%d')
                checkout_date = datetime.strptime(data.checkout_date, '%Y-%m-%d')
                
                booking = HotelBooking(
                    user_id=user.id,
                    booking_id=booking_id,
                    check_in=checkin_date,
                    check_out=checkout_date,
                    nights=data.nights,
                    total_price=data.total_price,
                    status='pending',
                    payment_status='unpaid',
                    name=data.name,
                    phone=data.phone,
                    notes=''
                )
                
                db.add(booking)
                db.commit()
                
                # Отправляем ссылку на оплату
                send_payment_link(
                    bot=bot,
                    chat_id=chat_id,
                    amount=booking.total_price,
                    booking_id=booking.booking_id,
                    booking_type='hotel'
                )
                
                # Отправляем уведомление менеджеру
                if MANAGER_CHAT_ID:
                    try:
                        manager_text = f"""
🏨 *НОВАЯ БРОНЬ ОТЕЛЯ*

*Номер брони:* {booking_id}
*Клиент:* {data.name} ({data.phone})
*TG:* @{message.from_user.username if message.from_user.username else 'нет'}
*ID:* {user_id}

*Детали брони:*
• Заезд: {data.checkin_display}
• Выезд: {data.checkout_display}
• Ночей: {data.nights}
• Стоимость: {data.total_price} руб.

*Статус:* Ожидает оплаты.
"""
                        bot.send_message(
                            MANAGER_CHAT_ID,
                            manager_text,
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        print(f"❌ Ошибка отправки менеджеру: {e}")
                
            except Exception as e:
                print(f"Ошибка создания бронирования: {e}")
                bot.send_message(
                    chat_id,
                    "❌ Произошла ошибка при создании бронирования. Пожалуйста, попробуйте еще раз или свяжитесь с менеджером.",
                    reply_markup=keyboards.main_menu()
                )
        
        # Очищаем состояние
        StateManager.clear_state(user_id)
        
    elif message.text == '✏️ Изменить данные':
        # Возвращаем к началу
        handle_hotel_start(bot, message)
        
    elif message.text == '🔙 Назад':
        # Возвращаем к вводу телефона
        StateManager.set_state(user_id, UserStates.HOTEL_ENTER_PHONE, StateManager.get_data(user_id))
        bot.send_message(
            chat_id,
            "📞 *Введите ваш номер телефона:*",
            parse_mode='Markdown',
            reply_markup=keyboards.back_button()
        )
        
    elif message.text == '❌ Отмена':
        StateManager.clear_state(user_id)
        bot.send_message(
            chat_id,
            "❌ Бронирование отменено. Возвращаемся в главное меню:",
            reply_markup=keyboards.main_menu()
        )