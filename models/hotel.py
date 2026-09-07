from telebot import types
from datetime import datetime, timedelta
import uuid
from utils.calendar import HotelCalendar

class HotelModule:
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db
        self.calendar = HotelCalendar()
    
    def start_hotel_booking(self, message):
        # Описание и цена отеля
        price_per_night = int(self.db.get_setting('hotel_price_per_night') or 10000)
        check_in = self.db.get_setting('hotel_check_in') or '14:00'
        check_out = self.db.get_setting('hotel_check_out') or '12:00'
        
        response = f"""
🏨 <b>Бабл Отель</b>

Цена: {price_per_night} руб./сутки
Заезд: с {check_in}
Выезд: до {check_out}

Для бронирования выберите даты заезда и выезда.
        """
        
        # Получаем заблокированные даты
        blocked_dates = self.db.get_blocked_dates()
        self.calendar.blocked_dates = blocked_dates
        
        markup = self.calendar.create_calendar()
        
        self.bot.send_message(
            message.chat.id,
            response,
            reply_markup=markup,
            parse_mode='HTML'
        )
    
    def handle_calendar_callback(self, call):
        data = call.data
        
        if data.startswith('date_'):
            # Пользователь выбрал дату
            date_str = data.split('_')[1]
            self.process_date_selection(call, date_str)
        
        elif data.startswith('nav_'):
            # Навигация по месяцам
            _, year, month = data.split('_')
            year, month = int(year), int(month)
            
            blocked_dates = self.db.get_blocked_dates()
            self.calendar.blocked_dates = blocked_dates
            
            markup = self.calendar.create_calendar(year, month)
            
            self.bot.edit_message_reply_markup(
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
        
        elif data == 'cancel_calendar':
            self.bot.send_message(
                call.message.chat.id,
                "Бронирование отменено.",
                reply_markup=self.get_main_menu()
            )
        
        self.bot.answer_callback_query(call.id)
    
    def process_date_selection(self, call, date_str):
        user_id = call.from_user.id
        state = self.db.get_user_state(user_id)
        
        if not state:
            state = {'state_data': {}}
        
        state_data = state['state_data']
        
        if 'check_in' not in state_data:
            # Выбор даты заезда
            state_data['check_in'] = date_str
            
            # Обновляем сообщение
            self.bot.edit_message_text(
                f"Выбрана дата заезда: {date_str}\n\n"
                f"Теперь выберите дату выезда:",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=self.calendar.create_calendar()
            )
            
            # Сохраняем состояние
            self.db.save_user_state(user_id, state_data, '🏨 Бабл Отель')
        
        else:
            # Выбор даты выезда
            check_in = datetime.strptime(state_data['check_in'], '%Y-%m-%d')
            check_out = datetime.strptime(date_str, '%Y-%m-%d')
            
            if check_out <= check_in:
                self.bot.answer_callback_query(
                    call.id,
                    "❌ Дата выезда должна быть позже даты заезда!",
                    show_alert=True
                )
                return
            
            # Расчет количества ночей
            nights = (check_out - check_in).days
            
            # Расчет стоимости
            price_per_night = int(self.db.get_setting('hotel_price_per_night') or 10000)
            total_price = nights * price_per_night
            
            state_data['check_out'] = date_str
            state_data['nights'] = nights
            state_data['total_price'] = total_price
            
            # Запрашиваем имя
            self.bot.edit_message_text(
                f"📅 Даты бронирования:\n"
                f"Заезд: {state_data['check_in']}\n"
                f"Выезд: {state_data['check_out']}\n"
                f"Ночей: {nights}\n"
                f"💰 Стоимость: {total_price} руб.\n\n"
                f"Введите ваше имя:",
                call.message.chat.id,
                call.message.message_id
            )
            
            # Сохраняем состояние и переходим к следующему шагу
            state_data['step'] = 'ask_name'
            self.db.save_user_state(user_id, state_data, '🏨 Бабл Отель')
    
    def handle_text_input(self, message):
        user_id = message.from_user.id
        state = self.db.get_user_state(user_id)
        
        if not state or '🏨 Бабл Отель' not in state['last_command']:
            return
        
        state_data = state['state_data']
        
        if state_data.get('step') == 'ask_name':
            # Сохраняем имя
            state_data['name'] = message.text
            state_data['step'] = 'ask_phone'
            
            # Запрашиваем телефон
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add(types.KeyboardButton("📞 Отправить телефон", request_contact=True))
            markup.add(types.KeyboardButton("◀️ Назад"))
            
            self.bot.send_message(
                message.chat.id,
                "Введите ваш номер телефона или нажмите кнопку ниже:",
                reply_markup=markup
            )
            
            self.db.save_user_state(user_id, state_data, '🏨 Бабл Отель')
        
        elif state_data.get('step') == 'ask_phone':
            # Сохраняем телефон
            state_data['phone'] = message.text
            
            # Создаем бронирование
            self.create_booking(message, state_data)
    
    def create_booking(self, message, booking_data):
        user_id = message.from_user.id
        user = self.db.get_user(user_id)
        
        # Генерируем ID бронирования
        booking_id = f"HOTEL-{uuid.uuid4().hex[:8].upper()}"
        
        # Сохраняем в БД
        db_booking_data = {
            'booking_id': booking_id,
            'user_id': user['id'],
            'check_in': booking_data['check_in'],
            'check_out': booking_data['check_out'],
            'nights': booking_data['nights'],
            'total_price': booking_data['total_price']
        }
        
        booking_db_id = self.db.create_hotel_booking(db_booking_data)
        
        # Отправляем подтверждение пользователю
        self.bot.send_message(
            message.chat.id,
            f"✅ Бронирование создано!\n\n"
            f"🏨 Бабл Отель\n"
            f"🆔 ID: {booking_id}\n"
            f"📅 Даты: {booking_data['check_in']} - {booking_data['check_out']}\n"
            f"🛏️ Ночей: {booking_data['nights']}\n"
            f"👤 Имя: {booking_data['name']}\n"
            f"📞 Телефон: {booking_data['phone']}\n"
            f"💰 Сумма: {booking_data['total_price']} руб.\n\n"
            f"Ожидайте ссылку на оплату от менеджера.",
            reply_markup=self.get_main_menu()
        )
        
        # Отправляем уведомление менеджеру
        self.notify_manager(booking_id, booking_data, user)
        
        # Очищаем состояние
        self.db.delete_user_state(user_id)
    
    def notify_manager(self, booking_id, booking_data, user):
        manager_chat_id = self.db.get_setting('admin_chat_id')
        if not manager_chat_id:
            return
        
        message = f"🏨 <b>НОВОЕ БРОНИРОВАНИЕ ОТЕЛЯ</b>\n\n"
        message += f"🆔 ID: {booking_id}\n"
        message += f"👤 Клиент: {user['first_name']}"
        if user['username']:
            message += f" (@{user['username']})"
        message += f"\n📞 Телефон: {booking_data.get('phone', 'не указан')}\n"
        message += f"📅 Даты: {booking_data['check_in']} - {booking_data['check_out']}\n"
        message += f"🛏️ Ночей: {booking_data['nights']}\n"
        message += f"💰 Сумма: {booking_data['total_price']} руб.\n\n"
        
        # Кнопки для менеджера
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("💳 Отправить счет", callback_data=f"hotel_send_bill_{booking_id}"),
            types.InlineKeyboardButton("❌ Отменить", callback_data=f"hotel_cancel_{booking_id}")
        )
        
        try:
            self.bot.send_message(
                manager_chat_id,
                message,
                reply_markup=markup,
                parse_mode='HTML'
            )
        except Exception as e:
            print(f"Ошибка отправки менеджеру: {e}")
    
    def handle_back(self, message):
        user_id = message.from_user.id
        state = self.db.get_user_state(user_id)
        
        if not state:
            self.bot.send_message(
                message.chat.id,
                "Главное меню:",
                reply_markup=self.get_main_menu()
            )
            return
        
        state_data = state['state_data']
        
        if state_data.get('step') == 'ask_phone':
            # Возвращаемся к вводу имени
            state_data['step'] = 'ask_name'
            
            self.bot.send_message(
                message.chat.id,
                "Введите ваше имя:"
            )
            
            self.db.save_user_state(user_id, state_data, '🏨 Бабл Отель')
        
        elif state_data.get('step') == 'ask_name':
            # Возвращаемся к календарю
            state_data.pop('step', None)
            state_data.pop('name', None)
            
            blocked_dates = self.db.get_blocked_dates()
            self.calendar.blocked_dates = blocked_dates
            markup = self.calendar.create_calendar()
            
            self.bot.send_message(
                message.chat.id,
                "Выберите дату заезда:",
                reply_markup=markup
            )
            
            self.db.save_user_state(user_id, state_data, '🏨 Бабл Отель')
    
    def get_main_menu(self):
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(
            types.KeyboardButton('🏨 Бабл Отель'),
            types.KeyboardButton('🎿 Инструкторы'),
            types.KeyboardButton('🗺️ Экскурсии'),
            types.KeyboardButton('🧊 Экспедиции в Арктику'),
            types.KeyboardButton('🛒 Магазин'),
            types.KeyboardButton('📋 Мои заказы'),
            types.KeyboardButton('✉️ Написать менеджеру')
        )
        return markup