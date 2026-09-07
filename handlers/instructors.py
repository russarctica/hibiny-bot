import telebot
from telebot import types
import json
from datetime import datetime, timedelta
import random
import string
import re

from database import get_db, User, InstructorBooking, InstructorOffer, InstructorExtension, Setting, Payment
from state_manager import StateManager
from states import UserStates, StateData
import keyboards
from config import MANAGER_CHAT_ID, INSTRUCTORS_CHAT_ID, SBP_PAYMENT_URL
from handlers.payment import send_payment_link, send_commission_payment_link

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def escape_md(text):
    if not text:
        return ""
    text = str(text)
    for char in ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']:
        text = text.replace(char, '\\' + char)
    return text

def get_user_link(user):
    if not user:
        return "неизвестно"
    if user.username:
        return f"@{user.username}"
    else:
        return f"[{user.first_name or 'ID'}](tg://user?id={user.user_id})"

def get_user_link_by_id(db, user_id):
    user = db.query(User).filter_by(user_id=user_id).first()
    return get_user_link(user)

def calc_end_time(start_time_str, hours):
    try:
        if not start_time_str or hours <= 0 or hours > 12:
            return ""
        start_h, start_m = map(int, start_time_str.split(':'))
        total_minutes = start_h * 60 + start_m + hours * 60
        end_h = (total_minutes // 60) % 24
        end_m = total_minutes % 60
        return f"{end_h:02d}:{end_m:02d}"
    except:
        return ""

def format_booking_text(booking, sport, end_time, note="", freeride_days=0):
    safe_id = booking.booking_id if booking.booking_id else str(booking.id)
    text = f"🎿 *НОВАЯ ЗАЯВКА {safe_id}*\n\n"
    text += f"*Ищет:* {sport}\n"
    text += f"*Программа:* {booking.program}\n"
    text += f"*Тип занятия:* {booking.lesson_type}"
    if booking.lesson_type == 'Группа':
        text += f" ({booking.group_size} чел.)"
    text += "\n"
    if booking.program == 'Фрирайд':
        if booking.student_type in ['начинающий', 'продолжающий']:
            level_display = 'Начинающий (возле трасс)' if booking.student_type == 'начинающий' else 'Продолжающий (есть опыт)'
            text += f"*Уровень:* {level_display}\n"
    else:
        if booking.student_type in ['Взрослый', 'Ребенок']:
            text += f"*Ученик:* {booking.student_type}\n"
    if hasattr(booking, 'children_info') and booking.children_info:
        text += f"*Дети:* {booking.children_info}\n"
    if booking.program == 'Фрирайд' and freeride_days > 0:
        text += f"*Продолжительность:* {freeride_days} дн.\n"
    else:
        text += f"*Продолжительность:* {booking.hours} час(ов)\n"
    text += f"*Дата:* {booking.lesson_date}\n"
    text += f"*Время:* {booking.lesson_time}"
    if end_time:
        text += f" — {end_time}"
    text += "\n"
    text += f"*Стоимость:* {int(booking.total_price)} руб.\n"
    if note:
        text += f"*Примечание:* {note}\n"
    if booking.group_type == 'open_group':
        text += f"*Статус:* 👥 Сборная группа (ждём участников)\n"
    else:
        text += f"*Статус:* Ищет инструктора"
    return text

def format_group_text(group_members):
    b = group_members[0]
    safe_id = b.booking_id if b.booking_id else str(b.id)
    text = f"👥 *ГРУППА НАБРАЛАСЬ! {safe_id}*\n\n"
    text += f"📅 *Дата:* {b.lesson_date}\n"
    text += f"🕒 *Время:* {b.lesson_time} — 14:00\n"
    text += f"📋 *Программа:* {b.program}\n"
    text += f"🏂 *Спорт:* {b.sport}\n"
    if b.student_type in ['Взрослый', 'Ребенок']:
        text += f"👶 *Ученик:* {b.student_type}\n"
    text += f"\n👤 *{len(group_members)} участников:*\n"
    for i, m in enumerate(group_members, 1):
        text += f"{i}. {m.client_name}, {m.client_phone}\n"
    return text

# ========== КЛИЕНТСКАЯ ЧАСТЬ ==========

def handle_instructors_start(bot, message, rebook_instructor_id=None, rebook_instructor_name=None):
    user_id = message.from_user.id
    chat_id = message.chat.id
    data = StateData(step=1)
    if rebook_instructor_id:
        data.rebook_instructor_id = rebook_instructor_id
        data.rebook_instructor_name = rebook_instructor_name
    StateManager.set_state(user_id, UserStates.INSTRUCTORS_SELECT_SPORT, data)
    bot.send_message(chat_id, "🎿 *Выберите вид спорта:*", parse_mode='Markdown', reply_markup=keyboards.instructors_sport_keyboard())

def handle_instructors_sport(bot, message):
    user_id = message.from_user.id; chat_id = message.chat.id
    if message.text == '🔙 Назад': StateManager.clear_state(user_id); bot.send_message(chat_id, "Возвращаемся в главное меню:", reply_markup=keyboards.main_menu()); return
    if message.text == '❌ Отмена': StateManager.clear_state(user_id); bot.send_message(chat_id, "Действие отменено.", reply_markup=keyboards.main_menu()); return
    if message.text == '🤸 Другое':
        data = StateManager.get_data(user_id); StateManager.set_state(user_id, UserStates.INSTRUCTORS_ENTER_OTHER_SPORT, data)
        bot.send_message(chat_id, "✏️ *Введите вид спорта:*\n\nНапример: сноукайтинг, сапборд", parse_mode='Markdown', reply_markup=keyboards.back_button()); return
    sport_mapping = {'🎿 Горные лыжи': 'Горные лыжи', '🏂 Сноуборд': 'Сноуборд'}
    if message.text not in sport_mapping: bot.send_message(chat_id, "❌ Пожалуйста, выберите вид спорта из списка:", reply_markup=keyboards.instructors_sport_keyboard()); return
    sport = sport_mapping[message.text]
    data = StateManager.get_data(user_id); data_dict = data.to_dict() if hasattr(data, 'to_dict') else {}
    data_dict['sport'] = sport; data_dict['step'] = 2
    StateManager.set_state(user_id, UserStates.INSTRUCTORS_PROGRAM_INFO, StateData(**data_dict))
    bot.send_message(chat_id, "🎿 *ИНСТРУКТОРЫ*\n\nВыберите программу:", parse_mode='Markdown', reply_markup=keyboards.instructors_program_keyboard())

def handle_instructors_other_sport(bot, message):
    user_id = message.from_user.id; chat_id = message.chat.id
    if message.text == '🔙 Назад':
        data = StateManager.get_data(user_id); StateManager.set_state(user_id, UserStates.INSTRUCTORS_SELECT_SPORT, data)
        bot.send_message(chat_id, "🎿 *Выберите вид спорта:*", reply_markup=keyboards.instructors_sport_keyboard()); return
    if message.text == '❌ Отмена': StateManager.clear_state(user_id); bot.send_message(chat_id, "Действие отменено.", reply_markup=keyboards.main_menu()); return
    other_sport = message.text.strip()
    data = StateManager.get_data(user_id); data_dict = data.to_dict() if hasattr(data, 'to_dict') else {}
    data_dict['sport'] = other_sport; data_dict['step'] = 2
    StateManager.set_state(user_id, UserStates.INSTRUCTORS_PROGRAM_INFO, StateData(**data_dict))
    bot.send_message(chat_id, "🎿 *ИНСТРУКТОРЫ*\n\nВыберите программу:", parse_mode='Markdown', reply_markup=keyboards.instructors_program_keyboard())

def handle_instructors_program(bot, message):
    user_id = message.from_user.id; chat_id = message.chat.id
    if message.text == '🔙 Назад':
        data = StateManager.get_data(user_id); StateManager.set_state(user_id, UserStates.INSTRUCTORS_SELECT_SPORT, data)
        bot.send_message(chat_id, "🎿 *Выберите вид спорта:*", reply_markup=keyboards.instructors_sport_keyboard()); return
    if message.text == '❌ Отмена': StateManager.clear_state(user_id); bot.send_message(chat_id, "Действие отменено.", reply_markup=keyboards.main_menu()); return
    program_mapping = {'🎿 Новичок': 'Новичок', '⛷️ Продолжающий': 'Продолжающий', '🏂 Карвинг': 'Карвинг', '🏔️ Фрирайд': 'Фрирайд'}
    if message.text not in program_mapping: bot.send_message(chat_id, "❌ Пожалуйста, выберите программу:", reply_markup=keyboards.instructors_program_keyboard()); return
    program = program_mapping[message.text]
    data = StateManager.get_data(user_id); data_dict = data.to_dict() if hasattr(data, 'to_dict') else {}
    data_dict['program'] = program; data_dict['step'] = 3
    StateManager.set_state(user_id, UserStates.INSTRUCTORS_SELECT_PEOPLE, StateData(**data_dict))
    bot.send_message(chat_id, "👤 *Выберите количество человек или запишитесь в сборную группу*", parse_mode='Markdown', reply_markup=keyboards.instructors_people_keyboard())

def handle_instructors_people(bot, message):
    user_id = message.from_user.id; chat_id = message.chat.id
    if message.text == '🔙 Назад':
        if StateManager.go_back(user_id): bot.send_message(chat_id, "🎿 *Выберите программу обучения:*", reply_markup=keyboards.instructors_program_keyboard())
        return
    if message.text == '❌ Отмена': StateManager.clear_state(user_id); bot.send_message(chat_id, "Действие отменено.", reply_markup=keyboards.main_menu()); return
    if message.text == '👥 Хочу в группу':
        data = StateManager.get_data(user_id); d = data.to_dict() if hasattr(data, 'to_dict') else {}
        d['group_type'] = 'open_group'; d['lesson_type'] = 'Группа'; d['group_size'] = 1
        bot.send_message(chat_id, "👥 *Сборная группа*\n\n⚠️ Сборная группа формируется чат-ботом.\nЧат-бот подбирает группу, подходящую вам по уровню.\nЕсли группа не наберётся до 19:00 предыдущего дня — предложим занятие индивидуально.", parse_mode='Markdown')
        program = d.get('program', '')
        if program == 'Фрирайд':
            StateManager.set_state(user_id, UserStates.INSTRUCTORS_FREERIDE_LEVEL, StateData(**d))
            bot.send_message(chat_id, "🏔️ *Выберите ваш уровень фрирайда:*", parse_mode='Markdown', reply_markup=keyboards.instructors_freeride_level_keyboard())
        else:
            StateManager.set_state(user_id, UserStates.INSTRUCTORS_SELECT_STUDENT, StateData(**d))
            bot.send_message(chat_id, "👤 *Укажите, для кого занятие:*\n\n👨 *Взрослый* - от 18 лет\n👶 *Ребенок* - до 18 лет", parse_mode='Markdown', reply_markup=keyboards.instructors_student_type_keyboard())
        return
    if message.text == '👤 Количество человек':
        bot.send_message(chat_id, "👤 *Введите количество человек*\n\nНапишите число в свободной форме.\n• Если *1 человек* — индивидуальное занятие.\n• Если *2 и более* — вы идёте своей компанией.\n\n_⚠️ Все участники должны иметь примерно одинаковый уровень катания._\n_Если уровни разные — лучше создать отдельные заявки._", parse_mode='Markdown', reply_markup=keyboards.back_button())
        return
    try:
        people_count = int(message.text.strip())
        if people_count < 1: bot.send_message(chat_id, "❌ Количество человек должно быть не менее 1.", reply_markup=keyboards.back_button()); return
    except ValueError: bot.send_message(chat_id, "❌ Пожалуйста, введите число или нажмите «👤 Количество человек»:", reply_markup=keyboards.instructors_people_keyboard()); return
    data = StateManager.get_data(user_id); d = data.to_dict() if hasattr(data, 'to_dict') else {}
    d['group_size'] = people_count
    if people_count == 1:
        d['group_type'] = 'individual'; d['lesson_type'] = 'Индивидуально'
        if d.get('program') == 'Фрирайд':
            StateManager.set_state(user_id, UserStates.INSTRUCTORS_FREERIDE_LEVEL, StateData(**d))
            bot.send_message(chat_id, "🏔️ *Выберите ваш уровень фрирайда:*", reply_markup=keyboards.instructors_freeride_level_keyboard())
        else:
            StateManager.set_state(user_id, UserStates.INSTRUCTORS_SELECT_STUDENT, StateData(**d))
            bot.send_message(chat_id, "👤 *Укажите, для кого занятие:*", reply_markup=keyboards.instructors_student_type_keyboard())
    else:
        d['group_type'] = 'my_company'; d['lesson_type'] = 'Группа'
        bot.send_message(chat_id, f"👥 *Вы записываете {people_count} человек*\n\n_⚠️ Инструктор не сможет одновременно учить новичка и тренировать продолжающего._\n_Если уровни разные — лучше создать отдельные заявки._", parse_mode='Markdown')
        StateManager.set_state(user_id, UserStates.INSTRUCTORS_CHILDREN_INFO, StateData(**d))
        bot.send_message(chat_id, "👶 *В вашей компании есть дети?*\n\n_⚠️ Обычно инструкторы не берут в одно занятие взрослых и детей, кроме случаев, когда ребёнок уже опытный и уровень совпадает со взрослым._", parse_mode='Markdown', reply_markup=keyboards.instructors_children_keyboard())

def handle_instructors_children_info(bot, message):
    user_id = message.from_user.id; chat_id = message.chat.id
    if message.text == '🔙 Назад': StateManager.set_state(user_id, UserStates.INSTRUCTORS_SELECT_PEOPLE, StateManager.get_data(user_id)); bot.send_message(chat_id, "Напишите количество человек в свободной форме:", reply_markup=keyboards.back_button()); return
    if message.text == '❌ Отмена': StateManager.clear_state(user_id); bot.send_message(chat_id, "Действие отменено.", reply_markup=keyboards.main_menu()); return
    data = StateManager.get_data(user_id); d = data.to_dict() if hasattr(data, 'to_dict') else {}
    if message.text == '👨 Только взрослые (18+)': d['student_type'] = 'Взрослый'; d['children_info'] = 'нет'
    elif message.text == '👶 Есть дети (до 18 лет)': StateManager.update_data(user_id, waiting_for='children_info'); bot.send_message(chat_id, "👶 *Сколько детей и какого возраста?*\n\nНапишите в свободной форме:", reply_markup=keyboards.back_button()); return
    else: d['student_type'] = 'Смешанная'; d['children_info'] = message.text.strip()
    if d.get('program') == 'Фрирайд':
        StateManager.set_state(user_id, UserStates.INSTRUCTORS_FREERIDE_LEVEL, StateData(**d)); bot.send_message(chat_id, "🏔️ *Выберите ваш уровень фрирайда:*", reply_markup=keyboards.instructors_freeride_level_keyboard())
    else:
        StateManager.set_state(user_id, UserStates.INSTRUCTORS_SELECT_HOURS, StateData(**d)); bot.send_message(chat_id, "⏱️ *Выберите продолжительность занятия:*", parse_mode='Markdown', reply_markup=keyboards.instructors_hours_keyboard())

def handle_instructors_freeride_level(bot, message):
    user_id = message.from_user.id; chat_id = message.chat.id
    if message.text == '🔙 Назад':
        data = StateManager.get_data(user_id)
        if hasattr(data, 'group_type') and data.group_type == 'my_company': StateManager.set_state(user_id, UserStates.INSTRUCTORS_CHILDREN_INFO, data); bot.send_message(chat_id, "👶 *В вашей компании есть дети?*", reply_markup=keyboards.instructors_children_keyboard())
        elif hasattr(data, 'group_type') and data.group_type == 'open_group': StateManager.set_state(user_id, UserStates.INSTRUCTORS_SELECT_PEOPLE, data); bot.send_message(chat_id, "Напишите количество человек или выберите «Хочу в группу»:", reply_markup=keyboards.instructors_people_keyboard())
        else:
            if StateManager.go_back(user_id): bot.send_message(chat_id, "👥 *Выберите тип занятия:*", reply_markup=keyboards.instructors_type_keyboard())
        return
    if message.text == '❌ Отмена': StateManager.clear_state(user_id); bot.send_message(chat_id, "Действие отменено.", reply_markup=keyboards.main_menu()); return
    level_mapping = {'🏔️ Начинающий (фрирайд возле трасс)': 'начинающий', '⛷️ Продолжающий (имеет опыт фрирайда)': 'продолжающий'}
    if message.text not in level_mapping: bot.send_message(chat_id, "❌ Пожалуйста, выберите уровень:", reply_markup=keyboards.instructors_freeride_level_keyboard()); return
    level = level_mapping[message.text]
    data = StateManager.get_data(user_id); data_dict = data.to_dict() if hasattr(data, 'to_dict') else {}
    data_dict['student_type'] = level
    if data_dict.get('group_type') == 'open_group':
        StateManager.set_state(user_id, UserStates.INSTRUCTORS_SELECT_GROUP_SLOT, StateData(**data_dict)); bot.send_message(chat_id, "📅 *Введите желаемую дату занятия (ДД.ММ.ГГГГ):*\n\nЯ покажу ближайшие групповые слоты.", parse_mode='Markdown', reply_markup=keyboards.back_button())
    else:
        StateManager.set_state(user_id, UserStates.INSTRUCTORS_FREERIDE_DURATION, StateData(**data_dict)); bot.send_message(chat_id, "⏱️ *Выберите формат занятия:*", parse_mode='Markdown', reply_markup=keyboards.instructors_freeride_duration_keyboard())

def handle_instructors_freeride_duration(bot, message):
    user_id = message.from_user.id; chat_id = message.chat.id
    if message.text == '🔙 Назад':
        if StateManager.go_back(user_id): bot.send_message(chat_id, "🏔️ *Выберите ваш уровень фрирайда:*", reply_markup=keyboards.instructors_freeride_level_keyboard())
        return
    if message.text == '❌ Отмена': StateManager.clear_state(user_id); bot.send_message(chat_id, "Действие отменено.", reply_markup=keyboards.main_menu()); return
    data = StateManager.get_data(user_id); data_dict = data.to_dict() if hasattr(data, 'to_dict') else {}
    if message.text == '4 часа': data_dict['hours'] = 4; data_dict['freeride_days'] = 0
    elif message.text == '1 день': data_dict['hours'] = 8; data_dict['freeride_days'] = 1
    elif message.text == 'Несколько дней': StateManager.set_state(user_id, UserStates.INSTRUCTORS_FREERIDE_DAYS, StateData(**data_dict)); bot.send_message(chat_id, "📅 *Введите количество дней:*", reply_markup=keyboards.back_button()); return
    elif message.text == 'Хочу в тур!': data_dict['hours'] = 0; data_dict['freeride_days'] = 0; data_dict['freeride_tour'] = True
    else: bot.send_message(chat_id, "❌ Пожалуйста, выберите формат:", reply_markup=keyboards.instructors_freeride_duration_keyboard()); return
    StateManager.set_state(user_id, UserStates.INSTRUCTORS_ENTER_DATE, StateData(**data_dict)); bot.send_message(chat_id, "📅 *Введите дату занятия (ДД.ММ.ГГГГ):*", reply_markup=keyboards.back_button())

def handle_instructors_freeride_days(bot, message):
    user_id = message.from_user.id; chat_id = message.chat.id
    if message.text == '🔙 Назад':
        if StateManager.go_back(user_id): bot.send_message(chat_id, "⏱️ *Выберите формат занятия:*", reply_markup=keyboards.instructors_freeride_duration_keyboard())
        return
    if message.text == '❌ Отмена': StateManager.clear_state(user_id); bot.send_message(chat_id, "Действие отменено.", reply_markup=keyboards.main_menu()); return
    try:
        days = int(message.text.strip())
        if days < 2: bot.send_message(chat_id, "❌ Минимум 2 дня.", reply_markup=keyboards.back_button()); return
        data = StateManager.get_data(user_id); data_dict = data.to_dict() if hasattr(data, 'to_dict') else {}
        data_dict['freeride_days'] = days; data_dict['hours'] = days * 8
        StateManager.set_state(user_id, UserStates.INSTRUCTORS_ENTER_DATE, StateData(**data_dict)); bot.send_message(chat_id, "📅 *Введите дату начала (ДД.ММ.ГГГГ):*", reply_markup=keyboards.back_button())
    except ValueError: bot.send_message(chat_id, "❌ Введите целое число дней.", reply_markup=keyboards.back_button())

def show_group_slots(bot, chat_id, user_id, user_date_str):
    from datetime import date
    try: user_date = datetime.strptime(user_date_str, "%d.%m.%Y").date()
    except: user_date = date.today() + timedelta(days=1)
    candidates = []
    for offset in range(-6, 7):
        d_check = user_date + timedelta(days=offset)
        if d_check.day % 2 == 0 and d_check > date.today():
            wd = ['пн','вт','ср','чт','пт','сб','вс'][d_check.weekday()]
            candidates.append({'date': d_check.strftime('%d.%m.%Y'), 'time': '12:00-14:00', 'display': f"{d_check.strftime('%d.%m.%Y')} ({wd}) — 12:00-14:00"})
    candidates.sort(key=lambda x: abs(datetime.strptime(x['date'], '%d.%m.%Y').date() - user_date))
    slots = candidates[:3]; slots.sort(key=lambda x: x['date'])
    if not slots: bot.send_message(chat_id, "❌ Нет доступных слотов в ближайшее время."); return
    data = StateManager.get_data(user_id); d = data.to_dict() if hasattr(data, 'to_dict') else {}
    with next(get_db()) as db:
        program = d.get('program',''); sport = d.get('sport',''); stype = d.get('student_type','')
        rec = []
        for s in slots:
            cnt = db.query(InstructorBooking).filter(
                InstructorBooking.group_status == 'waiting_group',
                InstructorBooking.lesson_date == s['date'], InstructorBooking.lesson_time == '12:00',
                InstructorBooking.program == program, InstructorBooking.sport == sport, InstructorBooking.student_type == stype
            ).count()
            if 0 < cnt < 5: rec.append({**s, 'count': cnt})
    d['group_slots_list'] = slots; d['group_slots_rec'] = rec; d['desired_date'] = user_date_str
    StateManager.set_state(user_id, UserStates.INSTRUCTORS_SELECT_GROUP_SLOT, StateData(**d))
    txt = "📅 *Групповые занятия проходят по чётным числам в 12:00-14:00*\n\n"
    if rec: txt += "🔹 *Рекомендуем* (уже есть заявки):\n"
    txt += "\n🔸 *Ближайшие даты:*\n"; txt += "\n💡 *Хотите другую дату?*\nНапишите её в формате ДД.ММ.ГГГГ"
    bot.send_message(chat_id, txt, parse_mode='Markdown', reply_markup=keyboards.create_group_slots_keyboard(slots, rec))

def handle_instructors_group_slot(bot, message):
    user_id = message.from_user.id; chat_id = message.chat.id
    if message.text == '🔙 Назад':
        data = StateManager.get_data(user_id)
        if hasattr(data, 'group_type') and data.group_type == 'open_group':
            StateManager.set_state(user_id, UserStates.INSTRUCTORS_SELECT_STUDENT, data); bot.send_message(chat_id, "👤 *Укажите, для кого занятие:*", reply_markup=keyboards.instructors_student_type_keyboard())
        return
    if message.text == '❌ Отмена': StateManager.clear_state(user_id); bot.send_message(chat_id, "Отменено.", reply_markup=keyboards.main_menu()); return
    date_str = message.text.strip()
    try: datetime.strptime(date_str, "%d.%m.%Y"); show_group_slots(bot, chat_id, user_id, date_str)
    except ValueError: bot.send_message(chat_id, "❌ Введите дату в формате ДД.ММ.ГГГГ")

def handle_group_slot_callback(bot, call):
    user_id = call.from_user.id; chat_id = call.message.chat.id
    date_str = call.data.replace('group_slot_', '')
    data = StateManager.get_data(user_id); d = data.to_dict() if hasattr(data, 'to_dict') else {}
    d['lesson_date'] = date_str; d['lesson_time'] = '12:00'; d['hours'] = 2
    total_price = calculate_price(program=d.get('program', 'Новичок'), lesson_type=d.get('lesson_type', 'Индивидуально'), group_size=d.get('group_size', 1), student_type=d.get('student_type', 'Взрослый'), hours=2)
    d['total_price'] = total_price
    d.pop('group_slots_list', None); d.pop('group_slots_rec', None); d.pop('desired_date', None)
    StateManager.set_state(user_id, UserStates.INSTRUCTORS_ENTER_NAME, StateData(**d))
    bot.answer_callback_query(call.id, f"✅ Выбрана дата: {date_str}")
    bot.send_message(chat_id, "👤 *Введите ваше имя и фамилию:*\n\nИмя будет использоваться для обращения и в документах.", parse_mode='Markdown', reply_markup=keyboards.back_button())

def handle_instructors_group_size(bot, message):
    user_id = message.from_user.id; chat_id = message.chat.id
    if message.text == '🔙 Назад':
        if StateManager.go_back(user_id): bot.send_message(chat_id, "👥 *Выберите тип занятия:*", reply_markup=keyboards.instructors_type_keyboard())
        return
    if message.text == '❌ Отмена': StateManager.clear_state(user_id); bot.send_message(chat_id, "Действие отменено.", reply_markup=keyboards.main_menu()); return
    try:
        group_size = int(message.text)
        if group_size < 2 or group_size > 6: bot.send_message(chat_id, "❌ Размер группы должен быть от 2 до 6 человек.", reply_markup=keyboards.instructors_group_size_keyboard()); return
        data = StateManager.get_data(user_id); data_dict = data.to_dict() if hasattr(data, 'to_dict') else {}
        data_dict['group_size'] = group_size; StateManager.set_state(user_id, UserStates.INSTRUCTORS_SELECT_STUDENT, StateData(**data_dict))
        bot.send_message(chat_id, "👤 *Укажите, для кого занятие:*", reply_markup=keyboards.instructors_student_type_keyboard())
    except ValueError: bot.send_message(chat_id, "❌ Пожалуйста, введите число от 2 до 6:", reply_markup=keyboards.instructors_group_size_keyboard())

def handle_instructors_student(bot, message):
    user_id = message.from_user.id; chat_id = message.chat.id
    if message.text == '🔙 Назад':
        data = StateManager.get_data(user_id)
        if hasattr(data, 'group_type') and data.group_type == 'open_group': StateManager.set_state(user_id, UserStates.INSTRUCTORS_SELECT_PEOPLE, data); bot.send_message(chat_id, "Напишите количество человек или выберите «Хочу в группу»:", reply_markup=keyboards.instructors_people_keyboard()); return
        if hasattr(data, 'lesson_type') and data.lesson_type == 'Группа':
            if StateManager.go_back(user_id): bot.send_message(chat_id, "👥 *Сколько человек будет заниматься?*", reply_markup=keyboards.instructors_group_size_keyboard())
        else:
            if StateManager.go_back(user_id): bot.send_message(chat_id, "👥 *Выберите тип занятия:*", reply_markup=keyboards.instructors_type_keyboard())
        return
    if message.text == '❌ Отмена': StateManager.clear_state(user_id); bot.send_message(chat_id, "Действие отменено.", reply_markup=keyboards.main_menu()); return
    student_mapping = {'👨 Взрослый': 'Взрослый', '👶 Ребенок': 'Ребенок'}
    if message.text not in student_mapping: bot.send_message(chat_id, "❌ Пожалуйста, выберите тип ученика:", reply_markup=keyboards.instructors_student_type_keyboard()); return
    student_type = student_mapping[message.text]
    data = StateManager.get_data(user_id); data_dict = data.to_dict() if hasattr(data, 'to_dict') else {}
    data_dict['student_type'] = student_type
    if data_dict.get('group_type') == 'open_group':
        StateManager.set_state(user_id, UserStates.INSTRUCTORS_SELECT_GROUP_SLOT, StateData(**data_dict)); bot.send_message(chat_id, "📅 *Введите желаемую дату занятия (ДД.ММ.ГГГГ):*\n\nЯ покажу ближайшие групповые слоты.", parse_mode='Markdown', reply_markup=keyboards.back_button())
    else:
        StateManager.set_state(user_id, UserStates.INSTRUCTORS_SELECT_HOURS, StateData(**data_dict)); bot.send_message(chat_id, "⏱️ *Выберите продолжительность занятия:*", parse_mode='Markdown', reply_markup=keyboards.instructors_hours_keyboard())

def handle_instructors_hours(bot, message):
    user_id = message.from_user.id; chat_id = message.chat.id
    if message.text == '🔙 Назад':
        if StateManager.go_back(user_id): bot.send_message(chat_id, "👤 *Укажите, для кого занятие:*", reply_markup=keyboards.instructors_student_type_keyboard())
        return
    if message.text == '❌ Отмена': StateManager.clear_state(user_id); bot.send_message(chat_id, "Действие отменено.", reply_markup=keyboards.main_menu()); return
    hours_mapping = {'1 час': 1, '2 часа': 2, '4 часа': 4, '6 часов': 6}
    if message.text not in hours_mapping: bot.send_message(chat_id, "❌ Пожалуйста, выберите продолжительность:", reply_markup=keyboards.instructors_hours_keyboard()); return
    hours = hours_mapping[message.text]
    data = StateManager.get_data(user_id); data_dict = data.to_dict() if hasattr(data, 'to_dict') else {}
    data_dict['hours'] = hours; StateManager.set_state(user_id, UserStates.INSTRUCTORS_ENTER_DATE, StateData(**data_dict))
    bot.send_message(chat_id, "📅 *Введите дату занятия в формате ДД.ММ.ГГГГ*\n\nПример: 25.12.2025\nМожно указать любую дату, включая сегодня", parse_mode='Markdown', reply_markup=keyboards.back_button())

def handle_instructors_date(bot, message):
    user_id = message.from_user.id; chat_id = message.chat.id
    if message.text == '🔙 Назад':
        data = StateManager.get_data(user_id)
        if hasattr(data, 'freeride_days') and data.freeride_days > 0: StateManager.set_state(user_id, UserStates.INSTRUCTORS_FREERIDE_DAYS, data); bot.send_message(chat_id, "📅 *Введите количество дней:*", reply_markup=keyboards.back_button())
        elif hasattr(data, 'program') and data.program == 'Фрирайд': StateManager.set_state(user_id, UserStates.INSTRUCTORS_FREERIDE_DURATION, data); bot.send_message(chat_id, "⏱️ *Выберите формат занятия:*", reply_markup=keyboards.instructors_freeride_duration_keyboard())
        else:
            if StateManager.go_back(user_id): bot.send_message(chat_id, "⏱️ *Выберите продолжительность занятия:*", reply_markup=keyboards.instructors_hours_keyboard())
        return
    if message.text == '❌ Отмена': StateManager.clear_state(user_id); bot.send_message(chat_id, "Действие отменено.", reply_markup=keyboards.main_menu()); return
    date_str = message.text.strip()
    try:
        lesson_date = datetime.strptime(date_str, "%d.%m.%Y")
        data = StateManager.get_data(user_id); data_dict = data.to_dict() if hasattr(data, 'to_dict') else {}
        data_dict['lesson_date'] = date_str; StateManager.set_state(user_id, UserStates.INSTRUCTORS_ENTER_TIME, StateData(**data_dict))
        bot.send_message(chat_id, "🕒 *Введите время занятия в формате ЧЧ:ММ*\n\nПример: 10:00\nДоступное время: с 9:00 до 22:00", parse_mode='Markdown', reply_markup=keyboards.back_button())
    except ValueError: bot.send_message(chat_id, "❌ Неверный формат даты! Пожалуйста, введите дату в формате ДД.ММ.ГГГГ (например: 25.12.2025):", reply_markup=keyboards.back_button())

def handle_instructors_time(bot, message):
    user_id = message.from_user.id; chat_id = message.chat.id
    if message.text == '🔙 Назад':
        if StateManager.go_back(user_id): bot.send_message(chat_id, "📅 *Введите дату занятия в формате ДД.ММ.ГГГГ*", reply_markup=keyboards.back_button())
        return
    if message.text == '❌ Отмена': StateManager.clear_state(user_id); bot.send_message(chat_id, "Действие отменено.", reply_markup=keyboards.main_menu()); return
    time_str = message.text.strip()
    if not re.match(r'^([0-1]?\d|2[0-3]):([0-5]\d)$', time_str): bot.send_message(chat_id, "❌ Неверный формат времени! Пожалуйста, введите время в формате ЧЧ:ММ (например: 10:00):", reply_markup=keyboards.back_button()); return
    hour = int(time_str.split(':')[0])
    if hour < 9 or hour > 22: bot.send_message(chat_id, "❌ Время должно быть с 9:00 до 22:00.", reply_markup=keyboards.back_button()); return
    data = StateManager.get_data(user_id); data_dict = data.to_dict() if hasattr(data, 'to_dict') else {}
    data_dict['lesson_time'] = time_str
    total_price = calculate_price(program=data_dict.get('program', 'Новичок'), lesson_type=data_dict.get('lesson_type', 'Индивидуально'), group_size=data_dict.get('group_size', 1), student_type=data_dict.get('student_type', 'Взрослый'), hours=data_dict.get('hours', 1))
    data_dict['total_price'] = total_price; StateManager.set_state(user_id, UserStates.INSTRUCTORS_ENTER_NAME, StateData(**data_dict))
    bot.send_message(chat_id, "👤 *Введите ваше имя и фамилию:*\n\nИмя будет использоваться для обращения и в документах.", parse_mode='Markdown', reply_markup=keyboards.back_button())

def handle_instructors_name(bot, message):
    user_id = message.from_user.id; chat_id = message.chat.id
    if message.text == '🔙 Назад':
        if StateManager.go_back(user_id): bot.send_message(chat_id, "🕒 *Введите время занятия в формате ЧЧ:ММ*", reply_markup=keyboards.back_button())
        return
    if message.text == '❌ Отмена': StateManager.clear_state(user_id); bot.send_message(chat_id, "Действие отменено.", reply_markup=keyboards.main_menu()); return
    name = message.text.strip()
    if len(name) < 2 or len(name) > 100: bot.send_message(chat_id, "❌ Имя должно быть от 2 до 100 символов.", reply_markup=keyboards.back_button()); return
    data = StateManager.get_data(user_id); data_dict = data.to_dict() if hasattr(data, 'to_dict') else {}
    data_dict['client_name'] = name; StateManager.set_state(user_id, UserStates.INSTRUCTORS_ENTER_PHONE, StateData(**data_dict))
    bot.send_message(chat_id, "📞 *Введите ваш номер телефона:*\n\nМожно вводить в любом формате, главное - чтобы были цифры\nПример: 8-900-123-45-67 или +7 900 123 45 67", parse_mode='Markdown', reply_markup=keyboards.back_button())

def handle_instructors_phone(bot, message):
    user_id = message.from_user.id; chat_id = message.chat.id
    if message.text == '🔙 Назад':
        if StateManager.go_back(user_id): bot.send_message(chat_id, "👤 *Введите ваше имя и фамилию:*", reply_markup=keyboards.back_button())
        return
    if message.text == '❌ Отмена': StateManager.clear_state(user_id); bot.send_message(chat_id, "Действие отменено.", reply_markup=keyboards.main_menu()); return
    digits = re.findall(r'\d', message.text.strip())
    if not digits or len(digits) < 10: bot.send_message(chat_id, "❌ Номер должен содержать не менее 10 цифр.", reply_markup=keyboards.back_button()); return
    phone = ''.join(digits)[-10:]; formatted_phone = f"+7{phone}"
    data = StateManager.get_data(user_id); data_dict = data.to_dict() if hasattr(data, 'to_dict') else {}
    data_dict['client_phone'] = formatted_phone; StateManager.set_state(user_id, UserStates.INSTRUCTORS_ENTER_NOTE, StateData(**data_dict))
    bot.send_message(chat_id, "📝 *Есть ли у вас особые пожелания?*\n\nНапример: нужен прокат, хотим всей семьёй, уточнения по времени.\nЕсли нет – нажмите «✉️ Пропустить».", parse_mode='Markdown', reply_markup=keyboards.instructors_note_keyboard())

def handle_instructors_note(bot, message):
    user_id = message.from_user.id; chat_id = message.chat.id
    if message.text == '🔙 Назад':
        if StateManager.go_back(user_id): bot.send_message(chat_id, "📞 *Введите ваш номер телефона:*", reply_markup=keyboards.back_button())
        return
    if message.text == '❌ Отмена': StateManager.clear_state(user_id); bot.send_message(chat_id, "Действие отменено.", reply_markup=keyboards.main_menu()); return
    note = "" if message.text == '✉️ Пропустить' else message.text.strip()
    data = StateManager.get_data(user_id); data_dict = data.to_dict() if hasattr(data, 'to_dict') else {}
    data_dict['note'] = note; StateManager.set_state(user_id, UserStates.INSTRUCTORS_CONFIRMATION, StateData(**data_dict))
    sport = data_dict.get('sport', 'Не указан'); program = data_dict.get('program', ''); lesson_type = data_dict.get('lesson_type', '')
    group_size = data_dict.get('group_size', 1); student_type = data_dict.get('student_type', ''); hours = data_dict.get('hours', 1)
    freeride_days = data_dict.get('freeride_days', 0); lesson_date = data_dict.get('lesson_date', ''); lesson_time = data_dict.get('lesson_time', '')
    total_price = data_dict.get('total_price', 0); client_name = data_dict.get('client_name', ''); formatted_phone = data_dict.get('client_phone', '')
    group_type = data_dict.get('group_type', 'individual'); children_info = data_dict.get('children_info', '')
    end_time = calc_end_time(lesson_time, hours)
    confirmation_text = f"✅ *Проверьте данные заявки:*\n\n"
    confirmation_text += f"🏂 *Вид спорта:* {sport}\n"; confirmation_text += f"📋 *Программа:* {program}\n"
    if group_type == 'open_group': confirmation_text += f"👥 *Тип:* Сборная группа\n"
    else:
        confirmation_text += f"👥 *Тип занятия:* {lesson_type}"
        if lesson_type == 'Группа': confirmation_text += f" ({group_size} чел.)"
        confirmation_text += "\n"
    if program == 'Фрирайд':
        level_display = 'Начинающий (возле трасс)' if student_type == 'начинающий' else 'Продолжающий (есть опыт)'
        confirmation_text += f"🏔️ *Уровень:* {level_display}\n"
        if freeride_days > 0: confirmation_text += f"⏱️ *Продолжительность:* {freeride_days} дн.\n"
        elif hours > 0: confirmation_text += f"⏱️ *Продолжительность:* {hours} час(ов)\n"
        else: confirmation_text += "⏱️ *Хочу в тур!* (цена обсуждается)\n"
    else:
        if student_type in ['Взрослый', 'Ребенок']: confirmation_text += f"👤 *Ученик:* {student_type}\n"
        if children_info and children_info != 'нет': confirmation_text += f"👶 *Из них дети:* {children_info}\n"
        confirmation_text += f"⏱️ *Продолжительность:* {hours} час(ов)\n"
    confirmation_text += f"📅 *Дата:* {lesson_date}\n"; confirmation_text += f"🕒 *Время:* {lesson_time}"
    if end_time: confirmation_text += f" — {end_time}"
    confirmation_text += "\n\n*Контактные данные:*\n"; confirmation_text += f"👤 Имя: {client_name}\n"; confirmation_text += f"📞 Телефон: {formatted_phone}\n\n"
    if note: confirmation_text += f"📝 *Примечание:* {note}\n\n"
    confirmation_text += f"💰 *Итоговая стоимость: {int(total_price)} руб.*\n\nВсё верно?"
    bot.send_message(chat_id, confirmation_text, parse_mode='Markdown', reply_markup=keyboards.instructors_confirmation_keyboard())

def handle_instructors_confirmation(bot, message):
    user_id = message.from_user.id; chat_id = message.chat.id
    if message.text == '✅ Подтвердить заявку':
        data = StateManager.get_data(user_id)
        with next(get_db()) as db:
            try:
                user = db.query(User).filter_by(user_id=user_id).first()
                if not user: user = User(user_id=user_id, username=message.from_user.username, first_name=message.from_user.first_name, last_name=message.from_user.last_name, phone=data.client_phone); db.add(user); db.commit(); db.refresh(user)
                total_price = getattr(data, 'total_price', 0); commission_percent = 10; commission_amount = total_price * commission_percent / 100
                group_type = getattr(data, 'group_type', 'individual'); group_status = 'waiting_group' if group_type == 'open_group' else None
                booking = InstructorBooking(user_id=user.id, booking_id='temp', program=data.program, lesson_type=data.lesson_type, group_size=getattr(data, 'group_size', 1), student_type=getattr(data, 'student_type', ''), hours=data.hours, lesson_date=data.lesson_date, lesson_time=data.lesson_time, client_name=data.client_name, client_phone=data.client_phone, base_price=total_price, total_price=total_price, commission_percent=commission_percent, commission_amount=commission_amount, status='searching', payment_status='unpaid', offer_expires_at=datetime.now()+timedelta(hours=48), sport=getattr(data, 'sport', ''), group_type=group_type, group_status=group_status, children_info=getattr(data, 'children_info', ''))
                
                # ПРОВЕРКА: если это повторная запись к конкретному инструктору
                if hasattr(data, 'rebook_instructor_id') and data.rebook_instructor_id:
                    booking.instructor_id = data.rebook_instructor_id
                    booking.instructor_name = getattr(data, 'rebook_instructor_name', 'Инструктор')
                    booking.status = 'searching'
                    booking.is_rebook = True
                    booking.offer_expires_at = datetime.now() + timedelta(hours=48)
                
                db.add(booking); db.commit(); db.refresh(booking); booking.booking_id = f"ИНСТР{booking.id}"; db.commit()
                safe_booking_id = booking.booking_id
                note = getattr(data, 'note', ''); sport = getattr(data, 'sport', ''); freeride_days = getattr(data, 'freeride_days', 0)
                end_time = calc_end_time(data.lesson_time, data.hours)
                
                # Если это повторная запись к инструктору
                if hasattr(data, 'rebook_instructor_id') and data.rebook_instructor_id:
                    instructor_user = db.query(User).filter_by(user_id=data.rebook_instructor_id).first()
                    instructor_link = get_user_link(instructor_user) if instructor_user else str(data.rebook_instructor_id)
                    
                    # Отправляем уведомление инструктору в личку с кнопками
                    booking_text = f"""
🎿 *ПОВТОРНАЯ ЗАЯВКА ОТ КЛИЕНТА*

*Номер заявки:* {safe_booking_id}
*Клиент:* {data.client_name}, {data.client_phone}
*Программа:* {data.program}
*Тип занятия:* {data.lesson_type} {f"({data.group_size} чел.)" if data.lesson_type == 'Группа' else ''}
*Ученик:* {data.student_type}
*Продолжительность:* {data.hours} час(ов)
*Дата:* {data.lesson_date}
*Время:* {data.lesson_time} — {end_time}
*Стоимость:* {int(total_price)} руб.

⚠️ Клиент записался к ВАМ повторно.
Подтвердите или измените условия в течение 48 часов.
"""
                    
                    markup = types.InlineKeyboardMarkup(row_width=2)
                    markup.add(
                        types.InlineKeyboardButton('✅ Принять', callback_data=f'instructor_take_{booking.id}'),
                        types.InlineKeyboardButton('✏️ Изменить условия', callback_data=f'instructor_modify_{booking.id}'),
                        types.InlineKeyboardButton('❌ Отклонить', callback_data=f'instructor_reject_{booking.id}')
                    )
                    
                    bot.send_message(data.rebook_instructor_id, booking_text, parse_mode='Markdown', reply_markup=markup)
                    
                    bot.send_message(
                        chat_id,
                        f"✅ *Заявка создана!*\n"
                        f"📋 {safe_booking_id}\n"
                        f"👤 Инструктор: {booking.instructor_name} ({instructor_link})\n"
                        f"📅 {data.lesson_date}\n"
                        f"🕒 {data.lesson_time} — {end_time}\n"
                        f"💰 {int(total_price)} руб.\n\n"
                        f"Ожидайте подтверждения от инструктора.",
                        parse_mode='Markdown',
                        reply_markup=keyboards.main_menu()
                    )
                
                # Обычная групповая заявка (open_group)
                elif group_type == 'open_group':
                    group_members = db.query(InstructorBooking).filter(InstructorBooking.group_status=='waiting_group', InstructorBooking.lesson_date==data.lesson_date, InstructorBooking.lesson_time==data.lesson_time, InstructorBooking.program==data.program, InstructorBooking.sport==getattr(data,'sport',''), InstructorBooking.student_type==getattr(data,'student_type','')).all()
                    lesson_dt = datetime.strptime(data.lesson_date, '%d.%m.%Y')
                    prev_day = (lesson_dt - timedelta(days=1)).strftime('%d.%m.%Y')
                    if len(group_members) >= 5:
                        for m in group_members: m.group_status = 'group_ready'; m.status = 'searching'
                        db.commit()
                        chat_text = format_group_text(group_members)
                        if INSTRUCTORS_CHAT_ID:
                            try:
                                b = group_members[0]
                                markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton('✅ Беру', callback_data=f'instructor_take_{b.id}'))
                                bot.send_message(INSTRUCTORS_CHAT_ID, chat_text, parse_mode='Markdown', reply_markup=markup)
                            except: pass
                        for m in group_members:
                            try:
                                user_m = db.query(User).filter_by(id=m.user_id).first()
                                if user_m: bot.send_message(user_m.user_id, f"✅ *ГРУППА НАБРАЛАСЬ!*\n\n📋 {m.booking_id if m.booking_id else m.id}\n📅 {m.lesson_date}\n🕒 {m.lesson_time}\n\nОжидайте предложений от инструкторов.", parse_mode='Markdown')
                            except: pass
                    else:
                        bot.send_message(chat_id, f"✅ *ЗАЯВКА В СБОРНУЮ ГРУППУ ПРИНЯТА!*\n\n📋 {safe_booking_id}\n📅 {data.lesson_date}\n🕒 {data.lesson_time}\n👥 В группе: {len(group_members)} чел. (макс. 5)\n\n💡 Если группа не наберётся до {prev_day} 19:00 — предложим индивидуальное занятие.\nВы всегда можете создать отдельную индивидуальную заявку.", parse_mode='Markdown', reply_markup=keyboards.main_menu())
                
                # Обычная индивидуальная заявка (НЕ повторная запись, НЕ open_group)
                else:
                    booking_text = format_booking_text(booking, sport, end_time, note, freeride_days)
                    if INSTRUCTORS_CHAT_ID:
                        try:
                            markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton('✅ Беру', callback_data=f'instructor_take_{booking.id}'), types.InlineKeyboardButton('✏️ Изменить', callback_data=f'instructor_modify_{booking.id}'))
                            bot.send_message(INSTRUCTORS_CHAT_ID, booking_text, parse_mode='Markdown', reply_markup=markup)
                        except: pass
                    bot.send_message(chat_id, f"✅ *Заявка подтверждена!*\n{safe_booking_id}\nОжидайте предложений.", reply_markup=keyboards.main_menu())
            except Exception as e: print(f"Ошибка: {e}"); bot.send_message(chat_id, "❌ Произошла ошибка.", reply_markup=keyboards.main_menu())
        StateManager.clear_state(user_id)
    elif message.text == '✏️ Изменить данные': handle_instructors_start(bot, message)
    elif message.text == '🔙 Назад':
        if StateManager.go_back(user_id): bot.send_message(chat_id, "📝 *Пожелания?*", reply_markup=keyboards.instructors_note_keyboard())
    elif message.text == '❌ Отмена': StateManager.clear_state(user_id); bot.send_message(chat_id, "❌ Отменено.", reply_markup=keyboards.main_menu())

