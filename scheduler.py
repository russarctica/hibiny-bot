import schedule
import time
import threading
from datetime import datetime, timedelta

# Глобальная переменная для бота
_bot = None

def set_bot(bot):
    """Устанавливает экземпляр бота"""
    global _bot
    _bot = bot

def check_instructor_reminders():
    """Проверка и отправка напоминаний инструкторам и клиентам"""
    global _bot
    if not _bot:
        return
        
    try:
        from database import get_db, InstructorBooking, User
        
        with next(get_db()) as db:
            now = datetime.now()
            
            bookings_24h = db.query(InstructorBooking).filter(
                InstructorBooking.status == 'accepted',
                InstructorBooking.reminder_24h_sent == False
            ).all()
            
            for booking in bookings_24h:
                try:
                    lesson_datetime = datetime.strptime(
                        f"{booking.lesson_date} {booking.lesson_time}",
                        "%d.%m.%Y %H:%M"
                    )
                    
                    time_diff = lesson_datetime - now
                    if timedelta(hours=23, minutes=55) <= time_diff <= timedelta(hours=24, minutes=5):
                        if booking.instructor_id:
                            try:
                                _bot.send_message(
                                    booking.instructor_id,
                                    f"⏰ *Напоминание за 24 часа*\n\n"
                                    f"🎿 У вас занятие с клиентом {booking.client_name}\n"
                                    f"📅 Дата: {booking.lesson_date}\n"
                                    f"🕒 Время: {booking.lesson_time}\n"
                                    f"⏱️ Длительность: {booking.hours} час(ов)\n\n"
                                    f"Не забудьте подготовиться!",
                                    parse_mode='Markdown'
                                )
                            except:
                                pass
                        
                        user = db.query(User).filter_by(id=booking.user_id).first()
                        if user and user.user_id:
                            try:
                                _bot.send_message(
                                    user.user_id,
                                    f"⏰ *Напоминание за 24 часа*\n\n"
                                    f"🎿 Завтра у вас занятие с инструктором {booking.instructor_name}\n"
                                    f"📅 Дата: {booking.lesson_date}\n"
                                    f"🕒 Время: {booking.lesson_time}\n"
                                    f"⏱️ Длительность: {booking.hours} час(ов)\n\n"
                                    f"Не опаздывайте!",
                                    parse_mode='Markdown'
                                )
                            except:
                                pass
                        
                        booking.reminder_24h_sent = True
                        db.commit()
                        
                except:
                    continue
            
            bookings_2h = db.query(InstructorBooking).filter(
                InstructorBooking.status == 'accepted',
                InstructorBooking.reminder_2h_sent == False
            ).all()
            
            for booking in bookings_2h:
                try:
                    lesson_datetime = datetime.strptime(
                        f"{booking.lesson_date} {booking.lesson_time}",
                        "%d.%m.%Y %H:%M"
                    )
                    
                    time_diff = lesson_datetime - now
                    if timedelta(hours=1, minutes=55) <= time_diff <= timedelta(hours=2, minutes=5):
                        if booking.instructor_id:
                            try:
                                _bot.send_message(
                                    booking.instructor_id,
                                    f"⏰ *Напоминание за 2 часа*\n\n"
                                    f"🎿 Через 2 часа у вас занятие с клиентом {booking.client_name}\n"
                                    f"📅 Дата: {booking.lesson_date}\n"
                                    f"🕒 Время: {booking.lesson_time}\n"
                                    f"⏱️ Длительность: {booking.hours} час(ов)\n\n"
                                    f"Выходите заранее!",
                                    parse_mode='Markdown'
                                )
                            except:
                                pass
                        
                        user = db.query(User).filter_by(id=booking.user_id).first()
                        if user and user.user_id:
                            try:
                                _bot.send_message(
                                    user.user_id,
                                    f"⏰ *Напоминание за 2 часа*\n\n"
                                    f"🎿 Через 2 часа у вас занятие с инструктором {booking.instructor_name}\n"
                                    f"📅 Дата: {booking.lesson_date}\n"
                                    f"🕒 Время: {booking.lesson_time}\n"
                                    f"⏱️ Длительность: {booking.hours} час(ов)\n\n"
                                    f"Не опаздывайте!",
                                    parse_mode='Markdown'
                                )
                            except:
                                pass
                        
                        booking.reminder_2h_sent = True
                        db.commit()
                        
                except:
                    continue
                    
    except:
        pass

