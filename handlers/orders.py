import telebot
from telebot import types
import json
from datetime import datetime, timedelta
import re
import random
import string

from database import get_db, User, HotelBooking, InstructorBooking, ShopOrder, ShopProduct, ExcursionBooking, Excursion, ExpeditionBooking, Expedition
from state_manager import StateManager
from states import UserStates, StateData
import keyboards
from config import MANAGER_CHAT_ID, INSTRUCTORS_CHAT_ID, GUIDES_CHAT_ID

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def escape_markdown(text):
    if not text:
        return ""
    text = str(text)
    for char in ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']:
        text = text.replace(char, '\\' + char)
    return text

def safe_send(bot, chat_id, text, **kwargs):
    try:
        return bot.send_message(chat_id, text, parse_mode='Markdown', **kwargs)
    except:
        return bot.send_message(chat_id, text.replace('*','').replace('_','').replace('\\',''), **kwargs)

def get_user_link(user):
    """Формирует кликабельную ссылку на пользователя Telegram"""
    if not user:
        return "неизвестно"
    if user.username:
        return f"@{user.username}"
    else:
        return f"[{user.first_name or 'ID'}](tg://user?id={user.user_id})"

def get_booking_details(db, otype, oid):
    """Формирует детали заказа с единой нумерацией ИНСТРN (без подчёркивания)"""
    if otype == 'hotel':
        b = db.query(HotelBooking).filter_by(id=oid).first()
        if b:
            check_in_str = b.check_in.strftime('%d.%m.%Y') if b.check_in else ''
            check_out_str = b.check_out.strftime('%d.%m.%Y') if b.check_out else ''
            return (f"🏨 *ОТЕЛЬ*\n"
                    f"Номер: {b.booking_id}\n"
                    f"Заезд: {check_in_str}\n"
                    f"Выезд: {check_out_str}\n"
                    f"Ночей: {b.nights}\n"
                    f"Имя: {b.name}\n"
                    f"Тел: {b.phone}\n"
                    f"💰 {int(b.total_price)} руб.\n"
                    f"Статус: {b.status}")
    elif otype == 'instructor':
        b = db.query(InstructorBooking).filter_by(id=oid).first()
        if b:
            correct_id = f"ИНСТР{b.id}"
            if b.booking_id != correct_id:
                b.booking_id = correct_id
                db.commit()
            display_id = correct_id
            instructor_link = ""
            if b.instructor_id:
                instructor_user = db.query(User).filter_by(user_id=b.instructor_id).first()
                if instructor_user:
                    instructor_link = get_user_link(instructor_user)
            if b.status == 'cancelled':
                status_text = "отменён"
            else:
                status_text = "оплачено" if b.payment_status == 'paid' else "не оплачено"
            
            details = (f"🎿 *ИНСТРУКТОР*\n"
                    f"📋 Номер заявки: {display_id}\n"
                    f"🎿 Инструктор: {b.instructor_name or 'не назначен'} ({instructor_link})\n"
                    f"📅 Дата: {b.lesson_date}\n"
                    f"🕒 Время: {b.lesson_time}\n"
                    f"💰 Стоимость: {int(b.total_price)} руб.\n"
                    f"📊 Статус: {status_text}")
            
            if hasattr(b, 'sport') and b.sport:
                details += f"\n🏂 Спорт: {b.sport}"
            if hasattr(b, 'program') and b.program:
                details += f"\n📋 Программа: {b.program}"
            if hasattr(b, 'student_type') and b.student_type:
                details += f"\n👶 Ученик: {b.student_type}"
            
            return details
    elif otype == 'excursion':
        b = db.query(ExcursionBooking).filter_by(id=oid).first()
        if b:
            correct_id = f"ЭКС{b.id}"
            if b.booking_id != correct_id:
                b.booking_id = correct_id
                db.commit()
            display_id = correct_id
            guide_link = ""
            if b.guide_id:
                guide_user = db.query(User).filter_by(user_id=b.guide_id).first()
                if guide_user:
                    guide_link = get_user_link(guide_user)
            if b.status == 'cancelled':
                status_text = "отменён"
            else:
                status_text = "оплачено" if b.payment_status == 'paid' else "не оплачено"
            
            details = (f"🗺️ *ЭКСКУРСИЯ*\n"
                    f"📋 Номер заявки: {display_id}\n"
                    f"🗺️ Гид: {b.guide_name or 'не назначен'} ({guide_link})\n"
                    f"📅 Дата: {b.booking_date}\n"
                    f"🕒 Время: {b.excursion_start_time or b.excursion_time or 'не указано'}\n"
                    f"👥 Человек: {b.people_count}\n"
                    f"💰 Стоимость: {int(b.total_price)} руб.\n"
                    f"📊 Статус: {status_text}")
            
            if hasattr(b, 'has_children') and b.has_children and b.children_info:
                details += f"\n👶 Дети: {b.children_info}"
            if hasattr(b, 'guide_start_location') and b.guide_start_location:
                details += f"\n📍 Место сбора: {b.guide_start_location}"
            if hasattr(b, 'guide_note') and b.guide_note:
                details += f"\n📝 Примечание: {b.guide_note}"
            
            return details
    return "❌ Заказ не найден"

# ========== КЛИЕНТ ==========