# ========== ФУНКЦИИ ДЛЯ ИНСТРУКТОРОВ ==========

def handle_instructor_take(bot, call):
    booking_id = int(call.data.replace('instructor_take_', ''))
    with next(get_db()) as db:
        booking = db.query(InstructorBooking).filter_by(id=booking_id).first()
        if not booking: bot.answer_callback_query(call.id, "❌ Заявка не найдена", show_alert=True); return
        if booking.status not in ['searching','offers_received'] and booking.group_status != 'group_ready': bot.answer_callback_query(call.id, "❌ Заявка уже занята", show_alert=True); return
        existing_offer = db.query(InstructorOffer).filter_by(booking_id=booking.id, instructor_id=call.from_user.id).first()
        if existing_offer: bot.answer_callback_query(call.id, "❌ Вы уже отправили предложение", show_alert=True); return
        instructor_user = db.query(User).filter_by(user_id=call.from_user.id).first()
        if not instructor_user: instructor_user = User(user_id=call.from_user.id, username=call.from_user.username, first_name=call.from_user.first_name, last_name=call.from_user.last_name); db.add(instructor_user); db.commit()
        instructor_name = call.from_user.first_name or "Инструктор"
        
        if booking.group_status == 'group_ready':
            booking.status = 'accepted'; booking.instructor_id = call.from_user.id; booking.instructor_name = instructor_name; booking.accepted_at = datetime.now()
            booking.group_status = 'grouped'; db.commit()
            
            group_members = db.query(InstructorBooking).filter(
                InstructorBooking.lesson_date == booking.lesson_date,
                InstructorBooking.lesson_time == booking.lesson_time,
                InstructorBooking.program == booking.program,
                InstructorBooking.sport == booking.sport,
                InstructorBooking.student_type == booking.student_type,
                InstructorBooking.group_status.in_(['group_ready', 'grouped']),
                InstructorBooking.status == 'searching'
            ).all()
            
            if booking not in group_members:
                group_members.append(booking)
            
            for m in group_members:
                m.group_status = 'grouped'
                m.status = 'accepted'
                m.instructor_id = call.from_user.id
                m.instructor_name = instructor_name
                m.accepted_at = datetime.now()
            db.commit()
            
            total_group_price = sum(m.total_price or 0 for m in group_members)
            members_text = ""
            for i, m in enumerate(group_members, 1):
                members_text += f"{i}. {m.client_name}, {m.client_phone}\n"
            price_per_person = booking.total_price
            end_time = calc_end_time(booking.lesson_time, booking.hours)
            
            for m in group_members:
                try:
                    user_m = db.query(User).filter_by(id=m.user_id).first()
                    if user_m:
                        safe_m_id = m.booking_id if m.booking_id else str(m.id)
                        bot.send_message(user_m.user_id,
                            f"✅ *Поздравляем! Групповое занятие состоится!*\n\n"
                            f"📋 {safe_m_id}\n"
                            f"👤 Инструктор: {instructor_name}\n"
                            f"📅 {booking.lesson_date}\n"
                            f"🕒 {booking.lesson_time} — {end_time}\n"
                            f"💰 {int(price_per_person)} руб.\n\n"
                            f"Если не сможете присутствовать — отмените занятие в разделе «Мои заявки».",
                            parse_mode='Markdown')
                except Exception as e: print(f"Ошибка уведомления участника {m.id}: {e}")
            
            try:
                bot.send_message(call.from_user.id,
                    f"👥 *ВЫ ИНСТРУКТОР ГРУППОВОГО ЗАНЯТИЯ ({len(group_members)} чел)!*\n\n"
                    f"📅 {booking.lesson_date}\n"
                    f"🕒 {booking.lesson_time} — {end_time}\n"
                    f"📋 {booking.program}\n"
                    f"🏂 {booking.sport}\n"
                    f"👶 {booking.student_type}\n\n"
                    f"👤 *{len(group_members)} участников:*\n{members_text}\n"
                    f"💸 Цена за 1 человека: {int(price_per_person)} руб.\n"
                    f"💰 Общая стоимость: {int(total_group_price)} руб.\n"
                    f"💸 Комиссия (10%): {int(total_group_price * 0.1)} руб.",
                    parse_mode='Markdown')
            except: pass
            
            if MANAGER_CHAT_ID:
                try:
                    instructor_link = get_user_link(instructor_user)
                    bot.send_message(MANAGER_CHAT_ID,
                        f"👥 *ГРУППА НАБРАЛАСЬ ({len(group_members)} чел)!*\n\n"
                        f"📅 {booking.lesson_date}\n"
                        f"🕒 {booking.lesson_time} — {end_time}\n"
                        f"📋 {booking.program}\n"
                        f"🏂 {booking.sport}\n"
                        f"👶 {booking.student_type}\n\n"
                        f"👤 *Инструктор:* {instructor_name} ({instructor_link})\n\n"
                        f"👤 *{len(group_members)} участников:*\n{members_text}\n"
                        f"💰 Общая стоимость: {int(total_group_price)} руб.\n"
                        f"💸 Комиссия (10%): {int(total_group_price * 0.1)} руб.",
                        parse_mode='Markdown')
                except Exception as e: print(f"Ошибка уведомления админа: {e}")
            
            if INSTRUCTORS_CHAT_ID:
                try: bot.send_message(INSTRUCTORS_CHAT_ID, f"✅ *Группа принята!*\n{instructor_name} взял группу на {booking.lesson_date} {booking.lesson_time} — {end_time}", parse_mode='Markdown')
                except: pass
            
            bot.answer_callback_query(call.id, "✅ Группа принята!")
            return
        
        offer = InstructorOffer(booking_id=booking.id, instructor_id=call.from_user.id, instructor_name=instructor_name, instructor_username=call.from_user.username or "", price=booking.total_price, status='pending')
        db.add(offer); db.commit()
        send_offer_to_client(bot, offer, booking, call.from_user.id)
        if booking.status == 'searching': booking.status = 'offers_received'
        db.commit()
        
        # Отправляем уведомление в чат инструкторов только если это НЕ повторная запись
        if not booking.is_rebook:
            send_offer_sent_notification(bot, booking, instructor_name, call.from_user.username, "приняты без изменений")
        
        bot.answer_callback_query(call.id, "✅ Предложение отправлено!")