def check_lesson_completion():
    """Проверяет занятия, до окончания которых осталось 10-15 минут, и отправляет вопрос о продлении"""
    global _bot
    if not _bot:
        return
    
    try:
        from database import get_db, InstructorBooking, User
        from handlers.instructors import send_lesson_completion_question
        
        with next(get_db()) as db:
            now = datetime.now()
            
            # Ищем подтверждённые занятия, по которым ещё не отправлен вопрос
            bookings = db.query(InstructorBooking).filter(
                InstructorBooking.status == 'accepted',
                InstructorBooking.reminder_end_sent == False
            ).all()
            
            for booking in bookings:
                try:
                    # Дата и время начала
                    lesson_datetime = datetime.strptime(
                        f"{booking.lesson_date} {booking.lesson_time}",
                        "%d.%m.%Y %H:%M"
                    )
                    
                    # Время окончания = начало + количество часов
                    end_datetime = lesson_datetime + timedelta(hours=booking.hours)
                    
                    # Время до окончания
                    time_to_end = end_datetime - now
                    
                    # Если до окончания осталось 10-15 минут
                    if timedelta(minutes=10) <= time_to_end <= timedelta(minutes=15):
                        user = db.query(User).filter_by(id=booking.user_id).first()
                        if user and user.user_id:
                            send_lesson_completion_question(_bot, user.user_id, booking)
                            booking.reminder_end_sent = True
                            db.commit()
                            print(f"✅ Вопрос о продлении отправлен клиенту {user.user_id} для занятия {booking.id} (до окончания {time_to_end})")
                            
                except Exception as e:
                    print(f"Ошибка при проверке занятия {booking.id}: {e}")
                    continue
                    
    except Exception as e:
        print(f"Ошибка в check_lesson_completion: {e}")

def check_excursion_reminders():
    """Проверка и отправка напоминаний гидам и клиентам за 23 часа до экскурсии"""
    global _bot
    if not _bot:
        return
        
    try:
        from database import get_db, ExcursionBooking, ExcursionOffer, User
        
        with next(get_db()) as db:
            now = datetime.now()
            
            bookings = db.query(ExcursionBooking).filter(
                ExcursionBooking.status == 'accepted',
                ExcursionBooking.group_is_ready == True,
                ExcursionBooking.reminder_24h_sent == False
            ).all()
            
            for booking in bookings:
                try:
                    excursion_time = "10:00"
                    
                    offer = db.query(ExcursionOffer).filter(
                        ExcursionOffer.booking_id == booking.id,
                        ExcursionOffer.status == 'accepted'
                    ).first()
                    
                    if offer and offer.offer_time:
                        excursion_time = offer.offer_time
                    elif hasattr(booking, 'excursion_time') and booking.excursion_time:
                        excursion_time = booking.excursion_time
                    
                    excursion_datetime = datetime.strptime(
                        f"{booking.booking_date} {excursion_time}",
                        "%d.%m.%Y %H:%M"
                    )
                    
                    time_diff = excursion_datetime - now
                    
                    if timedelta(hours=22, minutes=55) <= time_diff <= timedelta(hours=23, minutes=5):
                        if booking.guide_id:
                            try:
                                start_location = getattr(booking, 'guide_start_location', 'уточняется')
                                guide_note = getattr(booking, 'guide_note', 'нет')
                                end_time = getattr(booking, 'excursion_end_time', '')
                                
                                end_time_text = f" — {end_time}" if end_time else ""
                                
                                _bot.send_message(
                                    booking.guide_id,
                                    f"⏰ *Напоминание за 23 часа*\n\n"
                                    f"🗺️ У вас экскурсия с клиентом {booking.client_name}\n"
                                    f"📅 Дата: {booking.booking_date}\n"
                                    f"🕒 Время: {excursion_time}{end_time_text}\n"
                                    f"📍 Место сбора: {start_location}\n"
                                    f"📝 Примечание: {guide_note}\n"
                                    f"👥 Количество человек: {booking.people_count}\n\n"
                                    f"Не забудьте подготовиться!",
                                    parse_mode='Markdown'
                                )
                            except Exception as e:
                                print(f"Ошибка отправки гиду {booking.guide_id}: {e}")
                        
                        user = db.query(User).filter_by(id=booking.user_id).first()
                        if user and user.user_id:
                            try:
                                start_location = getattr(booking, 'guide_start_location', 'уточняется')
                                guide_note = getattr(booking, 'guide_note', 'нет')
                                end_time = getattr(booking, 'excursion_end_time', '')
                                
                                end_time_text = f" — {end_time}" if end_time else ""
                                
                                _bot.send_message(
                                    user.user_id,
                                    f"⏰ *Напоминание за 23 часа*\n\n"
                                    f"🗺️ Завтра у вас экскурсия с гидом {booking.guide_name}\n"
                                    f"📅 Дата: {booking.booking_date}\n"
                                    f"🕒 Время: {excursion_time}{end_time_text}\n"
                                    f"📍 Место сбора: {start_location}\n"
                                    f"📝 Примечание: {guide_note}\n"
                                    f"👥 Количество человек: {booking.people_count}\n\n"
                                    f"Не опаздывайте!",
                                    parse_mode='Markdown'
                                )
                            except Exception as e:
                                print(f"Ошибка отправки клиенту {user.user_id}: {e}")
                        
                        booking.reminder_24h_sent = True
                        db.commit()
                        print(f"✅ Напоминание за 23ч отправлено для экскурсии {booking.id} в {excursion_time}")
                        
                except Exception as e:
                    print(f"Ошибка при проверке экскурсии {booking.id}: {e}")
                    continue
                    
    except Exception as e:
        print(f"Ошибка в check_excursion_reminders: {e}")

