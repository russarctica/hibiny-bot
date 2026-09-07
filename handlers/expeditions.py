import telebot
from telebot import types
import json
from datetime import datetime, timedelta
import re
import random
import string
from database import get_db, User, Expedition, ExpeditionBooking, PromoOffer
from state_manager import StateManager
from states import UserStates, StateData
import keyboards

def handle_expeditions_start(bot, message):
    """Начало работы с экспедициями"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Устанавливаем состояние
    StateManager.set_state(user_id, UserStates.EXPEDITIONS_START, StateData(step=1))
    
    with next(get_db()) as db:
        # Получаем активные экспедиции
        expeditions = db.query(Expedition).filter_by(
            is_active=True
        ).order_by(Expedition.start_date.asc()).all()
        
        if not expeditions:
            bot.send_message(
                chat_id,
                "🧊 *ЭКСПЕДИЦИИ В АРКТИКУ*\n\n"
                "В данный момент нет доступных экспедиций.\n"
                "Следите за обновлениями - скоро появятся новые экспедиции!",
                parse_mode='Markdown',
                reply_markup=keyboards.main_menu()
            )
            StateManager.clear_state(user_id)
            return
        
        # Получаем активные промо-предложения
        promo_offers = db.query(PromoOffer).filter_by(
            is_active=True
        ).all()
        
        # Сохраняем данные
        expedition_ids = [exp.id for exp in expeditions]
        StateManager.set_state(
            user_id,
            UserStates.EXPEDITIONS_SELECT,
            StateData(
                expedition_ids=expedition_ids,
                current_page=0,
                has_promo=len(promo_offers) > 0,
                step=2
            )
        )
        
        # Показываем первую страницу экспедиций
        show_expeditions_page(bot, chat_id, expeditions, promo_offers, page=0)

def show_expeditions_page(bot, chat_id, expeditions, promo_offers, page=0):
    """Показывает страницу с экспедициями и промо-предложениями"""
    per_page = 2  # Меньше для лучшего отображения
    
    # Проверяем, показываем ли мы промо-предложения
    has_promo = len(promo_offers) > 0
    
    # Определяем, что показывать
    if has_promo and page == 0:
        # Показываем промо-предложения на первой странице
        show_promo_offers(bot, chat_id, promo_offers)
        return
    
    # Корректируем страницу для экспедиций
    if has_promo:
        exp_page = page - 1
    else:
        exp_page = page
    
    start = exp_page * per_page
    end = start + per_page
    current_expeditions = expeditions[start:end]
    
    if not current_expeditions and not has_promo:
        bot.send_message(
            chat_id,
            "❌ Нет доступных экспедиций.",
            reply_markup=keyboards.main_menu()
        )
        return
    
    for expedition in current_expeditions:
        # Проверяем количество свободных мест
        with next(get_db()) as db:
            bookings_count = db.query(ExpeditionBooking).filter_by(
                expedition_id=expedition.id,
                status='confirmed'
            ).count()
            
            free_spots = expedition.max_participants - bookings_count
            
            # Формируем текст экспедиции
            expedition_text = f"""
🧊 *{expedition.name}*

*Даты:* {expedition.start_date.strftime('%d.%m.%Y')} - {expedition.end_date.strftime('%d.%m.%Y')}
*Цена:* {int(expedition.price)} руб.
*Участников:* {free_spots} из {expedition.max_participants} мест
*Продолжительность:* {expedition.duration if hasattr(expedition, 'duration') else 'Не указано'}