def handle_instructor_modify_start(bot, call):
    booking_id = int(call.data.replace('instructor_modify_', ''))
    with next(get_db()) as db:
        booking = db.query(InstructorBooking).filter_by(id=booking_id).first()
        if not booking:
            bot.answer_callback_query(call.id, "❌ Заявка не найдена", show_alert=True)
            return
        existing_offer = db.query(InstructorOffer).filter_by(
            booking_id=booking.id,
            instructor_id=call.from_user.id
        ).first()
        if existing_offer:
            bot.answer_callback_query(call.id, "❌ Вы уже отправили предложение", show_alert=True)
            return
        
        booking_text = f"""
🎿 *ЗАЯВКА №{booking.id}*
*Программа:* {booking.program}
*Тип занятия:* {booking.lesson_type} {f"({booking.group_size} чел.)" if booking.lesson_type == 'Группа' else ''}
*Ученик:* {booking.student_type}
*Продолжительность:* {booking.hours} час(ов)
*Дата:* {booking.lesson_date}
*Время:* {booking.lesson_time}
*Стоимость:* {int(booking.total_price)} руб.
*Статус:* 🔍 Ищет инструктора
"""
        
        StateManager.set_state(
            call.from_user.id,
            UserStates.INSTRUCTOR_MODIFY_OFFER,
            StateData(
                booking_id=booking_id,
                original_price=booking.total_price,
                original_date=booking.lesson_date,
                original_time=booking.lesson_time,
                modified_price=booking.total_price,
                modified_date=booking.lesson_date,
                modified_time=booking.lesson_time
            )
        )
        
        bot.send_message(call.from_user.id, booking_text, parse_mode='Markdown')
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton('💰 Изменить цену', callback_data=f'modify_price_{booking_id}'),
            types.InlineKeyboardButton('📅 Изменить дату', callback_data=f'modify_date_{booking_id}'),
            types.InlineKeyboardButton('🕒 Изменить время', callback_data=f'modify_time_{booking_id}'),
            types.InlineKeyboardButton('✅ Завершить', callback_data=f'modify_done_{booking_id}'),
            types.InlineKeyboardButton('❌ Отменить', callback_data=f'modify_cancel_{booking_id}')
        )
        bot.send_message(call.from_user.id, "✏️ *Что хотите изменить?*", parse_mode='Markdown', reply_markup=markup)
        bot.answer_callback_query(call.id)