def handle_orders_start(bot, message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    StateManager.set_state(user_id, UserStates.ORDERS_LIST, StateData(step=1))
    with next(get_db()) as db:
        user = db.query(User).filter_by(user_id=user_id).first()
        if not user:
            safe_send(bot, chat_id, "📋 *Мои заказы*\n\nУ вас пока нет заказов.", reply_markup=keyboards.main_menu())
            StateManager.clear_state(user_id)
            return
        all_orders = []
        for b in db.query(HotelBooking).filter_by(user_id=user.id).all():
            if b.status == 'cancelled':
                continue
            created_str = b.created_at.strftime('%d.%m.%Y') if b.created_at else ''
            display_id = b.booking_id if b.booking_id else f"HOT{b.id}"
            all_orders.append({'type':'hotel','id':b.id,'order_id':display_id,'date':created_str,'status':b.status,'payment_status':b.payment_status,'amount':b.total_price})
        for b in db.query(InstructorBooking).filter_by(user_id=user.id).all():
            if b.status == 'cancelled':
                continue
            # ИЗМЕНЕНИЕ: берём lesson_date вместо created_at
            order_date = b.lesson_date if b.lesson_date else ''
            correct_id = f"ИНСТР{b.id}"
            if b.booking_id != correct_id:
                b.booking_id = correct_id
                db.commit()
            all_orders.append({'type':'instructor','id':b.id,'order_id':correct_id,'date':order_date,'time':b.lesson_time,'status':b.status,'payment_status':b.payment_status,'amount':b.total_price})
        for o in db.query(ShopOrder).filter_by(user_id=user.id).all():
            if o.status == 'cancelled':
                continue
            created_str = o.created_at.strftime('%d.%m.%Y') if o.created_at else ''
            display_id = o.order_id if o.order_id else f"SHOP{o.id}"
            all_orders.append({'type':'shop','id':o.id,'order_id':display_id,'date':created_str,'status':o.status,'payment_status':o.payment_status,'amount':o.total_price})
        for b in db.query(ExcursionBooking).filter_by(user_id=user.id).all():
            if b.status == 'cancelled':
                continue
            created_str = b.created_at.strftime('%d.%m.%Y') if b.created_at else ''
            correct_id = f"ЭКС{b.id}"
            if b.booking_id != correct_id:
                b.booking_id = correct_id
                db.commit()
            all_orders.append({'type':'excursion','id':b.id,'order_id':correct_id,'date':created_str,'time':b.excursion_start_time or b.excursion_time,'status':b.status,'payment_status':b.payment_status,'amount':b.total_price})
        all_orders.sort(key=lambda x: x['date'], reverse=True)
        if not all_orders:
            safe_send(bot, chat_id, "📋 *Мои заказы*\n\nУ вас пока нет заказов.", reply_markup=keyboards.main_menu())
            StateManager.clear_state(user_id)
            return
        StateManager.update_data(user_id, orders=all_orders, current_page=0)
        show_orders_page(bot, chat_id, all_orders, page=0)

def show_orders_page(bot, chat_id, orders, page=0):
    per_page = 5
    start = page * per_page
    end = start + per_page
    
    # ИЗМЕНЕНИЕ: только инлайн-кнопки, без текстового блока
    markup = types.InlineKeyboardMarkup(row_width=1)
    for o in orders[start:end]:
        time_str = f" {o.get('time', '')}" if o.get('time', '') else ""
        button_text = f"📋 {o['order_id']} - {o['date']}{time_str}"
        markup.add(types.InlineKeyboardButton(button_text, callback_data=f"order_select_{o['type']}_{o['id']}"))
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(types.InlineKeyboardButton('◀️ Назад', callback_data=f'orders_page_{page-1}'))
    if end < len(orders):
        nav_buttons.append(types.InlineKeyboardButton('▶️ Вперед', callback_data=f'orders_page_{page+1}'))
    if nav_buttons:
        markup.row(*nav_buttons)
    
    markup.add(types.InlineKeyboardButton('🔙 В главное меню', callback_data='orders_back_to_main'))
    
    safe_send(bot, chat_id, f"📋 *Мои заказы* — выберите заказ:", reply_markup=markup)

def handle_orders_list(bot, message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    txt = message.text
    if txt == '🔙 Назад в меню':
        StateManager.clear_state(user_id)
        safe_send(bot, chat_id, "Главное меню:", reply_markup=keyboards.main_menu())
        return
    if txt == '❌ Отмена':
        StateManager.clear_state(user_id)
        safe_send(bot, chat_id, "Отменено.", reply_markup=keyboards.main_menu())

def handle_orders_callback(bot, call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    if call.data.startswith('rebook_'):
        parts = call.data.replace('rebook_', '').split('_')
        if len(parts) == 2:
            otype = parts[0]
            oid = int(parts[1])
            rebook_order(bot, call, otype, oid)
        return
    
    if call.data == 'orders_back_to_main':
        StateManager.clear_state(user_id)
        safe_send(bot, chat_id, "Главное меню:", reply_markup=keyboards.main_menu())
        bot.answer_callback_query(call.id)
        return
    
    if call.data.startswith('orders_page_'):
        page = int(call.data.replace('orders_page_', ''))
        data = StateManager.get_data(user_id)
        if hasattr(data, 'orders'):
            StateManager.update_data(user_id, current_page=page)
            try:
                bot.delete_message(chat_id, call.message.message_id)
            except:
                pass
            show_orders_page(bot, chat_id, data.orders, page)
        bot.answer_callback_query(call.id)
        return
    
    if call.data.startswith('order_select_'):
        data_str = call.data.replace('order_select_', '')
        last_underscore = data_str.rfind('_')
        if last_underscore > 0:
            otype = data_str[:last_underscore]
            oid = int(data_str[last_underscore+1:])
            data = StateManager.get_data(user_id)
            if hasattr(data, 'orders'):
                order = next((o for o in data.orders if o['type'] == otype and o['id'] == oid), None)
                if order:
                    StateManager.set_state(user_id, UserStates.ORDER_DETAILS, StateData(order_type=otype, order_id=oid, order_code=order['order_id']))
                    show_order_details(bot, chat_id, order)
        bot.answer_callback_query(call.id)
        return

def show_order_details(bot, chat_id, order):
    with next(get_db()) as db:
        txt = get_booking_details(db, order['type'], order['id'])
        if txt == "❌ Заказ не найден":
            safe_send(bot, chat_id, txt)
            return
        markup = types.InlineKeyboardMarkup(row_width=2)
        if order['status'] in ['pending','confirmed','accepted','searching','offers_received']:
            if order['type'] in ['instructor','excursion']:
                markup.add(types.InlineKeyboardButton('❌ Отменить', callback_data=f'order_cancel_{order["type"]}_{order["id"]}'),
                          types.InlineKeyboardButton('📅 Перенести', callback_data=f'order_reschedule_{order["type"]}_{order["id"]}'))
        if order['type'] == 'instructor':
            b = db.query(InstructorBooking).filter_by(id=order['id']).first()
            if b and b.instructor_id:
                markup.add(types.InlineKeyboardButton('🔄 Записаться снова', callback_data=f'rebook_instructor_{order["id"]}'))
        elif order['type'] == 'excursion':
            b = db.query(ExcursionBooking).filter_by(id=order['id']).first()
            if b and b.guide_id:
                markup.add(types.InlineKeyboardButton('🔄 Записаться снова', callback_data=f'rebook_excursion_{order["id"]}'))
        markup.add(types.InlineKeyboardButton('📞 Менеджер', callback_data=f'order_contact_{order["type"]}_{order["id"]}'))
        markup.add(types.InlineKeyboardButton('🔙 К списку', callback_data='order_back_to_list'))
        safe_send(bot, chat_id, txt, reply_markup=markup)

def handle_order_details_callback(bot, call):
    user_id = call.from_user.id
    if call.data == 'order_back_to_list':
        data = StateManager.get_data(user_id)
        if hasattr(data, 'orders'):
            show_orders_page(bot, call.message.chat.id, data.orders, getattr(data,'current_page',0))
        else:
            handle_orders_start(bot, call.message)
        bot.answer_callback_query(call.id)
        return
    parts = call.data.split('_')
    if len(parts) >= 4:
        action, otype, oid = parts[1], parts[2], int(parts[3])
        if action == 'cancel':
            cancel_order(bot, call, otype, oid)
        elif action == 'reschedule':
            start_reschedule(bot, call, otype, oid)
        elif action == 'contact':
            from handlers.main import handle_write_manager
            handle_write_manager(bot, call.message)

def cancel_order(bot, call, otype, oid):
    with next(get_db()) as db:
        b = None
        if otype == 'hotel':
            b = db.query(HotelBooking).filter_by(id=oid).first()
        elif otype == 'instructor':
            b = db.query(InstructorBooking).filter_by(id=oid).first()
        elif otype == 'excursion':
            b = db.query(ExcursionBooking).filter_by(id=oid).first()
        else:
            bot.answer_callback_query(call.id, "❌ Нельзя отменить")
            return
        
        if b:
            was_group = hasattr(b, 'group_status') and b.group_status in ['waiting_group', 'group_ready', 'grouped']
            
            if otype == 'excursion':
                # Логика для групповой экскурсии
                b.status = 'cancelled'
                b.group_status = None
                db.commit()
                
                # Найти родительскую заявку
                parent_id = b.parent_booking_id
                if parent_id:
                    parent = db.query(ExcursionBooking).filter_by(id=parent_id).first()
                    if parent and parent.guide_id:
                        # Уведомить гида об изменении в группе
                        try:
                            from handlers.excursions import send_group_update_notifications
                            send_group_update_notifications(bot, parent, None)
                        except Exception as e:
                            print(f"Ошибка отправки уведомления гиду: {e}")
                        
                        # Уведомление админу
                        if MANAGER_CHAT_ID:
                            try:
                                members = db.query(ExcursionBooking).filter(
                                    ExcursionBooking.parent_booking_id == parent.id,
                                    ExcursionBooking.status != 'cancelled'
                                ).all()
                                all_members = [parent] + members
                                members_text = ""
                                total_people = 0
                                for i, m in enumerate(all_members, 1):
                                    members_text += f"{i}. {m.client_name}, {m.client_phone}\n"
                                    total_people += m.people_count or 0
                                
                                admin_msg = f"❌ *УЧАСТНИК ВЫБЫЛ ИЗ ГРУППЫ*\n\n"
                                admin_msg += f"Группа: {parent.booking_id}\n"
                                admin_msg += f"📅 {parent.booking_date}\n"
                                admin_msg += f"🕒 {parent.excursion_start_time or 'не указано'}\n"
                                admin_msg += f"📍 {parent.guide_start_location or 'не указано'}\n"
                                admin_msg += f"💰 Цена: {int(parent.guide_price_per_person or 0)} руб.\n\n"
                                admin_msg += f"👤 *Оставшиеся участники ({len(all_members)}):*\n{members_text}\n"
                                admin_msg += f"Всего человек: {total_people}\n"
                                admin_msg += f"\n❌ *Выбыл:* {b.client_name}, {b.client_phone}"
                                safe_send(bot, MANAGER_CHAT_ID, admin_msg)
                            except Exception as e:
                                print(f"Ошибка уведомления админа: {e}")
                
                details = get_booking_details(db, otype, oid)
                safe_send(bot, call.message.chat.id, f"❌ Заказ отменён.\n\n{details}")
                
                client_user = db.query(User).filter_by(id=b.user_id).first()
                if client_user and client_user.user_id != call.from_user.id:
                    safe_send(bot, client_user.user_id, f"❌ *Заказ отменён*\n\n{details}")
                if b.guide_id and b.guide_id != call.from_user.id:
                    safe_send(bot, b.guide_id, f"❌ *Заказ отменён*\n\n{details}")
                
                if MANAGER_CHAT_ID:
                    safe_send(bot, MANAGER_CHAT_ID, f"❌ *ЗАКАЗ ОТМЕНЁН*\n\n{details}")
                
                bot.answer_callback_query(call.id, "✅ Отменено")
            
            elif was_group and otype == 'instructor':
                # Сохраняем данные до сброса
                lesson_date = b.lesson_date
                lesson_time = b.lesson_time
                program = b.program
                sport = getattr(b, 'sport', '')
                student_type = getattr(b, 'student_type', '')
                client_name = b.client_name
                client_phone = b.client_phone
                booking_id = b.booking_id if b.booking_id else str(b.id)
                old_group_status = b.group_status
                
                # Помечаем текущую заявку как отменённую
                b.group_status = None
                b.status = 'cancelled'
                db.commit()
                
                # Находим оставшихся участников этой же группы
                remaining = db.query(InstructorBooking).filter(
                    InstructorBooking.lesson_date == lesson_date,
                    InstructorBooking.lesson_time == lesson_time,
                    InstructorBooking.program == program,
                    InstructorBooking.sport == sport,
                    InstructorBooking.student_type == student_type,
                    InstructorBooking.status != 'cancelled',
                    InstructorBooking.id != b.id
                ).all()
                
                remaining_count = len(remaining)
                total_group_price = sum(m.total_price or 0 for m in remaining)
                
                # Уведомление инструктору в личку
                if b.instructor_id:
                    try:
                        members_text = ""
                        for i, m in enumerate(remaining, 1):
                            members_text += f"{i}. {m.client_name}, {m.client_phone}\n"
                        
                        status_line = ""
                        if old_group_status == 'grouped':
                            status_line = f"\n👥 *Осталось в группе:* {remaining_count} чел.\n"
                            if remaining:
                                status_line += f"\n*Оставшиеся участники:*\n{members_text}"
                        
                        instructor_msg = f"👥 *ИЗМЕНЕНИЕ В ГРУППЕ ({remaining_count} чел)!*\n\n"
                        instructor_msg += f"📅 {lesson_date}\n"
                        instructor_msg += f"🕒 {lesson_time} — {int(float(lesson_time.split(':')[0]) + 2)}:{lesson_time.split(':')[1]}\n"
                        instructor_msg += f"📋 {program}\n"
                        instructor_msg += f"🏂 {sport}\n"
                        instructor_msg += f"👶 {student_type}\n\n"
                        instructor_msg += f"👤 *Инструктор:* {b.instructor_name or 'не назначен'}\n\n"
                        instructor_msg += f"👤 *Участники:*\n{members_text}\n"
                        instructor_msg += f"💰 *Общая стоимость:* {int(total_group_price)} руб.\n"
                        instructor_msg += f"💸 *Комиссия (10%):* {int(total_group_price * 0.1)} руб.\n"
                        instructor_msg += f"\n❌ *Выбыл:* {client_name}, {client_phone}"
                        
                        safe_send(bot, b.instructor_id, instructor_msg)
                    except Exception as e:
                        print(f"Ошибка уведомления инструктора: {e}")
                
                # Уведомление администратору
                if MANAGER_CHAT_ID:
                    try:
                        members_text = ""
                        for i, m in enumerate(remaining, 1):
                            members_text += f"{i}. {m.client_name}, {m.client_phone}\n"
                        
                        admin_msg = f"👥 *ИЗМЕНЕНИЕ В ГРУППЕ ({remaining_count} чел)!*\n\n"
                        admin_msg += f"📅 {lesson_date}\n"
                        admin_msg += f"🕒 {lesson_time} — {int(float(lesson_time.split(':')[0]) + 2)}:{lesson_time.split(':')[1]}\n"
                        admin_msg += f"📋 {program}\n"
                        admin_msg += f"🏂 {sport}\n"
                        admin_msg += f"👶 {student_type}\n\n"
                        admin_msg += f"👤 *Инструктор:* {b.instructor_name or 'не назначен'}\n\n"
                        admin_msg += f"👤 *Участники:*\n{members_text}\n"
                        admin_msg += f"💰 *Общая стоимость:* {int(total_group_price)} руб.\n"
                        admin_msg += f"💸 *Комиссия (10%):* {int(total_group_price * 0.1)} руб.\n"
                        admin_msg += f"\n❌ *Выбыл:* {client_name}, {client_phone}"
                        
                        safe_send(bot, MANAGER_CHAT_ID, admin_msg)
                    except Exception as e:
                        print(f"Ошибка уведомления админа: {e}")
                
                # Если группа была уже собрана (grouped) и осталось < 2 человек — уведомление, что группа расформирована
                if old_group_status == 'grouped' and remaining_count < 2:
                    disband_msg = f"⚠️ *ГРУППА РАСФОРМИРОВАНА*\n\n"
                    disband_msg += f"📅 {lesson_date}\n"
                    disband_msg += f"🕒 {lesson_time}\n"
                    disband_msg += f"Причина: в группе осталось менее 2 участников"
                    
                    if b.instructor_id:
                        safe_send(bot, b.instructor_id, disband_msg)
                    if MANAGER_CHAT_ID:
                        safe_send(bot, MANAGER_CHAT_ID, disband_msg)
                
                bot.answer_callback_query(call.id, "✅ Отменено")
                
            else:
                b.status = 'cancelled'
                db.commit()
                details = get_booking_details(db, otype, oid)
                
                safe_send(bot, call.message.chat.id, f"❌ Заказ отменён.\n\n{details}")
                
                if otype == 'instructor':
                    client_user = db.query(User).filter_by(id=b.user_id).first()
                    if client_user and client_user.user_id != call.from_user.id:
                        safe_send(bot, client_user.user_id, f"❌ *Заказ отменён*\n\n{details}")
                    if b.instructor_id and b.instructor_id != call.from_user.id:
                        safe_send(bot, b.instructor_id, f"❌ *Заказ отменён*\n\n{details}")
                elif otype == 'excursion':
                    client_user = db.query(User).filter_by(id=b.user_id).first()
                    if client_user and client_user.user_id != call.from_user.id:
                        safe_send(bot, client_user.user_id, f"❌ *Заказ отменён*\n\n{details}")
                    if b.guide_id and b.guide_id != call.from_user.id:
                        safe_send(bot, b.guide_id, f"❌ *Заказ отменён*\n\n{details}")
                
                if MANAGER_CHAT_ID:
                    safe_send(bot, MANAGER_CHAT_ID, f"❌ *ЗАКАЗ ОТМЕНЁН*\n\n{details}")
                
                bot.answer_callback_query(call.id, "✅ Отменено")
    
    # Перезагружаем список заказов
    with next(get_db()) as db:
        user = db.query(User).filter_by(user_id=call.from_user.id).first()
        if user:
            all_orders = []
            for b in db.query(InstructorBooking).filter_by(user_id=user.id).all():
                if b.status == 'cancelled':
                    continue
                order_date = b.lesson_date if b.lesson_date else ''
                correct_id = f"ИНСТР{b.id}"
                if b.booking_id != correct_id:
                    b.booking_id = correct_id
                    db.commit()
                all_orders.append({'type':'instructor','id':b.id,'order_id':correct_id,'date':order_date,'time':b.lesson_time,'status':b.status,'payment_status':b.payment_status,'amount':b.total_price})
            for b in db.query(ExcursionBooking).filter_by(user_id=user.id).all():
                if b.status == 'cancelled':
                    continue
                created_str = b.created_at.strftime('%d.%m.%Y') if b.created_at else ''
                correct_id = f"ЭКС{b.id}"
                if b.booking_id != correct_id:
                    b.booking_id = correct_id
                    db.commit()
                all_orders.append({'type':'excursion','id':b.id,'order_id':correct_id,'date':created_str,'time':b.excursion_start_time or b.excursion_time,'status':b.status,'payment_status':b.payment_status,'amount':b.total_price})
            for b in db.query(HotelBooking).filter_by(user_id=user.id).all():
                if b.status == 'cancelled':
                    continue
                created_str = b.created_at.strftime('%d.%m.%Y') if b.created_at else ''
                display_id = b.booking_id if b.booking_id else f"HOT{b.id}"
                all_orders.append({'type':'hotel','id':b.id,'order_id':display_id,'date':created_str,'status':b.status,'payment_status':b.payment_status,'amount':b.total_price})
            for o in db.query(ShopOrder).filter_by(user_id=user.id).all():
                if o.status == 'cancelled':
                    continue
                created_str = o.created_at.strftime('%d.%m.%Y') if o.created_at else ''
                display_id = o.order_id if o.order_id else f"SHOP{o.id}"
                all_orders.append({'type':'shop','id':o.id,'order_id':display_id,'date':created_str,'status':o.status,'payment_status':o.payment_status,'amount':o.total_price})
            all_orders.sort(key=lambda x: x['date'], reverse=True)
            StateManager.update_data(call.from_user.id, orders=all_orders, current_page=0)
            show_orders_page(bot, call.message.chat.id, all_orders, page=0)

def rebook_order(bot, call, otype, oid):
    """Перенаправляет на полный процесс бронирования с автозаполнением инструктора"""
    user_id = call.from_user.id
    
    if otype == 'instructor':
        with next(get_db()) as db:
            old = db.query(InstructorBooking).filter_by(id=oid).first()
            if old and old.instructor_id:
                from handlers.instructors import handle_instructors_start
                StateManager.set_state(
                    user_id,
                    UserStates.INSTRUCTORS_SELECT_SPORT,
                    StateData(
                        rebook_instructor_id=old.instructor_id,
                        rebook_instructor_name=old.instructor_name
                    )
                )
                bot.send_message(
                    call.message.chat.id,
                    "🎿 *Выберите вид спорта:*",
                    parse_mode='Markdown',
                    reply_markup=keyboards.instructors_sport_keyboard()
                )
                bot.answer_callback_query(call.id, "✅ Начинаем бронирование с этим инструктором")
                return
    elif otype == 'excursion':
        with next(get_db()) as db:
            old = db.query(ExcursionBooking).filter_by(id=oid).first()
            if old and old.guide_id:
                StateManager.set_state(
                    user_id,
                    UserStates.EXCURSIONS_START,
                    StateData(
                        rebook_guide_id=old.guide_id,
                        rebook_guide_name=old.guide_name
                    )
                )
                from handlers.excursions import handle_excursions_start
                handle_excursions_start(bot, call.message)
                bot.answer_callback_query(call.id, "🔄 Выберите экскурсию")
                return
    
    bot.answer_callback_query(call.id, "❌ Не удалось начать повторную запись")

def start_reschedule(bot, call, otype, oid):
    StateManager.set_state(call.from_user.id, UserStates.ORDER_RESCHEDULE_DATE, StateData(order_type=otype, order_id=oid))
    safe_send(bot, call.message.chat.id, "📅 Введите новую дату (ДД.ММ.ГГГГ):", reply_markup=keyboards.back_button())
    bot.answer_callback_query(call.id)

def handle_reschedule_date(bot, message):
    user_id = message.from_user.id
    if message.text == '🔙 Назад': StateManager.go_back(user_id); return
    if message.text == '❌ Отмена': StateManager.clear_state(user_id); safe_send(bot, message.chat.id, "Отменено.", reply_markup=keyboards.main_menu()); return
    try:
        datetime.strptime(message.text, "%d.%m.%Y")
        data = StateManager.get_data(user_id)
        data.new_date = message.text
        if data.order_type in ['instructor','excursion']:
            StateManager.set_state(user_id, UserStates.ORDER_RESCHEDULE_TIME, data)
            safe_send(bot, message.chat.id, "🕒 Введите новое время (ЧЧ:ММ):", reply_markup=keyboards.back_button())
        else:
            finish_reschedule(bot, message, data)
    except:
        safe_send(bot, message.chat.id, "❌ Неверный формат даты. ДД.ММ.ГГГГ:")

def handle_reschedule_time(bot, message):
    user_id = message.from_user.id
    if message.text == '🔙 Назад': StateManager.go_back(user_id); return
    if message.text == '❌ Отмена': StateManager.clear_state(user_id); safe_send(bot, message.chat.id, "Отменено."); return
    if not re.match(r'^([0-1]?[0-9]|2[0-3]):([0-5][0-9])$', message.text):
        safe_send(bot, message.chat.id, "❌ Неверный формат. ЧЧ:ММ:")
        return
    data = StateManager.get_data(user_id)
    data.new_time = message.text
    finish_reschedule(bot, message, data)

def finish_reschedule(bot, message, data):
    user_id = message.from_user.id
    chat_id = message.chat.id
    with next(get_db()) as db:
        if data.order_type == 'instructor':
            b = db.query(InstructorBooking).filter_by(id=data.order_id).first()
            if not b or b.status != 'accepted':
                safe_send(bot, chat_id, "❌ Заказ не активен.")
                StateManager.clear_state(user_id)
                return
            details = get_booking_details(db, 'instructor', data.order_id)
            inst_id = b.instructor_id
            nd, nt = data.new_date, getattr(data, 'new_time', b.lesson_time)
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton('✅ Согласен', callback_data=f"instr_reschedule_accept_{b.id}_{nd.replace('.','-')}_{nt.replace(':','~')}"),
                      types.InlineKeyboardButton('❌ Отклонить', callback_data=f'instr_reschedule_reject_{b.id}'))
            try:
                safe_send(bot, inst_id, f"🔄 *Клиент хочет перенести занятие*\n\n{details}\n\n*Новая дата:* {nd}\n*Новое время:* {nt}\n\nПодтвердите?", reply_markup=markup)
                safe_send(bot, chat_id, "✅ Запрос отправлен инструктору.")
            except:
                safe_send(bot, chat_id, "❌ Не удалось отправить запрос.")
        elif data.order_type == 'excursion':
            b = db.query(ExcursionBooking).filter_by(id=data.order_id).first()
            if not b or b.status != 'accepted':
                safe_send(bot, chat_id, "❌ Заказ не активен.")
                StateManager.clear_state(user_id)
                return
            details = get_booking_details(db, 'excursion', data.order_id)
            gid = b.guide_id
            nd, nt = data.new_date, getattr(data, 'new_time', b.excursion_start_time or '10:00')
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton('✅ Согласен', callback_data=f"guide_reschedule_accept_{b.id}_{nd.replace('.','-')}_{nt.replace(':','~')}"),
                      types.InlineKeyboardButton('❌ Отклонить', callback_data=f'guide_reschedule_reject_{b.id}'))
            try:
                safe_send(bot, gid, f"🔄 *Клиент хочет перенести экскурсию*\n\n{details}\n\n*Новая дата:* {nd}\n*Новое время:* {nt}\n\nПодтвердите?", reply_markup=markup)
                safe_send(bot, chat_id, "✅ Запрос отправлен гиду.")
            except:
                safe_send(bot, chat_id, "❌ Не удалось отправить запрос.")
    StateManager.clear_state(user_id)

# ========== ИНСТРУКТОРЫ ==========

def handle_instructor_my_bookings(bot, message):
    user_id = message.from_user.id
    with next(get_db()) as db:
        bookings = db.query(InstructorBooking).filter(InstructorBooking.instructor_id == user_id, InstructorBooking.status == 'accepted').all()
        if not bookings:
            safe_send(bot, message.chat.id, "У вас пока нет принятых занятий.", reply_markup=keyboards.instructors_main_menu())
            return
        markup = types.InlineKeyboardMarkup(row_width=1)
        for b in bookings:
            display_id = f"ИНСТР{b.id}"
            markup.add(types.InlineKeyboardButton(f"📋 {display_id} - {b.lesson_date} {b.lesson_time}", callback_data=f'instr_booking_detail_{b.id}'))
        safe_send(bot, message.chat.id, "🎿 *Ваши занятия:*", reply_markup=markup)

def show_instructor_booking_detail(bot, call, booking_id):
    with next(get_db()) as db:
        b = db.query(InstructorBooking).filter_by(id=booking_id).first()
        if not b:
            bot.answer_callback_query(call.id, "❌ Не найдено")
            return
        txt = get_booking_details(db, 'instructor', booking_id)
        client_user = db.query(User).filter_by(id=b.user_id).first()
        if client_user:
            txt += f"\n👤 Клиент: {get_user_link(client_user)}"
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton('❌ Отменить', callback_data=f'instr_cancel_{b.id}'),
                  types.InlineKeyboardButton('📅 Перенести', callback_data=f'instr_reschedule_{b.id}'))
        markup.add(types.InlineKeyboardButton('🔙 К списку', callback_data='instr_back_to_list'))
        safe_send(bot, call.message.chat.id, txt, reply_markup=markup)
        bot.answer_callback_query(call.id)

