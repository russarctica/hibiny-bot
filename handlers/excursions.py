import telebot
from telebot import types
import json
from datetime import datetime, timedelta
import random
import string
import re

from database import get_db, User, Excursion, ExcursionBooking, ExcursionOffer, Guide, Setting, Payment
from state_manager import StateManager
from states import UserStates, StateData
import keyboards
from config import MANAGER_CHAT_ID, GUIDES_CHAT_ID, SBP_PAYMENT_URL, EXCURSION_ACCESS_PRICE, EXCURSION_COMMISSION, EXCURSION_GROUP_DAYS_RANGE
from handlers.payment import send_commission_payment_link

# ========== ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ==========
def get_excursion_name(db, excursion_id):
    """Получает название экскурсии по ID"""
    excursion = db.query(Excursion).filter_by(id=excursion_id).first()
    return excursion.name if excursion else "Не указана"

def get_user_link(user):
    """Формирует кликабельную ссылку на пользователя Telegram"""
    if not user:
        return "неизвестно"
    if user.username:
        return f"@{user.username}"
    else:
        return f"[{user.first_name or 'ID'}](tg://user?id={user.user_id})"

def find_existing_groups_with_conditions(excursion_id, target_date_str):
    """Ищет существующие группы на эту же экскурсию в диапазоне ±5 дней"""
    target_date = datetime.strptime(target_date_str, "%d.%m.%Y")
    start_range = target_date - timedelta(days=EXCURSION_GROUP_DAYS_RANGE)
    end_range = target_date + timedelta(days=EXCURSION_GROUP_DAYS_RANGE)
    
    result = []
    
    with next(get_db()) as db:
        bookings = db.query(ExcursionBooking).filter(
            ExcursionBooking.excursion_id == excursion_id,
            ExcursionBooking.status.in_(['accepted', 'offers_received']),
            ExcursionBooking.guide_conditions_set == True,
            ExcursionBooking.is_first_in_group == True
        ).all()
        
        for b in bookings:
            try:
                b_date = datetime.strptime(b.booking_date, "%d.%m.%Y")
                if start_range <= b_date <= end_range:
                    child_bookings = db.query(ExcursionBooking).filter(
                        ExcursionBooking.parent_booking_id == b.id,
                        ExcursionBooking.status != 'cancelled'
                    ).all()
                    members = b.people_count + sum(c.people_count or 0 for c in child_bookings)
                    
                    result.append({
                        'booking_id': b.id,
                        'date': b.booking_date,
                        'location': b.guide_start_location or 'не указано',
                        'guide_name': b.guide_name or 'не назначен',
                        'guide_id': b.guide_id,
                        'current_people': members,
                        'max_people': b.group_max_people or 10,
                        'price_per_person': b.guide_price_per_person or 0
                    })
            except:
                continue
        
        return result

def handle_join_existing_group(bot, call):
    """Обработка присоединения к существующей группе"""
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    parent_booking_id = int(call.data.split('_')[-1])
    
    with next(get_db()) as db:
        parent = db.query(ExcursionBooking).filter_by(id=parent_booking_id).first()
        if not parent:
            bot.answer_callback_query(call.id, "❌ Группа не найдена", show_alert=True)
            return
        
        child_bookings = db.query(ExcursionBooking).filter(
            ExcursionBooking.parent_booking_id == parent.id,
            ExcursionBooking.status != 'cancelled'
        ).all()
        total_people = parent.people_count + sum(c.people_count or 0 for c in child_bookings)
        
        if parent.group_max_people and total_people >= parent.group_max_people:
            bot.answer_callback_query(call.id, "❌ В группе нет свободных мест", show_alert=True)
            return
        
        data = StateManager.get_data(user_id)
        data_dict = data.to_dict() if hasattr(data, 'to_dict') else {}
        data_dict['parent_booking_id'] = parent.id
        data_dict['is_joining_group'] = True
        data_dict['excursion_id'] = parent.excursion_id
        data_dict['excursion_name'] = get_excursion_name(db, parent.excursion_id)
        data_dict['booking_date'] = parent.booking_date
        
        remaining = parent.group_max_people - total_people if parent.group_max_people else 'не ограничено'
        
        excursion_text = f"""
🗺️ *ПРЕДЛОЖЕНИЕ ОТ ГИДА*

*Гид:* {parent.guide_name}
{get_user_link(db.query(User).filter_by(user_id=parent.guide_id).first())}

*Экскурсия:* {data_dict['excursion_name']}

*Предлагаемые условия:*
📅 *Дата:* {parent.booking_date}
🕒 *Время:* {parent.excursion_start_time or 'по договоренности'}
📍 *Место сбора:* {parent.guide_start_location or 'уточняется'}
👥 *Мест в группе:* {parent.group_max_people or 'не ограничено'} (осталось {remaining})
💰 *Цена за человека:* {int(parent.guide_price_per_person or 0)} руб.

*Номер заявки:* {parent.booking_id}
"""
        
        StateManager.set_state(user_id, UserStates.EXCURSIONS_VIEW_GROUP, StateData(**data_dict))
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, excursion_text, parse_mode='Markdown', reply_markup=keyboards.join_group_keyboard())

# ========== КЛИЕНТСКАЯ ЧАСТЬ ==========

def handle_excursions_start(bot, message):
    """Начало раздела экскурсий"""
    user_id = message.from_user.id
    chat_id = message.chat.id

    StateManager.set_state(user_id, UserStates.EXCURSIONS_START, StateData())

    bot.send_message(
        chat_id,
        "🗺️ *ЭКСКУРСИИ ПО ХИБИНАМ И КОЛЬСКОМУ ПОЛУОСТРОВУ*\n\n"
        "Выберите интересующую вас экскурсию:",
        parse_mode='Markdown',
        reply_markup=keyboards.excursions_list_keyboard()
    )

def handle_excursions_list(bot, message):
    """Обработка выбора экскурсии из списка"""
    user_id = message.from_user.id
    chat_id = message.chat.id

    if message.text == '🔙 Назад':
        StateManager.clear_state(user_id)
        bot.send_message(chat_id, "Возвращаемся в главное меню:", reply_markup=keyboards.main_menu())
        return

    if message.text == '❌ Отмена':
        StateManager.clear_state(user_id)
        bot.send_message(chat_id, "Действие отменено. Возвращаемся в главное меню:", reply_markup=keyboards.main_menu())
        return

    if message.text == '🏔️ Другие экскурсии':
        StateManager.set_state(user_id, UserStates.EXCURSIONS_OTHER, StateData())
        bot.send_message(chat_id, "🗺️ *ДРУГИЕ ЭКСКУРСИИ*\n\nВыберите сезон:", parse_mode='Markdown', reply_markup=keyboards.excursions_other_keyboard())
        return

    if message.text == '🧭 Туры':
        handle_tours_list(bot, message)
        return

    # Убираем все эмодзи в начале названия
    excursion_name = re.sub(r'^[^\w\s]+', '', message.text).strip()

    with next(get_db()) as db:
        excursion = db.query(Excursion).filter_by(name=excursion_name, is_active=True).first()

        if not excursion:
            bot.send_message(chat_id, "❌ Экскурсия не найдена. Пожалуйста, выберите из списка:", reply_markup=keyboards.excursions_list_keyboard())
            return

        StateManager.set_state(user_id, UserStates.EXCURSIONS_VIEW_DETAILS, StateData(excursion_id=excursion.id, excursion_name=excursion.name))

        excursion_text = f"""
🗺️ *{excursion.name}*

*Описание:*
{excursion.description}

Хотите забронировать эту экскурсию?
"""

        if excursion.photo_file_id:
            try:
                bot.send_photo(chat_id, excursion.photo_file_id, caption=excursion_text, parse_mode='Markdown', reply_markup=keyboards.excursion_detail_keyboard())
            except:
                bot.send_message(chat_id, excursion_text, parse_mode='Markdown', reply_markup=keyboards.excursion_detail_keyboard())
        else:
            bot.send_message(chat_id, excursion_text, parse_mode='Markdown', reply_markup=keyboards.excursion_detail_keyboard())

def handle_excursions_other(bot, message):
    """Обработка выбора сезона для 'Другие экскурсии'"""
    user_id = message.from_user.id
    chat_id = message.chat.id

    if message.text == '🔙 Назад':
        StateManager.set_state(user_id, UserStates.EXCURSIONS_START, StateData())
        bot.send_message(chat_id, "Выберите экскурсию:", reply_markup=keyboards.excursions_list_keyboard())
        return

    if message.text == '❌ Отмена':
        StateManager.clear_state(user_id)
        bot.send_message(chat_id, "Действие отменено. Возвращаемся в главное меню:", reply_markup=keyboards.main_menu())
        return

    if message.text in ['❄️ Зимние', '☀️ Летние']:
        season = "зимние" if message.text == '❄️ Зимние' else "летние"
        data = StateManager.get_data(user_id)
        data_dict = data.to_dict() if hasattr(data, 'to_dict') else {}
        data_dict['season'] = season
        data_dict['is_other_excursion'] = True
        StateManager.set_state(user_id, UserStates.EXCURSIONS_OTHER_INPUT, StateData(**data_dict))
        bot.send_message(
            chat_id,
            f"✏️ *Напишите какую экскурсию ищите (если {season}, то например снегоход или кайт, если летние, то например, сапы или дайвинг).*",
            parse_mode='Markdown',
            reply_markup=keyboards.back_button()
        )
    else:
        bot.send_message(chat_id, "❌ Пожалуйста, выберите сезон из списка:", reply_markup=keyboards.excursions_other_keyboard())

def handle_excursions_other_input(bot, message):
    """Обработка ввода названия экскурсии для 'Другие экскурсии'"""
    user_id = message.from_user.id
    chat_id = message.chat.id

    if message.text == '🔙 Назад':
        StateManager.set_state(user_id, UserStates.EXCURSIONS_OTHER, StateData())
        bot.send_message(chat_id, "Выберите сезон:", reply_markup=keyboards.excursions_other_keyboard())
        return

    if message.text == '❌ Отмена':
        StateManager.clear_state(user_id)
        bot.send_message(chat_id, "Действие отменено. Возвращаемся в главное меню:", reply_markup=keyboards.main_menu())
        return

    excursion_name = message.text.strip()
    if len(excursion_name) < 2:
        bot.send_message(chat_id, "❌ Название слишком короткое. Введите более подробное описание:", reply_markup=keyboards.back_button())
        return

    data = StateManager.get_data(user_id)
    data_dict = data.to_dict() if hasattr(data, 'to_dict') else {}
    data_dict['excursion_name'] = excursion_name
    data_dict['is_other_excursion'] = True

    StateManager.set_state(user_id, UserStates.EXCURSIONS_ENTER_DATE, StateData(**data_dict))
    bot.send_message(chat_id, "📅 *Введите желаемую дату экскурсии в формате ДД.ММ.ГГГГ:*\n\nПример: 25.12.2025", parse_mode='Markdown', reply_markup=keyboards.back_button())

def handle_tours_list(bot, message):
    """Показывает список доступных туров"""
    user_id = message.from_user.id
    chat_id = message.chat.id

    today = datetime.now().strftime("%d.%m.%Y")

    with next(get_db()) as db:
        tours = db.query(Excursion).filter(
            Excursion.is_tour == True,
            Excursion.is_active == True,
            Excursion.is_published == True,
            Excursion.end_date >= today
        ).all()

        if not tours:
            bot.send_message(chat_id, "🗺️ *ТУРЫ*\n\nНа данный момент нет доступных туров.", parse_mode='Markdown', reply_markup=keyboards.back_button())
            return

        markup = types.InlineKeyboardMarkup(row_width=1)
        for tour in tours:
            duration_days = ""
            if tour.start_date and tour.end_date:
                try:
                    start = datetime.strptime(tour.start_date, "%d.%m.%Y")
                    end = datetime.strptime(tour.end_date, "%d.%m.%Y")
                    days = (end - start).days + 1
                    duration_days = f" ({days} дн.: {tour.start_date} — {tour.end_date})"
                except:
                    pass
            markup.add(types.InlineKeyboardButton(
                f"🗺️ {tour.name}{duration_days}",
                callback_data=f'tour_select_{tour.id}'
            ))

        markup.add(types.InlineKeyboardButton('🔙 Назад', callback_data='tour_back_to_excursions'))

        bot.send_message(
            chat_id,
            "🗺️ *ДОСТУПНЫЕ ТУРЫ*\n\nВыберите интересующий вас тур:",
            parse_mode='Markdown',
            reply_markup=markup
        )

def handle_tour_select(bot, call):
    """Обработка выбора тура"""
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    tour_id = int(call.data.split('_')[-1])

    with next(get_db()) as db:
        tour = db.query(Excursion).filter_by(id=tour_id, is_tour=True, is_active=True).first()
        if not tour:
            bot.answer_callback_query(call.id, "❌ Тур не найден", show_alert=True)
            return

        StateManager.set_state(user_id, UserStates.EXCURSIONS_VIEW_DETAILS, StateData(
            excursion_id=tour.id,
            excursion_name=tour.name,
            is_tour=True
        ))

        duration_days = ""
        if tour.start_date and tour.end_date:
            try:
                start = datetime.strptime(tour.start_date, "%d.%m.%Y")
                end = datetime.strptime(tour.end_date, "%d.%m.%Y")
                days = (end - start).days + 1
                duration_days = f"\n📅 *Продолжительность:* {days} дн. ({tour.start_date} — {tour.end_date})"
            except:
                pass

        excursion_text = f"""
🗺️ *{tour.name}*

*Описание:*
{tour.description}
{duration_days}
📍 *Место старта:* {tour.start_location or 'не указано'}

Хотите забронировать этот тур?
"""

        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, excursion_text, parse_mode='Markdown', reply_markup=keyboards.excursion_detail_keyboard())

def handle_tour_back(bot, call):
    """Возврат к списку туров"""
    bot.answer_callback_query(call.id)
    fake_msg = types.Message(
        message_id=call.message.message_id,
        from_user=call.from_user,
        chat=call.message.chat,
        date=call.message.date,
        content_type='text',
        options={},
        json_string=''
    )
    fake_msg.text = '🧭 Туры'
    handle_tours_list(bot, fake_msg)

def handle_excursion_select(bot, message):
    """Обработка нажатия кнопки на деталях экскурсии"""
    user_id = message.from_user.id
    chat_id = message.chat.id

    if message.text == '🔙 Назад':
        if StateManager.go_back(user_id):
            bot.send_message(chat_id, "Выберите экскурсию:", reply_markup=keyboards.excursions_list_keyboard())
        return

    if message.text == '❌ Отмена':
        StateManager.clear_state(user_id)
        bot.send_message(chat_id, "Действие отменено. Возвращаемся в главное меню:", reply_markup=keyboards.main_menu())
        return

    if message.text == '✅ Забронировать':
        data = StateManager.get_data(user_id)
        data_dict = data.to_dict() if hasattr(data, 'to_dict') else {}
        data_dict['is_tour_booking'] = getattr(data, 'is_tour', False)
        StateManager.set_state(user_id, UserStates.EXCURSIONS_ENTER_DATE, StateData(**data_dict))
        bot.send_message(chat_id, "📅 *Введите желаемую дату экскурсии в формате ДД.ММ.ГГГГ:*\n\nПример: 25.12.2025", parse_mode='Markdown', reply_markup=keyboards.back_button())
    else:
        data = StateManager.get_data(user_id)
        if hasattr(data, 'excursion_id'):
            with next(get_db()) as db:
                excursion = db.query(Excursion).filter_by(id=data.excursion_id).first()
                if excursion:
                    excursion_text = f"""
🗺️ *{excursion.name}*

*Описание:*
{excursion.description}

Хотите забронировать эту экскурсию?
"""
                    bot.send_message(chat_id, excursion_text, parse_mode='Markdown', reply_markup=keyboards.excursion_detail_keyboard())

def handle_excursion_book(bot, message):
    handle_excursion_select(bot, message)