def process_pending_groups():
    """В 19:00 накануне: проверяем группы и рассылаем в чат инструкторов"""
    global _bot
    if not _bot:
        return
    
    try:
        from database import get_db, InstructorBooking
        from config import INSTRUCTORS_CHAT_ID, MANAGER_CHAT_ID
        from telebot import types
        
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%d.%m.%Y')
        
        with next(get_db()) as db:
            bookings = db.query(InstructorBooking).filter(
                InstructorBooking.group_status == 'waiting_group',
                InstructorBooking.lesson_date == tomorrow
            ).all()
            
            groups = {}
            for b in bookings:
                key = f"{b.lesson_date}|{b.lesson_time}|{b.program}|{b.sport}|{b.student_type}"
                if key not in groups:
                    groups[key] = []
                groups[key].append(b)
            
            for key, members in groups.items():
                b = members[0]
                
                if len(members) >= 2:
                    for m in members:
                        m.group_status = 'group_ready'
                        m.status = 'searching'
                    db.commit()
                    
                    from handlers.instructors import format_group_text
                    chat_text = format_group_text(members)
                    
                    try:
                        markup = types.InlineKeyboardMarkup().add(
                            types.InlineKeyboardButton('✅ Беру', callback_data=f'instructor_take_{b.id}')
                        )
                        _bot.send_message(INSTRUCTORS_CHAT_ID, chat_text, parse_mode='Markdown', reply_markup=markup)
                    except Exception as e:
                        print(f"Ошибка отправки группы в чат: {e}")
                    
                    for m in members:
                        try:
                            _bot.send_message(m.user_id,
                                f"✅ *ГРУППА НАБРАЛАСЬ!*\n\n"
                                f"📋 {m.booking_id if m.booking_id else m.id}\n"
                                f"📅 {m.lesson_date}\n"
                                f"🕒 {m.lesson_time}\n\n"
                                f"Ожидайте предложений от инструкторов.",
                                parse_mode='Markdown')
                        except: pass
                    
                    if MANAGER_CHAT_ID:
                        try:
                            members_text = ""
                            total_group_price = 0
                            for i, m in enumerate(members, 1):
                                members_text += f"{i}. {m.client_name}, {m.client_phone}\n"
                                total_group_price += m.total_price or 0
                            
                            _bot.send_message(MANAGER_CHAT_ID,
                                f"👥 *ГРУППА НАБРАЛАСЬ (авто)*\n\n"
                                f"📅 {b.lesson_date}\n"
                                f"🕒 {b.lesson_time} — 14:00\n"
                                f"📋 {b.program} | 🏂 {b.sport} | 👶 {b.student_type}\n\n"
                                f"👤 *{len(members)} участников:*\n{members_text}\n"
                                f"💰 Общая стоимость: {int(total_group_price)} руб.\n"
                                f"💸 Комиссия (10%): {int(total_group_price * 0.1)} руб.",
                                parse_mode='Markdown')
                        except Exception as e:
                            print(f"Ошибка уведомления админа: {e}")
                else:
                    for m in members:
                        m.group_status = 'individual_offered'
                        m.status = 'searching'
                    db.commit()
                    
                    for m in members:
                        try:
                            safe_id = m.booking_id if m.booking_id else str(m.id)
                            markup = types.InlineKeyboardMarkup().add(
                                types.InlineKeyboardButton('✅ Беру', callback_data=f'instructor_take_{m.id}')
                            )
                            _bot.send_message(INSTRUCTORS_CHAT_ID,
                                f"🎿 *ЗАЯВКА {safe_id}*\n{m.program} | {m.lesson_date} | {m.lesson_time}\n{m.client_name}, {m.client_phone}\n⚠️ Группа не набралась",
                                parse_mode='Markdown', reply_markup=markup)
                            _bot.send_message(m.user_id,
                                f"❌ Группа на {m.lesson_date} не набралась.\nВаша заявка переведена в индивидуальную.\nОжидайте предложений от инструкторов.")
                        except Exception as e:
                            print(f"Ошибка уведомления: {e}")
            
            print(f"✅ Группы на {tomorrow} обработаны")
            
    except Exception as e:
        print(f"Ошибка в process_pending_groups: {e}")