def handle_modify_price(bot, call):
    booking_id = int(call.data.replace('modify_price_', ''))
    StateManager.update_data(call.from_user.id, waiting_for="price", booking_id=booking_id)
    bot.send_message(call.from_user.id, "💰 *Введите новую цену (в рублях):*", parse_mode='Markdown')
    bot.answer_callback_query(call.id)

def handle_modify_date(bot, call):
    booking_id = int(call.data.replace('modify_date_', ''))
    StateManager.update_data(call.from_user.id, waiting_for="date", booking_id=booking_id)
    bot.send_message(call.from_user.id, "📅 *Введите новую дату в формате ДД.ММ.ГГГГ:*", parse_mode='Markdown')
    bot.answer_callback_query(call.id)

def handle_modify_time(bot, call):
    booking_id = int(call.data.replace('modify_time_', ''))
    StateManager.update_data(call.from_user.id, waiting_for="time", booking_id=booking_id)
    bot.send_message(call.from_user.id, "🕒 *Введите новое время в формате ЧЧ:ММ:*", parse_mode='Markdown')
    bot.answer_callback_query(call.id)

def handle_modify_done(bot, call):
    booking_id = int(call.data.replace('modify_done_', ''))
    with next(get_db()) as db:
        booking = db.query(InstructorBooking).filter_by(id=booking_id).first()
        if not booking:
            bot.answer_callback_query(call.id, "❌ Заявка не найдена", show_alert=True)
            return
        data = StateManager.get_data(call.from_user.id)
        if not data:
            bot.answer_callback_query(call.id, "❌ Данные не найдены", show_alert=True)
            return
        
        existing_offer = db.query(InstructorOffer).filter_by(
            booking_id=booking.id,
            instructor_id=call.from_user.id
        ).first()
        if existing_offer:
            bot.answer_callback_query(call.id, "❌ Вы уже отправили предложение", show_alert=True)
            return
        
        offer_price = getattr(data, 'modified_price', booking.total_price)
        offer_date = getattr(data, 'modified_date', None)
        offer_time = getattr(data, 'modified_time', None)
        conditions = []
        if offer_price != booking.total_price:
            conditions.append(f"цена {int(offer_price)} руб.")
        if offer_date:
            conditions.append(f"дата {offer_date}")
        if offer_time:
            conditions.append(f"время {offer_time}")
        
        if conditions:
            offer_message = f"Предлагаю свои условия: {', '.join(conditions)}"
            conditions_text = ", ".join(conditions)
        else:
            offer_message = "Готов провести занятие на указанных условиях"
            conditions_text = "приняты без изменений"
        
        instructor_user = db.query(User).filter_by(user_id=call.from_user.id).first()
        instructor_username = instructor_user.username if instructor_user and instructor_user.username else ""
        
        offer = InstructorOffer(
            booking_id=booking.id,
            instructor_id=call.from_user.id,
            instructor_name=call.from_user.first_name or "Инструктор",
            instructor_username=instructor_username,
            instructor_phone="",
            price=offer_price,
            offer_date=offer_date,
            offer_time=offer_time,
            message=offer_message,
            status='pending'
        )
        db.add(offer)
        db.commit()
        
        send_offer_to_client(bot, offer, booking, call.from_user.id)
        
        if booking.status == 'searching':
            booking.status = 'offers_received'
            db.commit()
        
        # Отправляем уведомление в чат инструкторов только если это НЕ повторная запись
        if not booking.is_rebook:
            send_offer_sent_notification(bot, booking, call.from_user.first_name or "Инструктор", instructor_username, conditions_text)
        
        StateManager.clear_state(call.from_user.id)
        
        bot.send_message(
            call.from_user.id,
            f"✅ *Предложение отправлено клиенту!*\n\n"
            f"Изменения: {conditions_text}",
            parse_mode='Markdown'
        )
        bot.answer_callback_query(call.id, "✅ Предложение отправлено")