def handle_excursion_date(bot, message):
    """Обработка ввода даты для экскурсии"""
    user_id = message.from_user.id
    chat_id = message.chat.id

    if message.text == '🔙 Назад':
        if StateManager.go_back(user_id):
            data = StateManager.get_data(user_id)
            if getattr(data, 'is_other_excursion', False):
                bot.send_message(chat_id, "✏️ *Напишите какую экскурсию ищите:*", parse_mode='Markdown', reply_markup=keyboards.back_button())
                return
            with next(get_db()) as db:
                excursion = db.query(Excursion).filter_by(id=data.excursion_id).first()
                if excursion:
                    excursion_text = f"""
🗺️ *{excursion.name}*

*Описание:*
{excursion.description}

Хотите забронировать эту экскурсию?
"""
                    bot.send_message(chat_id, excursion_text, parse_mode='Markdown', reply_markup=keyboards.excursion_detail_keyboard())
        return

    if message.text == '❌ Отмена':
        StateManager.clear_state(user_id)
        bot.send_message(chat_id, "Действие отменено. Возвращаемся в главное меню:", reply_markup=keyboards.main_menu())
        return

    date_str = message.text.strip()

    try:
        booking_date = datetime.strptime(date_str, "%d.%m.%Y")
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        if booking_date < today:
            bot.send_message(chat_id, "❌ Дата не может быть в прошлом. Введите будущую дату:", reply_markup=keyboards.back_button())
            return

        data = StateManager.get_data(user_id)
        data_dict = data.to_dict() if hasattr(data, 'to_dict') else {}
        data_dict['booking_date'] = date_str

        # Поиск групп ±5 дней
        if not getattr(data, 'is_other_excursion', False) and hasattr(data, 'excursion_id') and data.excursion_id:
            groups = find_existing_groups_with_conditions(data.excursion_id, date_str)
            if groups:
                markup = keyboards.existing_groups_keyboard(groups, date_str)
                StateManager.set_state(user_id, UserStates.EXCURSIONS_GROUP_SELECT, StateData(**data_dict))
                bot.send_message(chat_id, f"🔍 *Найдены группы поблизости!*\n\nВы можете присоединиться к существующей группе или оставить свою дату:", parse_mode='Markdown', reply_markup=markup)
                return
        
        # Уведомление, что клиент первый и групп нет
        bot.send_message(
            chat_id,
            "🔍 *Групп не найдено.*\n\n"
            "На данный момент вы единственный участник экскурсии.\n"
            "Ожидайте набора группы.\n"
            "Если группа не наберется за 24/2 часа до экскурсии, ваша заявка будет отменена.",
            parse_mode='Markdown'
        )
        
        data_dict['is_first_in_group'] = True
        StateManager.set_state(user_id, UserStates.EXCURSIONS_ENTER_PEOPLE, StateData(**data_dict))
        bot.send_message(chat_id, "👥 *Сколько человек поедет на экскурсию?*\n\nВведите количество от 1 до 10:", parse_mode='Markdown', reply_markup=keyboards.back_button())

    except ValueError:
        bot.send_message(chat_id, "❌ Неверный формат даты! Пожалуйста, введите дату в формате ДД.ММ.ГГГГ (например: 25.12.2025):", reply_markup=keyboards.back_button())

def handle_excursions_group_select(bot, call):
    """Обработка выбора группы или своей даты"""
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    data_str = call.data
    
    if data_str.startswith('join_existing_group_'):
        handle_join_existing_group(bot, call)
    elif data_str.startswith('keep_my_date_'):
        own_date = data_str.replace('keep_my_date_', '')
        data = StateManager.get_data(user_id)
        data_dict = data.to_dict() if hasattr(data, 'to_dict') else {}
        data_dict['booking_date'] = own_date
        data_dict['is_first_in_group'] = True
        StateManager.set_state(user_id, UserStates.EXCURSIONS_ENTER_PEOPLE, StateData(**data_dict))
        bot.send_message(chat_id, "👥 *Сколько человек поедет на экскурсию?*\n\nВведите количество от 1 до 10:", parse_mode='Markdown', reply_markup=keyboards.back_button())
        bot.answer_callback_query(call.id)
    else:
        bot.answer_callback_query(call.id)

def handle_keep_my_date(bot, call):
    """Обработка кнопки 'Оставить свою дату'"""
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    own_date = call.data.replace('keep_my_date_', '')
    
    data = StateManager.get_data(user_id)
    data_dict = data.to_dict() if hasattr(data, 'to_dict') else {}
    data_dict['booking_date'] = own_date
    data_dict['is_first_in_group'] = True
    
    StateManager.set_state(user_id, UserStates.EXCURSIONS_ENTER_PEOPLE, StateData(**data_dict))
    bot.send_message(chat_id, "👥 *Сколько человек поедет на экскурсию?*\n\nВведите количество от 1 до 10:", parse_mode='Markdown', reply_markup=keyboards.back_button())
    bot.answer_callback_query(call.id)

def handle_excursion_people(bot, message):
    """Обработка ввода количества человек"""
    user_id = message.from_user.id
    chat_id = message.chat.id

    if message.text == '🔙 Назад':
        if StateManager.go_back(user_id):
            bot.send_message(chat_id, "📅 *Введите желаемую дату экскурсии в формате ДД.ММ.ГГГГ:*", parse_mode='Markdown', reply_markup=keyboards.back_button())
        return

    if message.text == '❌ Отмена':
        StateManager.clear_state(user_id)
        bot.send_message(chat_id, "Действие отменено. Возвращаемся в главное меню:", reply_markup=keyboards.main_menu())
        return

    try:
        people_count = int(message.text)

        if people_count < 1:
            bot.send_message(chat_id, "❌ Количество человек должно быть не менее 1. Введите число от 1 до 10:", reply_markup=keyboards.back_button())
            return

        if people_count > 10:
            bot.send_message(chat_id, "❌ Количество человек не должно превышать 10. Введите число от 1 до 10:", reply_markup=keyboards.back_button())
            return

        data = StateManager.get_data(user_id)
        data_dict = data.to_dict() if hasattr(data, 'to_dict') else {}
        
        # Проверка лимита при присоединении к группе
        if getattr(data, 'parent_booking_id', None):
            with next(get_db()) as db:
                parent = db.query(ExcursionBooking).filter_by(id=data.parent_booking_id).first()
                if parent and parent.group_max_people:
                    child_bookings = db.query(ExcursionBooking).filter(
                        ExcursionBooking.parent_booking_id == parent.id,
                        ExcursionBooking.status != 'cancelled'
                    ).all()
                    already_people = parent.people_count + sum(c.people_count or 0 for c in child_bookings)
                    if already_people + people_count > parent.group_max_people:
                        remaining = parent.group_max_people - already_people
                        bot.send_message(
                            chat_id,
                            f"❌ *В группе недостаточно мест!*\n\n"
                            f"Всего мест: {parent.group_max_people}\n"
                            f"Уже занято: {already_people}\n"
                            f"Осталось: {remaining}\n"
                            f"Вы хотите забронировать: {people_count}\n\n"
                            f"Пожалуйста, уменьшите количество человек или выберите другую дату.",
                            parse_mode='Markdown'
                        )
                        return
        
        data_dict['people_count'] = people_count

        if people_count > 1:
            StateManager.set_state(user_id, UserStates.EXCURSIONS_CHILDREN_INFO, StateData(**data_dict))
            bot.send_message(chat_id, "👶 *В вашей компании есть дети?*", parse_mode='Markdown', reply_markup=keyboards.excursions_children_keyboard())
            return

        data_dict['has_children'] = False
        data_dict['children_info'] = ""

        StateManager.set_state(user_id, UserStates.EXCURSIONS_ENTER_NAME, StateData(**data_dict))
        bot.send_message(chat_id, "👤 *Введите ваше имя и фамилию:*\n\nИмя будет использоваться для обращения и в документах.", parse_mode='Markdown', reply_markup=keyboards.back_button())

    except ValueError:
        bot.send_message(chat_id, "❌ Пожалуйста, введите число (например: 2):", reply_markup=keyboards.back_button())

def handle_excursions_children_info(bot, message):
    """Обработка ввода информации о детях"""
    user_id = message.from_user.id
    chat_id = message.chat.id

    if message.text == '🔙 Назад':
        if StateManager.go_back(user_id):
            bot.send_message(chat_id, "👥 *Сколько человек поедет на экскурсию?*", reply_markup=keyboards.back_button())
        return

    if message.text == '❌ Отмена':
        StateManager.clear_state(user_id)
        bot.send_message(chat_id, "Действие отменено. Возвращаемся в главное меню:", reply_markup=keyboards.main_menu())
        return

    data = StateManager.get_data(user_id)
    data_dict = data.to_dict() if hasattr(data, 'to_dict') else {}

    if message.text == '👨 Только взрослые':
        data_dict['has_children'] = False
        data_dict['children_info'] = ""
        StateManager.set_state(user_id, UserStates.EXCURSIONS_ENTER_NAME, StateData(**data_dict))
        bot.send_message(chat_id, "👤 *Введите ваше имя и фамилию:*", parse_mode='Markdown', reply_markup=keyboards.back_button())
    elif message.text == '👶 Есть дети':
        StateManager.update_data(user_id, waiting_for='children_info')
        bot.send_message(chat_id, "👶 *Сколько детей и какого возраста?*\n\nНапишите в свободной форме:", reply_markup=keyboards.back_button())
    else:
        data_dict['has_children'] = True
        data_dict['children_info'] = message.text.strip()
        StateManager.set_state(user_id, UserStates.EXCURSIONS_ENTER_NAME, StateData(**data_dict))
        bot.send_message(chat_id, "👤 *Введите ваше имя и фамилию:*", parse_mode='Markdown', reply_markup=keyboards.back_button())

def handle_excursion_name(bot, message):
    """Обработка ввода имени для экскурсии"""
    user_id = message.from_user.id
    chat_id = message.chat.id

    if message.text == '🔙 Назад':
        if StateManager.go_back(user_id):
            data = StateManager.get_data(user_id)
            if hasattr(data, 'people_count') and data.people_count > 1:
                bot.send_message(chat_id, "👶 *В вашей компании есть дети?*", parse_mode='Markdown', reply_markup=keyboards.excursions_children_keyboard())
            else:
                bot.send_message(chat_id, "👥 *Сколько человек поедет на экскурсию?*", reply_markup=keyboards.back_button())
        return

    if message.text == '❌ Отмена':
        StateManager.clear_state(user_id)
        bot.send_message(chat_id, "Действие отменено. Возвращаемся в главное меню:", reply_markup=keyboards.main_menu())
        return

    name = message.text.strip()

    if len(name) < 2:
        bot.send_message(chat_id, "❌ Имя слишком короткое. Введите имя и фамилию (минимум 2 символа):", reply_markup=keyboards.back_button())
        return

    if len(name) > 100:
        bot.send_message(chat_id, "❌ Имя слишком длинное. Введите имя и фамилию (максимум 100 символов):", reply_markup=keyboards.back_button())
        return

    data = StateManager.get_data(user_id)
    data_dict = data.to_dict() if hasattr(data, 'to_dict') else {}
    data_dict['client_name'] = name

    StateManager.set_state(user_id, UserStates.EXCURSIONS_ENTER_PHONE, StateData(**data_dict))
    bot.send_message(chat_id, "📞 *Введите ваш номер телефона:*\n\nМожно вводить в любом формате, главное - чтобы были цифры\nПример: 8-900-123-45-67 или +7 900 123 45 67", parse_mode='Markdown', reply_markup=keyboards.back_button())

def handle_excursion_phone(bot, message):
    """Обработка ввода телефона для экскурсии"""
    user_id = message.from_user.id
    chat_id = message.chat.id

    if message.text == '🔙 Назад':
        if StateManager.go_back(user_id):
            bot.send_message(chat_id, "👤 *Введите ваше имя и фамилию:*", parse_mode='Markdown', reply_markup=keyboards.back_button())
        return

    if message.text == '❌ Отмена':
        StateManager.clear_state(user_id)
        bot.send_message(chat_id, "Действие отменено. Возвращаемся в главное меню:", reply_markup=keyboards.main_menu())
        return

    phone = message.text.strip()
    digits = re.findall(r'\d', phone)

    if not digits:
        bot.send_message(chat_id, "❌ Номер телефона должен содержать цифры. Введите номер телефона:", reply_markup=keyboards.back_button())
        return

    phone_number = ''.join(digits)

    if len(phone_number) < 10:
        bot.send_message(chat_id, "❌ Номер телефона слишком короткий. Введите номер телефона:", reply_markup=keyboards.back_button())
        return

    if len(phone_number) > 10:
        phone_number = phone_number[-10:]

    formatted_phone = f"+7{phone_number}"

    data = StateManager.get_data(user_id)
    data_dict = data.to_dict() if hasattr(data, 'to_dict') else {}
    data_dict['client_phone'] = formatted_phone

    # Для "Другие экскурсии" цена не определяется
    if not getattr(data, 'is_other_excursion', False) and hasattr(data, 'excursion_id') and data.excursion_id:
        with next(get_db()) as db:
            excursion = db.query(Excursion).filter_by(id=data.excursion_id).first()
            if excursion:
                data_dict['excursion_name'] = excursion.name
                data_dict['duration_hours'] = excursion.duration_hours

    StateManager.set_state(user_id, UserStates.EXCURSIONS_ENTER_NOTE, StateData(**data_dict))
    bot.send_message(chat_id, "📝 *Хотите добавить примечание к заявке?*\n\nНапример: нужен детский бустер, аллергия, особые пожелания.\nМожно пропустить, нажав «Пропустить».", parse_mode='Markdown', reply_markup=keyboards.instructors_note_keyboard())

def handle_excursion_note(bot, message):
    """Обработка ввода примечания клиентом"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '🔙 Назад':
        if StateManager.go_back(user_id):
            bot.send_message(chat_id, "📞 *Введите ваш номер телефона:*", parse_mode='Markdown', reply_markup=keyboards.back_button())
        return
    
    if message.text == '❌ Отмена':
        StateManager.clear_state(user_id)
        bot.send_message(chat_id, "Действие отменено. Возвращаемся в главное меню:", reply_markup=keyboards.main_menu())
        return
    
    data = StateManager.get_data(user_id)
    data_dict = data.to_dict() if hasattr(data, 'to_dict') else {}
    
    if message.text == '✉️ Пропустить':
        data_dict['client_note'] = ""
    else:
        data_dict['client_note'] = message.text.strip()
    
    StateManager.set_state(user_id, UserStates.EXCURSIONS_CONFIRMATION, StateData(**data_dict))
    data = StateManager.get_data(user_id)
    show_excursion_confirmation(bot, message, data)

def show_excursion_confirmation(bot, message, data):
    """Показывает подтверждение бронирования экскурсии"""
    chat_id = message.chat.id

    children_info = ""
    if hasattr(data, 'has_children') and data.has_children:
        children_info = f"\n👶 Дети: {data.children_info if hasattr(data, 'children_info') else 'есть'}"

    client_note = ""
    if hasattr(data, 'client_note') and data.client_note:
        client_note = f"\n📝 Примечание: {data.client_note}"

    confirmation_text = f"""
✅ *Проверьте данные бронирования:*

*Экскурсия:* {data.excursion_name if hasattr(data, 'excursion_name') else ''}
*Дата:* {data.booking_date if hasattr(data, 'booking_date') else ''}
*Количество человек:* {data.people_count if hasattr(data, 'people_count') else 1}{children_info}
*Продолжительность:* {data.duration_hours if hasattr(data, 'duration_hours') else 0} час(ов){client_note}

*Стоимость:*
💰 Стоимость будет уточнена гидом

*Контактные данные:*
👤 Имя: {data.client_name if hasattr(data, 'client_name') else ''}
📞 Телефон: {data.client_phone if hasattr(data, 'client_phone') else ''}