def process_excursion_pending_groups():
    """В 19:00 накануне: проверяем группы экскурсий и рассылаем в чат гидов"""
    global _bot
    if not _bot:
        return
    
    try:
        from database import get_db, ExcursionBooking, Excursion
        from config import GUIDES_CHAT_ID, MANAGER_CHAT_ID
        from telebot import types
        
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%d.%m.%Y')
        
        with next(get_db()) as db:
            bookings = db.query(ExcursionBooking).filter(
                ExcursionBooking.group_status == 'waiting_group',
                ExcursionBooking.booking_date == tomorrow,
                ExcursionBooking.status != 'cancelled'
            ).all()
            
            groups = {}
            for b in bookings:
                key = f"{b.booking_date}|{b.excursion_id}"
                if key not in groups:
                    groups[key] = []
                groups[key].append(b)
            
            for key, members in groups.items():
                b = members[0]
                excursion = db.query(Excursion).filter_by(id=b.excursion_id).first()
                excursion_name = excursion.name if excursion else "Не указана"
                
                if len(members) >= 2:
                    # Группа набралась
                    for m in members:
                        m.group_status = 'group_ready'
                        m.status = 'searching'
                    db.commit()
                    
                    # Формируем текст для чата гидов
                    members_text = ""
                    total_people = 0
                    for i, m in enumerate(members, 1):
                        members_text += f"{i}. {m.client_name}, {m.client_phone}\n"
                        total_people += m.people_count or 0
                    
                    chat_text = f"""
👥 *ГРУППА НАБРАЛАСЬ!*

📅 *Дата:* {b.booking_date}
🗺️ *Экскурсия:* {excursion_name}
👤 *Участников:* {len(members)}
👥 *Всего человек:* {total_people}

*Участники:*
{members_text}
"""
                    try:
                        markup = types.InlineKeyboardMarkup().add(
                            types.InlineKeyboardButton('✅ Предложить', callback_data=f'guide_offer_{b.id}')
                        )
                        _bot.send_message(GUIDES_CHAT_ID, chat_text, parse_mode='Markdown', reply_markup=markup)
                    except Exception as e:
                        print(f"Ошибка отправки группы в чат гидов: {e}")
                    
                    # Уведомление участникам
                    for m in members:
                        try:
                            _bot.send_message(m.user_id,
                                f"✅ *ГРУППА НАБРАЛАСЬ!*\n\n"
                                f"📋 {m.booking_id}\n"
                                f"📅 {m.booking_date}\n"
                                f"🗺️ {excursion_name}\n\n"
                                f"Ожидайте предложений от гидов.",
                                parse_mode='Markdown')
                        except:
                            pass
                    
                    # Уведомление админу
                    if MANAGER_CHAT_ID:
                        try:
                            _bot.send_message(MANAGER_CHAT_ID,
                                f"👥 *ГРУППА ЭКСКУРСИИ НАБРАЛАСЬ*\n\n"
                                f"📅 {b.booking_date}\n"
                                f"🗺️ {excursion_name}\n"
                                f"👤 Участников: {len(members)}\n"
                                f"👥 Всего человек: {total_people}",
                                parse_mode='Markdown')
                        except Exception as e:
                            print(f"Ошибка уведомления админа: {e}")
                else:
                    # Группа не набралась
                    for m in members:
                        m.group_status = 'individual_offered'
                        m.status = 'searching'
                    db.commit()
                    
                    for m in members:
                        try:
                            markup = types.InlineKeyboardMarkup().add(
                                types.InlineKeyboardButton('✅ Предложить', callback_data=f'guide_offer_{m.id}')
                            )
                            _bot.send_message(GUIDES_CHAT_ID,
                                f"🗺️ *ЗАЯВКА {m.booking_id}*\n"
                                f"{m.client_name}, {m.client_phone}\n"
                                f"📅 {m.booking_date}\n"
                                f"⚠️ Группа не набралась — индивидуальная заявка",
                                parse_mode='Markdown', reply_markup=markup)
                            _bot.send_message(m.user_id,
                                f"❌ Группа на {m.booking_date} не набралась.\n"
                                f"Ваша заявка переведена в индивидуальную.\n"
                                f"Ожидайте предложений от гидов.")
                        except Exception as e:
                            print(f"Ошибка уведомления: {e}")
            
            print(f"✅ Группы экскурсий на {tomorrow} обработаны")
            
    except Exception as e:
        print(f"Ошибка в process_excursion_pending_groups: {e}")