def handle_modify_cancel(bot, call):
    StateManager.clear_state(call.from_user.id)
    bot.send_message(call.from_user.id, "❌ Изменение условий отменено.", parse_mode='Markdown')
    bot.answer_callback_query(call.id, "❌ Отменено")

def handle_accept_offer(bot, call):
    offer_id = int(call.data.replace('accept_offer_', ''))
    with next(get_db()) as db:
        offer = db.query(InstructorOffer).filter_by(id=offer_id).first()
        if not offer: return
        booking = offer.booking
        if booking.status == 'accepted': return
        
        offer.status = 'accepted'
        booking.status = 'accepted'
        booking.instructor_id = offer.instructor_id
        booking.instructor_name = offer.instructor_name
        booking.accepted_at = datetime.now()
        
        if offer.price != booking.total_price:
            booking.total_price = offer.price
        if offer.offer_date:
            booking.lesson_date = offer.offer_date
        if offer.offer_time:
            booking.lesson_time = offer.offer_time
        
        db.commit()
        
        instructor_user = db.query(User).filter_by(user_id=offer.instructor_id).first()
        instructor_link = get_user_link(instructor_user)
        safe_booking_id = booking.booking_id if booking.booking_id else str(booking.id)
        end_time = calc_end_time(booking.lesson_time, booking.hours)
        
        bot.send_message(
            call.from_user.id,
            f"✅ *Поздравляем с выбором инструктора!*\n\n"
            f"📋 Номер заявки: {safe_booking_id}\n"
            f"🎿 Инструктор: {offer.instructor_name} ({instructor_link})\n"
            f"📅 Дата: {offer.offer_date if offer.offer_date else booking.lesson_date}\n"
            f"🕒 Время: {offer.offer_time if offer.offer_time else booking.lesson_time} — {end_time}\n"
            f"💰 Стоимость: {int(offer.price)} руб.\n"
            f"🎿 Программа: {booking.program}\n"
            f"👥 Тип занятия: {booking.lesson_type} {f'({booking.group_size} чел.)' if booking.lesson_type == 'Группа' else ''}\n"
            f"👤 Ученик: {booking.student_type}\n"
            f"⏱️ Продолжительность: {booking.hours} час(ов)\n\n"
            f"*Инструктор свяжется с вами для уточнения деталей.*",
            parse_mode='Markdown'
        )
        
        client_user = db.query(User).filter_by(id=booking.user_id).first()
        client_link = get_user_link(client_user) if client_user else booking.client_name
        
        bot.send_message(
            offer.instructor_id,
            f"✅ *Клиент выбрал вас!*\n\n"
            f"📋 Номер заявки: {safe_booking_id}\n"
            f"👤 Клиент: {client_link}, {booking.client_phone}\n"
            f"📅 Дата: {offer.offer_date if offer.offer_date else booking.lesson_date}\n"
            f"🕒 Время: {offer.offer_time if offer.offer_time else booking.lesson_time} — {end_time}\n"
            f"💰 Стоимость: {int(offer.price)} руб.\n\n"
            f"Свяжитесь с клиентом.",
            parse_mode='Markdown'
        )
        
        # Отправляем уведомление в чат инструкторов только если это НЕ повторная запись
        if not booking.is_rebook and INSTRUCTORS_CHAT_ID:
            try:
                instructor_username_display = f" (@{offer.instructor_username})" if offer.instructor_username else ""
                chat_text = f"""
✅ *КЛИЕНТ ВЫБРАЛ ИНСТРУКТОРА!*

📋 Номер заявки: {safe_booking_id}
🎿 Инструктор: {offer.instructor_name}{instructor_username_display}

*Детали занятия:*
👤 Контакт клиента: {client_link}, {booking.client_phone}
🎿 Программа: {booking.program}
👥 Тип занятия: {booking.lesson_type} {f"({booking.group_size} чел.)" if booking.lesson_type == 'Группа' else ''}
🎯 Ученик: {booking.student_type}
⏱️ Продолжительность: {booking.hours} час(ов)
📅 Дата: {offer.offer_date if offer.offer_date else booking.lesson_date}
🕒 Время: {offer.offer_time if offer.offer_time else booking.lesson_time} — {end_time}
💰 Стоимость: {int(offer.price)} руб.

Свяжитесь с клиентом для уточнения деталей.
"""
                bot.send_message(INSTRUCTORS_CHAT_ID, chat_text, parse_mode='Markdown')
            except: pass
        
        if MANAGER_CHAT_ID:
            try:
                manager_text = f"""
🎿 *НОВОЕ БРОНИРОВАНИЕ ИНСТРУКТОРА*

*Номер заявки:* {safe_booking_id}
*Инструктор:* {offer.instructor_name} (@{offer.instructor_username if offer.instructor_username else 'без username'})
*Клиент:* {client_link} ({booking.client_phone})

*Детали заявки:*
• Программа: {booking.program}
• Тип: {booking.lesson_type} {f"({booking.group_size} чел.)" if booking.lesson_type == 'Группа' else ''}
• Ученик: {booking.student_type}
• Часы: {booking.hours}
• Дата: {offer.offer_date if offer.offer_date else booking.lesson_date}
• Время: {offer.offer_time if offer.offer_time else booking.lesson_time} — {end_time}
• Стоимость: {int(offer.price)} руб.

*Статус:* Ожидает оплаты от клиента
"""
                bot.send_message(MANAGER_CHAT_ID, manager_text, parse_mode='Markdown')
            except: pass
        
        other_offers = db.query(InstructorOffer).filter_by(booking_id=booking.id, status='pending').all()
        for other_offer in other_offers:
            if other_offer.id != offer.id:
                other_offer.status = 'rejected'
        db.commit()
        
        bot.answer_callback_query(call.id, "✅ Вы приняли предложение!")