Всё верно?
"""

    bot.send_message(chat_id, confirmation_text, parse_mode='Markdown', reply_markup=keyboards.excursion_confirmation_keyboard())

def handle_excursion_confirmation(bot, message):
    """Обработка подтверждения бронирования экскурсии"""
    user_id = message.from_user.id
    chat_id = message.chat.id

    if message.text == '✅ Подтвердить бронирование':
        data = StateManager.get_data(user_id)

        required_fields = ['booking_date', 'people_count', 'client_name', 'client_phone']
        if not getattr(data, 'is_other_excursion', False):
            required_fields.append('excursion_id')

        missing_fields = [field for field in required_fields if not hasattr(data, field)]

        if missing_fields:
            bot.send_message(chat_id, f"❌ Не хватает данных: {', '.join(missing_fields)}. Начните бронирование заново.", reply_markup=keyboards.main_menu())
            StateManager.clear_state(user_id)
            return

        with next(get_db()) as db:
            try:
                user = db.query(User).filter_by(user_id=user_id).first()
                if not user:
                    user = User(user_id=user_id, username=message.from_user.username, first_name=message.from_user.first_name, last_name=message.from_user.last_name, phone=data.client_phone)
                    db.add(user)
                    db.commit()
                    db.refresh(user)

                excursion = None
                if not getattr(data, 'is_other_excursion', False) and hasattr(data, 'excursion_id') and data.excursion_id:
                    excursion = db.query(Excursion).filter_by(id=data.excursion_id).first()

                # Проверка лимита при присоединении к группе
                if getattr(data, 'parent_booking_id', None):
                    parent = db.query(ExcursionBooking).filter_by(id=data.parent_booking_id).first()
                    if parent and parent.group_max_people:
                        child_bookings = db.query(ExcursionBooking).filter(
                            ExcursionBooking.parent_booking_id == parent.id,
                            ExcursionBooking.status != 'cancelled'
                        ).all()
                        already_people = parent.people_count + sum(c.people_count or 0 for c in child_bookings)
                        if already_people + data.people_count > parent.group_max_people:
                            remaining = parent.group_max_people - already_people
                            bot.send_message(
                                chat_id,
                                f"❌ *В группе недостаточно мест!*\n\n"
                                f"Всего мест: {parent.group_max_people}\n"
                                f"Уже занято: {already_people}\n"
                                f"Осталось: {remaining}\n"
                                f"Вы хотите забронировать: {data.people_count}\n\n"
                                f"Пожалуйста, уменьшите количество человек или выберите другую дату.",
                                parse_mode='Markdown'
                            )
                            return

                booking = ExcursionBooking(
                    user_id=user.id,
                    excursion_id=data.excursion_id if not getattr(data, 'is_other_excursion', False) else None,
                    booking_id="temp",
                    booking_date=data.booking_date,
                    people_count=data.people_count,
                    client_name=data.client_name,
                    client_phone=data.client_phone,
                    total_price=0,
                    status='searching',
                    payment_status='unpaid',
                    has_children=getattr(data, 'has_children', False),
                    children_info=getattr(data, 'children_info', ''),
                    group_status='waiting_group',
                    is_tour_booking=getattr(data, 'is_tour_booking', False),
                    client_note=getattr(data, 'client_note', ''),
                    is_first_in_group=getattr(data, 'is_first_in_group', False),
                    parent_booking_id=getattr(data, 'parent_booking_id', None),
                    is_joining_group=getattr(data, 'is_joining_group', False),
                    guide_conditions_set=False,
                    group_is_ready=False,
                    group_checked_24h=False,
                    group_checked_2h=False,
                    client_contacts_hidden=True
                )
                db.add(booking)
                db.commit()
                db.refresh(booking)

                booking.booking_id = f"ЭКС{booking.id}"
                db.commit()

                excursion_name = getattr(data, 'excursion_name', 'Другая экскурсия')
                if excursion:
                    excursion_name = excursion.name

                bot.send_message(
                    chat_id,
                    f"🎉 *ЗАЯВКА НА ЭКСКУРСИЮ ПОДТВЕРЖДЕНА!*\n\n"
                    f"📋 Номер заявки: {booking.booking_id}\n"
                    f"🗺️ Экскурсия: {excursion_name}\n"
                    f"📅 Дата: {data.booking_date}\n"
                    f"👥 Количество человек: {data.people_count}\n"
                    f"💰 Стоимость будет уточнена гидом\n\n"
                    f"*Что дальше?*\n"
                    f"1. Заявка отправлена гидам\n"
                    f"2. Гиды предложат свои условия\n"
                    f"3. Вы получите предложения в течение 48 часов\n"
                    f"4. Выберите подходящее предложение\n\n"
                    f"Следите за уведомлениями! ⏰",
                    parse_mode='Markdown',
                    reply_markup=keyboards.main_menu()
                )

                # Отправка уведомлений
                is_tour = getattr(data, 'is_tour_booking', False)

                if is_tour and excursion and excursion.guide_user_id:
                    # Тур: только гиду-создателю и админу
                    guide_user = db.query(User).filter_by(user_id=excursion.guide_user_id).first()
                    if guide_user:
                        guide_text = f"""
🗺️ *НОВАЯ ЗАЯВКА НА ТУР!*

*Номер заявки:* {booking.booking_id}
*Тур:* {excursion_name}
*Клиент:* {data.client_name} ({data.client_phone})
*Дата:* {data.booking_date}
*Количество человек:* {data.people_count}
{f"👶 Дети: {data.children_info}" if getattr(data, 'has_children', False) and data.children_info else ""}
{f"📝 Примечание: {data.client_note}" if getattr(data, 'client_note', '') else ""}
*Статус:* 🔍 Требуется подтверждение
"""
                        bot.send_message(guide_user.user_id, guide_text, parse_mode='Markdown')

                    if MANAGER_CHAT_ID:
                        manager_text = f"""
🗺️ *НОВАЯ ЗАЯВКА НА ТУР*

*Номер заявки:* {booking.booking_id}
*Тур:* {excursion_name}
*Клиент:* {data.client_name} ({data.client_phone})
*TG:* @{message.from_user.username if message.from_user.username else 'нет'}
*ID:* {user_id}
*Дата:* {data.booking_date}
*Количество человек:* {data.people_count}
{f"👶 Дети: {data.children_info}" if getattr(data, 'has_children', False) and data.children_info else ""}
{f"📝 Примечание: {data.client_note}" if getattr(data, 'client_note', '') else ""}
*Статус:* 🔍 Требуется подтверждение гида
"""
                        bot.send_message(MANAGER_CHAT_ID, manager_text, parse_mode='Markdown')
                else:
                    # Обычная экскурсия: в общий чат гидов (БЕЗ ЦЕНЫ)
                    if GUIDES_CHAT_ID and not getattr(data, 'is_joining_group', False):
                        try:
                            chat_text = f"""
🗺️ *НОВАЯ ЗАЯВКА НА ЭКСКУРСИЮ*

*Номер заявки:* {booking.booking_id}
*Экскурсия:* {excursion_name}
*Желаемая дата:* {data.booking_date}
*Количество человек:* {data.people_count}
{f"👶 Дети: {data.children_info}" if getattr(data, 'has_children', False) and data.children_info else ""}
{f"📝 Примечание: {data.client_note}" if getattr(data, 'client_note', '') else ""}
*Статус:* 🔍 Ищет гида"""
                            markup = keyboards.create_guide_offer_button(booking.id)
                            bot.send_message(GUIDES_CHAT_ID, chat_text, parse_mode='Markdown', reply_markup=markup)
                            print(f"✅ Отправлено сообщение в чат гидов (GUIDES_CHAT_ID={GUIDES_CHAT_ID})")
                        except Exception as e:
                            print(f"❌ Ошибка отправки в чат гидов: {e}")

                # Если это присоединение к существующей группе — уведомить гида
                if booking.parent_booking_id:
                    parent_booking = db.query(ExcursionBooking).filter_by(id=booking.parent_booking_id).first()
                    if parent_booking and parent_booking.guide_id:
                        try:
                            # Считаем остаток мест
                            child_bookings = db.query(ExcursionBooking).filter(
                                ExcursionBooking.parent_booking_id == parent_booking.id,
                                ExcursionBooking.status != 'cancelled'
                            ).all()
                            already_people = parent_booking.people_count + sum(c.people_count or 0 for c in child_bookings)
                            remaining = parent_booking.group_max_people - already_people if parent_booking.group_max_people else 'не ограничено'
                            
                            guide_msg = f"""
👥 *НОВАЯ ЗАЯВКА В ГРУППУ {parent_booking.booking_id} ({booking.people_count} чел)!*

📅 *Дата:* {parent_booking.booking_date}
🕒 *Время:* {parent_booking.excursion_start_time or 'по договоренности'}
📍 *Место сбора:* {parent_booking.guide_start_location or 'уточняется'}
👥 *Мест в группе:* от {parent_booking.group_min_people} до {parent_booking.group_max_people}
💰 *Цена за человека:* {int(parent_booking.guide_price_per_person or 0)} руб.

👤 *Участники:*
{booking.client_name} (новый!)

💰 *Общая стоимость:* {int((parent_booking.guide_price_per_person or 0) * (already_people + booking.people_count))} руб.
💸 *Комиссия (5%):* {int((parent_booking.guide_price_per_person or 0) * (already_people + booking.people_count) * 0.05)} руб.
*Осталось мест:* {remaining}
"""
                            markup = keyboards.guide_confirm_join_keyboard(booking.id)
                            bot.send_message(parent_booking.guide_id, guide_msg, parse_mode='Markdown', reply_markup=markup)
                        except Exception as e:
                            print(f"Ошибка отправки уведомления гиду о новой заявке: {e}")

            except Exception as e:
                print(f"Ошибка создания бронирования: {e}")
                import traceback
                traceback.print_exc()
                bot.send_message(chat_id, "❌ Произошла ошибка при создании заявки. Пожалуйста, попробуйте еще раз или свяжитесь с менеджером.", reply_markup=keyboards.main_menu())

        StateManager.clear_state(user_id)

    elif message.text == '✏️ Изменить данные':
        handle_excursions_start(bot, message)
    elif message.text == '🔙 Назад':
        if StateManager.go_back(user_id):
            bot.send_message(chat_id, "📞 *Введите ваш номер телефона:*", parse_mode='Markdown', reply_markup=keyboards.back_button())
        else:
            handle_excursions_start(bot, message)
    elif message.text == '❌ Отмена':
        StateManager.clear_state(user_id)
        bot.send_message(chat_id, "❌ Бронирование отменено. Возвращаемся в главное меню:", reply_markup=keyboards.main_menu())

# ========== ГИДСКАЯ ЧАСТЬ (СОЗДАНИЕ ЭКСКУРСИЙ) ==========

def handle_guide_start(bot, message):
    """Начало работы с гидом"""
    user_id = message.from_user.id
    chat_id = message.chat.id

    with next(get_db()) as db:
        guide = db.query(Guide).filter_by(user_id=user_id).first()
        user = db.query(User).filter_by(user_id=user_id).first()

        if not guide:
            if not user:
                user = User(user_id=user_id, username=message.from_user.username, first_name=message.from_user.first_name, last_name=message.from_user.last_name, is_guide=True)
                db.add(user)
                db.commit()
                db.refresh(user)

            guide = Guide(user_id=user_id, name=message.from_user.first_name or "Гид", username=message.from_user.username or "", phone="", specialties="", is_active=True)
            db.add(guide)
            db.commit()

        if user and not user.is_guide:
            user.is_guide = True
            db.commit()

    StateManager.clear_state(user_id)
    bot.send_message(chat_id, "👋 *Добро пожаловать в панель гида!*\n\nЗдесь вы можете создавать и управлять своими экскурсиями, получать заявки от клиентов и отправлять предложения.\n\nВыберите действие:", parse_mode='Markdown', reply_markup=keyboards.guide_menu_keyboard())

def handle_guide_access_payment(bot, message):
    """Обработка оплаты доступа для создания экскурсии"""
    user_id = message.from_user.id
    chat_id = message.chat.id

    with next(get_db()) as db:
        guide = db.query(Guide).filter_by(user_id=user_id).first()
        if not guide:
            bot.send_message(chat_id, "❌ Вы не зарегистрированы как гид. Используйте команду /guide для регистрации.")
            return

        existing = db.query(Excursion).filter_by(
            guide_user_id=user_id,
            access_paid=True,
            is_published=False
        ).first()

        if existing:
            bot.send_message(chat_id, "⚠️ У вас уже есть оплаченный доступ для создания экскурсии. Продолжите создание.")
            StateManager.set_state(user_id, UserStates.GUIDE_CREATE_NAME, StateData(excursion_id=existing.id))
            bot.send_message(chat_id, "✏️ *Введите название экскурсии:*\n\nМинимум 3 символа.", parse_mode='Markdown', reply_markup=keyboards.guide_create_cancel_keyboard())
            return

    payment_text = f"""
💳 *Оплата доступа для создания экскурсии*

💰 Стоимость доступа: *{EXCURSION_ACCESS_PRICE} руб.*

Для создания одной экскурсии необходимо оплатить доступ.
После оплаты вы сможете создать экскурсию, и она появится в списке для клиентов.

⚠️ *Важно:* доступ действует на создание ОДНОЙ экскурсии.
Чтобы создать ещё одну экскурсию, нужно будет снова оплатить доступ.

Нажмите «Оплатить» для перехода к оплате по СБП.
"""

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton('💳 Оплатить доступ', url=SBP_PAYMENT_URL),
        types.InlineKeyboardButton('✅ Я оплатил', callback_data=f'guide_access_paid_{user_id}')
    )

    bot.send_message(chat_id, payment_text, parse_mode='Markdown', reply_markup=markup)

def handle_guide_access_paid(bot, call):
    """Подтверждение оплаты доступа гидом - автоматическое открытие доступа"""
    user_id = int(call.data.split('_')[-1])
    chat_id = call.message.chat.id

    with next(get_db()) as db:
        guide = db.query(Guide).filter_by(user_id=user_id).first()
        if not guide:
            bot.answer_callback_query(call.id, "❌ Гид не найден", show_alert=True)
            return

        excursion = Excursion(
            name="Новая экскурсия",
            description="",
            price_per_person=0,
            min_people=1,
            max_people=10,
            duration_hours=2,
            guide_user_id=user_id,
            access_paid=True,
            is_active=False,
            is_published=False
        )
        db.add(excursion)
        db.commit()
        db.refresh(excursion)

        if MANAGER_CHAT_ID:
            manager_text = f"""
🗺️ *НОВЫЙ ЭКСКУРСОВОД ОПЛАТИЛ ДОСТУП*

👤 Гид: {guide.name}
🆔 ID: {user_id}
📞 Телефон: {guide.phone or 'не указан'}
💰 Сумма: {EXCURSION_ACCESS_PRICE} руб.
📋 Экскурсия: в процессе создания