def check_excursion_group_status():
    """Проверка групп за 24 часа и за 2 часа до начала экскурсии"""
    global _bot
    if not _bot:
        return
    
    try:
        from database import get_db, ExcursionBooking, Excursion, User
        from config import MANAGER_CHAT_ID
        
        now = datetime.now()
        
        with next(get_db()) as db:
            groups = db.query(ExcursionBooking).filter(
                ExcursionBooking.guide_conditions_set == True,
                ExcursionBooking.is_first_in_group == True,
                ExcursionBooking.status == 'accepted',
                ExcursionBooking.group_is_ready == False
            ).all()
            
            for group in groups:
                try:
                    start_datetime = datetime.strptime(
                        f"{group.booking_date} {group.excursion_start_time or '10:00'}",
                        "%d.%m.%Y %H:%M"
                    )
                    
                    time_to_start = start_datetime - now
                    
                    # Проверка за 24 часа (±5 минут)
                    if timedelta(hours=23, minutes=55) <= time_to_start <= timedelta(hours=24, minutes=5):
                        if not group.group_checked_24h:
                            members = db.query(ExcursionBooking).filter(
                                ExcursionBooking.parent_booking_id == group.id,
                                ExcursionBooking.status != 'cancelled'
                            ).all()
                            total_members = len(members) + 1
                            
                            if total_members >= group.group_min_people:
                                group.group_is_ready = True
                                group.group_checked_24h = True
                                db.commit()
                                
                                # Уведомление гиду
                                if group.guide_id:
                                    try:
                                        members_text = ""
                                        for i, m in enumerate([group] + members, 1):
                                            members_text += f"{i}. {m.client_name}, {m.client_phone}\n"
                                        
                                        _bot.send_message(
                                            group.guide_id,
                                            f"✅ *ГРУППА НАБРАЛАСЬ!*\n\n"
                                            f"📅 {group.booking_date}\n"
                                            f"🕒 {group.excursion_start_time} — {group.excursion_end_time or 'по договоренности'}\n"
                                            f"📍 {group.guide_start_location or 'уточняется'}\n"
                                            f"👥 Участников: {total_members}\n\n"
                                            f"*Контакты участников:*\n{members_text}",
                                            parse_mode='Markdown'
                                        )
                                    except:
                                        pass
                                
                                # Уведомление участникам
                                for m in members:
                                    try:
                                        _bot.send_message(
                                            m.user_id,
                                            f"✅ *ГРУППА НАБРАЛАСЬ!*\n\n"
                                            f"📅 {group.booking_date}\n"
                                            f"🕒 {group.excursion_start_time} — {group.excursion_end_time or 'по договоренности'}\n"
                                            f"📍 {group.guide_start_location or 'уточняется'}\n"
                                            f"👥 Гид: {group.guide_name}\n\n"
                                            f"Ожидайте дальнейших инструкций.",
                                            parse_mode='Markdown'
                                        )
                                    except:
                                        pass
                            else:
                                # Группа НЕ набралась — отмена
                                cancel_excursion_group(db, _bot, group, members, total_members)
                    
                    # Проверка за 2 часа (±5 минут)
                    if timedelta(hours=1, minutes=55) <= time_to_start <= timedelta(hours=2, minutes=5):
                        if not group.group_checked_2h:
                            members = db.query(ExcursionBooking).filter(
                                ExcursionBooking.parent_booking_id == group.id,
                                ExcursionBooking.status != 'cancelled'
                            ).all()
                            total_members = len(members) + 1
                            
                            if total_members >= group.group_min_people:
                                group.group_is_ready = True
                                group.group_checked_2h = True
                                db.commit()
                                
                                if group.guide_id:
                                    try:
                                        members_text = ""
                                        for i, m in enumerate([group] + members, 1):
                                            members_text += f"{i}. {m.client_name}, {m.client_phone}\n"
                                        
                                        _bot.send_message(
                                            group.guide_id,
                                            f"✅ *ГРУППА НАБРАЛАСЬ!*\n\n"
                                            f"📅 {group.booking_date}\n"
                                            f"🕒 {group.excursion_start_time} — {group.excursion_end_time or 'по договоренности'}\n"
                                            f"👥 Участников: {total_members}\n\n"
                                            f"*Контакты участников:*\n{members_text}",
                                            parse_mode='Markdown'
                                        )
                                    except:
                                        pass
                            else:
                                cancel_excursion_group(db, _bot, group, members, total_members)
                                
                except Exception as e:
                    print(f"Ошибка проверки группы {group.id}: {e}")
                    continue
                    
    except Exception as e:
        print(f"Ошибка в check_excursion_group_status: {e}")

