import telebot
from telebot import types
from config import SBP_PAYMENT_URL, MANAGER_CHAT_ID, YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY
from database import get_db, Payment, User, InstructorBooking, ExcursionBooking, HotelBooking, ShopOrder, Excursion
from datetime import datetime
import logging
from services.payment_service import create_yookassa_payment

logger = logging.getLogger(__name__)


def send_payment_link(bot: telebot.TeleBot, chat_id: int, amount: float, booking_id: str, booking_type: str, user_id: int = None):
    """
    Отправляет пользователю ссылку для оплаты.
    Если YooKassa настроена — создаёт автоматический платёж с суммой.
    Если нет — отправляет ссылку на СБП.
    """
    # Проверяем, настроена ли YooKassa и есть ли сумма
    if YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY and amount > 0:
        # Создаём платёж в YooKassa
        payment_url = create_yookassa_payment(
            amount=amount,
            description=f"{booking_type} {booking_id}",
            order_id=booking_id,
            user_id=user_id or chat_id
        )
        
        if payment_url:
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton(f"💳 Оплатить {int(amount)} руб.", url=payment_url),
                types.InlineKeyboardButton("✅ Я оплатил", callback_data=f'confirm_payment_{booking_type}_{booking_id}')
            )
            bot.send_message(
                chat_id,
                f"💳 *Счёт на оплату*\n\n"
                f"💰 Сумма к оплате: *{int(amount)} руб.*\n"
                f"📋 Номер заказа: `{booking_id}`\n\n"
                f"Нажмите кнопку ниже для оплаты картой или СБП.\n"
                f"После оплаты нажмите 'Я оплатил'.",
                parse_mode='Markdown',
                reply_markup=markup
            )
            return
    
    # Если YooKassa не настроена или сумма 0 — отправляем старую ссылку
    payment_text = (
        f"💳 *Счет на оплату*\n\n"
        f"💰 Сумма к оплате: *{int(amount)} руб.*\n"
        f"📋 Номер заказа: `{booking_id}`\n\n"
        f"Для оплаты по СБП перейдите по ссылке ниже и нажмите кнопку \"Я оплатил\" после подтверждения платежа."
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("💳 Оплатить по СБП", url=SBP_PAYMENT_URL),
        types.InlineKeyboardButton("✅ Я оплатил", callback_data=f'confirm_payment_{booking_type}_{booking_id}')
    )
    try:
        bot.send_message(chat_id, payment_text, parse_mode='Markdown', reply_markup=markup)
        logger.info(f"Payment link sent to user {chat_id} for booking {booking_id}")
    except Exception as e:
        logger.error(f"Failed to send payment link: {e}")


def send_commission_payment_link(bot: telebot.TeleBot, chat_id: int, amount: float, booking_id: str, booking_type: str, user_id: int = None):
    """
    Отправляет ссылку на оплату комиссии (для инструктора/гида).
    """
    # Проверяем, настроена ли YooKassa
    if YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY and amount > 0:
        payment_url = create_yookassa_payment(
            amount=amount,
            description=f"Комиссия {booking_type} {booking_id}",
            order_id=f"commission_{booking_id}",
            user_id=user_id or chat_id
        )
        
        if payment_url:
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton(f"💳 Оплатить комиссию {int(amount)} руб.", url=payment_url),
                types.InlineKeyboardButton("✅ Я оплатил", callback_data=f'commission_paid_{booking_type}_{booking_id}')
            )
            bot.send_message(
                chat_id,
                f"💰 *Оплата комиссии*\n\n"
                f"💸 Сумма комиссии: *{int(amount)} руб.*\n"
                f"📋 Номер заказа: `{booking_id}`\n\n"
                f"Нажмите кнопку ниже для оплаты.",
                parse_mode='Markdown',
                reply_markup=markup
            )
            return
    
    # Если YooKassa не настроена — отправляем ссылку на СБП
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton('💳 Оплатить комиссию', url=SBP_PAYMENT_URL),
        types.InlineKeyboardButton('✅ Я оплатил', callback_data=f'commission_paid_{booking_type}_{booking_id}')
    )
    bot.send_message(
        chat_id,
        f"💰 *Оплата комиссии*\n\n"
        f"💸 Сумма комиссии: *{int(amount)} руб.*\n"
        f"📋 Номер заказа: `{booking_id}`\n\n"
        f"Оплатите по ссылке и нажмите 'Я оплатил'.",
        parse_mode='Markdown',
        reply_markup=markup
    )


