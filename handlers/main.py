import telebot
from telebot import types
from database import get_db, User, UserState, Setting
from states import UserStates, StateData
import keyboards
import json

def handle_start(bot, message):
    """Обработка команды /start"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    with next(get_db()) as db:
        # Проверяем, есть ли пользователь в базе
        user = db.query(User).filter_by(user_id=user_id).first()
        
        if not user:
            # Регистрируем нового пользователя
            user = User(
                user_id=user_id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name
            )
            db.add(user)
            db.commit()
            db.refresh(user) # Обновляем объект, чтобы получить ID
            
        # ВСЕГДА проверяем и назначаем админа для нужного ID
        if user_id == 6091836352 and not user.is_admin:
            user.is_admin = True
            db.commit()
            print(f"✅ Пользователь {user_id} назначен администратором")
        
        # Создаем состояние пользователя
        state = db.query(UserState).filter_by(user_id=user_id).first()
        if not state:
            state = UserState(
                user_id=user_id,
                state=UserStates.MAIN_MENU.value,
                data=json.dumps({}),
                previous_state=None,
                previous_data=None
            )
            db.add(state)
        else:
            state.state = UserStates.MAIN_MENU.value
            state.data = json.dumps({})
        db.commit()
    
    welcome_text = """
🎿 *Добро пожаловать в "Хибины"!*

Здесь вы можете:

🏨 Забронировать Бабл-Отель
🎿 Найти инструктора или гида
🗺️ Заказать экскурсию или тур по Кольскому
🧊 Присоединиться к экспедиции в Арктику
🛒 Купить товары Севера и методички

Выберите нужный раздел:
"""
    
    bot.send_message(
        chat_id,
        welcome_text,
        parse_mode='Markdown',
        reply_markup=keyboards.main_menu()
    )

def handle_main_menu(bot, message):
    """Обработка главного меню"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '🏨 Бабл Отель':
        from handlers.hotel import handle_hotel_start
        handle_hotel_start(bot, message)
    
    elif message.text == '🎿 Инструкторы':
        from handlers.instructors import handle_instructors_start
        handle_instructors_start(bot, message)
    
    elif message.text == '🗺️ Экскурсии':
        from handlers.excursions import handle_excursions_start
        handle_excursions_start(bot, message)
    
    elif message.text == '🧊 Экспедиции':
        from handlers.expeditions import handle_expeditions_start
        handle_expeditions_start(bot, message)
    
    elif message.text == '🛒 Магазин':
        from handlers.shop import handle_shop_start
        handle_shop_start(bot, message)
    
    elif message.text == '📋 Мои заказы':
        from handlers.orders import handle_orders_start
        handle_orders_start(bot, message)
    
    elif message.text == '✉️ Написать менеджеру':
        handle_write_manager(bot, message)
    
    elif message.text == '👑 Админка':
        # Скрытая кнопка админки, показывается только админам
        handle_admin_access(bot, message)

def handle_write_manager(bot, message):
    """Обработка 'Написать менеджеру'"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    from config import MANAGER_CHAT_ID
    
    if not MANAGER_CHAT_ID:
        bot.send_message(
            chat_id,
            "❌ Менеджер пока не доступен. Пожалуйста, попробуйте позже.",
            reply_markup=keyboards.main_menu()
        )
        return
    
    # Сохраняем состояние
    from state_manager import StateManager
    StateManager.set_state(user_id, UserStates.WRITE_MANAGER, 
                          StateData(manager_chat_id=MANAGER_CHAT_ID))
    
    bot.send_message(
        chat_id,
        "✍️ *Напишите ваше сообщение менеджеру:*\n\n"
        "Опишите ваш вопрос или проблему. Я перешлю его менеджеру, и он ответит вам в ближайшее время.\n\n"
        "Для отмены нажмите ❌ Отмена",
        parse_mode='Markdown',
        reply_markup=keyboards.cancel_button()
    )

def handle_manager_message(bot, message):
    """Пересылка сообщения менеджеру"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    from state_manager import StateManager
    state = StateManager.get_state(user_id)
    
    if state != UserStates.WRITE_MANAGER:
        bot.send_message(chat_id, "Пожалуйста, используйте кнопку 'Написать менеджеру' из меню.")
        return
    
    data = StateManager.get_data(user_id)
    manager_chat_id = data.manager_chat_id if hasattr(data, 'manager_chat_id') else None
    
    if not manager_chat_id:
        bot.send_message(chat_id, "❌ Менеджер не доступен.")
        StateManager.clear_state(user_id)
        bot.send_message(chat_id, "Возвращаемся в главное меню:", 
                         reply_markup=keyboards.main_menu())
        return
    
    if message.text == '❌ Отмена':
        StateManager.clear_state(user_id)
        bot.send_message(
            chat_id,
            "Действие отменено. Возвращаемся в главное меню:",
            reply_markup=keyboards.main_menu()
        )
        return
    
    # Формируем информацию о пользователе
    with next(get_db()) as db:
        user = db.query(User).filter_by(user_id=user_id).first()
        user_info = f"👤 Пользователь: {user.first_name or ''} {user.last_name or ''}\n"
        if user.username:
            user_info += f"🔗 @{user.username}\n"
        if user.phone:
            user_info += f"📞 Телефон: {user.phone}\n"
        user_info += f"🆔 ID: {user_id}"
    
    # Пересылаем сообщение менеджеру
    try:
        bot.send_message(
            manager_chat_id,
            f"📩 *Новое сообщение от пользователя*\n\n"
            f"{user_info}\n\n"
            f"💬 *Сообщение:*\n{message.text}",
            parse_mode='Markdown'
        )
        
        bot.send_message(
            chat_id,
            "✅ Ваше сообщение успешно отправлено менеджеру! Он ответит вам в ближайшее время.\n\n"
            "Возвращаемся в главное меню:",
            reply_markup=keyboards.main_menu()
        )
        
    except Exception as e:
        bot.send_message(
            chat_id,
            f"❌ Ошибка при отправке сообщения. Пожалуйста, попробуйте позже.\nОшибка: {str(e)}",
            reply_markup=keyboards.main_menu()
        )
    
    # Возвращаем в главное меню
    StateManager.clear_state(user_id)

def handle_admin_access(bot, message):
    """Проверка доступа к админке"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверяем, является ли пользователь администратором
    with next(get_db()) as db:
        user = db.query(User).filter_by(user_id=user_id).first()
        
        if user and user.is_admin:
            # Пользователь администратор - открываем админку
            from handlers.admin import handle_admin_start
            handle_admin_start(bot, message)
        else:
            # Пользователь не администратор - скрываем кнопку
            bot.send_message(
                chat_id,
                "Возвращаемся в главное меню:",
                reply_markup=keyboards.main_menu()
            )