def handle_reject_offer(bot, call):
    offer_id = int(call.data.replace('reject_offer_', ''))
    with next(get_db()) as db:
        offer = db.query(InstructorOffer).filter_by(id=offer_id).first()
        if not offer:
            bot.answer_callback_query(call.id, "❌ Предложение не найдено", show_alert=True)
            return
        booking = offer.booking
        if booking.status == 'accepted':
            bot.answer_callback_query(call.id, "❌ Заявка уже принята", show_alert=True)
            return
        
        offer.status = 'rejected'
        db.commit()
        
        safe_booking_id = booking.booking_id if booking.booking_id else str(booking.id)
        
        bot.send_message(
            call.from_user.id,
            f"❌ *Вы отклонили предложение от инструктора {offer.instructor_name}*\n\n"
            f"Мы сообщим инструктору об этом.\n"
            f"Вы можете дождаться других предложений.\n\n"
            f"Номер заявки: {safe_booking_id}",
            parse_mode='Markdown'
        )
        
        if INSTRUCTORS_CHAT_ID:
            try:
                chat_text = f"""
🎿 *ОЖИДАЕТ ИНСТРУКТОРА:*

*Номер заявки:* {safe_booking_id}
🕒 *Статус:* Клиент отклонил заявку инструктора {offer.instructor_name}
И ожидает предложений от других инструкторов.
"""
                bot.send_message(INSTRUCTORS_CHAT_ID, chat_text, parse_mode='Markdown')
            except: pass
        
        bot.answer_callback_query(call.id, "❌ Предложение отклонено")