*Описание:*
{expedition.description[:300]}{'...' if len(expedition.description) > 300 else ''}
"""
            
            markup = types.InlineKeyboardMarkup()
            if free_spots > 0:
                markup.add(
                    types.InlineKeyboardButton(
                        '📋 Подробнее и бронирование',
                        callback_data=f'expedition_details_{expedition.id}'
                    )
                )
            else:
                markup.add(
                    types.InlineKeyboardButton(
                        '❌ Нет мест',
                        callback_data='ignore'
                    )
                )
            
            bot.send_message(
                chat_id,
                expedition_text,
                parse_mode='Markdown',
                reply_markup=markup
            )
    
    # Добавляем навигацию если нужно
    total_pages = (len(expeditions) + per_page - 1) // per_page
    if has_promo:
        total_pages += 1  # Добавляем страницу с промо
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = []
    
    if page > 0:
        buttons.append(types.KeyboardButton('◀️ Предыдущие'))
    if (has_promo and page < total_pages - 1) or (not has_promo and page < total_pages - 1):
        buttons.append(types.KeyboardButton('▶️ Следующие'))
    
    if buttons:
        if len(buttons) == 2:
            markup.row(buttons[0], buttons[1])
        else:
            markup.row(buttons[0])
    
    markup.row(
        types.KeyboardButton('🔙 Назад'),
        types.KeyboardButton('❌ Отмена')
    )
    
    bot.send_message(
        chat_id,
        f"Страница {page + 1} из {total_pages}",
        reply_markup=markup
    )

def show_promo_offers(bot, chat_id, promo_offers):
    """Показывает промо-предложения"""
    if not promo_offers:
        return
    
    bot.send_message(
        chat_id,
        "🎁 *СПЕЦИАЛЬНЫЕ ПРЕДЛОЖЕНИЯ И ПРОМО-АКЦИИ*\n\n"
        "Ограниченные предложения от наших партнеров:",
        parse_mode='Markdown'
    )
    
    for promo in promo_offers:
        price_text = f"{promo.price} руб." if promo.price > 0 else "Цена обсуждается индивидуально"
        promo_text = f"""
🎁 *{promo.name}*

*Срок действия:* {promo.start_date.strftime('%d.%m.%Y')} - {promo.end_date.strftime('%d.%m.%Y')}
*Цена:* {price_text}

*Описание:*
{promo.description[:300]}{'...' if len(promo.description) > 300 else ''}
"""
        
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton(
                '📋 Подробнее и заказ',
                callback_data=f'order_promo_{promo.id}'
            )
        )
        
        bot.send_message(
            chat_id,
            promo_text,
            parse_mode='Markdown',
            reply_markup=markup
        )

def handle_expeditions_select(bot, message):
    """Обработка выбора экспедиции"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверка на кнопку "Назад"
    if message.text == '🔙 Назад':
        StateManager.clear_state(user_id)
        bot.send_message(
            chat_id,
            "Возвращаемся в главное меню:",
            reply_markup=keyboards.main_menu()
        )
        return
    
    # Проверка на кнопку "Отмена"
    if message.text == '❌ Отмена':
        StateManager.clear_state(user_id)
        bot.send_message(
            chat_id,
            "Действие отменено. Возвращаемся в главное меню:",
            reply_markup=keyboards.main_menu()
        )
        return
    
    # Проверка на навигацию
    if message.text == '◀️ Предыдущие':
        data = StateManager.get_data(user_id)
        if data.current_page > 0:
            data.current_page -= 1
            StateManager.update_data(user_id, current_page=data.current_page)
            
            with next(get_db()) as db:
                expeditions = db.query(Expedition).filter(
                    Expedition.id.in_(data.expedition_ids),
                    Expedition.is_active == True
                ).all()
                
                promo_offers = db.query(PromoOffer).filter_by(
                    is_active=True
                ).all()
                
                show_expeditions_page(bot, chat_id, expeditions, promo_offers, data.current_page)
        return
    
    elif message.text == '▶️ Следующие':
        data = StateManager.get_data(user_id)
        
        # Получаем общее количество страниц
        with next(get_db()) as db:
            expeditions = db.query(Expedition).filter(
                Expedition.id.in_(data.expedition_ids),
                Expedition.is_active == True
            ).all()
            
            promo_offers = db.query(PromoOffer).filter_by(
                is_active=True
            ).all()
            
            per_page = 2
            total_exp_pages = (len(expeditions) + per_page - 1) // per_page
            if data.has_promo:
                total_pages = total_exp_pages + 1
            else:
                total_pages = total_exp_pages
            
            if data.current_page < total_pages - 1:
                data.current_page += 1
                StateManager.update_data(user_id, current_page=data.current_page)
                show_expeditions_page(bot, chat_id, expeditions, promo_offers, data.current_page)
        return