def handle_instructor_cancel(bot, call, booking_id):
    with next(get_db()) as db:
        b = db.query(InstructorBooking).filter_by(id=booking_id).first()
        if b:
            if hasattr(b, 'group_status') and b.group_status in ['waiting_group', 'group_ready', 'grouped']:
                # Сохраняем данные для уведомлений
                lesson_date = b.lesson_date
                lesson_time = b.lesson_time
                program = b.program
                sport = getattr(b, 'sport', '')
                student_type = getattr(b, 'student_type', '')
                client_name = b.client_name
                client_phone = b.client_phone
                
                b.group_status = None
                b.status = 'cancelled'
                db.commit()
                
                # Находим оставшихся участников
                remaining = db.query(InstructorBooking).filter(
                    InstructorBooking.lesson_date == lesson_date,
                    InstructorBooking.lesson_time == lesson_time,
                    InstructorBooking.program == program,
                    InstructorBooking.sport == sport,
                    InstructorBooking.student_type == student_type,
                    InstructorBooking.status != 'cancelled',
                    InstructorBooking.id != b.id
                ).all()
                
                remaining_count = len(remaining)
                total_group_price = sum(m.total_price or 0 for m in remaining)
                
                # Уведомление клиенту
                user = db.query(User).filter_by(id=b.user_id).first()
                if user and user.user_id:
                    safe_send(bot, user.user_id, f"❌ *Инструктор отменил занятие*\n\n{b.lesson_date} {b.lesson_time}")
                
                # Уведомление инструктору в личку
                members_text = ""
                for i, m in enumerate(remaining, 1):
                    members_text += f"{i}. {m.client_name}, {m.client_phone}\n"
                
                instructor_msg = f"👥 *ИЗМЕНЕНИЕ В ГРУППЕ ({remaining_count} чел)!*\n\n"
                instructor_msg += f"📅 {lesson_date}\n"
                instructor_msg += f"🕒 {lesson_time} — {int(float(lesson_time.split(':')[0]) + 2)}:{lesson_time.split(':')[1]}\n"
                instructor_msg += f"📋 {program}\n"
                instructor_msg += f"🏂 {sport}\n"
                instructor_msg += f"👶 {student_type}\n\n"
                instructor_msg += f"👤 *Участники:*\n{members_text}\n"
                instructor_msg += f"💰 *Общая стоимость:* {int(total_group_price)} руб.\n"
                instructor_msg += f"💸 *Комиссия (10%):* {int(total_group_price * 0.1)} руб.\n"
                instructor_msg += f"\n❌ *Выбыл (отмена инструктором):* {client_name}, {client_phone}"
                
                safe_send(bot, b.instructor_id, instructor_msg)
                
                if MANAGER_CHAT_ID:
                    safe_send(bot, MANAGER_CHAT_ID, instructor_msg)
                
                # Если осталось < 2 человек — уведомление о расформировании
                if remaining_count < 2:
                    disband_msg = f"⚠️ *ГРУППА РАСФОРМИРОВАНА*\n\n📅 {lesson_date}\n🕒 {lesson_time}"
                    safe_send(bot, b.instructor_id, disband_msg)
                    if MANAGER_CHAT_ID:
                        safe_send(bot, MANAGER_CHAT_ID, disband_msg)
                
            else:
                b.status = 'cancelled'
                db.commit()
                details = get_booking_details(db, 'instructor', booking_id)
                user = db.query(User).filter_by(id=b.user_id).first()
                if user and user.user_id:
                    safe_send(bot, user.user_id, f"❌ *Инструктор отменил занятие*\n\n{details}")
                if MANAGER_CHAT_ID:
                    safe_send(bot, MANAGER_CHAT_ID, f"❌ *ИНСТРУКТОР ОТМЕНИЛ ЗАНЯТИЕ*\n\n{details}")
                if INSTRUCTORS_CHAT_ID:
                    safe_send(bot, INSTRUCTORS_CHAT_ID, f"❌ *ЗАНЯТИЕ ОТМЕНЕНО*\n\n{details}")
            
            bot.answer_callback_query(call.id, "✅ Отменено")
            safe_send(bot, call.message.chat.id, f"❌ Занятие отменено.")