def handle_wait_offer(bot, call):
    offer_id = int(call.data.replace('wait_offer_', ''))
    with next(get_db()) as db:
        offer = db.query(InstructorOffer).filter_by(id=offer_id).first()
        if not offer:
            bot.answer_callback_query(call.id, "❌ Предложение не найдено", show_alert=True)
            return
        booking = offer.booking
        safe_booking_id = booking.booking_id if booking.booking_id else str(booking.id)
        
        bot.send_message(
            call.from_user.id,
            f"⏳ *Вы можете вернуться к этой заявке позже, но не позднее {(datetime.now() + timedelta(hours=48)).strftime('%d.%m.%Y %H:%M')}*\n\n"
            "Мы уведомим вас, когда появятся новые предложения от инструкторов.\n\n"
            f"Номер заявки: {safe_booking_id}",
            parse_mode='Markdown'
        )
        
        if INSTRUCTORS_CHAT_ID:
            try:
                chat_text = f"""
🎿 *ОЖИДАЕТ ИНСТРУКТОРА:*

*Номер заявки:* {safe_booking_id}
🕒 *Статус:* Клиент ожидает еще предложений от других инструкторов.
"""
                bot.send_message(INSTRUCTORS_CHAT_ID, chat_text, parse_mode='Markdown')
            except: pass
        
        bot.answer_callback_query(call.id, "⏳ Ждем другие предложения")

def handle_instructor_reject(bot, call):
    """Инструктор отклоняет повторную заявку"""
    booking_id = int(call.data.replace('instructor_reject_', ''))
    
    with next(get_db()) as db:
        booking = db.query(InstructorBooking).filter_by(id=booking_id).first()
        if not booking:
            bot.answer_callback_query(call.id, "❌ Заявка не найдена", show_alert=True)
            return
        
        booking.status = 'cancelled'
        db.commit()
        
        user = db.query(User).filter_by(id=booking.user_id).first()
        if user and user.user_id:
            bot.send_message(
                user.user_id,
                f"❌ *Инструктор {booking.instructor_name} отклонил вашу заявку*\n\n"
                f"📋 Номер заявки: {booking.booking_id}\n"
                f"Вы можете создать новую заявку на другого инструктора.",
                parse_mode='Markdown'
            )
        
        if MANAGER_CHAT_ID:
            bot.send_message(
                MANAGER_CHAT_ID,
                f"❌ *ИНСТРУКТОР ОТКЛОНИЛ ПОВТОРНУЮ ЗАЯВКУ*\n\n"
                f"Инструктор: {booking.instructor_name}\n"
                f"Клиент: {booking.client_name}, {booking.client_phone}\n"
                f"Номер заявки: {booking.booking_id}",
                parse_mode='Markdown'
            )
        
        bot.answer_callback_query(call.id, "✅ Заявка отклонена")
        bot.send_message(call.from_user.id, "❌ Вы отклонили заявку клиента.")

# ========== ЗАВЕРШЕНИЕ И ОПЛАТА ==========

def send_lesson_completion_question(bot, user_id, booking):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton('⏱️ Продлить на час', callback_data=f'extend_lesson_{booking.id}'),
        types.InlineKeyboardButton('✅ Завершить', callback_data=f'end_lesson_{booking.id}')
    )
    
    bot.send_message(
        user_id,
        f"⏰ *Ваше занятие подходит к концу*\n\n"
        f"Вы хотите продлить занятие еще на один час?",
        parse_mode='Markdown',
        reply_markup=markup
    )

def handle_extend_lesson(bot, call):
    booking_id = int(call.data.replace('extend_lesson_', ''))
    
    with next(get_db()) as db:
        booking = db.query(InstructorBooking).filter_by(id=booking_id).first()
        if not booking:
            try:
                bot.answer_callback_query(call.id, "❌ Занятие не найдено", show_alert=True)
            except:
                pass
            return
        
        booking.hours += 1
        booking.total_price = booking.base_price * booking.hours
        booking.reminder_end_sent = False
        db.commit()
        
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"✅ *Занятие продлено на 1 час!*\n\n"
                     f"Новая длительность: {booking.hours} час(ов)\n"
                     f"Общая стоимость: {int(booking.total_price)} руб.",
                parse_mode='Markdown'
            )
        except:
            bot.send_message(
                call.message.chat.id,
                f"✅ *Занятие продлено на 1 час!*\n\n"
                f"Новая длительность: {booking.hours} час(ов)\n"
                f"Общая стоимость: {int(booking.total_price)} руб.",
                parse_mode='Markdown'
            )
        
        try:
            bot.answer_callback_query(call.id, "✅ Занятие продлено")
        except:
            pass

def handle_end_lesson(bot, call):
    booking_id = int(call.data.replace('end_lesson_', ''))
    
    with next(get_db()) as db:
        booking = db.query(InstructorBooking).filter_by(id=booking_id).first()
        if not booking:
            try:
                bot.answer_callback_query(call.id, "❌ Занятие не найдено", show_alert=True)
            except:
                pass
            return
        
        instructor_user = db.query(User).filter_by(user_id=booking.instructor_id).first()
        instructor_link = get_user_link(instructor_user) if instructor_user else booking.instructor_name
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton('✅ Я оплатил', callback_data=f'client_paid_{booking.id}')
        )
        
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"💰 *Оплатите занятие*\n\n"
                     f"Сумма к оплате: {int(booking.total_price)} руб.\n"
                     f"Инструктор: {instructor_link}\n\n"
                     f"Способ оплаты уточните у инструктора.\n"
                     f"После оплаты нажмите \"Я оплатил\".",
                parse_mode='Markdown',
                reply_markup=markup
            )
        except:
            bot.send_message(
                call.message.chat.id,
                f"💰 *Оплатите занятие*\n\n"
                f"Сумма к оплате: {int(booking.total_price)} руб.\n"
                f"Инструктор: {instructor_link}\n\n"
                f"Способ оплаты уточните у инструктора.\n"
                f"После оплаты нажмите \"Я оплатил\".",
                parse_mode='Markdown',
                reply_markup=markup
            )
        
        try:
            bot.answer_callback_query(call.id, "✅ Занятие завершено")
        except:
            pass

def handle_client_paid(bot, call):
    booking_id = int(call.data.replace('client_paid_', ''))
    
    with next(get_db()) as db:
        booking = db.query(InstructorBooking).filter_by(id=booking_id).first()
        if not booking:
            try:
                bot.answer_callback_query(call.id, "❌ Занятие не найдено", show_alert=True)
            except:
                pass
            return
        
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"✅ *Спасибо!*\n\n"
                     f"Поставьте инструктору {booking.instructor_name} оценку и напишите отзыв "
                     f"(можно пропустить).\n\n"
                     f"А ещё рекомендуем выбрать экскурсию или купить товары Арктики в нашем магазине!",
                parse_mode='Markdown',
                reply_markup=keyboards.main_menu()
            )
        except:
            bot.send_message(
                call.message.chat.id,
                f"✅ *Спасибо!*\n\n"
                f"Поставьте инструктору {booking.instructor_name} оценку и напишите отзыв "
                f"(можно пропустить).\n\n"
                f"А ещё рекомендуем выбрать экскурсию или купить товары Арктики в нашем магазине!",
                parse_mode='Markdown',
                reply_markup=keyboards.main_menu()
            )
        
        instructor_link = get_user_link_by_id(db, booking.instructor_id) if booking.instructor_id else booking.instructor_name
        end_time = calc_end_time(booking.lesson_time, booking.hours)
        
        # Отправляем сообщение инструктору и ссылку на оплату комиссии
        bot.send_message(
            booking.instructor_id,
            f"💰 *Клиент оплатил занятие!*\n\n"
            f"👤 Клиент: {booking.client_name}\n"
            f"📞 Телефон: {booking.client_phone}\n"
            f"📅 Дата: {booking.lesson_date}\n"
            f"🕒 Время: {booking.lesson_time} — {end_time}\n"
            f"Сумма: {int(booking.total_price)} руб.\n"
            f"Комиссия (10%): {int(booking.commission_amount)} руб.\n\n"
            f"Оплатите комиссию:",
            parse_mode='Markdown'
        )
        
        # Отправляем ссылку на оплату комиссии через YooKassa
        send_commission_payment_link(
            bot=bot,
            chat_id=booking.instructor_id,
            amount=booking.commission_amount,
            booking_id=booking.booking_id,
            booking_type='instructor',
            user_id=booking.instructor_id
        )
        
        booking.status = 'completed'
        booking.payment_status = 'pending_commission'
        db.commit()
        
        try:
            bot.answer_callback_query(call.id, "✅ Спасибо!")
        except:
            pass

def handle_instructor_paid_commission(bot, call):
    booking_id = int(call.data.replace('instructor_paid_commission_', ''))
    
    with next(get_db()) as db:
        booking = db.query(InstructorBooking).filter_by(id=booking_id).first()
        if not booking:
            try:
                bot.answer_callback_query(call.id, "❌ Занятие не найдено", show_alert=True)
            except:
                pass
            return
        
        # Используем новую функцию send_commission_payment_link
        # Сначала проверяем статус платежа через YooKassa
        commission_amount = booking.commission_amount
        
        # Отправляем ссылку на оплату комиссии через YooKassa
        send_commission_payment_link(
            bot=bot,
            chat_id=booking.instructor_id,
            amount=commission_amount,
            booking_id=booking.booking_id,
            booking_type='instructor',
            user_id=booking.instructor_id
        )
        
        # Остальное обрабатывается в handle_commission_paid в payment.py
        try:
            bot.answer_callback_query(call.id, "✅ Ссылка на оплату комиссии отправлена")
        except:
            pass