def handle_expeditions_callback(bot, call):
    """Обработка callback для экспедиций"""
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    if call.data.startswith('expedition_details_'):
        expedition_id = int(call.data.replace('expedition_details_', ''))
        
        with next(get_db()) as db:
            expedition = db.query(Expedition).filter_by(
                id=expedition_id,
                is_active=True
            ).first()
            
            if not expedition:
                bot.answer_callback_query(call.id, "❌ Экспедиция не найдена!", show_alert=True)
                return
            
            # Проверяем количество свободных мест
            bookings_count = db.query(ExpeditionBooking).filter_by(
                expedition_id=expedition_id,
                status='confirmed'
            ).count()
            
            free_spots = expedition.max_participants - bookings_count
            
            if free_spots <= 0:
                bot.answer_callback_query(call.id, "❌ Нет свободных мест!", show_alert=True)
                return
            
            # Сохраняем выбранную экспедицию
            StateManager.set_state(
                user_id,
                UserStates.EXPEDITIONS_ENTER_NAME,
                StateData(
                    expedition_id=expedition_id,
                    expedition_name=expedition.name,
                    expedition_price=expedition.price,
                    max_participants=expedition.max_participants,
                    free_spots=free_spots,
                    step=3
                )
            )
            
            # Показываем детали и запрашиваем имя
            expedition_details = f"""
🧊 *{expedition.name}*

*Даты:* {expedition.start_date.strftime('%d.%m.%Y')} - {expedition.end_date.strftime('%d.%m.%Y')}
*Цена:* {int(expedition.price)} руб.
*Свободных мест:* {free_spots} из {expedition.max_participants}
*Продолжительность:* {expedition.duration if hasattr(expedition, 'duration') else 'Не указано'}

*Описание:*
{expedition.description}

*Программа:*
{expedition.program if hasattr(expedition, 'program') else 'Не указана'}

*Включено в стоимость:*
{expedition.included if hasattr(expedition, 'included') else 'Не указано'}
"""
            
            bot.send_message(
                chat_id,
                expedition_details,
                parse_mode='Markdown'
            )
            
            bot.send_message(
                chat_id,
                "✍️ *ВВЕДИТЕ ВАШЕ ИМЯ И ФАМИЛИЮ:*\n\n"
                "Пример: Иван Иванов\n\n"
                "Для отмены нажмите ❌ Отмена",
                parse_mode='Markdown',
                reply_markup=keyboards.cancel_button()
            )
            
            bot.answer_callback_query(call.id)
    
    elif call.data.startswith('order_promo_'):
        # Обработка заказа промо-предложения
        promo_id = int(call.data.replace('order_promo_', ''))
        
        with next(get_db()) as db:
            promo = db.query(PromoOffer).filter_by(
                id=promo_id,
                is_active=True
            ).first()
            
            if not promo:
                bot.answer_callback_query(call.id, "❌ Предложение не найдено!", show_alert=True)
                return
            
            # Сохраняем данные промо-предложения
            StateManager.set_state(
                user_id,
                UserStates.EXPEDITIONS_ENTER_NAME,
                StateData(
                    promo_id=promo_id,
                    promo_name=promo.name,
                    promo_price=promo.price,
                    promo_description=promo.description,
                    is_promo=True,
                    step=3
                )
            )
            
            price_text = f"{promo.price} руб." if promo.price > 0 else "Цена обсуждается индивидуально"
            promo_details = f"""
🎁 *{promo.name}*

*Срок действия:* {promo.start_date.strftime('%d.%m.%Y')} - {promo.end_date.strftime('%d.%m.%Y')}
*Цена:* {price_text}

*Описание:*
{promo.description}
"""
            
            bot.send_message(
                chat_id,
                promo_details,
                parse_mode='Markdown'
            )
            
            bot.send_message(
                chat_id,
                "✍️ *ВВЕДИТЕ ВАШЕ ИМЯ И ФАМИЛИЮ:*\n\n"
                "Пример: Иван Иванов\n\n"
                "Для отмены нажмите ❌ Отмена",
                parse_mode='Markdown',
                reply_markup=keyboards.cancel_button()
            )
            
            bot.answer_callback_query(call.id)