def cancel_excursion_group(db, bot, group, members, total_members):
    """Отмена группы при недоборе участников"""
    from config import MANAGER_CHAT_ID
    
    group.status = 'cancelled'
    group.group_is_ready = False
    db.commit()
    
    for m in members:
        m.status = 'cancelled'
        db.commit()
        try:
            bot.send_message(
                m.user_id,
                f"❌ *ГРУППА НЕ НАБРАЛАСЬ*\n\n"
                f"📅 {group.booking_date} в {group.excursion_start_time}\n"
                f"Требуется минимум {group.group_min_people} человек, записалось {total_members}.\n\n"
                f"Ваша заявка отменена.\n"
                f"Вы можете попробовать другую дату или другую экскурсию.",
                parse_mode='Markdown'
            )
        except:
            pass
    
    if MANAGER_CHAT_ID:
        try:
            members_text = ""
            for i, m in enumerate([group] + members, 1):
                members_text += f"{i}. {m.client_name}, {m.client_phone}\n"
            
            bot.send_message(
                MANAGER_CHAT_ID,
                f"❌ *ГРУППА ОТМЕНЕНА (НЕДОБОР)*\n\n"
                f"📅 {group.booking_date} в {group.excursion_start_time}\n"
                f"Требуется минимум {group.group_min_people} человек, записалось {total_members}.\n\n"
                f"👤 *Участники (контакты):*\n{members_text}",
                parse_mode='Markdown'
            )
        except Exception as e:
            print(f"Ошибка уведомления админа: {e}")
    
    print(f"❌ Группа {group.booking_id} отменена (недобор: {total_members}/{group.group_min_people})")