✅ Доступ открыт автоматически.
"""
            bot.send_message(MANAGER_CHAT_ID, manager_text, parse_mode='Markdown')

        bot.answer_callback_query(call.id, "✅ Оплата подтверждена! Создайте экскурсию.")

        bot.send_message(chat_id, "✅ Доступ подтверждён! Создайте экскурсию.")
        StateManager.set_state(user_id, UserStates.GUIDE_CREATE_NAME, StateData(excursion_id=excursion.id))
        bot.send_message(chat_id, "✏️ *Введите название экскурсии:*\n\nМинимум 3 символа.", parse_mode='Markdown', reply_markup=keyboards.guide_create_cancel_keyboard())

def handle_guide_create_name(bot, message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    if message.text == '❌ Отменить создание':
        StateManager.clear_state(user_id)
        bot.send_message(chat_id, "❌ Создание экскурсии отменено.", reply_markup=keyboards.guide_menu_keyboard())
        return
    name = message.text.strip()
    if len(name) < 3:
        bot.send_message(chat_id, "❌ Название слишком короткое. Введите название экскурсии (минимум 3 символа):", reply_markup=keyboards.guide_create_cancel_keyboard())
        return
    if len(name) > 200:
        bot.send_message(chat_id, "❌ Название слишком длинное. Введите название экскурсии (максимум 200 символов):", reply_markup=keyboards.guide_create_cancel_keyboard())
        return

    data = StateManager.get_data(user_id)
    data_dict = data.to_dict() if hasattr(data, 'to_dict') else {}
    data_dict['excursion_name'] = name

    StateManager.set_state(user_id, UserStates.GUIDE_CREATE_DESCRIPTION, StateData(**data_dict))
    bot.send_message(chat_id, "📝 *Введите описание экскурсии:*\n\nОпишите маршрут, достопримечательности, что включено, особенности:\n(минимум 50 символов)", parse_mode='Markdown', reply_markup=keyboards.guide_create_cancel_keyboard())

def handle_guide_create_description(bot, message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    if message.text == '❌ Отменить создание':
        StateManager.clear_state(user_id)
        bot.send_message(chat_id, "❌ Создание экскурсии отменено.", reply_markup=keyboards.guide_menu_keyboard())
        return
    description = message.text.strip()
    if len(description) < 50:
        bot.send_message(chat_id, "❌ Описание слишком короткое. Введите подробное описание (минимум 50 символов):", reply_markup=keyboards.guide_create_cancel_keyboard())
        return
    data = StateManager.get_data(user_id)
    data_dict = data.to_dict() if hasattr(data, 'to_dict') else {}
    data_dict['excursion_description'] = description
    StateManager.set_state(user_id, UserStates.GUIDE_CREATE_PHOTO, StateData(**data_dict))
    bot.send_message(chat_id, "📸 *Пришлите фото для экскурсии:*\n\nОтправьте одно фото (рекомендуется горизонтальная ориентация)\nМожно пропустить этот шаг, отправив любой текст", parse_mode='Markdown', reply_markup=keyboards.guide_create_cancel_keyboard())

def handle_guide_create_photo(bot, message):
    pass

def handle_guide_create_photo_input(bot, message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    if message.text == '❌ Отменить создание':
        StateManager.clear_state(user_id)
        bot.send_message(chat_id, "❌ Создание экскурсии отменено.", reply_markup=keyboards.guide_menu_keyboard())
        return
    if message.photo:
        photo_file_id = message.photo[-1].file_id
        data = StateManager.get_data(user_id)
        data_dict = data.to_dict() if hasattr(data, 'to_dict') else {}
        data_dict['photo_file_id'] = photo_file_id
        StateManager.set_state(user_id, UserStates.GUIDE_CREATE_PRICE, StateData(**data_dict))
        bot.send_message(chat_id, "✅ *Фото сохранено!*\n\n💰 *Введите цену за человека и скидку за группу через пробел:*\n\nПример: *2500 10* — цена 2500 руб., скидка за группу 10%", parse_mode='Markdown', reply_markup=keyboards.guide_create_cancel_keyboard())
    else:
        data = StateManager.get_data(user_id)
        data_dict = data.to_dict() if hasattr(data, 'to_dict') else {}
        StateManager.set_state(user_id, UserStates.GUIDE_CREATE_PRICE, StateData(**data_dict))
        bot.send_message(chat_id, "⏭️ *Шаг с фото пропущен.*\n\n💰 *Введите цену за человека и скидку за группу через пробел:*\n\nПример: *2500 10* — цена 2500 руб., скидка за группу 10%", parse_mode='Markdown', reply_markup=keyboards.guide_create_cancel_keyboard())

def handle_guide_create_price(bot, message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    if message.text == '❌ Отменить создание':
        StateManager.clear_state(user_id)
        bot.send_message(chat_id, "❌ Создание экскурсии отменено.", reply_markup=keyboards.guide_menu_keyboard())
        return

    parts = message.text.strip().split()

    if len(parts) != 2:
        bot.send_message(chat_id, "❌ Введите цену и скидку через пробел.\nПример: *2500 10* — цена 2500 руб., скидка за группу 10%", parse_mode='Markdown', reply_markup=keyboards.guide_create_cancel_keyboard())
        return

    try:
        price = float(parts[0])
        discount = int(parts[1])

        if price <= 0:
            bot.send_message(chat_id, "❌ Цена должна быть больше 0. Введите корректную цену:", reply_markup=keyboards.guide_create_cancel_keyboard())
            return

        if discount < 0 or discount > 100:
            bot.send_message(chat_id, "❌ Скидка должна быть от 0 до 100%. Введите корректное значение:", reply_markup=keyboards.guide_create_cancel_keyboard())
            return

        data = StateManager.get_data(user_id)
        data_dict = data.to_dict() if hasattr(data, 'to_dict') else {}
        data_dict['price_per_person'] = price
        data_dict['group_discount'] = discount

        StateManager.set_state(user_id, UserStates.GUIDE_CREATE_MIN_PEOPLE, StateData(**data_dict))
        bot.send_message(chat_id, "👥 *Введите минимальное количество человек для проведения экскурсии:*\n\nМинимальное количество людей, при котором экскурсия состоится.", parse_mode='Markdown', reply_markup=keyboards.guide_create_cancel_keyboard())

    except ValueError:
        bot.send_message(chat_id, "❌ Неверный формат. Введите: *цена скидка* (например: 2500 10)", reply_markup=keyboards.guide_create_cancel_keyboard())

def handle_guide_create_min_people(bot, message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    if message.text == '❌ Отменить создание':
        StateManager.clear_state(user_id)
        bot.send_message(chat_id, "❌ Создание экскурсии отменено.", reply_markup=keyboards.guide_menu_keyboard())
        return
    try:
        min_people = int(message.text)
        if min_people < 1:
            bot.send_message(chat_id, "❌ Минимальное количество должно быть не менее 1. Введите корректное число:", reply_markup=keyboards.guide_create_cancel_keyboard())
            return
        data = StateManager.get_data(user_id)
        data_dict = data.to_dict() if hasattr(data, 'to_dict') else {}
        data_dict['min_people'] = min_people
        StateManager.set_state(user_id, UserStates.GUIDE_CREATE_MAX_PEOPLE, StateData(**data_dict))
        bot.send_message(chat_id, "👥 *Введите максимальное количество человек в группе:*\n\nМаксимальное количество людей, которое может принять экскурсия.", parse_mode='Markdown', reply_markup=keyboards.guide_create_cancel_keyboard())
    except ValueError:
        bot.send_message(chat_id, "❌ Неверный формат. Введите целое число (например: 2):", reply_markup=keyboards.guide_create_cancel_keyboard())

def handle_guide_create_max_people(bot, message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    if message.text == '❌ Отменить создание':
        StateManager.clear_state(user_id)
        bot.send_message(chat_id, "❌ Создание экскурсии отменено.", reply_markup=keyboards.guide_menu_keyboard())
        return
    try:
        max_people = int(message.text)
        data = StateManager.get_data(user_id)
        min_people = data.min_people if hasattr(data, 'min_people') else 1
        if max_people < min_people:
            bot.send_message(chat_id, f"❌ Максимальное количество должно быть не меньше минимального ({min_people}). Введите корректное число:", reply_markup=keyboards.guide_create_cancel_keyboard())
            return
        data_dict = data.to_dict() if hasattr(data, 'to_dict') else {}
        data_dict['max_people'] = max_people
        StateManager.set_state(user_id, UserStates.GUIDE_CREATE_DATES, StateData(**data_dict))
        bot.send_message(chat_id, "📅 *Введите дату начала и окончания тура через пробел:*\n\nФормат: ДД.ММ.ГГГГ ДД.ММ.ГГГГ\nПример: 01.04.2026 05.04.2026", parse_mode='Markdown', reply_markup=keyboards.guide_create_cancel_keyboard())
    except ValueError:
        bot.send_message(chat_id, "❌ Неверный формат. Введите целое число (например: 4):", reply_markup=keyboards.guide_create_cancel_keyboard())

def handle_guide_create_dates(bot, message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    if message.text == '❌ Отменить создание':
        StateManager.clear_state(user_id)
        bot.send_message(chat_id, "❌ Создание экскурсии отменено.", reply_markup=keyboards.guide_menu_keyboard())
        return

    parts = message.text.strip().split()

    if len(parts) != 2:
        bot.send_message(chat_id, "❌ Введите две даты через пробел: ДД.ММ.ГГГГ ДД.ММ.ГГГГ", reply_markup=keyboards.guide_create_cancel_keyboard())
        return

    try:
        start = datetime.strptime(parts[0], "%d.%m.%Y")
        end = datetime.strptime(parts[1], "%d.%m.%Y")

        if end < start:
            bot.send_message(chat_id, "❌ Дата окончания не может быть раньше даты начала.", reply_markup=keyboards.guide_create_cancel_keyboard())
            return

        data = StateManager.get_data(user_id)
        data_dict = data.to_dict() if hasattr(data, 'to_dict') else {}
        data_dict['start_date'] = parts[0]
        data_dict['end_date'] = parts[1]

        StateManager.set_state(user_id, UserStates.GUIDE_CREATE_LOCATION, StateData(**data_dict))
        bot.send_message(chat_id, "📍 *Укажите место старта экскурсии:*\n\nНапример: Кировск, Мурманск, Апатиты...", parse_mode='Markdown', reply_markup=keyboards.guide_create_cancel_keyboard())

    except ValueError:
        bot.send_message(chat_id, "❌ Неверный формат даты. Введите: ДД.ММ.ГГГГ ДД.ММ.ГГГГ", reply_markup=keyboards.guide_create_cancel_keyboard())

def handle_guide_create_location(bot, message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    if message.text == '❌ Отменить создание':
        StateManager.clear_state(user_id)
        bot.send_message(chat_id, "❌ Создание экскурсии отменено.", reply_markup=keyboards.guide_menu_keyboard())
        return

    location = message.text.strip()
    if len(location) < 2:
        bot.send_message(chat_id, "❌ Место старта слишком короткое. Введите корректное место:", reply_markup=keyboards.guide_create_cancel_keyboard())
        return

    data = StateManager.get_data(user_id)
    data_dict = data.to_dict() if hasattr(data, 'to_dict') else {}
    data_dict['start_location'] = location

    StateManager.set_state(user_id, UserStates.GUIDE_CREATE_TIMES, StateData(**data_dict))
    bot.send_message(chat_id, "🕒 *Введите время начала экскурсии:*\n\nФормат: ЧЧ:ММ\nНапример: 10:00\nИли напишите «любое»", parse_mode='Markdown', reply_markup=keyboards.guide_create_cancel_keyboard())

def handle_guide_create_times(bot, message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    if message.text == '❌ Отменить создание':
        StateManager.clear_state(user_id)
        bot.send_message(chat_id, "❌ Создание экскурсии отменено.", reply_markup=keyboards.guide_menu_keyboard())
        return

    time_str = message.text.strip()

    if time_str.lower() == 'любое':
        time_str = ""

    if time_str:
        time_pattern = r'^([0-1]?[0-9]|2[0-3]):([0-5][0-9])$'
        if not re.match(time_pattern, time_str):
            bot.send_message(chat_id, "❌ Неверный формат времени. Введите время в формате ЧЧ:ММ или «любое»:", reply_markup=keyboards.guide_create_cancel_keyboard())
            return

    data = StateManager.get_data(user_id)
    data_dict = data.to_dict() if hasattr(data, 'to_dict') else {}
    data_dict['available_times'] = time_str

    StateManager.set_state(user_id, UserStates.GUIDE_CREATE_RULES, StateData(**data_dict))
    bot.send_message(chat_id, "📋 *Введите правила бронирования:*\n\nВведите процент предоплаты и количество дней для отмены через пробел.\nПример: *30 3* — предоплата 30%, отмена за 3 дня\n\nПредоплата: 0-50%", parse_mode='Markdown', reply_markup=keyboards.guide_create_cancel_keyboard())

def handle_guide_create_rules(bot, message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    if message.text == '❌ Отменить создание':
        StateManager.clear_state(user_id)
        bot.send_message(chat_id, "❌ Создание экскурсии отменено.", reply_markup=keyboards.guide_menu_keyboard())
        return

    parts = message.text.strip().split()

    if len(parts) != 2:
        bot.send_message(chat_id, "❌ Введите процент предоплаты и количество дней для отмены через пробел.\nПример: *30 3* — предоплата 30%, отмена за 3 дня", parse_mode='Markdown', reply_markup=keyboards.guide_create_cancel_keyboard())
        return

    try:
        prepayment = int(parts[0])
        cancellation = int(parts[1])

        if prepayment < 0 or prepayment > 50:
            bot.send_message(chat_id, "❌ Предоплата должна быть от 0 до 50%. Введите корректное значение:", reply_markup=keyboards.guide_create_cancel_keyboard())
            return

        if cancellation < 0:
            bot.send_message(chat_id, "❌ Количество дней должно быть больше 0. Введите корректное значение:", reply_markup=keyboards.guide_create_cancel_keyboard())
            return

        data = StateManager.get_data(user_id)
        data_dict = data.to_dict() if hasattr(data, 'to_dict') else {}
        data_dict['prepayment_percent'] = prepayment
        data_dict['cancellation_days'] = cancellation

        StateManager.set_state(user_id, UserStates.GUIDE_CREATE_NOTE, StateData(**data_dict))
        bot.send_message(chat_id, "📝 *Добавьте примечание для клиентов:*\n\nНапример: что взять с собой, особые условия, контакты.\nМожно пропустить, написав «пропустить».", parse_mode='Markdown', reply_markup=keyboards.guide_create_cancel_keyboard())

    except ValueError:
        bot.send_message(chat_id, "❌ Неверный формат. Введите: *%предоплаты дни* (например: 30 3)", reply_markup=keyboards.guide_create_cancel_keyboard())

def handle_guide_create_note(bot, message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    if message.text == '❌ Отменить создание':
        StateManager.clear_state(user_id)
        bot.send_message(chat_id, "❌ Создание экскурсии отменено.", reply_markup=keyboards.guide_menu_keyboard())
        return

    note = message.text.strip()
    if note.lower() == 'пропустить':
        note = ""

    data = StateManager.get_data(user_id)
    data_dict = data.to_dict() if hasattr(data, 'to_dict') else {}
    data_dict['guide_note'] = note

    StateManager.set_state(user_id, UserStates.GUIDE_CREATE_CONFIRMATION, StateData(**data_dict))
    show_guide_excursion_confirmation(bot, message)

def show_guide_excursion_confirmation(bot, message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    data = StateManager.get_data(user_id)

    duration_days = ""
    if hasattr(data, 'start_date') and hasattr(data, 'end_date') and data.start_date and data.end_date:
        try:
            start = datetime.strptime(data.start_date, "%d.%m.%Y")
            end = datetime.strptime(data.end_date, "%d.%m.%Y")
            days = (end - start).days + 1
            duration_days = f"\n*Продолжительность:* {days} дн. ({data.start_date} — {data.end_date})"
        except:
            pass

    confirmation_text = f"""
✅ *Проверьте данные экскурсии:*

*Название:* {data.excursion_name if hasattr(data, 'excursion_name') else ''}
*Описание:* {data.excursion_description[:100] + '...' if hasattr(data, 'excursion_description') and len(data.excursion_description) > 100 else data.excursion_description if hasattr(data, 'excursion_description') else ''}
*Цена:* {data.price_per_person if hasattr(data, 'price_per_person') else 0} руб./чел.
*Скидка за группу:* {data.group_discount if hasattr(data, 'group_discount') else 0}%
*Минимальная группа:* {data.min_people if hasattr(data, 'min_people') else 1} чел.
*Максимальная группа:* {data.max_people if hasattr(data, 'max_people') else 10} чел.
{duration_days}
*Место старта:* {data.start_location if hasattr(data, 'start_location') else 'не указано'}
*Время:* {data.available_times if hasattr(data, 'available_times') and data.available_times else 'любое'}
*Предоплата:* {data.prepayment_percent if hasattr(data, 'prepayment_percent') else 30}%
*Отмена за:* {data.cancellation_days if hasattr(data, 'cancellation_days') else 3} дн.
*Примечание:* {data.guide_note if hasattr(data, 'guide_note') and data.guide_note else 'нет'}
{'*Фото:* есть' if hasattr(data, 'photo_file_id') and data.photo_file_id else '*Фото:* нет'}