def handle_expeditions_enter_name(bot, message):
    """Обработка ввода имени для экспедиции"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        StateManager.clear_state(user_id)
        bot.send_message(
            chat_id,
            "Действие отменено. Возвращаемся в главное меню:",
            reply_markup=keyboards.main_menu()
        )
        return
    
    name = message.text.strip()
    
    if len(name) < 3:
        bot.send_message(
            chat_id,
            "❌ Имя слишком короткое! Введите имя и фамилию:",
            reply_markup=keyboards.cancel_button()
        )
        return
    
    data = StateManager.get_data(user_id)
    data.client_name = name
    
    if hasattr(data, 'is_promo') and data.is_promo:
        # Для промо-предложений переходим к телефону
        StateManager.set_state(user_id, UserStates.EXPEDITIONS_ENTER_PHONE, data)
        
        bot.send_message(
            chat_id,
            "📞 *ВВЕДИТЕ ВАШ НОМЕР ТЕЛЕФОНА:*\n\n"
            "Пример: +79161234567 или 89161234567 или 9161234567\n\n"
            "Для отмены нажмите ❌ Отмена",
            parse_mode='Markdown',
            reply_markup=keyboards.cancel_button()
        )
    else:
        # Для экспедиций запрашиваем количество человек
        StateManager.set_state(user_id, UserStates.EXPEDITIONS_ENTER_PEOPLE, data)
        
        bot.send_message(
            chat_id,
            f"👥 *СКОЛЬКО ЧЕЛОВЕК ХОТИТЕ ЗАПИСАТЬ НА ЭКСПЕДИЦИЮ?*\n\n"
            f"Доступно мест: {data.free_spots}\n"
            f"Максимально в группе: {data.max_participants}\n\n"
            f"Введите количество (от 1 до {min(data.free_spots, data.max_participants)}):",
            parse_mode='Markdown',
            reply_markup=keyboards.cancel_button()
        )

def handle_expeditions_enter_people(bot, message):
    """Обработка ввода количества людей"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        StateManager.clear_state(user_id)
        bot.send_message(
            chat_id,
            "Действие отменено. Возвращаемся в главное меню:",
            reply_markup=keyboards.main_menu()
        )
        return
    
    try:
        people_count = int(message.text.strip())
        data = StateManager.get_data(user_id)
        
        if people_count < 1 or people_count > data.free_spots:
            bot.send_message(
                chat_id,
                f"❌ Некорректное количество! Введите число от 1 до {data.free_spots}:",
                reply_markup=keyboards.cancel_button()
            )
            return
        
        data.people_count = people_count
        data.calculated_total_price = data.expedition_price * people_count  # Сохраняем расчетную стоимость отдельно
        
        StateManager.set_state(user_id, UserStates.EXPEDITIONS_ENTER_PHONE, data)
        
        bot.send_message(
            chat_id,
            "📞 *ВВЕДИТЕ ВАШ НОМЕР ТЕЛЕФОНА:*\n\n"
            "Пример: +79161234567 или 89161234567 или 9161234567\n\n"
            "Для отмены нажмите ❌ Отмена",
            parse_mode='Markdown',
            reply_markup=keyboards.cancel_button()
        )
        
    except ValueError:
        bot.send_message(
            chat_id,
            "❌ Неверный формат! Введите число:",
            reply_markup=keyboards.cancel_button()
        )