def handle_instructor_reschedule_start(bot, call, booking_id):
    StateManager.set_state(call.from_user.id, UserStates.INSTRUCTOR_RESCHEDULE_DATE, StateData(booking_id=booking_id))
    safe_send(bot, call.message.chat.id, "📅 Введите новую дату (ДД.ММ.ГГГГ):", reply_markup=keyboards.back_button())
    bot.answer_callback_query(call.id)

def handle_instructor_reschedule_date(bot, message):
    user_id = message.from_user.id
    if message.text == '🔙 Назад': StateManager.clear_state(user_id); safe_send(bot, message.chat.id, "Отмена.", reply_markup=keyboards.instructors_main_menu()); return
    try:
        datetime.strptime(message.text, "%d.%m.%Y")
        data = StateManager.get_data(user_id)
        data.new_date = message.text
        StateManager.set_state(user_id, UserStates.INSTRUCTOR_RESCHEDULE_TIME, data)
        safe_send(bot, message.chat.id, "🕒 Введите новое время (ЧЧ:ММ):", reply_markup=keyboards.back_button())
    except:
        safe_send(bot, message.chat.id, "❌ Неверный формат даты.")

def handle_instructor_reschedule_time(bot, message):
    user_id = message.from_user.id
    if message.text == '🔙 Назад': StateManager.go_back(user_id); return
    if not re.match(r'^([0-1]?[0-9]|2[0-3]):([0-5][0-9])$', message.text):
        safe_send(bot, message.chat.id, "❌ Неверный формат.")
        return
    data = StateManager.get_data(user_id)
    data.new_time = message.text
    with next(get_db()) as db:
        b = db.query(InstructorBooking).filter_by(id=data.booking_id).first()
        if b:
            details = get_booking_details(db, 'instructor', data.booking_id)
            user = db.query(User).filter_by(id=b.user_id).first()
            if user:
                nd, nt = data.new_date, data.new_time
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton('✅ Согласен', callback_data=f"instr_reschedule_accept_{b.id}_{nd.replace('.','-')}_{nt.replace(':','~')}"),
                          types.InlineKeyboardButton('❌ Отклонить', callback_data=f'instr_reschedule_reject_{b.id}'))
                try:
                    safe_send(bot, user.user_id, f"🔄 *Инструктор хочет перенести занятие*\n\n{details}\n\n*Новая дата:* {nd}\n*Новое время:* {nt}\n\nПодтвердите?", reply_markup=markup)
                    safe_send(bot, message.chat.id, "✅ Запрос отправлен клиенту.")
                except:
                    safe_send(bot, message.chat.id, "❌ Не удалось отправить запрос.")
    StateManager.clear_state(user_id)