Всё верно? Экскурсия будет добавлена в общий список.
"""
    bot.send_message(chat_id, confirmation_text, parse_mode='Markdown', reply_markup=keyboards.confirmation_buttons())

def handle_guide_create_confirmation(bot, message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    if message.text == '✅ Подтвердить бронирование' or message.text == '✅ Подтвердить заявку':
        data = StateManager.get_data(user_id)
        required_fields = ['excursion_name', 'excursion_description', 'price_per_person', 'min_people', 'max_people', 'start_date', 'end_date', 'start_location']
        missing_fields = [field for field in required_fields if not hasattr(data, field)]
        if missing_fields:
            bot.send_message(chat_id, f"❌ Не хватает данных: {', '.join(missing_fields)}. Начните создание заново.", reply_markup=keyboards.guide_menu_keyboard())
            StateManager.clear_state(user_id)
            return
        with next(get_db()) as db:
            try:
                guide = db.query(Guide).filter_by(user_id=user_id).first()
                if not guide:
                    bot.send_message(chat_id, "❌ Вы не зарегистрированы как гид. Используйте команду /guide для регистрации.", reply_markup=keyboards.main_menu())
                    StateManager.clear_state(user_id)
                    return

                excursion = Excursion(
                    name=data.excursion_name,
                    description=data.excursion_description,
                    price_per_person=data.price_per_person,
                    min_people=data.min_people,
                    max_people=data.max_people,
                    duration_hours=(datetime.strptime(data.end_date, "%d.%m.%Y") - datetime.strptime(data.start_date, "%d.%m.%Y")).days + 1,
                    photo_file_id=data.photo_file_id if hasattr(data, 'photo_file_id') else None,
                    is_active=True,
                    is_published=True,
                    start_date=data.start_date,
                    end_date=data.end_date,
                    start_location=data.start_location,
                    prepayment_percent=getattr(data, 'prepayment_percent', 30),
                    cancellation_days=getattr(data, 'cancellation_days', 3),
                    group_discount=getattr(data, 'group_discount', 0),
                    guide_user_id=user_id,
                    access_paid=True
                )
                db.add(excursion)
                db.commit()
                bot.send_message(chat_id, f"🎉 *ЭКСКУРСИЯ СОЗДАНА!*\n\n🗺️ Название: {data.excursion_name}\n💰 Цена: {data.price_per_person} руб./чел.\n👥 Группа: {data.min_people}-{data.max_people} чел.\n📅 Даты: {data.start_date} — {data.end_date}\n\n✅ Экскурсия добавлена в общий список и доступна для бронирования клиентами.", parse_mode='Markdown', reply_markup=keyboards.guide_menu_keyboard())
                if MANAGER_CHAT_ID:
                    manager_text = f"🗺️ *НОВАЯ ЭКСКУРСИЯ ОТ ГИДА*\n*Гид:* {guide.name}\n*Экскурсия:* {data.excursion_name}\n*Цена:* {data.price_per_person} руб./чел.\n*Группа:* {data.min_people}-{data.max_people} чел.\n*Даты:* {data.start_date} — {data.end_date}"
                    bot.send_message(MANAGER_CHAT_ID, manager_text, parse_mode='Markdown')
            except Exception as e:
                print(f"Ошибка создания экскурсии: {e}")
                bot.send_message(chat_id, "❌ Произошла ошибка при создании экскурсии. Пожалуйста, попробуйте еще раз.", reply_markup=keyboards.guide_menu_keyboard())
        StateManager.clear_state(user_id)
    elif message.text == '✏️ Изменить данные':
        StateManager.set_state(user_id, UserStates.GUIDE_CREATE_START, StateData())
        bot.send_message(chat_id, "✏️ *Создание новой экскурсии*\n\nВведите название экскурсии:", parse_mode='Markdown', reply_markup=keyboards.guide_create_cancel_keyboard())
    elif message.text == '🔙 Назад':
        if StateManager.go_back(user_id):
            bot.send_message(chat_id, "📝 *Добавьте примечание для клиентов:*", parse_mode='Markdown', reply_markup=keyboards.guide_create_cancel_keyboard())
    elif message.text == '❌ Отмена':
        StateManager.clear_state(user_id)
        bot.send_message(chat_id, "❌ Создание экскурсии отменено.", reply_markup=keyboards.guide_menu_keyboard())

def handle_guide_menu(bot, message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    if message.text == '➕ Создать экскурсию':
        handle_guide_access_payment(bot, message)
    elif message.text == '📋 Мои заявки':
        from handlers.orders import handle_guide_my_bookings
        handle_guide_my_bookings(bot, message)
    elif message.text == '📊 Статистика':
        with next(get_db()) as db:
            my_offers = db.query(ExcursionOffer).filter_by(guide_id=user_id).count()
            accepted = db.query(ExcursionOffer).filter_by(guide_id=user_id, status='accepted').count()
            bot.send_message(chat_id, f"📊 *Ваша статистика:*\n\n• Отправлено предложений: {my_offers}\n• Принято клиентами: {accepted}", parse_mode='Markdown')
        bot.send_message(chat_id, "Выберите действие:", reply_markup=keyboards.guide_menu_keyboard())
    elif message.text == '🔙 Назад':
        StateManager.clear_state(user_id)
        bot.send_message(chat_id, "Возвращаемся в главное меню:", reply_markup=keyboards.main_menu())

# ========== ФУНКЦИИ ДЛЯ ГИДОВ (ПРЕДЛОЖЕНИЯ) ==========

def handle_guide_offer_start(bot, call):
    """Начало создания предложения от гида"""
    try:
        booking_id = int(call.data.split('_')[-1])
        print(f"🔍 Гид {call.from_user.id} нажал 'Предложить' для заявки {booking_id}")

        with next(get_db()) as db:
            booking = db.query(ExcursionBooking).filter_by(id=booking_id).first()
            if not booking:
                bot.answer_callback_query(call.id, "❌ Заявка не найдена", show_alert=True)
                return

            excursion_name = get_excursion_name(db, booking.excursion_id)

            StateManager.set_state(
                call.from_user.id,
                UserStates.GUIDE_MODIFY_OFFER,
                StateData(
                    booking_id=booking_id,
                    original_price=booking.total_price,
                    original_date=booking.booking_date,
                    modified_price=booking.total_price,
                    modified_date=booking.booking_date,
                    modified_time="",
                    modified_description=""
                )
            )
            print(f"📌 Состояние установлено: {StateManager.get_state(call.from_user.id)}")

            booking_text = f"""
⚠️ *Важно: вы ОБЯЗАНЫ внести изменения в заявку!*
Необходимо указать:
1) Цену за человека
2) Место сбора
3) Время начала
4) Минимальное количество человек (при котором экскурсия состоится)
5) Максимальное количество человек (после которого набор закрыт)

*Пример:* мин 3, макс 8 — если записалось только 2 человека, экскурсия НЕ СОСТОИТСЯ,
контакты клиентов НЕ публикуются гиду, заявка отменяется за 24/2 часа до начала.

*После того как клиент внесёт предоплату, вы НЕ СМОЖЕТЕ изменить цену!*

*Номер заявки:* {booking.booking_id}
*Экскурсия:* {excursion_name}
*Желаемая дата:* {booking.booking_date}
*Количество человек:* {booking.people_count}
{f"👶 Дети: {booking.children_info}" if booking.has_children and booking.children_info else ""}
{f"📝 Примечание клиента: {booking.client_note}" if booking.client_note else ""}
"""
            bot.send_message(call.from_user.id, booking_text, parse_mode='Markdown')
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton('💰 Цена за человека', callback_data=f'guide_modify_price_{booking_id}'),
                types.InlineKeyboardButton('📍 Место сбора', callback_data=f'guide_modify_location_{booking_id}'),
                types.InlineKeyboardButton('🕒 Время начала', callback_data=f'guide_modify_time_{booking_id}'),
                types.InlineKeyboardButton('👥 Мин. кол-во человек', callback_data=f'guide_modify_min_people_{booking_id}'),
                types.InlineKeyboardButton('👥 Макс. кол-во человек', callback_data=f'guide_modify_max_people_{booking_id}'),
                types.InlineKeyboardButton('📝 Добавить описание', callback_data=f'guide_modify_desc_{booking_id}'),
                types.InlineKeyboardButton('✅ Отправить предложение', callback_data=f'guide_modify_done_{booking_id}'),
                types.InlineKeyboardButton('❌ Отменить', callback_data=f'guide_modify_cancel_{booking_id}')
            )
            bot.send_message(call.from_user.id, "Заполните обязательные поля:", parse_mode='Markdown', reply_markup=markup)

            bot.answer_callback_query(call.id, "✏️ Вы можете изменить условия")

    except Exception as e:
        print(f"Ошибка в handle_guide_offer_start: {e}")
        bot.answer_callback_query(call.id, "❌ Ошибка", show_alert=True)

def handle_guide_modify_price(bot, call):
    """Изменение цены гидом"""
    print(f"🔍 handle_guide_modify_price: user={call.from_user.id}, data={call.data}")
    
    booking_id = int(call.data.split('_')[-1])

    with next(get_db()) as db:
        booking = db.query(ExcursionBooking).filter_by(id=booking_id).first()
        if not booking:
            bot.answer_callback_query(call.id, "❌ Заявка не найдена", show_alert=True)
            return

        if booking.status == 'accepted' or booking.prepayment_paid:
            bot.answer_callback_query(call.id, "❌ Нельзя изменить цену после подтверждения бронирования или внесения предоплаты.", show_alert=True)
            return

        bot.send_message(
            call.from_user.id,
            f"💰 *Введите новую цену за человека (в рублях):*\n\n"
            f"Текущая цена: {booking.total_price} руб.\n"
            f"Минимальная цена: {booking.total_price} руб. (нельзя снижать)\n\n"
            f"Введите сумму:",
            parse_mode='Markdown'
        )

        StateManager.update_data(call.from_user.id, waiting_for="price", booking_id=booking_id)
        bot.answer_callback_query(call.id, "💰 Введите новую цену")

def handle_guide_modify_date(bot, call):
    """Изменение даты гидом"""
    booking_id = int(call.data.split('_')[-1])

    with next(get_db()) as db:
        booking = db.query(ExcursionBooking).filter_by(id=booking_id).first()
        if not booking:
            bot.answer_callback_query(call.id, "❌ Заявка не найдена", show_alert=True)
            return

        if booking.status == 'accepted' or booking.prepayment_paid:
            bot.answer_callback_query(call.id, "❌ Нельзя изменить дату после подтверждения бронирования или внесения предоплаты.", show_alert=True)
            return

        bot.send_message(
            call.from_user.id,
            f"📅 *Введите новую дату в формате ДД.ММ.ГГГГ:*\n\n"
            f"Текущая дата: {booking.booking_date}\n"
            f"Пример: 25.12.2025\n\n"
            f"Введите новую дату:",
            parse_mode='Markdown'
        )

        StateManager.update_data(call.from_user.id, waiting_for="date", booking_id=booking_id)
        bot.answer_callback_query(call.id, "📅 Введите новую дату")

def handle_guide_modify_time(bot, call):
    """Изменение времени гидом"""
    booking_id = int(call.data.split('_')[-1])

    with next(get_db()) as db:
        booking = db.query(ExcursionBooking).filter_by(id=booking_id).first()
        if not booking:
            bot.answer_callback_query(call.id, "❌ Заявка не найдена", show_alert=True)
            return

        if booking.status == 'accepted' or booking.prepayment_paid:
            bot.answer_callback_query(call.id, "❌ Нельзя изменить время после подтверждения бронирования или внесения предоплаты.", show_alert=True)
            return

        bot.send_message(
            call.from_user.id,
            f"🕒 *Введите новое время в формате ЧЧ:ММ:*\n\n"
            f"Пример: 14:30\n\n"
            f"Введите новое время:",
            parse_mode='Markdown'
        )

        StateManager.update_data(call.from_user.id, waiting_for="time", booking_id=booking_id)
        bot.answer_callback_query(call.id, "🕒 Введите новое время")

def handle_guide_modify_location(bot, call):
    """Изменение места сбора гидом"""
    booking_id = int(call.data.split('_')[-1])

    bot.send_message(
        call.from_user.id,
        f"📍 *Введите новое место сбора:*\n\n"
        f"Например: Кировск, ул. Ленина 1\n\n"
        f"Введите место сбора:",
        parse_mode='Markdown'
    )

    StateManager.update_data(call.from_user.id, waiting_for="location", booking_id=booking_id)
    bot.answer_callback_query(call.id, "📍 Введите место сбора")

def handle_guide_modify_seats(bot, call):
    """Изменение количества мест гидом"""
    booking_id = int(call.data.split('_')[-1])

    bot.send_message(
        call.from_user.id,
        f"👥 *Введите новое максимальное количество мест:*\n\n"
        f"Введите число от 1 до 20:",
        parse_mode='Markdown'
    )

    StateManager.update_data(call.from_user.id, waiting_for="seats", booking_id=booking_id)
    bot.answer_callback_query(call.id, "👥 Введите количество мест")

def handle_guide_modify_min_people(bot, call):
    """Гид указывает минимальное количество человек"""
    booking_id = int(call.data.split('_')[-1])
    
    bot.send_message(
        call.from_user.id,
        f"👥 *Введите минимальное количество человек для проведения экскурсии:*\n\n"
        f"Пример: 3 — если запишется меньше 3 человек, экскурсия НЕ СОСТОИТСЯ.\n\n"
        f"Введите число:",
        parse_mode='Markdown'
    )
    
    StateManager.update_data(call.from_user.id, waiting_for="min_people", booking_id=booking_id)
    bot.answer_callback_query(call.id)

def handle_guide_modify_max_people(bot, call):
    """Гид указывает максимальное количество человек"""
    booking_id = int(call.data.split('_')[-1])
    
    bot.send_message(
        call.from_user.id,
        f"👥 *Введите максимальное количество человек в группе:*\n\n"
        f"Пример: 8 — после записи 8 человек набор на эту экскурсию будет закрыт.\n\n"
        f"Введите число:",
        parse_mode='Markdown'
    )
    
    StateManager.update_data(call.from_user.id, waiting_for="max_people", booking_id=booking_id)
    bot.answer_callback_query(call.id)

def handle_guide_modify_desc(bot, call):
    """Добавление описания гидом"""
    booking_id = int(call.data.split('_')[-1])

    bot.send_message(
        call.from_user.id,
        f"📝 *Введите описание вашего предложения:*\n\n"
        f"Расскажите, что вас ждет, особенности маршрута, что включено.\n\n"
        f"Введите описание:",
        parse_mode='Markdown'
    )

    StateManager.update_data(call.from_user.id, waiting_for="description", booking_id=booking_id)
    bot.answer_callback_query(call.id, "📝 Введите описание")

def handle_guide_modify_done(bot, call):
    """Отправка предложения клиенту"""
    booking_id = int(call.data.split('_')[-1])

    with next(get_db()) as db:
        booking = db.query(ExcursionBooking).filter_by(id=booking_id).first()
        if not booking:
            bot.answer_callback_query(call.id, "❌ Заявка не найдена", show_alert=True)
            return

        existing_offer = db.query(ExcursionOffer).filter_by(
            booking_id=booking.id,
            guide_id=call.from_user.id
        ).first()

        if existing_offer:
            bot.answer_callback_query(call.id, "❌ Вы уже отправили предложение по этой заявке", show_alert=True)
            return

        data = StateManager.get_data(call.from_user.id)

        # Проверка обязательных полей
        required_checks = []
        if not hasattr(data, 'modified_price') or not data.modified_price:
            required_checks.append("цена не указана")
        if not hasattr(data, 'modified_location') or not data.modified_location:
            required_checks.append("место сбора не указано")
        if not hasattr(data, 'modified_time') or not data.modified_time:
            required_checks.append("время не указано")
        if not hasattr(data, 'modified_min_people') or not data.modified_min_people:
            required_checks.append("минимальное количество человек не указано")
        if not hasattr(data, 'modified_max_people') or not data.modified_max_people:
            required_checks.append("максимальное количество человек не указано")

        if required_checks:
            bot.answer_callback_query(
                call.id,
                f"❌ Вы должны заполнить обязательные поля: {', '.join(required_checks)}",
                show_alert=True
            )
            return

        offer_price = data.modified_price
        offer_date = booking.booking_date
        offer_time = data.modified_time
        offer_location = data.modified_location
        offer_description = ""
        conditions = []

        conditions.append(f"цена {offer_price} руб.")
        conditions.append(f"место сбора {offer_location}")
        conditions.append(f"время {offer_time}")

        if hasattr(data, 'modified_date') and data.modified_date:
            offer_date = data.modified_date
            conditions.append(f"дата {data.modified_date}")

        if hasattr(data, 'modified_description') and data.modified_description:
            offer_description = data.modified_description
            conditions.append("добавлено описание")

        guide_user = db.query(User).filter_by(user_id=call.from_user.id).first()
        guide_username = guide_user.username if guide_user and guide_user.username else ""

        offer = ExcursionOffer(
            booking_id=booking.id,
            guide_id=call.from_user.id,
            guide_name=call.from_user.first_name or "Гид",
            guide_username=guide_username,
            price=offer_price,
            offer_date=offer_date,
            offer_time=offer_time,
            description=offer_description,
            status='pending'
        )
        db.add(offer)
        db.commit()

        # Сохраняем данные в бронирование
        booking.guide_start_location = offer_location
        booking.excursion_start_time = offer_time
        booking.guide_note = offer_description
        booking.guide_price_per_person = offer_price
        booking.group_min_people = data.modified_min_people
        booking.group_max_people = data.modified_max_people
        booking.guide_conditions_set = True
        booking.client_contacts_hidden = False
        if offer_date != booking.booking_date:
            booking.booking_date = offer_date
        db.commit()

        send_excursion_offer_to_client(bot, offer, booking)

        if booking.status == 'searching':
            booking.status = 'offers_received'
            db.commit()

        guide_name = call.from_user.first_name or "Гид"
        conditions_text = ", ".join(conditions)

        if not booking.is_rebook and GUIDES_CHAT_ID:
            try:
                notification_text = f"""
🗺️ *ПРЕДЛОЖЕНИЕ ОТПРАВЛЕНО*

*Номер заявки:* {booking.id}
*Гид:* {guide_name} (@{guide_username if guide_username else 'без username'})
*Условия:* {conditions_text}

✅ Предложение отправлено клиенту.