def handle_expeditions_enter_phone(bot, message):
    """Обработка ввода телефона"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        StateManager.clear_state(user_id)
        bot.send_message(
            chat_id,
            "Действие отменено. Возвращаемся в главное меню:",
            reply_markup=keyboards.main_menu()
        )
        return
    
    phone = message.text.strip()
    
    # УПРОЩЕННАЯ ПРОВЕРКА ТЕЛЕФОНА - принимаем почти любой ввод
    # Убираем все нецифровые символы, кроме плюса
    phone_clean = re.sub(r'[^\d+]', '', phone)
    
    # Проверяем минимальную длину (упрощенно)
    if len(phone_clean) < 6:
        bot.send_message(
            chat_id,
            "❌ Слишком короткий номер. Введите корректный номер телефона (минимум 6 цифр):",
            reply_markup=keyboards.cancel_button()
        )
        return
    
    data = StateManager.get_data(user_id)
    data.phone = phone_clean
    
    if hasattr(data, 'is_promo') and data.is_promo:
        # Для промо-предложений запрашиваем пожелания
        StateManager.set_state(user_id, UserStates.EXPEDITIONS_ENTER_WISHES, data)
        
        bot.send_message(
            chat_id,
            "💭 *ЕСТЬ ЛИ У ВАС ПОЖЕЛАНИЯ ИЛИ ВОПРОСЫ ПО ПРЕДЛОЖЕНИЮ?*\n\n"
            "Опишите ваши пожелания или вопросы:\n"
            "(Если нет - напишите 'нет')\n\n"
            "Для отмены нажмите ❌ Отмена",
            parse_mode='Markdown',
            reply_markup=keyboards.cancel_button()
        )
    else:
        # Для экспедиций показываем подтверждение
        show_expedition_confirmation(bot, chat_id, data)

def handle_expeditions_enter_wishes(bot, message):
    """Обработка ввода пожеланий"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        StateManager.clear_state(user_id)
        bot.send_message(
            chat_id,
            "Действие отменено. Возвращаемся в главное меню:",
            reply_markup=keyboards.main_menu()
        )
        return
    
    data = StateManager.get_data(user_id)
    data.wishes = message.text.strip()
    
    # Показываем подтверждение для промо-предложения
    show_promo_confirmation(bot, chat_id, data)

def show_expedition_confirmation(bot, chat_id, data):
    """Показывает подтверждение бронирования экспедиции"""
    total_price = getattr(data, 'calculated_total_price', 0)  # Используем расчетную стоимость
    
    confirmation_text = f"""
✅ *ПОДТВЕРЖДЕНИЕ БРОНИРОВАНИЯ ЭКСПЕДИЦИИ*

*Экспедиция:* {data.expedition_name}
*Имя:* {data.client_name}
*Телефон:* {data.phone}
*Количество человек:* {data.people_count}
*Общая стоимость:* {int(total_price)} руб.

*Всё верно?*
"""
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('✅ Подтвердить'),
        types.KeyboardButton('✏️ Изменить данные'),
        types.KeyboardButton('🔙 Назад'),
        types.KeyboardButton('❌ Отмена')
    )
    
    bot.send_message(
        chat_id,
        confirmation_text,
        parse_mode='Markdown',
        reply_markup=markup
    )
    
    # Сохраняем состояние с правильным user_id
    StateManager.set_state(
        chat_id,  # Временно используем chat_id как ключ
        UserStates.EXPEDITIONS_CONFIRMATION,
        data
    )

def show_promo_confirmation(bot, chat_id, data):
    """Показывает подтверждение заказа промо-предложения"""
    price_text = f"{data.promo_price} руб." if data.promo_price > 0 else "Цена обсуждается индивидуально"
    
    confirmation_text = f"""
✅ *ПОДТВЕРЖДЕНИЕ ЗАЯВКИ НА ПРОМО-ПРЕДЛОЖЕНИЕ*

*Предложение:* {data.promo_name}
*Имя:* {data.client_name}
*Телефон:* {data.phone}
*Цена:* {price_text}
*Пожелания:* {data.wishes}

*Всё верно?*
"""
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('✅ Подтвердить'),
        types.KeyboardButton('✏️ Изменить данные'),
        types.KeyboardButton('🔙 Назад'),
        types.KeyboardButton('❌ Отмена')
    )
    
    bot.send_message(
        chat_id,
        confirmation_text,
        parse_mode='Markdown',
        reply_markup=markup
    )
    
    # Сохраняем состояние с правильным user_id
    StateManager.set_state(
        chat_id,  # Временно используем chat_id как ключ
        UserStates.EXPEDITIONS_CONFIRMATION,
        data
    )