def handle_instructor_reschedule_accept(bot, call, booking_id, nd_str, nt_str):
    nd, nt = nd_str.replace('-','.'), nt_str.replace('~',':')
    with next(get_db()) as db:
        b = db.query(InstructorBooking).filter_by(id=booking_id).first()
        if b:
            b.lesson_date, b.lesson_time = nd, nt
            db.commit()
            details = get_booking_details(db, 'instructor', booking_id)
            if b.instructor_id:
                safe_send(bot, b.instructor_id, f"✅ *Клиент подтвердил перенос*\n\n{details}\n\n*Новая дата:* {nd} {nt}")
            if MANAGER_CHAT_ID:
                safe_send(bot, MANAGER_CHAT_ID, f"✅ *ПЕРЕНОС ПОДТВЕРЖДЁН*\n\n{details}\n\nНовая дата: {nd} {nt}")
            bot.edit_message_text("✅ Перенос подтверждён!", chat_id=call.message.chat.id, message_id=call.message.message_id)

def handle_instructor_reschedule_reject(bot, call, booking_id):
    with next(get_db()) as db:
        b = db.query(InstructorBooking).filter_by(id=booking_id).first()
        if b and b.instructor_id:
            details = get_booking_details(db, 'instructor', booking_id)
            safe_send(bot, b.instructor_id, f"❌ *Клиент отклонил перенос*\n\n{details}")
    bot.edit_message_text("❌ Перенос отклонён", chat_id=call.message.chat.id, message_id=call.message.message_id)