⏳ Ожидаем решения клиента (до {(datetime.now() + timedelta(hours=48)).strftime('%d.%m.%Y %H:%M')})
"""
                bot.send_message(GUIDES_CHAT_ID, notification_text, parse_mode='Markdown')
            except Exception as e:
                print(f"❌ Ошибка отправки в чат гидов: {e}")

        bot.answer_callback_query(call.id, "✅ Предложение отправлено клиенту!")

        bot.send_message(
            call.from_user.id,
            "✅ *Предложение отправлено клиенту!*\n\n"
            f"Клиент получит ваше предложение и сможет принять или отклонить его.\n\n"
            f"⚠️ *Важно:* после того как клиент внесёт предоплату, вы НЕ СМОЖЕТЕ изменить цену!",
            parse_mode='Markdown'
        )

        StateManager.clear_state(call.from_user.id)

def handle_guide_modify_cancel(bot, call):
    """Отмена изменения условий"""
    booking_id = int(call.data.split('_')[-1])

    StateManager.clear_state(call.from_user.id)

    bot.send_message(
        call.from_user.id,
        "❌ Изменение условий отменено.\n\n"
        "Вы можете вернуться в чат гидов.",
        parse_mode='Markdown'
    )

    bot.answer_callback_query(call.id, "❌ Изменение отменено")

def handle_guide_modify_input(bot, message):
    """Обработка ввода от гида при изменении условий"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    data = StateManager.get_data(user_id)
    
    print(f"🔍 handle_guide_modify_input: user={user_id}, state={StateManager.get_state(user_id)}, waiting_for={getattr(data, 'waiting_for', 'None')}, text={message.text}")

    if not hasattr(data, 'waiting_for'):
        print(f"DEBUG GUIDE MODIFY: no waiting_for attribute!")
        return

    if data.waiting_for == 'price':
        try:
            new_price = float(message.text)
            original_price = data.original_price

            if new_price < original_price:
                bot.send_message(
                    chat_id,
                    f"❌ *Цена не может быть ниже исходной!*\n\n"
                    f"Исходная цена: {original_price} руб.\n"
                    f"Минимальная цена: {original_price} руб.\n\n"
                    f"Пожалуйста, введите цену не ниже {original_price} руб.:",
                    parse_mode='Markdown'
                )
                return

            StateManager.update_data(user_id, modified_price=new_price, waiting_for=None)

            booking_id = data.booking_id
            with next(get_db()) as db:
                booking = db.query(ExcursionBooking).filter_by(id=booking_id).first()
                if booking:
                    excursion = db.query(Excursion).filter_by(id=booking.excursion_id).first()
                    excursion_name = excursion.name if excursion else "Не указана"
                    current_price = new_price
                    current_date = data.modified_date if hasattr(data, 'modified_date') and data.modified_date else booking.booking_date
                    current_time = data.modified_time if hasattr(data, 'modified_time') and data.modified_time else ""
                    current_location = data.modified_location if hasattr(data, 'modified_location') and data.modified_location else "не указано"

                    booking_text = f"""
🗺️ *ОБНОВЛЕННАЯ ЗАЯВКА*

*Номер заявки:* {booking.id}
*Экскурсия:* {excursion_name}
*Желаемая дата:* {current_date}
{f"*Время:* {current_time}" if current_time else ""}
*Место сбора:* {current_location}
*Количество человек:* {booking.people_count}
*Стоимость за человека:* {int(current_price)} руб. (изменено)
*Статус:* 🔍 Ищет гида
"""
                    bot.send_message(chat_id, booking_text, parse_mode='Markdown')

            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton('💰 Изменить цену', callback_data=f'guide_modify_price_{booking_id}'),
                types.InlineKeyboardButton('📅 Изменить дату', callback_data=f'guide_modify_date_{booking_id}'),
                types.InlineKeyboardButton('🕒 Изменить время', callback_data=f'guide_modify_time_{booking_id}'),
                types.InlineKeyboardButton('📍 Изменить место сбора', callback_data=f'guide_modify_location_{booking_id}'),
                types.InlineKeyboardButton('👥 Мин. кол-во человек', callback_data=f'guide_modify_min_people_{booking_id}'),
                types.InlineKeyboardButton('👥 Макс. кол-во человек', callback_data=f'guide_modify_max_people_{booking_id}'),
                types.InlineKeyboardButton('📝 Добавить описание', callback_data=f'guide_modify_desc_{booking_id}'),
                types.InlineKeyboardButton('✅ Отправить предложение', callback_data=f'guide_modify_done_{booking_id}'),
                types.InlineKeyboardButton('❌ Отменить', callback_data=f'guide_modify_cancel_{booking_id}')
            )
            bot.send_message(chat_id, "✏️ *Что хотите изменить?*", parse_mode='Markdown', reply_markup=markup)
            
            # Автоматический переход к вводу времени
            StateManager.update_data(user_id, waiting_for="time", booking_id=booking_id)

        except ValueError:
            bot.send_message(chat_id, "❌ Неверный формат цены. Введите число (например: 2500):")

    elif data.waiting_for == 'date':
        date_str = message.text.strip()
        try:
            datetime.strptime(date_str, "%d.%m.%Y")
            StateManager.update_data(user_id, modified_date=date_str, waiting_for=None)

            booking_id = data.booking_id
            with next(get_db()) as db:
                booking = db.query(ExcursionBooking).filter_by(id=booking_id).first()
                if booking:
                    excursion = db.query(Excursion).filter_by(id=booking.excursion_id).first()
                    excursion_name = excursion.name if excursion else "Не указана"
                    current_price = data.modified_price if hasattr(data, 'modified_price') and data.modified_price else booking.total_price
                    current_time = data.modified_time if hasattr(data, 'modified_time') and data.modified_time else ""
                    current_location = data.modified_location if hasattr(data, 'modified_location') and data.modified_location else "не указано"

                    booking_text = f"""
🗺️ *ОБНОВЛЕННАЯ ЗАЯВКА*

*Номер заявки:* {booking.id}
*Экскурсия:* {excursion_name}
*Дата:* {date_str} (изменено)
{f"*Время:* {current_time}" if current_time else ""}
*Место сбора:* {current_location}
*Количество человек:* {booking.people_count}
*Стоимость за человека:* {int(current_price)} руб.
*Статус:* 🔍 Ищет гида
"""
                    bot.send_message(chat_id, booking_text, parse_mode='Markdown')

            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton('💰 Изменить цену', callback_data=f'guide_modify_price_{booking_id}'),
                types.InlineKeyboardButton('📅 Изменить дату', callback_data=f'guide_modify_date_{booking_id}'),
                types.InlineKeyboardButton('🕒 Изменить время', callback_data=f'guide_modify_time_{booking_id}'),
                types.InlineKeyboardButton('📍 Изменить место сбора', callback_data=f'guide_modify_location_{booking_id}'),
                types.InlineKeyboardButton('👥 Мин. кол-во человек', callback_data=f'guide_modify_min_people_{booking_id}'),
                types.InlineKeyboardButton('👥 Макс. кол-во человек', callback_data=f'guide_modify_max_people_{booking_id}'),
                types.InlineKeyboardButton('📝 Добавить описание', callback_data=f'guide_modify_desc_{booking_id}'),
                types.InlineKeyboardButton('✅ Отправить предложение', callback_data=f'guide_modify_done_{booking_id}'),
                types.InlineKeyboardButton('❌ Отменить', callback_data=f'guide_modify_cancel_{booking_id}')
            )
            bot.send_message(chat_id, "✏️ *Что хотите изменить?*", parse_mode='Markdown', reply_markup=markup)

        except ValueError:
            bot.send_message(chat_id, "❌ Неверный формат даты. Введите дату в формате ДД.ММ.ГГГГ (например: 25.12.2025):")

    elif data.waiting_for == 'time':
        time_str = message.text.strip()
        time_pattern = r'^([0-1]?[0-9]|2[0-3]):([0-5][0-9])$'

        if re.match(time_pattern, time_str):
            StateManager.update_data(user_id, modified_time=time_str, waiting_for=None)

            booking_id = data.booking_id
            with next(get_db()) as db:
                booking = db.query(ExcursionBooking).filter_by(id=booking_id).first()
                if booking:
                    excursion = db.query(Excursion).filter_by(id=booking.excursion_id).first()
                    excursion_name = excursion.name if excursion else "Не указана"
                    current_price = data.modified_price if hasattr(data, 'modified_price') and data.modified_price else booking.total_price
                    current_date = data.modified_date if hasattr(data, 'modified_date') and data.modified_date else booking.booking_date
                    current_location = data.modified_location if hasattr(data, 'modified_location') and data.modified_location else "не указано"

                    booking_text = f"""
🗺️ *ОБНОВЛЕННАЯ ЗАЯВКА*

*Номер заявки:* {booking.id}
*Экскурсия:* {excursion_name}
*Дата:* {current_date}
*Время:* {time_str} (изменено)
*Место сбора:* {current_location}
*Количество человек:* {booking.people_count}
*Стоимость за человека:* {int(current_price)} руб.
*Статус:* 🔍 Ищет гида
"""
                    bot.send_message(chat_id, booking_text, parse_mode='Markdown')

            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton('💰 Изменить цену', callback_data=f'guide_modify_price_{booking_id}'),
                types.InlineKeyboardButton('📅 Изменить дату', callback_data=f'guide_modify_date_{booking_id}'),
                types.InlineKeyboardButton('🕒 Изменить время', callback_data=f'guide_modify_time_{booking_id}'),
                types.InlineKeyboardButton('📍 Изменить место сбора', callback_data=f'guide_modify_location_{booking_id}'),
                types.InlineKeyboardButton('👥 Мин. кол-во человек', callback_data=f'guide_modify_min_people_{booking_id}'),
                types.InlineKeyboardButton('👥 Макс. кол-во человек', callback_data=f'guide_modify_max_people_{booking_id}'),
                types.InlineKeyboardButton('📝 Добавить описание', callback_data=f'guide_modify_desc_{booking_id}'),
                types.InlineKeyboardButton('✅ Отправить предложение', callback_data=f'guide_modify_done_{booking_id}'),
                types.InlineKeyboardButton('❌ Отменить', callback_data=f'guide_modify_cancel_{booking_id}')
            )
            bot.send_message(chat_id, "✏️ *Что хотите изменить?*", parse_mode='Markdown', reply_markup=markup)
            
            # Автоматический переход к вводу места сбора
            StateManager.update_data(user_id, waiting_for="location", booking_id=booking_id)

        else:
            bot.send_message(chat_id, "❌ Неверный формат времени. Введите время в формате ЧЧ:ММ (например: 14:30):")

    elif data.waiting_for == 'location':
        location = message.text.strip()
        if len(location) < 2:
            bot.send_message(chat_id, "❌ Место сбора слишком короткое. Введите корректное место:", reply_markup=keyboards.back_button())
            return

        StateManager.update_data(user_id, modified_location=location, waiting_for=None)

        booking_id = data.booking_id
        with next(get_db()) as db:
            booking = db.query(ExcursionBooking).filter_by(id=booking_id).first()
            if booking:
                excursion = db.query(Excursion).filter_by(id=booking.excursion_id).first()
                excursion_name = excursion.name if excursion else "Не указана"
                current_price = data.modified_price if hasattr(data, 'modified_price') and data.modified_price else booking.total_price
                current_date = data.modified_date if hasattr(data, 'modified_date') and data.modified_date else booking.booking_date
                current_time = data.modified_time if hasattr(data, 'modified_time') and data.modified_time else ""

                booking_text = f"""
🗺️ *ОБНОВЛЕННАЯ ЗАЯВКА*

*Номер заявки:* {booking.id}
*Экскурсия:* {excursion_name}
*Дата:* {current_date}
{f"*Время:* {current_time}" if current_time else ""}
*Место сбора:* {location} (изменено)
*Количество человек:* {booking.people_count}
*Стоимость за человека:* {int(current_price)} руб.
*Статус:* 🔍 Ищет гида
"""
                bot.send_message(chat_id, booking_text, parse_mode='Markdown')

        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton('💰 Изменить цену', callback_data=f'guide_modify_price_{booking_id}'),
            types.InlineKeyboardButton('📅 Изменить дату', callback_data=f'guide_modify_date_{booking_id}'),
            types.InlineKeyboardButton('🕒 Изменить время', callback_data=f'guide_modify_time_{booking_id}'),
            types.InlineKeyboardButton('📍 Изменить место сбора', callback_data=f'guide_modify_location_{booking_id}'),
            types.InlineKeyboardButton('👥 Мин. кол-во человек', callback_data=f'guide_modify_min_people_{booking_id}'),
            types.InlineKeyboardButton('👥 Макс. кол-во человек', callback_data=f'guide_modify_max_people_{booking_id}'),
            types.InlineKeyboardButton('📝 Добавить описание', callback_data=f'guide_modify_desc_{booking_id}'),
            types.InlineKeyboardButton('✅ Отправить предложение', callback_data=f'guide_modify_done_{booking_id}'),
            types.InlineKeyboardButton('❌ Отменить', callback_data=f'guide_modify_cancel_{booking_id}')
        )
        bot.send_message(chat_id, "✏️ *Что хотите изменить?*", parse_mode='Markdown', reply_markup=markup)
        
        # Автоматический переход к вводу минимального количества
        StateManager.update_data(user_id, waiting_for="min_people", booking_id=booking_id)

    elif data.waiting_for == 'min_people':
        try:
            min_people = int(message.text)
            if min_people < 1:
                bot.send_message(chat_id, "❌ Минимальное количество должно быть не менее 1:", reply_markup=keyboards.back_button())
                return
            
            StateManager.update_data(user_id, modified_min_people=min_people, waiting_for=None)
            
            booking_id = data.booking_id
            with next(get_db()) as db:
                booking = db.query(ExcursionBooking).filter_by(id=booking_id).first()
                if booking:
                    booking.group_min_people = min_people
                    db.commit()
            
            bot.send_message(chat_id, f"✅ Минимальное количество: {min_people} чел.", parse_mode='Markdown')
            # Показать обновлённую клавиатуру
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton('💰 Цена за человека', callback_data=f'guide_modify_price_{booking_id}'),
                types.InlineKeyboardButton('📍 Место сбора', callback_data=f'guide_modify_location_{booking_id}'),
                types.InlineKeyboardButton('🕒 Время начала', callback_data=f'guide_modify_time_{booking_id}'),
                types.InlineKeyboardButton('👥 Мин. кол-во человек', callback_data=f'guide_modify_min_people_{booking_id}'),
                types.InlineKeyboardButton('👥 Макс. кол-во человек', callback_data=f'guide_modify_max_people_{booking_id}'),
                types.InlineKeyboardButton('📝 Добавить описание', callback_data=f'guide_modify_desc_{booking_id}'),
                types.InlineKeyboardButton('✅ Отправить предложение', callback_data=f'guide_modify_done_{booking_id}'),
                types.InlineKeyboardButton('❌ Отменить', callback_data=f'guide_modify_cancel_{booking_id}')
            )
            bot.send_message(chat_id, "✏️ *Что хотите изменить?*", parse_mode='Markdown', reply_markup=markup)
            
            # Автоматический переход к вводу максимального количества
            StateManager.update_data(user_id, waiting_for="max_people", booking_id=booking_id)
            
        except ValueError:
            bot.send_message(chat_id, "❌ Неверный формат. Введите целое число:")
    
    elif data.waiting_for == 'max_people':
        try:
            max_people = int(message.text)
            if max_people < 1:
                bot.send_message(chat_id, "❌ Максимальное количество должно быть не менее 1:", reply_markup=keyboards.back_button())
                return
            
            StateManager.update_data(user_id, modified_max_people=max_people, waiting_for=None)
            
            booking_id = data.booking_id
            with next(get_db()) as db:
                booking = db.query(ExcursionBooking).filter_by(id=booking_id).first()
                if booking:
                    booking.group_max_people = max_people
                    db.commit()
            
            bot.send_message(chat_id, f"✅ Максимальное количество: {max_people} чел.", parse_mode='Markdown')
            # Показать обновлённую клавиатуру
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton('💰 Цена за человека', callback_data=f'guide_modify_price_{booking_id}'),
                types.InlineKeyboardButton('📍 Место сбора', callback_data=f'guide_modify_location_{booking_id}'),
                types.InlineKeyboardButton('🕒 Время начала', callback_data=f'guide_modify_time_{booking_id}'),
                types.InlineKeyboardButton('👥 Мин. кол-во человек', callback_data=f'guide_modify_min_people_{booking_id}'),
                types.InlineKeyboardButton('👥 Макс. кол-во человек', callback_data=f'guide_modify_max_people_{booking_id}'),
                types.InlineKeyboardButton('📝 Добавить описание', callback_data=f'guide_modify_desc_{booking_id}'),
                types.InlineKeyboardButton('✅ Отправить предложение', callback_data=f'guide_modify_done_{booking_id}'),
                types.InlineKeyboardButton('❌ Отменить', callback_data=f'guide_modify_cancel_{booking_id}')
            )
            bot.send_message(chat_id, "✏️ *Что хотите изменить?*", parse_mode='Markdown', reply_markup=markup)
            
        except ValueError:
            bot.send_message(chat_id, "❌ Неверный формат. Введите целое число:")

    elif data.waiting_for == 'seats':
        try:
            seats = int(message.text)
            if seats < 1 or seats > 20:
                bot.send_message(chat_id, "❌ Количество мест должно быть от 1 до 20. Введите корректное число:", reply_markup=keyboards.back_button())
                return

            StateManager.update_data(user_id, modified_seats=seats, waiting_for=None)

            booking_id = data.booking_id
            with next(get_db()) as db:
                booking = db.query(ExcursionBooking).filter_by(id=booking_id).first()
                if booking:
                    excursion = db.query(Excursion).filter_by(id=booking.excursion_id).first()
                    excursion_name = excursion.name if excursion else "Не указана"
                    current_price = data.modified_price if hasattr(data, 'modified_price') and data.modified_price else booking.total_price
                    current_date = data.modified_date if hasattr(data, 'modified_date') and data.modified_date else booking.booking_date
                    current_time = data.modified_time if hasattr(data, 'modified_time') and data.modified_time else ""
                    current_location = data.modified_location if hasattr(data, 'modified_location') and data.modified_location else "не указано"

                    booking_text = f"""
🗺️ *ОБНОВЛЕННАЯ ЗАЯВКА*

*Номер заявки:* {booking.id}
*Экскурсия:* {excursion_name}
*Дата:* {current_date}
{f"*Время:* {current_time}" if current_time else ""}
*Место сбора:* {current_location}
*Количество мест:* {seats} (изменено)
*Количество человек:* {booking.people_count}
*Стоимость за человека:* {int(current_price)} руб.
*Статус:* 🔍 Ищет гида
"""
                    bot.send_message(chat_id, booking_text, parse_mode='Markdown')

            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton('💰 Изменить цену', callback_data=f'guide_modify_price_{booking_id}'),
                types.InlineKeyboardButton('📅 Изменить дату', callback_data=f'guide_modify_date_{booking_id}'),
                types.InlineKeyboardButton('🕒 Изменить время', callback_data=f'guide_modify_time_{booking_id}'),
                types.InlineKeyboardButton('📍 Изменить место сбора', callback_data=f'guide_modify_location_{booking_id}'),
                types.InlineKeyboardButton('👥 Мин. кол-во человек', callback_data=f'guide_modify_min_people_{booking_id}'),
                types.InlineKeyboardButton('👥 Макс. кол-во человек', callback_data=f'guide_modify_max_people_{booking_id}'),
                types.InlineKeyboardButton('📝 Добавить описание', callback_data=f'guide_modify_desc_{booking_id}'),
                types.InlineKeyboardButton('✅ Отправить предложение', callback_data=f'guide_modify_done_{booking_id}'),
                types.InlineKeyboardButton('❌ Отменить', callback_data=f'guide_modify_cancel_{booking_id}')
            )
            bot.send_message(chat_id, "✏️ *Что хотите изменить?*", parse_mode='Markdown', reply_markup=markup)

        except ValueError:
            bot.send_message(chat_id, "❌ Неверный формат. Введите целое число от 1 до 20:")

    elif data.waiting_for == 'description':
        description = message.text.strip()
        if len(description) < 20:
            bot.send_message(chat_id, "❌ Описание слишком короткое. Введите минимум 20 символов:")
            return

        StateManager.update_data(user_id, modified_description=description, waiting_for=None)

        booking_id = data.booking_id
        with next(get_db()) as db:
            booking = db.query(ExcursionBooking).filter_by(id=booking_id).first()
            if booking:
                excursion = db.query(Excursion).filter_by(id=booking.excursion_id).first()
                excursion_name = excursion.name if excursion else "Не указана"
                current_price = data.modified_price if hasattr(data, 'modified_price') and data.modified_price else booking.total_price
                current_date = data.modified_date if hasattr(data, 'modified_date') and data.modified_date else booking.booking_date
                current_time = data.modified_time if hasattr(data, 'modified_time') and data.modified_time else ""
                current_location = data.modified_location if hasattr(data, 'modified_location') and data.modified_location else "не указано"

                booking_text = f"""
🗺️ *ОБНОВЛЕННАЯ ЗАЯВКА*

*Номер заявки:* {booking.id}
*Экскурсия:* {excursion_name}
*Дата:* {current_date}
{f"*Время:* {current_time}" if current_time else ""}
*Место сбора:* {current_location}
*Количество человек:* {booking.people_count}
*Стоимость за человека:* {int(current_price)} руб.
*Описание добавлено*
*Статус:* 🔍 Ищет гида
"""
                bot.send_message(chat_id, booking_text, parse_mode='Markdown')

        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton('💰 Изменить цену', callback_data=f'guide_modify_price_{booking_id}'),
            types.InlineKeyboardButton('📅 Изменить дату', callback_data=f'guide_modify_date_{booking_id}'),
            types.InlineKeyboardButton('🕒 Изменить время', callback_data=f'guide_modify_time_{booking_id}'),
            types.InlineKeyboardButton('📍 Изменить место сбора', callback_data=f'guide_modify_location_{booking_id}'),
            types.InlineKeyboardButton('👥 Мин. кол-во человек', callback_data=f'guide_modify_min_people_{booking_id}'),
            types.InlineKeyboardButton('👥 Макс. кол-во человек', callback_data=f'guide_modify_max_people_{booking_id}'),
            types.InlineKeyboardButton('📝 Добавить описание', callback_data=f'guide_modify_desc_{booking_id}'),
            types.InlineKeyboardButton('✅ Отправить предложение', callback_data=f'guide_modify_done_{booking_id}'),
            types.InlineKeyboardButton('❌ Отменить', callback_data=f'guide_modify_cancel_{booking_id}')
        )
        bot.send_message(chat_id, "✏️ *Что хотите изменить?*", parse_mode='Markdown', reply_markup=markup)