def send_offer_to_client(bot, offer, booking, instructor_user_id):
    try:
        with next(get_db()) as db:
            instructor_user = db.query(User).filter_by(user_id=offer.instructor_id).first()
            instructor_link = get_user_link(instructor_user)
            safe_booking_id = booking.booking_id if booking.booking_id else str(booking.id)
            
            offer_text = f"""
🎿 *ПРЕДЛОЖЕНИЕ ОТ ИНСТРУКТОРА*

*Инструктор:* {offer.instructor_name} ({instructor_link})
{'@' + offer.instructor_username if offer.instructor_username else ''}

*Предлагаемые условия:*
"""
            if offer.offer_date and offer.offer_date != booking.lesson_date:
                offer_text += f"📅 *Дата:* {offer.offer_date} *(вместо {booking.lesson_date})*\n"
            else:
                offer_text += f"📅 *Дата:* {booking.lesson_date}\n"
            
            if offer.offer_time and offer.offer_time != booking.lesson_time:
                offer_text += f"🕒 *Время:* {offer.offer_time} *(вместо {booking.lesson_time})*\n"
            else:
                offer_text += f"🕒 *Время:* {booking.lesson_time}\n"
            
            if offer.price != booking.total_price:
                offer_text += f"💰 *Стоимость:* {int(offer.price)} руб. *(вместо {int(booking.total_price)} руб.)*\n"
            else:
                offer_text += f"💰 *Стоимость:* {int(offer.price)} руб.\n"
            
            if offer.message and offer.message != "без изменений":
                offer_text += f"\n💬 *Сообщение инструктора:*\n{offer.message}\n"
            
            offer_text += f"\n*Номер заявки:* {safe_booking_id}"
            
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton('✅ Принять', callback_data=f'accept_offer_{offer.id}'),
                types.InlineKeyboardButton('❌ Отклонить', callback_data=f'reject_offer_{offer.id}'),
                types.InlineKeyboardButton('⏳ Подождать другие', callback_data=f'wait_offer_{offer.id}')
            )
            
            user = db.query(User).filter_by(id=booking.user_id).first()
            if user:
                bot.send_message(user.user_id, offer_text, parse_mode='Markdown', reply_markup=markup)
                print(f"✅ Предложение отправлено клиенту {user.user_id}")
    except Exception as e:
        print(f"❌ Ошибка в send_offer_to_client: {e}")

def send_offer_sent_notification(bot, booking, instructor_name, instructor_username, conditions_text):
    # Отправляем только если это НЕ повторная запись
    if booking.is_rebook:
        return
    
    if INSTRUCTORS_CHAT_ID:
        try:
            safe_booking_id = booking.booking_id if booking.booking_id else str(booking.id)
            username_display = f" (@{instructor_username})" if instructor_username else ""
            end_time = calc_end_time(booking.lesson_time, booking.hours)
            
            notification_text = f"""
🎿 *ПРЕДЛОЖЕНИЕ ОТПРАВЛЕНО*

*Номер заявки:* {safe_booking_id}
*Инструктор:* {instructor_name}{username_display}
*Условия:* {conditions_text}
📅 Дата: {booking.lesson_date}
🕒 Время: {booking.lesson_time} — {end_time}

✅ Предложение отправлено клиенту.

⏳ Ожидаем решения клиента (до {(datetime.now() + timedelta(hours=48)).strftime('%d.%m.%Y %H:%M')})
"""
            bot.send_message(INSTRUCTORS_CHAT_ID, notification_text, parse_mode='Markdown')
        except Exception as e:
            print(f"❌ Ошибка отправки уведомления в чат инструкторов: {e}")

def handle_instructor_modify_input(bot, message):
    """Обработка ввода от инструктора при изменении условий"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    data = StateManager.get_data(user_id)
    
    if not hasattr(data, 'waiting_for'):
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
                booking = db.query(InstructorBooking).filter_by(id=booking_id).first()
                current_price = new_price
                current_date = getattr(data, 'modified_date', booking.lesson_date)
                current_time = getattr(data, 'modified_time', booking.lesson_time)
                old_price = booking.total_price
                end_time = calc_end_time(current_time, booking.hours)
                
                booking_text = f"""
🎿 *ОБНОВЛЕННАЯ ЗАЯВКА*

*Номер заявки:* {booking.id}
*Программа:* {booking.program}
*Тип занятия:* {booking.lesson_type} {f"({booking.group_size} чел.)" if booking.lesson_type == 'Группа' else ''}
*Ученик:* {booking.student_type}
*Продолжительность:* {booking.hours} час(ов)
*Дата:* {current_date}
*Время:* {current_time} — {end_time}
*Стоимость:* {int(current_price)} руб. *(изменено, было {int(old_price)} руб.)*
*Статус:* 🔍 Ищет инструктора
"""
                bot.send_message(chat_id, booking_text, parse_mode='Markdown')
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton('💰 Изменить цену', callback_data=f'modify_price_{booking_id}'),
                types.InlineKeyboardButton('📅 Изменить дату', callback_data=f'modify_date_{booking_id}'),
                types.InlineKeyboardButton('🕒 Изменить время', callback_data=f'modify_time_{booking_id}'),
                types.InlineKeyboardButton('✅ Завершить', callback_data=f'modify_done_{booking_id}'),
                types.InlineKeyboardButton('❌ Отменить', callback_data=f'modify_cancel_{booking_id}')
            )
            bot.send_message(chat_id, "✏️ *Что хотите изменить ещё?*", parse_mode='Markdown', reply_markup=markup)
            
        except ValueError:
            bot.send_message(chat_id, "❌ Неверный формат цены. Введите число (например: 2500):")
    
    elif data.waiting_for == 'date':
        date_str = message.text.strip()
        try:
            datetime.strptime(date_str, "%d.%m.%Y")
            StateManager.update_data(user_id, modified_date=date_str, waiting_for=None)
            
            booking_id = data.booking_id
            with next(get_db()) as db:
                booking = db.query(InstructorBooking).filter_by(id=booking_id).first()
                current_price = getattr(data, 'modified_price', booking.total_price)
                current_date = date_str
                current_time = getattr(data, 'modified_time', booking.lesson_time)
                old_date = booking.lesson_date
                end_time = calc_end_time(current_time, booking.hours)
                
                booking_text = f"""
🎿 *ОБНОВЛЕННАЯ ЗАЯВКА*

*Номер заявки:* {booking.id}
*Программа:* {booking.program}
*Тип занятия:* {booking.lesson_type} {f"({booking.group_size} чел.)" if booking.lesson_type == 'Группа' else ''}
*Ученик:* {booking.student_type}
*Продолжительность:* {booking.hours} час(ов)
*Дата:* {current_date} *(изменено, было {old_date})*
*Время:* {current_time} — {end_time}
*Стоимость:* {int(current_price)} руб.
*Статус:* 🔍 Ищет инструктора
"""
                bot.send_message(chat_id, booking_text, parse_mode='Markdown')
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton('💰 Изменить цену', callback_data=f'modify_price_{booking_id}'),
                types.InlineKeyboardButton('📅 Изменить дату', callback_data=f'modify_date_{booking_id}'),
                types.InlineKeyboardButton('🕒 Изменить время', callback_data=f'modify_time_{booking_id}'),
                types.InlineKeyboardButton('✅ Завершить', callback_data=f'modify_done_{booking_id}'),
                types.InlineKeyboardButton('❌ Отменить', callback_data=f'modify_cancel_{booking_id}')
            )
            bot.send_message(chat_id, "✏️ *Что хотите изменить ещё?*", parse_mode='Markdown', reply_markup=markup)
            
        except ValueError:
            bot.send_message(chat_id, "❌ Неверный формат даты. Введите дату в формате ДД.ММ.ГГГГ (например: 25.12.2025):")
    
    elif data.waiting_for == 'time':
        time_str = message.text.strip()
        time_pattern = r'^([0-1]?[0-9]|2[0-3]):([0-5][0-9])$'
        
        if re.match(time_pattern, time_str):
            hour = int(time_str.split(':')[0])
            if hour < 9 or hour > 22:
                bot.send_message(chat_id, "❌ Время должно быть с 9:00 до 22:00.")
                return
            
            StateManager.update_data(user_id, modified_time=time_str, waiting_for=None)
            
            booking_id = data.booking_id
            with next(get_db()) as db:
                booking = db.query(InstructorBooking).filter_by(id=booking_id).first()
                current_price = getattr(data, 'modified_price', booking.total_price)
                current_date = getattr(data, 'modified_date', booking.lesson_date)
                current_time = time_str
                old_time = booking.lesson_time
                end_time = calc_end_time(current_time, booking.hours)
                
                booking_text = f"""
🎿 *ОБНОВЛЕННАЯ ЗАЯВКА*

*Номер заявки:* {booking.id}
*Программа:* {booking.program}
*Тип занятия:* {booking.lesson_type} {f"({booking.group_size} чел.)" if booking.lesson_type == 'Группа' else ''}
*Ученик:* {booking.student_type}
*Продолжительность:* {booking.hours} час(ов)
*Дата:* {current_date}
*Время:* {current_time} — {end_time} *(изменено, было {old_time})*
*Стоимость:* {int(current_price)} руб.
*Статус:* 🔍 Ищет инструктора
"""
                bot.send_message(chat_id, booking_text, parse_mode='Markdown')
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton('💰 Изменить цену', callback_data=f'modify_price_{booking_id}'),
                types.InlineKeyboardButton('📅 Изменить дату', callback_data=f'modify_date_{booking_id}'),
                types.InlineKeyboardButton('🕒 Изменить время', callback_data=f'modify_time_{booking_id}'),
                types.InlineKeyboardButton('✅ Завершить', callback_data=f'modify_done_{booking_id}'),
                types.InlineKeyboardButton('❌ Отменить', callback_data=f'modify_cancel_{booking_id}')
            )
            bot.send_message(chat_id, "✏️ *Что хотите изменить ещё?*", parse_mode='Markdown', reply_markup=markup)
            
        else:
            bot.send_message(chat_id, "❌ Неверный формат времени. Введите время в формате ЧЧ:ММ (например: 14:30):")

def calculate_price(program, lesson_type, group_size, student_type, hours):
    with next(get_db()) as db:
        settings = {s.key: s.value for s in db.query(Setting).all()}
        base_price = float(settings.get('instructor_base_price', 2000))
        if program == 'Фрирайд': base_price = float(settings.get('instructor_freeride_price', 2500))
        elif program == 'Карвинг': base_price = float(settings.get('instructor_carving_price', 2500))
        if student_type == 'Ребенок': base_price = float(settings.get('instructor_child_price', 1500))
        if lesson_type == 'Группа' and group_size > 1: base_price *= (1 - float(settings.get('instructor_group_discount', 10))/100)
        return base_price * hours * group_size