# ========== ГИДЫ ==========

def handle_guide_my_bookings(bot, message):
    user_id = message.from_user.id
    with next(get_db()) as db:
        bookings = db.query(ExcursionBooking).filter(ExcursionBooking.guide_id == user_id, ExcursionBooking.status == 'accepted').all()
        if not bookings:
            safe_send(bot, message.chat.id, "У вас пока нет принятых экскурсий.", reply_markup=keyboards.guide_menu_keyboard())
            return
        markup = types.InlineKeyboardMarkup(row_width=1)
        for b in bookings:
            display_id = f"ЭКС{b.id}"
            markup.add(types.InlineKeyboardButton(f"📋 {display_id} - {b.booking_date}", callback_data=f'guide_booking_detail_{b.id}'))
        safe_send(bot, message.chat.id, "🗺️ *Ваши экскурсии:*", reply_markup=markup)

def show_guide_booking_detail(bot, call, booking_id):
    with next(get_db()) as db:
        b = db.query(ExcursionBooking).filter_by(id=booking_id).first()
        if not b:
            bot.answer_callback_query(call.id, "❌ Не найдено")
            return
        txt = get_booking_details(db, 'excursion', booking_id)
        client_user = db.query(User).filter_by(id=b.user_id).first()
        if client_user:
            txt += f"\n👤 Клиент: {get_user_link(client_user)}"
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton('❌ Отменить', callback_data=f'guide_cancel_{b.id}'),
                  types.InlineKeyboardButton('📅 Перенести', callback_data=f'guide_reschedule_{b.id}'))
        markup.add(types.InlineKeyboardButton('🔙 К списку', callback_data='guide_back_to_list'))
        safe_send(bot, call.message.chat.id, txt, reply_markup=markup)
        bot.answer_callback_query(call.id)