def handle_guide_confirm_join(bot, call):
    """Гид подтверждает присоединение нового участника к группе"""
    booking_id = int(call.data.split('_')[-1])
    
    with next(get_db()) as db:
        booking = db.query(ExcursionBooking).filter_by(id=booking_id).first()
        if not booking:
            bot.answer_callback_query(call.id, "❌ Заявка не найдена", show_alert=True)
            return
        
        parent = db.query(ExcursionBooking).filter_by(id=booking.parent_booking_id).first()
        if not parent:
            bot.answer_callback_query(call.id, "❌ Родительская группа не найдена", show_alert=True)
            return
        
        child_bookings = db.query(ExcursionBooking).filter(
            ExcursionBooking.parent_booking_id == parent.id,
            ExcursionBooking.status != 'cancelled'
        ).all()
        total_people = parent.people_count + sum(c.people_count or 0 for c in child_bookings) + booking.people_count
        
        if parent.group_max_people and total_people > parent.group_max_people:
            bot.answer_callback_query(call.id, "❌ В группе нет свободных мест", show_alert=True)
            booking.status = 'cancelled'
            db.commit()
            return
        
        booking.status = 'accepted'
        booking.guide_id = parent.guide_id
        booking.guide_name = parent.guide_name
        booking.guide_start_location = parent.guide_start_location
        booking.excursion_start_time = parent.excursion_start_time
        booking.guide_price_per_person = parent.guide_price_per_person
        booking.group_min_people = parent.group_min_people
        booking.group_max_people = parent.group_max_people
        booking.guide_conditions_set = True
        booking.accepted_at = datetime.now()
        db.commit()
        
        send_group_update_notifications(bot, parent, booking)
        bot.answer_callback_query(call.id, "✅ Участник добавлен в группу!")

def handle_guide_reject_join(bot, call):
    """Гид отклоняет присоединение нового участника"""
    booking_id = int(call.data.split('_')[-1])
    
    with next(get_db()) as db:
        booking = db.query(ExcursionBooking).filter_by(id=booking_id).first()
        if not booking:
            bot.answer_callback_query(call.id, "❌ Заявка не найдена", show_alert=True)
            return
        
        booking.status = 'cancelled'
        db.commit()
        
        user = db.query(User).filter_by(id=booking.user_id).first()
        if user:
            bot.send_message(
                user.user_id,
                f"❌ *Гид отклонил вашу заявку*\n\n"
                f"К сожалению, гид не подтвердил ваше присоединение к группе.\n"
                f"Попробуйте другую дату или другую экскурсию.",
                parse_mode='Markdown'
            )
        
        bot.answer_callback_query(call.id, "❌ Заявка отклонена")

def send_group_update_notifications(bot, parent, new_member=None):
    """Отправляет уведомления об изменении в группе"""
    with next(get_db()) as db:
        members = db.query(ExcursionBooking).filter(
            ExcursionBooking.parent_booking_id == parent.id,
            ExcursionBooking.status != 'cancelled'
        ).all()
        all_members = [parent] + members
        
        total_people = sum(m.people_count or 0 for m in all_members)
        
        price = parent.guide_price_per_person or 0
        
        if parent.guide_id:
            try:
                if parent.client_contacts_hidden:
                    members_text = ""
                    for i, m in enumerate(all_members, 1):
                        is_new = " (новый!)" if new_member and m.id == new_member.id else ""
                        members_text += f"{i}. {m.client_name}{is_new}\n"
                else:
                    members_text = ""
                    for i, m in enumerate(all_members, 1):
                        is_new = " (новый!)" if new_member and m.id == new_member.id else ""
                        members_text += f"{i}. {m.client_name}, {m.client_phone}{is_new}\n"
                
                guide_msg = f"""
👥 *ИЗМЕНЕНИЕ В ГРУППЕ {parent.booking_id} ({len(all_members)} чел)!*

📅 *Дата:* {parent.booking_date}
🕒 *Время:* {parent.excursion_start_time} — {parent.excursion_end_time or 'по договоренности'}
📍 *Место сбора:* {parent.guide_start_location or 'уточняется'}
👥 *Мест в группе:* от {parent.group_min_people} до {parent.group_max_people}
💰 *Цена за человека:* {int(price)} руб.

👤 *Участники:*
{members_text}

💰 *Общая стоимость:* {int(price * total_people)} руб.
💸 *Комиссия (5%):* {int(price * total_people * 0.05)} руб.
Осталось мест: {parent.group_max_people - total_people if parent.group_max_people else 'не ограничено'}
"""
                bot.send_message(parent.guide_id, guide_msg, parse_mode='Markdown')
            except:
                pass
        
        if MANAGER_CHAT_ID:
            try:
                members_text = ""
                for i, m in enumerate(all_members, 1):
                    is_new = " (новый!)" if new_member and m.id == new_member.id else ""
                    members_text += f"{i}. {m.client_name}, {m.client_phone}{is_new}\n"
                
                admin_msg = f"""
👥 *ИЗМЕНЕНИЕ В ГРУППЕ {parent.booking_id} ({len(all_members)} чел)!*

📅 *Дата:* {parent.booking_date}
🕒 *Время:* {parent.excursion_start_time} — {parent.excursion_end_time or 'по договоренности'}
📍 *Место сбора:* {parent.guide_start_location or 'уточняется'}
👥 *Мест в группе:* от {parent.group_min_people} до {parent.group_max_people}
💰 *Цена за человека:* {int(price)} руб.

👤 *Участники (контакты):*
{members_text}

💰 *Общая стоимость:* {int(price * total_people)} руб.
💸 *Комиссия (5%):* {int(price * total_people * 0.05)} руб.
Осталось мест: {parent.group_max_people - total_people if parent.group_max_people else 'не ограничено'}
"""
                bot.send_message(MANAGER_CHAT_ID, admin_msg, parse_mode='Markdown')
            except:
                pass
        
        if new_member:
            client_user = db.query(User).filter_by(id=new_member.user_id).first()
            if client_user:
                try:
                    prepayment = int(price * new_member.people_count * 0.3)
                    total = int(price * new_member.people_count)
                    client_msg = f"""
✅ *ПОЗДРАВЛЯЕМ ВЫ ЗАПИСАНЫ НА ЭКСКУРСИЮ!*

*Гид:* {parent.guide_name}
{get_user_link(db.query(User).filter_by(user_id=parent.guide_id).first())}

*Экскурсия:* {get_excursion_name(db, parent.excursion_id)}

*Предлагаемые условия:*
📅 *Дата:* {parent.booking_date}
🕒 *Время:* {parent.excursion_start_time} — {parent.excursion_end_time or 'по договоренности'}
📍 *Место сбора:* {parent.guide_start_location or 'уточняется'}
💰 *Цена за человека:* {int(price)} руб.
📋 *Общая стоимость:* {total} руб.

*Внесите предоплату 30% — {prepayment} руб. из {total} руб.*

Для уточнения на какой счёт вносить предоплату свяжитесь с гидом ({get_user_link(db.query(User).filter_by(user_id=parent.guide_id).first())}).

После внесения предоплаты нажмите кнопку 'Я внёс предоплату'.

*Номер заявки:* {new_member.booking_id}
"""
                    markup = types.InlineKeyboardMarkup().add(
                        types.InlineKeyboardButton('💳 Я внёс предоплату', callback_data=f'excursion_prepayment_{new_member.id}')
                    )
                    bot.send_message(client_user.user_id, client_msg, parse_mode='Markdown', reply_markup=markup)
                except:
                    pass

# ========== ОБРАБОТЧИКИ ВЫБОРА ПРЕДЛОЖЕНИЯ КЛИЕНТОМ ==========

def handle_accept_offer(bot, call):
    """Клиент принимает предложение гида"""
    # Сначала отвечаем на callback, чтобы избежать ошибки "query is too old"
    bot.answer_callback_query(call.id)
    
    offer_id = int(call.data.split('_')[-1])

    with next(get_db()) as db:
        offer = db.query(ExcursionOffer).filter_by(id=offer_id).first()
        if not offer:
            bot.send_message(call.message.chat.id, "❌ Предложение не найдено")
            return

        booking = db.query(ExcursionBooking).filter_by(id=offer.booking_id).first()
        if not booking:
            bot.send_message(call.message.chat.id, "❌ Бронирование не найдено")
            return

        if booking.status == 'accepted':
            bot.send_message(call.message.chat.id, "❌ Это предложение уже принято")
            return

        if booking.status == 'expired':
            bot.send_message(call.message.chat.id, "❌ Время на выбор истекло")
            return

        offer.status = 'accepted'
        booking.status = 'accepted'
        booking.guide_id = offer.guide_id
        booking.guide_name = offer.guide_name
        booking.accepted_at = datetime.now()

        booking.total_price = offer.price * booking.people_count
        if offer.offer_date:
            booking.booking_date = offer.offer_date
        if offer.offer_time:
            booking.excursion_time = offer.offer_time

        db.commit()

        excursion_name = get_excursion_name(db, booking.excursion_id)
        guide_user = db.query(User).filter_by(user_id=offer.guide_id).first()
        guide_link = get_user_link(guide_user)

        prepayment_percent = 30
        excursion = db.query(Excursion).filter_by(id=booking.excursion_id).first()
        if excursion and excursion.prepayment_percent:
            prepayment_percent = excursion.prepayment_percent

        prepayment_amount = booking.total_price * prepayment_percent / 100

        bot.send_message(
            call.from_user.id,
            f"✅ *Поздравляем с выбором гида!*\n\n"
            f"*Детали вашей экскурсии:*\n"
            f"🗺️ Экскурсия: {excursion_name}\n"
            f"🗺️ Гид: {offer.guide_name} ({guide_link})\n"
            f"📅 Дата: {offer.offer_date if offer.offer_date else booking.booking_date}\n"
            f"🕒 Время: {offer.offer_time if offer.offer_time else 'по договоренности'}\n"
            f"📍 Место сбора: {booking.guide_start_location or 'уточняется'}\n"
            f"👥 Количество человек: {booking.people_count}\n"
            f"💰 Полная стоимость: {int(booking.total_price)} руб.\n\n"
            f"*Внесите предоплату {prepayment_percent}% — {int(prepayment_amount)} руб. из {int(booking.total_price)} руб.*\n\n"
            f"Для уточнения на какой счёт вносить предоплату свяжитесь с гидом ({guide_link}).\n\n"
            f"После внесения предоплаты нажмите кнопку 'Я внёс предоплату'.",
            parse_mode='Markdown',
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton('💳 Я внёс предоплату', callback_data=f'excursion_prepayment_{booking.id}')
            )
        )

        if MANAGER_CHAT_ID:
            members = db.query(ExcursionBooking).filter(
                ExcursionBooking.parent_booking_id == booking.id,
                ExcursionBooking.status != 'cancelled'
            ).all()
            all_members = [booking] + members
            total_people = sum(m.people_count or 0 for m in all_members)
            
            members_text = ""
            for i, m in enumerate(all_members, 1):
                members_text += f"{i}. {m.client_name}, {m.client_phone}\n"
            
            admin_msg = f"""
🗺️ *ДЕТАЛИ ЭКСКУРСИИ*

*Экскурсия:* {excursion_name}
*Гид:* {booking.guide_name} ({get_user_link(guide_user)})
📅 *Дата:* {booking.booking_date}
🕒 *Время:* {booking.excursion_start_time} — {booking.excursion_end_time or 'по договоренности'}
📍 *Место сбора:* {booking.guide_start_location or 'уточняется'}
👥 *Мест в группе:* от {booking.group_min_people} до {booking.group_max_people}
💰 *Стоимость за человека:* {int(booking.guide_price_per_person)} руб.

*Записалось {len(all_members)} человек:*
{members_text}

💰 *Общая стоимость:* {int(booking.guide_price_per_person * total_people)} руб.
💸 *Комиссия (5%):* {int(booking.guide_price_per_person * total_people * 0.05)} руб.
Свободных мест: {booking.group_max_people - total_people if booking.group_max_people else 'не ограничено'}
"""
            bot.send_message(MANAGER_CHAT_ID, admin_msg, parse_mode='Markdown')

        other_offers = db.query(ExcursionOffer).filter_by(booking_id=booking.id, status='pending').all()
        for other_offer in other_offers:
            if other_offer.id != offer.id:
                other_offer.status = 'rejected'
        db.commit()