def handle_expeditions_confirmation(bot, message):
    """Обработка подтверждения экспедиции"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Получаем данные из состояния
    data = StateManager.get_data(chat_id)  # Используем chat_id вместо message.text
    
    if not data:
        # Пробуем получить данные по user_id
        data = StateManager.get_data(user_id)
        
        if not data:
            StateManager.clear_state(user_id)
            bot.send_message(
                chat_id,
                "❌ Данные не найдены. Начните заново.",
                reply_markup=keyboards.main_menu()
            )
            return
    
    if message.text == '✅ Подтвердить':
        try:
            with next(get_db()) as db:
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
                else:
                    # Обновляем телефон если нужно
                    if not user.phone:
                        user.phone = data.phone
                        db.commit()
                
                if hasattr(data, 'is_promo') and data.is_promo:
                    # Создаем заявку на промо-предложение
                    booking_id = 'PROMO' + ''.join(random.choices(string.digits, k=8))
                    
                    # Отправляем подтверждение клиенту
                    bot.send_message(
                        chat_id,
                        f"✅ *ВАША ЗАЯВКА ПРИНЯТА!*\n\n"
                        f"Номер заявки: {booking_id}\n"
                        f"Предложение: {data.promo_name}\n"
                        f"Ваши пожелания: {data.wishes}\n\n"
                        f"Менеджер свяжется с вами в ближайшее время для уточнения деталей.\n\n"
                        f"Спасибо за интерес к нашему предложению! 🎁",
                        parse_mode='Markdown',
                        reply_markup=keyboards.main_menu()
                    )
                    
                    # Отправляем уведомление менеджеру
                    from config import MANAGER_CHAT_ID
                    if MANAGER_CHAT_ID:
                        try:
                            manager_text = f"""
🎁 *НОВАЯ ЗАЯВКА НА ПРОМО-ПРЕДЛОЖЕНИЕ*

*Номер заявки:* {booking_id}
*Клиент:* {data.client_name}
*TG:* @{message.from_user.username if message.from_user.username else 'нет'}
*ID:* {user_id}
*Телефон:* {data.phone}
*Предложение:* {data.promo_name}
*Цена:* {data.promo_price if data.promo_price > 0 else 'Обсуждается'} руб.
*Пожелания:* {data.wishes}

*Статус:* Новая заявка
"""
                            bot.send_message(
                                MANAGER_CHAT_ID,
                                manager_text,
                                parse_mode='Markdown'
                            )
                        except Exception as e:
                            print(f"❌ Ошибка отправки менеджеру: {e}")
                
                else:
                    # Создаем бронирование экспедиции
                    booking_id = 'EXP' + ''.join(random.choices(string.digits, k=8))
                    
                    # Рассчитываем общую стоимость (для отображения)
                    total_price = data.expedition_price * data.people_count
                    
                    # Создаем бронирование БЕЗ поля total_price
                    booking = ExpeditionBooking(
                        user_id=user.id,
                        booking_id=booking_id,
                        expedition_id=data.expedition_id,
                        people_count=data.people_count,
                        # total_price=total_price,  # УБИРАЕМ это поле, так как его нет в модели
                        client_name=data.client_name,
                        client_phone=data.phone,
                        status='pending',
                        payment_status='unpaid'
                    )
                    db.add(booking)
                    db.commit()
                    
                    # Получаем экспедицию для информации
                    expedition = db.query(Expedition).filter_by(id=data.expedition_id).first()
                    
                    # Отправляем подтверждение клиенту
                    bot.send_message(
                        chat_id,
                        f"✅ *ВАША ЗАЯВКА ПРИНЯТА!*\n\n"
                        f"Номер бронирования: {booking_id}\n"
                        f"Экспедиция: {expedition.name if expedition else data.expedition_name}\n"
                        f"Количество человек: {data.people_count}\n"
                        f"Общая стоимость: {int(total_price)} руб.\n\n"
                        f"*Следующие шаги:*\n"
                        f"1. Оплатите заказ по реквизитам ниже\n"
                        f"2. После оплаты менеджер подтвердит ваше участие\n"
                        f"3. С вами свяжется куратор экспедиции\n\n"
                        f"*Реквизиты для оплаты:*\n"
                        f"Сбербанк: 40817810099910004312\n"
                        f"БИК: 044525225\n"
                        f"Назначение: Экспедиция {booking_id}",
                        parse_mode='Markdown',
                        reply_markup=keyboards.main_menu()
                    )
                    
                    # Отправляем уведомление менеджеру
                    from config import MANAGER_CHAT_ID
                    if MANAGER_CHAT_ID:
                        try:
                            manager_text = f"""