def handle_guide_cancel(bot, call, booking_id):
    with next(get_db()) as db:
        b = db.query(ExcursionBooking).filter_by(id=booking_id).first()
        if b:
            # Проверяем, была ли группа
            if b.parent_booking_id:
                parent = db.query(ExcursionBooking).filter_by(id=b.parent_booking_id).first()
                if parent and parent.guide_id:
                    try:
                        from handlers.excursions import send_group_update_notifications
                        send_group_update_notifications(bot, parent, None)
                    except Exception as e:
                        print(f"Ошибка отправки уведомления гиду: {e}")
                    
                    if MANAGER_CHAT_ID:
                        try:
                            members = db.query(ExcursionBooking).filter(
                                ExcursionBooking.parent_booking_id == parent.id,
                                ExcursionBooking.status != 'cancelled'
                            ).all()
                            all_members = [parent] + members
                            members_text = ""
                            total_people = 0
                            for i, m in enumerate(all_members, 1):
                                members_text += f"{i}. {m.client_name}, {m.client_phone}\n"
                                total_people += m.people_count or 0
                            
                            admin_msg = f"❌ *ГИД ОТМЕНИЛ УЧАСТИЕ В ГРУППЕ*\n\n"
                            admin_msg += f"Группа: {parent.booking_id}\n"
                            admin_msg += f"📅 {parent.booking_date}\n"
                            admin_msg += f"🕒 {parent.excursion_start_time or 'не указано'}\n"
                            admin_msg += f"📍 {parent.guide_start_location or 'не указано'}\n"
                            admin_msg += f"👤 *Оставшиеся участники ({len(all_members)}):*\n{members_text}\n"
                            admin_msg += f"Всего человек: {total_people}\n"
                            admin_msg += f"\n❌ *Выбыл (отмена гидом):* {b.client_name}, {b.client_phone}"
                            safe_send(bot, MANAGER_CHAT_ID, admin_msg)
                        except Exception as e:
                            print(f"Ошибка уведомления админа: {e}")
            
            b.status = 'cancelled'
            b.group_status = None
            db.commit()
            details = get_booking_details(db, 'excursion', booking_id)
            client_user = db.query(User).filter_by(id=b.user_id).first()
            if client_user:
                safe_send(bot, client_user.user_id, f"❌ *Гид отменил экскурсию*\n\n{details}")
            if MANAGER_CHAT_ID:
                safe_send(bot, MANAGER_CHAT_ID, f"❌ *ГИД ОТМЕНИЛ ЭКСКУРСИЮ*\n\n{details}")
            if GUIDES_CHAT_ID:
                safe_send(bot, GUIDES_CHAT_ID, f"❌ *ЭКСКУРСИЯ ОТМЕНЕНА*\n\n{details}")
            bot.answer_callback_query(call.id, "✅ Отменено")
            safe_send(bot, call.message.chat.id, f"❌ Экскурсия отменена.\n\n{details}")