def send_automatic_daily_report():
    """Отправляет автоматический ежедневный отчет администратору"""
    global _bot
    if not _bot:
        return
        
    admin_id = 6091836352
    today = datetime.now().date()
    
    try:
        from database import get_db, HotelBooking, InstructorBooking, ExcursionBooking, ShopOrder, Payment, User
        
        with next(get_db()) as db:
            hotel_bookings = db.query(HotelBooking).filter(
                HotelBooking.created_at >= today
            ).all()
            
            instructor_bookings = db.query(InstructorBooking).filter(
                InstructorBooking.created_at >= today
            ).all()
            
            excursion_bookings = db.query(ExcursionBooking).filter(
                ExcursionBooking.created_at >= today
            ).all()
            
            shop_orders = db.query(ShopOrder).filter(
                ShopOrder.created_at >= today
            ).all()
            
            payments = db.query(Payment).filter(
                Payment.created_at >= today,
                Payment.status == 'completed'
            ).all()
            
            new_users = db.query(User).filter(
                User.created_at >= today
            ).count()
            
            total_users = db.query(User).count()
            
            total_income = sum(p.amount for p in payments) if payments else 0
            
            upcoming_lessons = db.query(InstructorBooking).filter(
                InstructorBooking.status == 'accepted',
                InstructorBooking.lesson_date == today.strftime("%d.%m.%Y")
            ).all()
            
            completed_lessons = db.query(InstructorBooking).filter(
                InstructorBooking.status == 'completed',
                InstructorBooking.updated_at >= today
            ).all()
            
            report_text = f"""
⏰ *АВТОМАТИЧЕСКИЙ ЕЖЕДНЕВНЫЙ ОТЧЕТ*
*Дата:* {today.strftime("%d.%m.%Y")}
*Время:* {datetime.now().strftime("%H:%M")}

📊 *СТАТИСТИКА ЗА ДЕНЬ:*

🏨 *Отель:*
• Новых бронирований: {len(hotel_bookings)}
• Общая стоимость: {int(sum(b.total_price for b in hotel_bookings)) if hotel_bookings else 0} руб.

🎿 *Инструкторы:*
• Новых заявок: {len(instructor_bookings)}
• Общая стоимость: {int(sum(b.total_price for b in instructor_bookings)) if instructor_bookings else 0} руб.
• Занятий сегодня: {len(upcoming_lessons)}
• Завершено сегодня: {len(completed_lessons)}

🗺️ *Экскурсии:*
• Новых бронирований: {len(excursion_bookings)}
• Общая стоимость: {int(sum(b.total_price for b in excursion_bookings)) if excursion_bookings else 0} руб.

🛒 *Магазин:*
• Новых заказов: {len(shop_orders)}
• Общая стоимость: {int(sum(o.total_price for o in shop_orders)) if shop_orders else 0} руб.

💰 *ФИНАНСЫ:*
• Поступило платежей: {len(payments)}
• Общая сумма: {int(total_income)} руб.

👥 *ПОЛЬЗОВАТЕЛИ:*
• Новых пользователей: {new_users}
• Всего пользователей: {total_users}

📈 *ИТОГО ЗА ДЕНЬ:*
• Всего заказов: {len(hotel_bookings) + len(instructor_bookings) + len(excursion_bookings) + len(shop_orders)}
• Общий доход: {int((sum(b.total_price for b in hotel_bookings) if hotel_bookings else 0) + (sum(b.total_price for b in instructor_bookings) if instructor_bookings else 0) + (sum(b.total_price for b in excursion_bookings) if excursion_bookings else 0) + (sum(o.total_price for o in shop_orders) if shop_orders else 0))} руб.
"""
            
            if upcoming_lessons:
                report_text += "\n🎿 *ЗАНЯТИЯ СЕГОДНЯ:*\n"
                for lesson in upcoming_lessons:
                    report_text += f"• {lesson.lesson_time} - {lesson.client_name} (инстр. {lesson.instructor_name})\n"
            
            if completed_lessons:
                report_text += "\n✅ *ЗАВЕРШЕННЫЕ ЗАНЯТИЯ:*\n"
                for lesson in completed_lessons:
                    report_text += f"• {lesson.lesson_time} - {lesson.client_name} ({int(lesson.total_price)} руб.)\n"
            
            _bot.send_message(admin_id, report_text, parse_mode='Markdown')
            
    except Exception as e:
        print(f"Ошибка в send_automatic_daily_report: {e}")

def run_scheduler():
    """Запускает планировщик задач"""
    global _bot
    if not _bot:
        return
    
    schedule.every(1).minutes.do(check_instructor_reminders)
    schedule.every(5).minutes.do(check_lesson_completion)
    schedule.every(1).minutes.do(check_excursion_reminders)
    schedule.every(1).minutes.do(check_excursion_group_status)
    schedule.every().day.at("19:00").do(process_pending_groups)
    schedule.every().day.at("19:01").do(process_excursion_pending_groups)
    schedule.every().day.at("23:59").do(send_automatic_daily_report)
    
    print("⏰ Планировщик запущен")
    
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)
        except Exception as e:
            print(f"Ошибка в планировщике: {e}")
            time.sleep(60)

def start_scheduler_thread(bot):
    """Запускает планировщик в отдельном потоке"""
    global _bot
    _bot = bot
    
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    print("✅ Поток планировщика запущен")

if __name__ == "__main__":
    print("Запуск планировщика...")