def handle_excursion_prepayment(bot, call):
    """Клиент подтверждает внесение предоплаты гиду"""
    booking_id = int(call.data.split('_')[-1])

    with next(get_db()) as db:
        booking = db.query(ExcursionBooking).filter_by(id=booking_id).first()
        if not booking:
            bot.answer_callback_query(call.id, "❌ Бронирование не найдено", show_alert=True)
            return

        prepayment_percent = 30
        excursion = db.query(Excursion).filter_by(id=booking.excursion_id).first()
        if excursion and excursion.prepayment_percent:
            prepayment_percent = excursion.prepayment_percent

        prepayment_amount = booking.total_price * prepayment_percent / 100

        booking.prepayment_amount = prepayment_amount
        booking.prepayment_paid = True
        booking.prepayment_paid_at = datetime.now()
        booking.status = 'prepayment_paid'
        db.commit()

        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"✅ *Предоплата подтверждена!*\n\n"
                     f"Спасибо! Вы внесли предоплату {int(prepayment_amount)} руб.\n"
                     f"Гид получит уведомление.",
                parse_mode='Markdown',
                reply_markup=None
            )
        except Exception as e:
            bot.send_message(
                call.message.chat.id,
                f"✅ *Предоплата подтверждена!*\n\n"
                f"Спасибо! Вы внесли предоплату {int(prepayment_amount)} руб.\n"
                f"Гид получит уведомление.",
                parse_mode='Markdown'
            )

        commission_amount = booking.total_price * EXCURSION_COMMISSION / 100

        # Собираем всех участников группы
        if booking.parent_booking_id:
            parent = db.query(ExcursionBooking).filter_by(id=booking.parent_booking_id).first()
            members = db.query(ExcursionBooking).filter(
                ExcursionBooking.parent_booking_id == booking.parent_booking_id,
                ExcursionBooking.status != 'cancelled'
            ).all()
            all_members = [parent] + members if parent else [booking]
        else:
            child_members = db.query(ExcursionBooking).filter(
                ExcursionBooking.parent_booking_id == booking.id,
                ExcursionBooking.status != 'cancelled'
            ).all()
            all_members = [booking] + child_members
        
        members_text = ""
        total_people = 0
        for i, m in enumerate(all_members, 1):
            members_text += f"{i}. {m.client_name}, {m.client_phone}\n"
            total_people += m.people_count or 0

        # ОТПРАВЛЯЕМ КОМИССИЮ ЧЕРЕЗ send_commission_payment_link
        send_commission_payment_link(
            bot=bot,
            chat_id=booking.guide_id,
            amount=commission_amount,
            booking_id=booking.booking_id,
            booking_type='excursion',
            user_id=booking.guide_id
        )

        if MANAGER_CHAT_ID:
            bot.send_message(
                MANAGER_CHAT_ID,
                f"💰 *КЛИЕНТ ВНЁС ПРЕДОПЛАТУ*\n\n"
                f"Номер заявки: {booking.booking_id}\n"
                f"Клиент: {booking.client_name} ({booking.client_phone})\n"
                f"Сумма предоплаты: {int(prepayment_amount)} руб.\n"
                f"Полная стоимость: {int(booking.total_price)} руб.\n"
                f"Комиссия (5%): {int(commission_amount)} руб.\n"
                f"Гид: {booking.guide_name}\n"
                f"Дата: {booking.booking_date}\n\n"
                f"👥 *Участники группы:*\n{members_text}\n"
                f"Всего человек: {total_people}\n"
                f"Статус: Ожидает оплаты комиссии от гида",
                parse_mode='Markdown'
            )

        bot.answer_callback_query(call.id, "✅ Предоплата подтверждена!")

def handle_excursion_commission_paid(bot, call):
    """Гид подтверждает оплату комиссии"""
    booking_id = int(call.data.split('_')[-1])

    with next(get_db()) as db:
        booking = db.query(ExcursionBooking).filter_by(id=booking_id).first()
        if not booking:
            bot.answer_callback_query(call.id, "❌ Бронирование не найдено", show_alert=True)
            return

        commission_amount = booking.total_price * EXCURSION_COMMISSION / 100

        payment = Payment(
            user_id=booking.guide_id,
            booking_type='excursion_commission',
            booking_id=booking.id,
            amount=commission_amount,
            payment_method='sbp',
            status='completed'
        )
        db.add(payment)

        booking.payment_status = 'commission_paid'
        db.commit()

        # Собираем всех участников группы
        if booking.parent_booking_id:
            parent = db.query(ExcursionBooking).filter_by(id=booking.parent_booking_id).first()
            members = db.query(ExcursionBooking).filter(
                ExcursionBooking.parent_booking_id == booking.parent_booking_id,
                ExcursionBooking.status != 'cancelled'
            ).all()
            all_members = [parent] + members if parent else [booking]
        else:
            child_members = db.query(ExcursionBooking).filter(
                ExcursionBooking.parent_booking_id == booking.id,
                ExcursionBooking.status != 'cancelled'
            ).all()
            all_members = [booking] + child_members
        
        members_text = ""
        total_people = 0
        for i, m in enumerate(all_members, 1):
            members_text += f"{i}. {m.client_name}, {m.client_phone}\n"
            total_people += m.people_count or 0

        if MANAGER_CHAT_ID:
            bot.send_message(
                MANAGER_CHAT_ID,
                f"💰 *КОМИССИЯ ЗА ЭКСКУРСИЮ ОПЛАЧЕНА*\n\n"
                f"Гид: {booking.guide_name} (ID: {booking.guide_id})\n"
                f"Клиент: {booking.client_name}\n"
                f"Сумма экскурсии: {int(booking.total_price)} руб.\n"
                f"Комиссия (5%): {int(commission_amount)} руб.\n"
                f"Дата экскурсии: {booking.booking_date}\n\n"
                f"👥 *Участники группы:*\n{members_text}\n"
                f"Всего человек: {total_people}\n"
                f"Статус: ✅ Комиссия оплачена",
                parse_mode='Markdown'
            )

        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="✅ *Комиссия успешно оплачена!*\n\nСпасибо!",
                parse_mode='Markdown',
                reply_markup=None
            )
        except Exception as e:
            bot.send_message(
                call.message.chat.id,
                "✅ *Комиссия успешно оплачена!*\n\nСпасибо!",
                parse_mode='Markdown'
            )

        bot.send_message(
            booking.guide_id,
            "✅ *Спасибо! Комиссия оплачена.*\n\n"
            "Теперь вы можете провести экскурсию с клиентом.",
            parse_mode='Markdown'
        )

        bot.answer_callback_query(call.id, "✅ Комиссия оплачена")

def handle_excursion_client_paid(bot, call):
    """Клиент подтверждает оплату гиду (полная оплата)"""
    booking_id = int(call.data.split('_')[-1])

    with next(get_db()) as db:
        booking = db.query(ExcursionBooking).filter_by(id=booking_id).first()
        if not booking:
            bot.answer_callback_query(call.id, "❌ Бронирование не найдено", show_alert=True)
            return

        excursion_name = get_excursion_name(db, booking.excursion_id)

        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"✅ *Спасибо!*\n\n"
                     f"Поставьте гиду {booking.guide_name} оценку и напишите отзыв "
                     f"(можно пропустить).\n\n"
                     f"А ещё рекомендуем выбрать экскурсию или купить товары Арктики в нашем магазине!",
                parse_mode='Markdown',
                reply_markup=None
            )
        except Exception as e:
            print(f"Ошибка при редактировании сообщения: {e}")
            bot.send_message(
                call.message.chat.id,
                f"✅ *Спасибо!*\n\n"
                f"Поставьте гиду {booking.guide_name} оценку и напишите отзыв "
                f"(можно пропустить).\n\n"
                f"А ещё рекомендуем выбрать экскурсию или купить товары Арктики в нашем магазине!",
                parse_mode='Markdown',
                reply_markup=keyboards.main_menu()
            )

        booking.payment_status = 'paid'
        db.commit()

        # Собираем всех участников группы
        if booking.parent_booking_id:
            parent = db.query(ExcursionBooking).filter_by(id=booking.parent_booking_id).first()
            members = db.query(ExcursionBooking).filter(
                ExcursionBooking.parent_booking_id == booking.parent_booking_id,
                ExcursionBooking.status != 'cancelled'
            ).all()
            all_members = [parent] + members if parent else [booking]
        else:
            child_members = db.query(ExcursionBooking).filter(
                ExcursionBooking.parent_booking_id == booking.id,
                ExcursionBooking.status != 'cancelled'
            ).all()
            all_members = [booking] + child_members
        
        members_text = ""
        total_people = 0
        for i, m in enumerate(all_members, 1):
            members_text += f"{i}. {m.client_name}, {m.client_phone}\n"
            total_people += m.people_count or 0

        if MANAGER_CHAT_ID:
            bot.send_message(
                MANAGER_CHAT_ID,
                f"💰 *КЛИЕНТ ПОЛНОСТЬЮ ОПЛАТИЛ ЭКСКУРСИЮ*\n\n"
                f"Номер заявки: {booking.booking_id}\n"
                f"Гид: {booking.guide_name}\n"
                f"Клиент: {booking.client_name}\n"
                f"Сумма: {int(booking.total_price)} руб.\n"
                f"Дата: {booking.booking_date}\n\n"
                f"👥 *Участники группы:*\n{members_text}\n"
                f"Всего человек: {total_people}",
                parse_mode='Markdown'
            )

        bot.answer_callback_query(call.id, "✅ Спасибо!")

def handle_guide_paid_commission(bot, call):
    """Гид подтверждает оплату комиссии (старая версия, для совместимости)"""
    booking_id = int(call.data.split('_')[-1])

    with next(get_db()) as db:
        booking = db.query(ExcursionBooking).filter_by(id=booking_id).first()
        if not booking:
            bot.answer_callback_query(call.id, "❌ Занятие не найдено", show_alert=True)
            return

        commission_amount = booking.total_price * 10 / 100

        payment = Payment(
            user_id=booking.guide_id,
            booking_type='excursion_commission',
            booking_id=booking.id,
            amount=commission_amount,
            payment_method='sbp',
            status='completed'
        )
        db.add(payment)

        booking.payment_status = 'paid'
        db.commit()

        if MANAGER_CHAT_ID:
            bot.send_message(
                MANAGER_CHAT_ID,
                f"💰 *КОМИССИЯ ЗА ЭКСКУРСИЮ ОПЛАЧЕНА*\n\n"
                f"Гид: {booking.guide_name} (ID: {booking.guide_id})\n"
                f"Клиент: {booking.client_name}\n"
                f"Сумма экскурсии: {int(booking.total_price)} руб.\n"
                f"Комиссия (10%): {int(commission_amount)} руб.\n"
                f"Дата экскурсии: {booking.booking_date}",
                parse_mode='Markdown'
            )

        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="✅ *Комиссия успешно оплачена!*\n\nСпасибо!",
                parse_mode='Markdown',
                reply_markup=None
            )
        except Exception as e:
            bot.send_message(
                call.message.chat.id,
                "✅ *Комиссия успешно оплачена!*\n\nСпасибо!",
                parse_mode='Markdown'
            )

        bot.answer_callback_query(call.id, "✅ Комиссия оплачена")

def handle_reject_offer(bot, call):
    """Клиент отклоняет предложение гида"""
    offer_id = int(call.data.split('_')[-1])

    with next(get_db()) as db:
        offer = db.query(ExcursionOffer).filter_by(id=offer_id).first()
        if not offer:
            bot.answer_callback_query(call.id, "❌ Предложение не найдено", show_alert=True)
            return

        booking = db.query(ExcursionBooking).filter_by(id=offer.booking_id).first()
        if not booking:
            bot.answer_callback_query(call.id, "❌ Бронирование не найдено", show_alert=True)
            return

        if booking.status == 'accepted':
            bot.answer_callback_query(call.id, "❌ Заявка уже принята", show_alert=True)
            return

        offer.status = 'rejected'
        db.commit()

        bot.send_message(
            call.from_user.id,
            f"❌ *Вы отклонили предложение от гида {offer.guide_name}*\n\n"
            f"Вы можете дождаться других предложений.",
            parse_mode='Markdown'
        )

        if GUIDES_CHAT_ID:
            try:
                chat_text = f"""
🗺️ *ОЖИДАЕТ ГИДА:*

*Номер заявки:* {booking.id}
🕒 *Статус:* Клиент отклонил заявку гида {offer.guide_name}
И ожидает предложений от других гидов.
"""
                bot.send_message(GUIDES_CHAT_ID, chat_text, parse_mode='Markdown')
            except Exception as e:
                print(f"❌ Ошибка отправки в чат гидов: {e}")

        bot.answer_callback_query(call.id, "❌ Предложение отклонено")

def handle_wait_offer(bot, call):
    """Клиент ждет другие предложения"""
    offer_id = int(call.data.split('_')[-1])

    with next(get_db()) as db:
        offer = db.query(ExcursionOffer).filter_by(id=offer_id).first()
        if not offer:
            bot.answer_callback_query(call.id, "❌ Предложение не найдено", show_alert=True)
            return

        booking = db.query(ExcursionBooking).filter_by(id=offer.booking_id).first()
        if not booking:
            bot.answer_callback_query(call.id, "❌ Бронирование не найдено", show_alert=True)
            return

        bot.send_message(
            call.from_user.id,
            f"⏳ *Вы можете вернуться к этой заявке позже, но не позднее {(datetime.now() + timedelta(hours=48)).strftime('%d.%m.%Y %H:%M')}*\n\n"
            "Мы уведомим вас, когда появятся новые предложения от гидов.",
            parse_mode='Markdown'
        )

        if GUIDES_CHAT_ID:
            try:
                chat_text = f"""
🗺️ *ОЖИДАЕТ ГИДА:*

*Номер заявки:* {booking.id}
🕒 *Статус:* Клиент ожидает еще предложений от других гидов.
"""
                bot.send_message(GUIDES_CHAT_ID, chat_text, parse_mode='Markdown')
            except Exception as e:
                print(f"❌ Ошибка отправки в чат гидов: {e}")

        bot.answer_callback_query(call.id, "⏳ Ждем другие предложения")

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def send_excursion_offer_to_client(bot, offer, booking):
    """Отправляет предложение гида клиенту"""
    try:
        with next(get_db()) as db:
            excursion_name = get_excursion_name(db, booking.excursion_id)
            user = db.query(User).filter_by(id=booking.user_id).first()

            if not user:
                print(f"❌ Пользователь не найден для бронирования {booking.id}")
                return

            offer_text = f"""
🗺️ *ПРЕДЛОЖЕНИЕ ОТ ГИДА*

*Гид:* {offer.guide_name}
{'@' + offer.guide_username if offer.guide_username else ''}

*Экскурсия:* {excursion_name}

*Предлагаемые условия:*
📅 *Дата:* {offer.offer_date}
🕒 *Время:* {offer.offer_time if offer.offer_time else 'по договоренности'}
📍 *Место сбора:* {booking.guide_start_location or 'уточняется'}
👥 *Количество человек:* {booking.people_count}
💰 *Цена за человека:* {int(offer.price)} руб.
📋 *Общая стоимость:* {int(offer.price * booking.people_count)} руб.
"""
            if offer.description:
                offer_text += f"\n💬 *Описание от гида:*\n{offer.description}\n"

            offer_text += f"\n*Номер заявки:* {booking.booking_id}"

            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton('✅ Принять', callback_data=f'guide_accept_offer_{offer.id}'),
                types.InlineKeyboardButton('❌ Отклонить', callback_data=f'guide_reject_offer_{offer.id}'),
                types.InlineKeyboardButton('⏳ Подождать другие', callback_data=f'guide_wait_offer_{offer.id}')
            )

            bot.send_message(user.user_id, offer_text, parse_mode='Markdown', reply_markup=markup)
            print(f"✅ Предложение отправлено клиенту {user.user_id}")

    except Exception as e:
        print(f"❌ Ошибка в send_excursion_offer_to_client: {e}")