def handle_payment_confirmation(bot: telebot.TeleBot, call: telebot.types.CallbackQuery):
    """Обработчик подтверждения оплаты от пользователя."""
    data_parts = call.data.split('_')
    booking_type = data_parts[2]
    booking_id = '_'.join(data_parts[3:])
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    with next(get_db()) as db:
        try:
            user = db.query(User).filter_by(user_id=user_id).first()
            if not user:
                bot.answer_callback_query(call.id, "❌ Пользователь не найден", show_alert=True)
                return

            payment = Payment(
                user_id=user.id,
                booking_type=booking_type,
                booking_id=booking_id,
                amount=0,
                payment_method='yookassa',
                status='pending',
                transaction_id=f"yookassa_{datetime.now().timestamp()}"
            )
            db.add(payment)
            db.flush()

            payment.status = 'completed'

            if booking_type == 'hotel':
                booking = db.query(HotelBooking).filter_by(booking_id=booking_id).first()
                if booking:
                    booking.payment_status = 'paid'
                    booking.status = 'confirmed'
                    payment.amount = booking.total_price
            elif booking_type == 'instructor':
                booking = db.query(InstructorBooking).filter_by(booking_id=booking_id).first()
                if booking:
                    booking.payment_status = 'paid'
                    payment.amount = booking.total_price
            elif booking_type == 'excursion':
                booking = db.query(ExcursionBooking).filter_by(booking_id=booking_id).first()
                if booking:
                    booking.payment_status = 'paid'
                    booking.status = 'confirmed'
                    payment.amount = booking.total_price
            elif booking_type == 'shop':
                booking = db.query(ShopOrder).filter_by(order_id=booking_id).first()
                if booking:
                    booking.payment_status = 'paid'
                    payment.amount = booking.total_price
                    if booking.product and booking.product.category == 'digital':
                        bot.send_message(
                            chat_id,
                            f"📎 *Ваш цифровой товар*\n\nСсылка для скачивания: {booking.product.file_url}",
                            parse_mode='Markdown'
                        )

            db.commit()

            try:
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=call.message.message_id,
                    text=f"✅ *Оплата подтверждена!*\n\nСпасибо! Ваш платеж на сумму *{int(payment.amount)} руб.* прошел успешно.",
                    parse_mode='Markdown'
                )
            except Exception:
                bot.send_message(
                    chat_id,
                    f"✅ *Оплата подтверждена!*\n\nСпасибо! Ваш платеж на сумму *{int(payment.amount)} руб.* прошел успешно.",
                    parse_mode='Markdown'
                )

            # Уведомление менеджеру
            if MANAGER_CHAT_ID:
                if booking_type == 'hotel' and booking:
                    manager_text = f"🏨 *ОПЛАЧЕНА БРОНЬ ОТЕЛЯ*\n*Номер:* {booking.booking_id}\n*Клиент:* {booking.name} ({booking.phone})\n*Сумма:* {int(booking.total_price)} руб."
                    bot.send_message(MANAGER_CHAT_ID, manager_text, parse_mode='Markdown')
                elif booking_type == 'excursion' and booking:
                    excursion = db.query(Excursion).filter_by(id=booking.excursion_id).first()
                    manager_text = f"🗺️ *ОПЛАЧЕНА ЭКСКУРСИЯ*\n*Номер:* {booking.booking_id}\n*Экскурсия:* {excursion.name if excursion else 'Не указана'}\n*Клиент:* {booking.client_name} ({booking.client_phone})\n*Сумма:* {int(booking.total_price)} руб."
                    bot.send_message(MANAGER_CHAT_ID, manager_text, parse_mode='Markdown')
                elif booking_type == 'instructor' and booking:
                    manager_text = f"🎿 *ОПЛАЧЕНО ЗАНЯТИЕ С ИНСТРУКТОРОМ*\n*Номер:* {booking.booking_id}\n*Клиент:* {booking.client_name} ({booking.client_phone})\n*Сумма:* {int(booking.total_price)} руб."
                    bot.send_message(MANAGER_CHAT_ID, manager_text, parse_mode='Markdown')

            bot.answer_callback_query(call.id, "✅ Оплата подтверждена!")

        except Exception as e:
            logger.error(f"Error in payment confirmation: {e}", exc_info=True)
            db.rollback()
            bot.answer_callback_query(call.id, "❌ Ошибка при подтверждении оплаты", show_alert=True)


def handle_commission_paid(bot: telebot.TeleBot, call: telebot.types.CallbackQuery):
    """Обработчик подтверждения оплаты комиссии от инструктора/гида."""
    data_parts = call.data.split('_')
    booking_type = data_parts[2]
    booking_id = data_parts[3]
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    with next(get_db()) as db:
        try:
            user = db.query(User).filter_by(user_id=user_id).first()
            if not user:
                bot.answer_callback_query(call.id, "❌ Пользователь не найден", show_alert=True)
                return

            # Находим бронирование
            if booking_type == 'excursion':
                booking = db.query(ExcursionBooking).filter_by(booking_id=booking_id).first()
                if booking:
                    commission_amount = booking.total_price * 5 / 100  # 5% комиссия
                    booking.payment_status = 'commission_paid'
                    db.commit()
                    
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=call.message.message_id,
                        text=f"✅ *Комиссия оплачена!*\n\nСпасибо!",
                        parse_mode='Markdown'
                    )
                    
                    if MANAGER_CHAT_ID:
                        manager_text = f"💰 *КОМИССИЯ ОПЛАЧЕНА*\n*Экскурсия:* {booking.booking_id}\n*Сумма:* {int(commission_amount)} руб."
                        bot.send_message(MANAGER_CHAT_ID, manager_text, parse_mode='Markdown')
                    
                    bot.answer_callback_query(call.id, "✅ Комиссия оплачена!")

            elif booking_type == 'instructor':
                booking = db.query(InstructorBooking).filter_by(booking_id=booking_id).first()
                if booking:
                    commission_amount = booking.total_price * 10 / 100  # 10% комиссия
                    booking.payment_status = 'commission_paid'
                    db.commit()
                    
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=call.message.message_id,
                        text=f"✅ *Комиссия оплачена!*\n\nСпасибо!",
                        parse_mode='Markdown'
                    )
                    
                    if MANAGER_CHAT_ID:
                        manager_text = f"💰 *КОМИССИЯ ОПЛАЧЕНА*\n*Занятие:* {booking.booking_id}\n*Сумма:* {int(commission_amount)} руб."
                        bot.send_message(MANAGER_CHAT_ID, manager_text, parse_mode='Markdown')
                    
                    bot.answer_callback_query(call.id, "✅ Комиссия оплачена!")

        except Exception as e:
            logger.error(f"Error in commission payment: {e}", exc_info=True)
            db.rollback()
            bot.answer_callback_query(call.id, "❌ Ошибка при оплате комиссии", show_alert=True)