def handle_guide_reschedule_start(bot, call, booking_id):
    StateManager.set_state(call.from_user.id, UserStates.GUIDE_RESCHEDULE_DATE, StateData(booking_id=booking_id))
    safe_send(bot, call.message.chat.id, "📅 Введите новую дату (ДД.ММ.ГГГГ):", reply_markup=keyboards.back_button())
    bot.answer_callback_query(call.id)

def handle_guide_reschedule_date(bot, message):
    user_id = message.from_user.id
    if message.text == '🔙 Назад': StateManager.clear_state(user_id); safe_send(bot, message.chat.id, "Отмена.", reply_markup=keyboards.guide_menu_keyboard()); return
    try:
        datetime.strptime(message.text, "%d.%m.%Y")
        data = StateManager.get_data(user_id)
        data.new_date = message.text
        StateManager.set_state(user_id, UserStates.GUIDE_RESCHEDULE_TIME, data)
        safe_send(bot, message.chat.id, "🕒 Введите новое время (ЧЧ:ММ):", reply_markup=keyboards.back_button())
    except:
        safe_send(bot, message.chat.id, "❌ Неверный формат даты.")

def handle_guide_reschedule_time(bot, message):
    user_id = message.from_user.id
    if message.text == '🔙 Назад': StateManager.go_back(user_id); return
    if not re.match(r'^([0-1]?[0-9]|2[0-3]):([0-5][0-9])$', message.text):
        safe_send(bot, message.chat.id, "❌ Неверный формат.")
        return
    data = StateManager.get_data(user_id)
    data.new_time = message.text
    with next(get_db()) as db:
        b = db.query(ExcursionBooking).filter_by(id=data.booking_id).first()
        if b:
            details = get_booking_details(db, 'excursion', data.booking_id)
            user = db.query(User).filter_by(id=b.user_id).first()
            if user:
                nd, nt = data.new_date, data.new_time
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton('✅ Согласен', callback_data=f"guide_reschedule_accept_{b.id}_{nd.replace('.','-')}_{nt.replace(':','~')}"),
                          types.InlineKeyboardButton('❌ Отклонить', callback_data=f'guide_reschedule_reject_{b.id}'))
                try:
                    safe_send(bot, user.user_id, f"🔄 *Гид хочет перенести экскурсию*\n\n{details}\n\n*Новая дата:* {nd}\n*Новое время:* {nt}\n\nПодтвердите?", reply_markup=markup)
                    safe_send(bot, message.chat.id, "✅ Запрос отправлен клиенту.")
                except:
                    safe_send(bot, message.chat.id, "❌ Не удалось отправить запрос.")
    StateManager.clear_state(user_id)

def handle_guide_reschedule_accept(bot, call, booking_id, nd_str, nt_str):
    nd, nt = nd_str.replace('-','.'), nt_str.replace('~',':')
    with next(get_db()) as db:
        b = db.query(ExcursionBooking).filter_by(id=booking_id).first()
        if b:
            b.booking_date = nd
            b.excursion_start_time = nt
            db.commit()
            details = get_booking_details(db, 'excursion', booking_id)
            if b.guide_id:
                safe_send(bot, b.guide_id, f"✅ *Клиент подтвердил перенос*\n\n{details}\n\n*Новая дата:* {nd} {nt}")
            if MANAGER_CHAT_ID:
                safe_send(bot, MANAGER_CHAT_ID, f"✅ *ПЕРЕНОС ПОДТВЕРЖДЁН*\n\n{details}\n\nНовая дата: {nd} {nt}")
            bot.edit_message_text("✅ Перенос подтверждён!", chat_id=call.message.chat.id, message_id=call.message.message_id)

def handle_guide_reschedule_reject(bot, call, booking_id):
    with next(get_db()) as db:
        b = db.query(ExcursionBooking).filter_by(id=booking_id).first()
        if b and b.guide_id:
            details = get_booking_details(db, 'excursion', booking_id)
            safe_send(bot, b.guide_id, f"❌ *Клиент отклонил перенос*\n\n{details}")
    bot.edit_message_text("❌ Перенос отклонён", chat_id=call.message.chat.id, message_id=call.message.message_id)