🧊 *НОВАЯ ЗАЯВКА НА ЭКСПЕДИЦИЮ*

*Номер брони:* {booking_id}
*Клиент:* {data.client_name}
*TG:* @{message.from_user.username if message.from_user.username else 'нет'}
*ID:* {user_id}
*Телефон:* {data.phone}
*Экспедиция:* {expedition.name if expedition else data.expedition_name}
*Количество человек:* {data.people_count}
*Стоимость за человека:* {int(data.expedition_price)} руб.
*Общая стоимость (рассчитано):* {int(total_price)} руб.

*Статус:* Ожидает оплаты
"""
                            bot.send_message(
                                MANAGER_CHAT_ID,
                                manager_text,
                                parse_mode='Markdown'
                            )
                        except Exception as e:
                            print(f"Ошибка отправки менеджеру: {e}")
                
        except Exception as e:
            print(f"Ошибка создания заявки: {e}")
            import traceback
            traceback.print_exc()
            bot.send_message(
                chat_id,
                "❌ Произошла ошибка при создании заявки. Пожалуйста, попробуйте еще раз или свяжитесь с менеджером.",
                reply_markup=keyboards.main_menu()
            )
        
        StateManager.clear_state(user_id)
        StateManager.clear_state(chat_id)  # Очищаем и по chat_id
    
    elif message.text == '✏️ Изменить данные':
        # Возвращаем к началу
        handle_expeditions_start(bot, message)
    
    elif message.text == '🔙 Назад':
        # Возвращаем на предыдущий шаг
        if hasattr(data, 'phone'):
            # Возвращаем к вводу телефона
            StateManager.set_state(user_id, UserStates.EXPEDITIONS_ENTER_PHONE, data)
            bot.send_message(
                chat_id,
                "📞 *ВВЕДИТЕ ВАШ НОМЕР ТЕЛЕФОНА:*\n\n"
                "Пример: +79161234567 или 89161234567\n\n"
                "Для отмены нажмите ❌ Отмена",
                parse_mode='Markdown',
                reply_markup=keyboards.cancel_button()
            )
        elif hasattr(data, 'client_name'):
            # Возвращаем к вводу имени
            StateManager.set_state(user_id, UserStates.EXPEDITIONS_ENTER_NAME, data)
            bot.send_message(
                chat_id,
                "✍️ *ВВЕДИТЕ ВАШЕ ИМЯ И ФАМИЛИЮ:*\n\n"
                "Пример: Иван Иванов\n\n"
                "Для отмены нажмите ❌ Отмена",
                parse_mode='Markdown',
                reply_markup=keyboards.cancel_button()
            )
        else:
            handle_expeditions_start(bot, message)
    
    elif message.text == '❌ Отмена':
        StateManager.clear_state(user_id)
        StateManager.clear_state(chat_id)
        bot.send_message(
            chat_id,
            "❌ Заявка отменена. Возвращаемся в главное меню:",
            reply_markup=keyboards.main_menu()
        )