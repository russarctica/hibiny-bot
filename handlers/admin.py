import telebot
from telebot import types
import json
from datetime import datetime, timedelta
import re
from decimal import Decimal
from database import get_db, User, HotelBooking, BlockedDate, Setting, \
    InstructorBooking, InstructorOffer, Excursion, Guide, Expedition, \
    ShopProduct, ShopOrder, PromoOffer, BroadcastMessage, DailyReport, \
    ExcursionBooking, ExcursionOffer, ExpeditionBooking
from state_manager import StateManager
from states import UserStates, StateData
import keyboards
from config import MANAGER_CHAT_ID
from sqlalchemy import func

# ========== ОСНОВНЫЕ ФУНКЦИИ АДМИНКИ ==========

def handle_admin_start(bot, message):
    """Вход в админку"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    with next(get_db()) as db:
        # Проверяем, является ли пользователь администратором
        user = db.query(User).filter_by(user_id=user_id).first()
        if not user or not user.is_admin:
            bot.send_message(
                chat_id,
                "❌ У вас нет доступа к админке!",
                reply_markup=keyboards.main_menu()
            )
            return
    
    # Сохраняем состояние
    StateManager.set_state(user_id, UserStates.ADMIN_MAIN, StateData())
    
    # Отправляем меню админки
    bot.send_message(
        chat_id,
        "👑 *АДМИН-ПАНЕЛЬ*\n\n"
        "Выберите раздел для управления:",
        parse_mode='Markdown',
        reply_markup=keyboards.admin_main_menu()
    )

def handle_admin_states(bot, message):
    """Обработка состояний админки"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    state = StateManager.get_state(user_id)
    
    # Если пользователь нажимает "Назад" из главного меню админки
    if message.text == '🔙 Выход из админки':
        StateManager.clear_state(user_id)
        bot.send_message(
            chat_id,
            "Выход из админки. Возвращаемся в главное меню:",
            reply_markup=keyboards.main_menu()
        )
        return
    
    # Если пользователь нажимает "Назад" из подменю админки
    if message.text == '🔙 Назад в админку':
        StateManager.set_state(user_id, UserStates.ADMIN_MAIN, StateData())
        bot.send_message(
            chat_id,
            "👑 *АДМИН-ПАНЕЛЬ*\n\n"
            "Выберите раздел для управления:",
            parse_mode='Markdown',
            reply_markup=keyboards.admin_main_menu()
        )
        return
    
    # Главное меню админки
    if state == UserStates.ADMIN_MAIN:
        if message.text == '🏨 Управление отелем':
            handle_admin_hotel_menu(bot, message)
        elif message.text == '🎿 Управление инструкторами':
            handle_admin_instructors_menu(bot, message)
        elif message.text == '🗺️ Управление экскурсиями':
            handle_admin_excursions_menu(bot, message)
        elif message.text == '🧊 Управление экспедициями':
            handle_admin_expeditions_menu(bot, message)
        elif message.text == '🛒 Управление магазином':
            handle_admin_shop_menu(bot, message)
        elif message.text == '📊 Статистика и отчеты':
            handle_admin_statistics_menu(bot, message)
        elif message.text == '📢 Рассылки и предложения':
            handle_admin_broadcast_menu(bot, message)
    
    # Меню управления отелем
    elif state == UserStates.ADMIN_HOTEL:
        if message.text == '📅 Заблокировать дату':
            handle_admin_block_date(bot, message)
        elif message.text == '✅ Разблокировать дату':
            handle_admin_unblock_date(bot, message)
        elif message.text == '📋 Все бронирования':
            handle_admin_view_bookings(bot, message)
        elif message.text == '❌ Отменить бронирование':
            handle_admin_cancel_booking(bot, message)
    
    # Меню управления инструкторами
    elif state == UserStates.ADMIN_INSTRUCTORS:
        if message.text == '💰 Настройка цен':
            handle_admin_price_settings(bot, message)
        elif message.text == '📋 Список инструкторов':
            handle_admin_instructors_list(bot, message)
        elif message.text == '📊 Статистика инструктора':
            handle_admin_instructor_stats(bot, message)
        elif message.text == '❌ Отменить заказ':
            handle_admin_cancel_instructor_booking(bot, message)
    
    # Меню настройки цен инструкторов
    elif state == UserStates.ADMIN_PRICE_SETTINGS:
        if message.text == '📝 Изменить базовую цену':
            handle_admin_set_price_base(bot, message)
        elif message.text == '📝 Изменить цену для детей':
            handle_admin_set_price_child(bot, message)
        elif message.text == '📝 Изменить цену фрирайда':
            handle_admin_set_price_freeride(bot, message)
        elif message.text == '📝 Изменить цену карвинга':
            handle_admin_set_price_carving(bot, message)
        elif message.text == '📝 Изменить скидку группы':
            handle_admin_set_discount_group(bot, message)
        elif message.text == '📝 Изменить комиссию':
            handle_admin_set_commission(bot, message)
    
    # Меню управления экскурсиями
    elif state == UserStates.ADMIN_EXCURSIONS:
        if message.text == '➕ Добавить экскурсию':
            handle_admin_add_excursion(bot, message)
        elif message.text == '📋 Список экскурсий':
            handle_admin_excursions_list(bot, message)
        elif message.text == '✏️ Редактировать экскурсию':
            handle_admin_edit_excursion(bot, message)
        elif message.text == '💰 Настройка цен':
            handle_admin_excursion_price_settings(bot, message)
    
    # Меню управления экспедициями
    elif state == UserStates.ADMIN_EXPEDITIONS:
        if message.text == '➕ Добавить экспедицию':
            handle_admin_add_expedition(bot, message)
        elif message.text == '📋 Список экспедиций':
            handle_admin_expeditions_list(bot, message)
        elif message.text == '✏️ Редактировать экспедицию':
            handle_admin_edit_expedition(bot, message)
        elif message.text == '✅ Подтвердить оплату':
            handle_admin_confirm_expedition_payment(bot, message)
    
    # Меню управления магазином
    elif state == UserStates.ADMIN_SHOP:
        if message.text == '➕ Добавить товар':
            handle_admin_add_product(bot, message)
        elif message.text == '📋 Список товаров':
            handle_admin_products_list(bot, message)
        elif message.text == '✏️ Редактировать товар':
            handle_admin_edit_product(bot, message)
        elif message.text == '📦 Управление заказами':
            handle_admin_view_orders(bot, message)
    
    # Меню статистики
    elif state == UserStates.ADMIN_STATISTICS:
        if message.text == '📊 Отчет за сегодня':
            handle_admin_stats_daily(bot, message)
        elif message.text == '📈 Отчет за неделю':
            handle_admin_stats_weekly(bot, message)
        elif message.text == '📉 Отчет за месяц':
            handle_admin_stats_monthly(bot, message)
        elif message.text == '💰 Финансовая статистика':
            handle_admin_stats_financial(bot, message)
    
    # Меню рассылок
    elif state == UserStates.ADMIN_BROADCAST:
        if message.text == '📢 Создать рассылку':
            handle_admin_create_broadcast(bot, message)
        elif message.text == '🎁 Создать промо-предложение':
            handle_admin_create_promo(bot, message)
        elif message.text == '📋 Список предложений':
            handle_admin_promo_list(bot, message)
    
    # Обработка ввода данных для админки
    elif state.value.startswith('admin_'):
        handle_admin_input(bot, message)

def handle_admin_input(bot, message):
    """Обработка ввода данных в админке"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    state = StateManager.get_state(user_id)
    data = StateManager.get_data(user_id)
    
    # ========== БЛОКИРОВКА ДАТЫ ОТЕЛЯ ==========
    if state == UserStates.ADMIN_BLOCK_DATE:
        handle_admin_block_date_input(bot, message)
    
    # ========== РАЗБЛОКИРОВКА ДАТЫ ОТЕЛЯ ==========
    elif state == UserStates.ADMIN_UNBLOCK_DATE:
        handle_admin_unblock_date_input(bot, message)
    
    # ========== ОТМЕНА БРОНИРОВАНИЯ ОТЕЛЯ ==========
    elif state == UserStates.ADMIN_CANCEL_BOOKING:
        handle_admin_cancel_booking_input(bot, message)
    
    # ========== НАСТРОЙКА ЦЕН ИНСТРУКТОРОВ ==========
    elif state == UserStates.ADMIN_SET_PRICE_BASE:
        handle_admin_set_price_base_input(bot, message)
    elif state == UserStates.ADMIN_SET_PRICE_CHILD:
        handle_admin_set_price_child_input(bot, message)
    elif state == UserStates.ADMIN_SET_PRICE_FREERIDE:
        handle_admin_set_price_freeride_input(bot, message)
    elif state == UserStates.ADMIN_SET_PRICE_CARVING:
        handle_admin_set_price_carving_input(bot, message)
    elif state == UserStates.ADMIN_SET_DISCOUNT_GROUP:
        handle_admin_set_discount_group_input(bot, message)
    elif state == UserStates.ADMIN_SET_COMMISSION:
        handle_admin_set_commission_input(bot, message)
    
    # ========== СТАТИСТИКА ИНСТРУКТОРА ==========
    elif state == UserStates.ADMIN_INSTRUCTOR_STATS:
        handle_admin_instructor_stats_input(bot, message)
    
    # ========== ДОБАВЛЕНИЕ ЭКСКУРСИИ ==========
    elif state == UserStates.ADMIN_ADD_EXCURSION_NAME:
        handle_admin_add_excursion_name_input(bot, message)
    elif state == UserStates.ADMIN_ADD_EXCURSION_DESC:
        handle_admin_add_excursion_desc_input(bot, message)
    elif state == UserStates.ADMIN_ADD_EXCURSION_PRICE:
        handle_admin_add_excursion_price_input(bot, message)
    elif state == UserStates.ADMIN_ADD_EXCURSION_MIN_PEOPLE:
        handle_admin_add_excursion_min_people_input(bot, message)
    elif state == UserStates.ADMIN_ADD_EXCURSION_MAX_PEOPLE:
        handle_admin_add_excursion_max_people_input(bot, message)
    elif state == UserStates.ADMIN_ADD_EXCURSION_DURATION:
        handle_admin_add_excursion_duration_input(bot, message)
    
    # ========== РЕДАКТИРОВАНИЕ ЭКСКУРСИИ ==========
    elif state == UserStates.ADMIN_EDIT_EXCURSION:
        handle_admin_edit_excursion_input(bot, message)
    elif state == UserStates.ADMIN_EDIT_EXCURSION_DETAILS:
        handle_admin_edit_excursion_details_input(bot, message)
    
    # ========== НАСТРОЙКА ЦЕН ЭКСКУРСИЙ ==========
    elif state == UserStates.ADMIN_SET_GUIDE_COMMISSION:
        handle_admin_set_guide_commission_input(bot, message)
    
    # ========== ДОБАВЛЕНИЕ ЭКСПЕДИЦИИ ==========
    elif state == UserStates.ADMIN_ADD_EXPEDITION_NAME:
        handle_admin_add_expedition_name_input(bot, message)
    elif state == UserStates.ADMIN_ADD_EXPEDITION_DESC:
        handle_admin_add_expedition_desc_input(bot, message)
    elif state == UserStates.ADMIN_ADD_EXPEDITION_PROGRAM:
        handle_admin_add_expedition_program_input(bot, message)
    elif state == UserStates.ADMIN_ADD_EXPEDITION_INCLUDED:
        handle_admin_add_expedition_included_input(bot, message)
    elif state == UserStates.ADMIN_ADD_EXPEDITION_PRICE:
        handle_admin_add_expedition_price_input(bot, message)
    elif state == UserStates.ADMIN_ADD_EXPEDITION_START_DATE:
        handle_admin_add_expedition_start_date_input(bot, message)
    elif state == UserStates.ADMIN_ADD_EXPEDITION_END_DATE:
        handle_admin_add_expedition_end_date_input(bot, message)
    elif state == UserStates.ADMIN_ADD_EXPEDITION_MAX_PEOPLE:
        handle_admin_add_expedition_max_people_input(bot, message)
    
    # ========== РЕДАКТИРОВАНИЕ ЭКСПЕДИЦИИ ==========
    elif state == UserStates.ADMIN_EDIT_EXPEDITION:
        handle_admin_edit_expedition_input(bot, message)
    elif state == UserStates.ADMIN_EDIT_EXPEDITION_DETAILS:
        handle_admin_edit_expedition_details_input(bot, message)
    
    # ========== ПОДТВЕРЖДЕНИЕ ОПЛАТЫ ЭКСПЕДИЦИИ ==========
    elif state == UserStates.ADMIN_CONFIRM_EXPEDITION_PAYMENT:
        handle_admin_confirm_expedition_payment_input(bot, message)
    
    # ========== ДОБАВЛЕНИЕ ТОВАРА ==========
    elif state == UserStates.ADMIN_ADD_PRODUCT_NAME:
        handle_admin_add_product_name_input(bot, message)
    elif state == UserStates.ADMIN_ADD_PRODUCT_TYPE:
        handle_admin_add_product_type_input(bot, message)
    elif state == UserStates.ADMIN_ADD_PRODUCT_DESC:
        handle_admin_add_product_desc_input(bot, message)
    elif state == UserStates.ADMIN_ADD_PRODUCT_PRICE:
        handle_admin_add_product_price_input(bot, message)
    elif state == UserStates.ADMIN_ADD_PRODUCT_STOCK:
        handle_admin_add_product_stock_input(bot, message)
    elif state == UserStates.ADMIN_ADD_PRODUCT_FILE_URL:
        handle_admin_add_product_file_url_input(bot, message)
    
    # ========== РЕДАКТИРОВАНИЕ ТОВАРА ==========
    elif state == UserStates.ADMIN_EDIT_PRODUCT:
        handle_admin_edit_product_input(bot, message)
    elif state == UserStates.ADMIN_EDIT_PRODUCT_DETAILS:
        handle_admin_edit_product_details_input(bot, message)
    
    # ========== ПРОСМОТР ЗАКАЗОВ МАГАЗИНА ==========
    elif state == UserStates.ADMIN_VIEW_ORDERS:
        handle_admin_view_orders_input(bot, message)
    
    # ========== СОЗДАНИЕ РАССЫЛКИ ==========
    elif state == UserStates.ADMIN_CREATE_BROADCAST_TEXT:
        handle_admin_create_broadcast_text_input(bot, message)
    elif state == UserStates.ADMIN_CREATE_BROADCAST_CONFIRM:
        handle_admin_create_broadcast_confirm_input(bot, message)
    
    # ========== СОЗДАНИЕ ПРОМО-ПРЕДЛОЖЕНИЯ ==========
    elif state == UserStates.ADMIN_CREATE_PROMO_NAME:
        handle_admin_create_promo_name_input(bot, message)
    elif state == UserStates.ADMIN_CREATE_PROMO_DESC:
        handle_admin_create_promo_desc_input(bot, message)
    elif state == UserStates.ADMIN_CREATE_PROMO_PRICE:
        handle_admin_create_promo_price_input(bot, message)
    elif state == UserStates.ADMIN_CREATE_PROMO_DATES:
        handle_admin_create_promo_dates_input(bot, message)
    elif state == UserStates.ADMIN_CREATE_PROMO_CONFIRM:
        handle_admin_create_promo_confirm_input(bot, message)
    
    else:
        bot.send_message(
            chat_id,
            "Неизвестная команда. Возвращаемся в меню админки:",
            reply_markup=keyboards.admin_main_menu()
        )

# ========== ОБРАБОТКА CALLBACK ДЛЯ АДМИНКИ ==========

def handle_admin_callback(bot, call):
    """Обработка callback для админки"""
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    with next(get_db()) as db:
        # Проверяем, является ли пользователь администратором
        user = db.query(User).filter_by(user_id=user_id).first()
        if not user or not user.is_admin:
            bot.answer_callback_query(call.id, "❌ Нет доступа!", show_alert=True)
            return
    
    # ========== УПРАВЛЕНИЕ БРОНИРОВАНИЯМИ ОТЕЛЯ ==========
    if call.data.startswith('admin_booking_detail_'):
        booking_id = int(call.data.replace('admin_booking_detail_', ''))
        handle_admin_booking_detail(bot, call, booking_id)
    
    elif call.data.startswith('admin_booking_cancel_'):
        booking_id = int(call.data.replace('admin_booking_cancel_', ''))
        handle_admin_booking_cancel_confirm(bot, call, booking_id)
    
    elif call.data.startswith('admin_booking_confirm_'):
        booking_id = int(call.data.replace('admin_booking_confirm_', ''))
        handle_admin_booking_confirm(bot, call, booking_id)
    
    elif call.data.startswith('admin_booking_paid_'):
        booking_id = int(call.data.replace('admin_booking_paid_', ''))
        handle_admin_booking_paid(bot, call, booking_id)
    
    # ========== УПРАВЛЕНИЕ ЭКСКУРСИЯМИ ==========
    elif call.data.startswith('admin_excursion_edit_'):
        excursion_id = int(call.data.replace('admin_excursion_edit_', ''))
        handle_admin_excursion_edit_start(bot, call, excursion_id)
    
    elif call.data.startswith('admin_excursion_delete_'):
        excursion_id = int(call.data.replace('admin_excursion_delete_', ''))
        handle_admin_excursion_delete_confirm(bot, call, excursion_id)
    
    elif call.data.startswith('admin_excursion_toggle_'):
        excursion_id = int(call.data.replace('admin_excursion_toggle_', ''))
        handle_admin_excursion_toggle(bot, call, excursion_id)
    
    elif call.data.startswith('admin_excursion_stats_'):
        excursion_id = int(call.data.replace('admin_excursion_stats_', ''))
        handle_admin_excursion_stats(bot, call, excursion_id)
    
    # ========== УПРАВЛЕНИЕ ИНСТРУКТОРАМИ ==========
    elif call.data.startswith('admin_instructor_stats_'):
        instructor_id = int(call.data.replace('admin_instructor_stats_', ''))
        handle_admin_instructor_stats_detail(bot, call, instructor_id)
    
    elif call.data.startswith('admin_instructor_edit_'):
        instructor_id = int(call.data.replace('admin_instructor_edit_', ''))
        handle_admin_instructor_edit_start(bot, call, instructor_id)
    
    elif call.data.startswith('admin_instructor_delete_'):
        instructor_id = int(call.data.replace('admin_instructor_delete_', ''))
        handle_admin_instructor_delete_confirm(bot, call, instructor_id)
    
    elif call.data.startswith('admin_instructor_pay_'):
        instructor_id = int(call.data.replace('admin_instructor_pay_', ''))
        handle_admin_instructor_pay(bot, call, instructor_id)
    
    # ========== УПРАВЛЕНИЕ ТОВАРАМИ ==========
    elif call.data.startswith('admin_product_edit_'):
        product_id = int(call.data.replace('admin_product_edit_', ''))
        handle_admin_product_edit_start(bot, call, product_id)
    
    elif call.data.startswith('admin_product_delete_'):
        product_id = int(call.data.replace('admin_product_delete_', ''))
        handle_admin_product_delete_confirm(bot, call, product_id)
    
    elif call.data.startswith('admin_product_toggle_'):
        product_id = int(call.data.replace('admin_product_toggle_', ''))
        handle_admin_product_toggle(bot, call, product_id)
    
    elif call.data.startswith('admin_product_stats_'):
        product_id = int(call.data.replace('admin_product_stats_', ''))
        handle_admin_product_stats(bot, call, product_id)
    
    # ========== УПРАВЛЕНИЕ ЭКСПЕДИЦИЯМИ ==========
    elif call.data.startswith('admin_expedition_edit_'):
        expedition_id = int(call.data.replace('admin_expedition_edit_', ''))
        handle_admin_expedition_edit_start(bot, call, expedition_id)
    
    elif call.data.startswith('admin_expedition_delete_'):
        expedition_id = int(call.data.replace('admin_expedition_delete_', ''))
        handle_admin_expedition_delete_confirm(bot, call, expedition_id)
    
    elif call.data.startswith('admin_expedition_toggle_'):
        expedition_id = int(call.data.replace('admin_expedition_toggle_', ''))
        handle_admin_expedition_toggle(bot, call, expedition_id)
    
    elif call.data.startswith('admin_expedition_stats_'):
        expedition_id = int(call.data.replace('admin_expedition_stats_', ''))
        handle_admin_expedition_stats(bot, call, expedition_id)
    
    # ========== УПРАВЛЕНИЕ ЗАКАЗАМИ МАГАЗИНА ==========
    elif call.data.startswith('admin_order_detail_'):
        order_id = int(call.data.replace('admin_order_detail_', ''))
        handle_admin_order_detail(bot, call, order_id)
    
    elif call.data.startswith('admin_order_shipped_'):
        order_id = int(call.data.replace('admin_order_shipped_', ''))
        handle_admin_order_shipped(bot, call, order_id)
    
    elif call.data.startswith('admin_order_delivered_'):
        order_id = int(call.data.replace('admin_order_delivered_', ''))
        handle_admin_order_delivered(bot, call, order_id)
    
    elif call.data.startswith('admin_order_cancel_'):
        order_id = int(call.data.replace('admin_order_cancel_', ''))
        handle_admin_order_cancel_confirm(bot, call, order_id)
    
    # ========== ПОДТВЕРЖДЕНИЕ РАССЫЛКИ ==========
    elif call.data.startswith('admin_broadcast_confirm_'):
        admin_id = int(call.data.replace('admin_broadcast_confirm_', ''))
        handle_admin_broadcast_confirm(bot, call, admin_id)
    
    elif call.data.startswith('admin_broadcast_active_'):
        admin_id = int(call.data.replace('admin_broadcast_active_', ''))
        handle_admin_broadcast_active(bot, call, admin_id)
    
    elif call.data.startswith('admin_broadcast_preview_'):
        admin_id = int(call.data.replace('admin_broadcast_preview_', ''))
        handle_admin_broadcast_preview(bot, call, admin_id)
    
    elif call.data.startswith('admin_broadcast_cancel_'):
        admin_id = int(call.data.replace('admin_broadcast_cancel_', ''))
        handle_admin_broadcast_cancel(bot, call, admin_id)
    
    # ========== ПОДТВЕРЖДЕНИЕ ПРОМО-ПРЕДЛОЖЕНИЯ ==========
    elif call.data.startswith('admin_promo_create_'):
        admin_id = int(call.data.replace('admin_promo_create_', ''))
        handle_admin_promo_create_confirm(bot, call, admin_id)
    
    elif call.data.startswith('admin_promo_cancel_'):
        admin_id = int(call.data.replace('admin_promo_cancel_', ''))
        handle_admin_promo_cancel(bot, call, admin_id)
    
    # ========== ОБНОВЛЕНИЕ СПИСКОВ ==========
    elif call.data == 'admin_refresh_expeditions':
        handle_admin_expeditions_list_from_callback(bot, call)
    
    elif call.data == 'admin_refresh_products':
        handle_admin_products_list_from_callback(bot, call)
    
    elif call.data == 'admin_refresh_orders':
        handle_admin_view_orders_from_callback(bot, call)
    
    else:
        bot.answer_callback_query(call.id, "Неизвестная команда")

# ========== МЕНЮ АДМИНКИ ==========

def handle_admin_hotel_menu(bot, message):
    """Меню управления отелем"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    StateManager.set_state(user_id, UserStates.ADMIN_HOTEL, StateData())
    
    bot.send_message(
        chat_id,
        "🏨 *УПРАВЛЕНИЕ ОТЕЛЕМ*\n\n"
        "Выберите действие:",
        parse_mode='Markdown',
        reply_markup=keyboards.admin_hotel_menu()
    )

def handle_admin_instructors_menu(bot, message):
    """Меню управления инструкторами"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    StateManager.set_state(user_id, UserStates.ADMIN_INSTRUCTORS, StateData())
    
    bot.send_message(
        chat_id,
        "🎿 *УПРАВЛЕНИЕ ИНСТРУКТОРОВ*\n\n"
        "Выберите действие:",
        parse_mode='Markdown',
        reply_markup=keyboards.admin_instructors_menu()
    )

def handle_admin_excursions_menu(bot, message):
    """Меню управления экскурсиями"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    StateManager.set_state(user_id, UserStates.ADMIN_EXCURSIONS, StateData())
    
    bot.send_message(
        chat_id,
        "🗺️ *УПРАВЛЕНИЕ ЭКСКУРСИЯМИ*\n\n"
        "Выберите действие:",
        parse_mode='Markdown',
        reply_markup=keyboards.admin_excursions_menu()
    )

def handle_admin_expeditions_menu(bot, message):
    """Меню управления экспедициями"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    StateManager.set_state(user_id, UserStates.ADMIN_EXPEDITIONS, StateData())
    
    bot.send_message(
        chat_id,
        "🧊 *УПРАВЛЕНИЕ ЭКСПЕДИЦИЯМИ*\n\n"
        "Выберите действие:",
        parse_mode='Markdown',
        reply_markup=keyboards.admin_expeditions_menu()
    )

def handle_admin_shop_menu(bot, message):
    """Меню управления магазином"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    StateManager.set_state(user_id, UserStates.ADMIN_SHOP, StateData())
    
    bot.send_message(
        chat_id,
        "🛒 *УПРАВЛЕНИЕ МАГАЗИНОМ*\n\n"
        "Выберите действие:",
        parse_mode='Markdown',
        reply_markup=keyboards.admin_shop_menu()
    )

def handle_admin_statistics_menu(bot, message):
    """Меню статистики"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    StateManager.set_state(user_id, UserStates.ADMIN_STATISTICS, StateData())
    
    bot.send_message(
        chat_id,
        "📊 *СТАТИСТИКА И ОТЧЕТЫ*\n\n"
        "Выберите тип отчета:",
        parse_mode='Markdown',
        reply_markup=keyboards.admin_statistics_menu()
    )

def handle_admin_broadcast_menu(bot, message):
    """Меню рассылок"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    StateManager.set_state(user_id, UserStates.ADMIN_BROADCAST, StateData())
    
    bot.send_message(
        chat_id,
        "📢 *РАССЫЛКИ И ПРЕДЛОЖЕНИЯ*\n\n"
        "Выберите действие:",
        parse_mode='Markdown',
        reply_markup=keyboards.admin_broadcast_menu()
    )

# ========== ФУНКЦИИ ДЛЯ ОТЕЛЯ (РАБОТАЮТ - НЕ ТРОГАТЬ!) ==========

def handle_admin_block_date(bot, message):
    """Блокировка даты отеля"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    StateManager.set_state(user_id, UserStates.ADMIN_BLOCK_DATE, StateData())
    
    bot.send_message(
        chat_id,
        "📅 *БЛОКИРОВКА ДАТЫ ОТЕЛЯ*\n\n"
        "Введите дату в формате ДД.ММ.ГГГГ:\n"
        "Пример: 25.12.2025\n\n"
        "Для отмены нажмите ❌ Отмена",
        parse_mode='Markdown',
        reply_markup=keyboards.cancel_button()
    )

def handle_admin_block_date_input(bot, message):
    """Обработка ввода даты для блокировки"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_hotel_menu(bot, message)
        return
    
    date_str = message.text.strip()
    try:
        # Проверяем формат даты
        date_obj = datetime.strptime(date_str, "%d.%m.%Y")
        
        with next(get_db()) as db:
            # Проверяем, не заблокирована ли уже дата
            existing = db.query(BlockedDate).filter_by(date=date_obj).first()
            if existing:
                bot.send_message(
                    chat_id,
                    f"❌ Дата {date_str} уже заблокирована!",
                    reply_markup=keyboards.admin_hotel_menu()
                )
                StateManager.set_state(user_id, UserStates.ADMIN_HOTEL, StateData())
                return
            
            # Блокируем дату
            blocked_date = BlockedDate(
                date=date_obj,
                reason=f"Заблокирована администратором {user_id}"
            )
            db.add(blocked_date)
            db.commit()
            
            bot.send_message(
                chat_id,
                f"✅ Дата {date_str} успешно заблокирована!",
                reply_markup=keyboards.admin_hotel_menu()
            )
            StateManager.set_state(user_id, UserStates.ADMIN_HOTEL, StateData())
            
    except ValueError:
        bot.send_message(
            chat_id,
            "❌ Неверный формат даты! Введите дату в формате ДД.ММ.ГГГГ:\n"
            "Пример: 25.12.2025",
            reply_markup=keyboards.cancel_button()
        )

def handle_admin_unblock_date(bot, message):
    """Разблокировка даты отеля"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    StateManager.set_state(user_id, UserStates.ADMIN_UNBLOCK_DATE, StateData())
    
    bot.send_message(
        chat_id,
        "✅ *РАЗБЛОКИРОВКА ДАТЫ ОТЕЛЯ*\n\n"
        "Введите дату в формате ДД.ММ.ГГГГ:\n"
        "Пример: 25.12.2025\n\n"
        "Для отмены нажмите ❌ Отмена",
        parse_mode='Markdown',
        reply_markup=keyboards.cancel_button()
    )

def handle_admin_unblock_date_input(bot, message):
    """Обработка ввода даты для разблокировки"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_hotel_menu(bot, message)
        return
    
    date_str = message.text.strip()
    try:
        # Проверяем формат даты
        date_obj = datetime.strptime(date_str, "%d.%m.%Y")
        
        with next(get_db()) as db:
            # Находим заблокированную дату
            blocked_date = db.query(BlockedDate).filter_by(date=date_obj).first()
            if not blocked_date:
                bot.send_message(
                    chat_id,
                    f"❌ Дата {date_str} не была заблокирована!",
                    reply_markup=keyboards.admin_hotel_menu()
                )
                StateManager.set_state(user_id, UserStates.ADMIN_HOTEL, StateData())
                return
            
            # Разблокируем дату
            db.delete(blocked_date)
            db.commit()
            
            bot.send_message(
                chat_id,
                f"✅ Дата {date_str} успешно разблокирована!",
                reply_markup=keyboards.admin_hotel_menu()
            )
            StateManager.set_state(user_id, UserStates.ADMIN_HOTEL, StateData())
            
    except ValueError:
        bot.send_message(
            chat_id,
            "❌ Неверный формат даты! Введите дату в формате ДД.ММ.ГГГГ:\n"
            "Пример: 25.12.2025",
            reply_markup=keyboards.cancel_button()
        )

def handle_admin_view_bookings(bot, message):
    """Просмотр всех бронирований отеля"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    with next(get_db()) as db:
        # Получаем все бронирования
        bookings = db.query(HotelBooking).order_by(HotelBooking.check_in.desc()).all()
        
        if not bookings:
            bot.send_message(
                chat_id,
                "📋 *БРОНИРОВАНИЯ ОТЕЛЯ*\n\n"
                "Нет активных бронирований.",
                parse_mode='Markdown',
                reply_markup=keyboards.admin_hotel_menu()
            )
            return
        
        # Отправляем по 10 бронирований за раз
        for i in range(0, len(bookings), 10):
            batch = bookings[i:i+10]
            message_text = "📋 *БРОНИРОВАНИЯ ОТЕЛЯ*\n\n"
            
            for booking in batch:
                user = db.query(User).filter_by(id=booking.user_id).first()
                user_info = f"{user.first_name} {user.last_name}" if user else "Неизвестно"
                
                message_text += f"*ID:* {booking.id}\n"
                message_text += f"*Клиент:* {user_info}\n"
                message_text += f"*Даты:* {booking.check_in.strftime('%d.%m.%Y')} - {booking.check_out.strftime('%d.%m.%Y')}\n"
                message_text += f"*Ночей:* {booking.nights}\n"
                message_text += f"*Стоимость:* {booking.total_price} руб.\n"
                message_text += f"*Статус:* {booking.status}\n"
                message_text += f"*Оплата:* {booking.payment_status}\n"
                message_text += "─" * 20 + "\n"
            
            if i + 10 < len(bookings):
                message_text += f"\nПоказано {i+1}-{i+len(batch)} из {len(bookings)}"
            
            bot.send_message(
                chat_id,
                message_text,
                parse_mode='Markdown'
            )
        
        # Добавляем кнопки управления
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton('📊 Экспорт в CSV', callback_data='admin_export_hotel'),
            types.InlineKeyboardButton('🔄 Обновить', callback_data='admin_refresh_hotel')
        )
        
        bot.send_message(
            chat_id,
            "Выберите действие:",
            reply_markup=markup
        )
        
        StateManager.set_state(user_id, UserStates.ADMIN_HOTEL, StateData())

def handle_admin_cancel_booking(bot, message):
    """Отмена бронирования отеля"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    StateManager.set_state(user_id, UserStates.ADMIN_CANCEL_BOOKING, StateData())
    
    bot.send_message(
        chat_id,
        "❌ *ОТМЕНА БРОНИРОВАНИЯ ОТЕЛЯ*\n\n"
        "Введите ID бронирования:\n\n"
        "Для отмены нажмите ❌ Отмена",
        parse_mode='Markdown',
        reply_markup=keyboards.cancel_button()
    )

def handle_admin_cancel_booking_input(bot, message):
    """Обработка ввода ID для отмены бронирования"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_hotel_menu(bot, message)
        return
    
    try:
        booking_id = int(message.text.strip())
        
        with next(get_db()) as db:
            # Находим бронирование
            booking = db.query(HotelBooking).filter_by(id=booking_id).first()
            if not booking:
                bot.send_message(
                    chat_id,
                    f"❌ Бронирование с ID {booking_id} не найдено!",
                    reply_markup=keyboards.admin_hotel_menu()
                )
                StateManager.set_state(user_id, UserStates.ADMIN_HOTEL, StateData())
                return
            
            # Отменяем бронирование
            booking.status = 'cancelled'
            db.commit()
            
            # Уведомляем пользователя
            try:
                user = db.query(User).filter_by(id=booking.user_id).first()
                if user and user.user_id:
                    bot.send_message(
                        user.user_id,
                        f"❌ Ваше бронирование отеля (ID: {booking.id}) отменено администратором.\n\n"
                        f"Даты: {booking.check_in.strftime('%d.%m.%Y')} - {booking.check_out.strftime('%d.%m.%Y')}\n"
                        f"Сумма возврата: {booking.total_price} руб.\n\n"
                        f"По вопросам возврата обратитесь к менеджеру.",
                        parse_mode='Markdown'
                    )
            except Exception as e:
                print(f"Ошибка уведомления пользователя: {e}")
            
            bot.send_message(
                chat_id,
                f"✅ Бронирование ID {booking_id} успешно отменено!\n"
                f"Пользователь уведомлен.",
                reply_markup=keyboards.admin_hotel_menu()
            )
            StateManager.set_state(user_id, UserStates.ADMIN_HOTEL, StateData())
            
    except ValueError:
        bot.send_message(
            chat_id,
            "❌ Неверный формат ID! Введите число:",
            reply_markup=keyboards.cancel_button()
        )

# ========== ФУНКЦИИ ДЛЯ ИНСТРУКТОРОВ (РАБОТАЮТ - НЕ ТРОГАТЬ!) ==========

def handle_admin_price_settings(bot, message):
    """Настройка цен инструкторов"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    StateManager.set_state(user_id, UserStates.ADMIN_PRICE_SETTINGS, StateData())
    
    with next(get_db()) as db:
        # Получаем текущие настройки
        base_price = db.query(Setting).filter_by(key='instructor_base_price').first()
        child_price = db.query(Setting).filter_by(key='instructor_child_price').first()
        freeride_price = db.query(Setting).filter_by(key='instructor_freeride_price').first()
        carving_price = db.query(Setting).filter_by(key='instructor_carving_price').first()
        group_discount = db.query(Setting).filter_by(key='instructor_group_discount').first()
        commission = db.query(Setting).filter_by(key='instructor_commission').first()
        
        message_text = (
            "💰 *НАСТРОЙКА ЦЕН ИНСТРУКТОРОВ*\n\n"
            f"*Текущие цены:*\n"
            f"• Базовая цена (взрослый/новичок): {base_price.value if base_price else '2000'} руб./час\n"
            f"• Цена для детей: {child_price.value if child_price else '1500'} руб./час\n"
            f"• Фрирайд: {freeride_price.value if freeride_price else '2500'} руб./час\n"
            f"• Карвинг: {carving_price.value if carving_price else '2500'} руб./час\n"
            f"• Скидка за группу: {group_discount.value if group_discount else '10'}%\n"
            f"• Комиссия платформы: {commission.value if commission else '10'}%\n\n"
            "Выберите, что хотите изменить:"
        )
        
        bot.send_message(
            chat_id,
            message_text,
            parse_mode='Markdown',
            reply_markup=keyboards.admin_price_settings_menu()
        )

def handle_admin_set_price_base(bot, message):
    """Изменение базовой цены"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    StateManager.set_state(user_id, UserStates.ADMIN_SET_PRICE_BASE, StateData())
    
    bot.send_message(
        chat_id,
        "📝 *ИЗМЕНЕНИЕ БАЗОВОЙ ЦЕНЫ*\n\n"
        "Введите новую базовую цену (в рублях за час):\n"
        "Пример: 2500\n\n"
        "Для отмены нажмите ❌ Отмена",
        parse_mode='Markdown',
        reply_markup=keyboards.cancel_button()
    )

def handle_admin_set_price_base_input(bot, message):
    """Обработка ввода базовой цены"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_price_settings(bot, message)
        return
    
    try:
        price = float(message.text.strip())
        if price <= 0:
            raise ValueError
        
        with next(get_db()) as db:
            # Сохраняем цену
            setting = db.query(Setting).filter_by(key='instructor_base_price').first()
            if setting:
                setting.value = str(price)
            else:
                setting = Setting(key='instructor_base_price', value=str(price))
                db.add(setting)
            
            db.commit()
            
            bot.send_message(
                chat_id,
                f"✅ Базовая цена успешно изменена на {price} руб./час!",
                reply_markup=keyboards.admin_price_settings_menu()
            )
            StateManager.set_state(user_id, UserStates.ADMIN_PRICE_SETTINGS, StateData())
            
    except (ValueError, TypeError):
        bot.send_message(
            chat_id,
            "❌ Неверный формат цены! Введите число больше 0:",
            reply_markup=keyboards.cancel_button()
        )

def handle_admin_set_price_child(bot, message):
    """Изменение цены для детей"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    StateManager.set_state(user_id, UserStates.ADMIN_SET_PRICE_CHILD, StateData())
    
    bot.send_message(
        chat_id,
        "📝 *ИЗМЕНЕНИЕ ЦЕНЫ ДЛЯ ДЕТЕЙ*\n\n"
        "Введите новую цену для детей (в рублях за час):\n"
        "Пример: 1800\n\n"
        "Для отмены нажмите ❌ Отмена",
        parse_mode='Markdown',
        reply_markup=keyboards.cancel_button()
    )

def handle_admin_set_price_child_input(bot, message):
    """Обработка ввода цены для детей"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_price_settings(bot, message)
        return
    
    try:
        price = float(message.text.strip())
        if price <= 0:
            raise ValueError
        
        with next(get_db()) as db:
            # Сохраняем цену
            setting = db.query(Setting).filter_by(key='instructor_child_price').first()
            if setting:
                setting.value = str(price)
            else:
                setting = Setting(key='instructor_child_price', value=str(price))
                db.add(setting)
            
            db.commit()
            
            bot.send_message(
                chat_id,
                f"✅ Цена для детей успешно изменена на {price} руб./час!",
                reply_markup=keyboards.admin_price_settings_menu()
            )
            StateManager.set_state(user_id, UserStates.ADMIN_PRICE_SETTINGS, StateData())
            
    except (ValueError, TypeError):
        bot.send_message(
            chat_id,
            "❌ Неверный формат цены! Введите число больше 0:",
            reply_markup=keyboards.cancel_button()
        )

def handle_admin_set_price_freeride(bot, message):
    """Изменение цены фрирайда"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    StateManager.set_state(user_id, UserStates.ADMIN_SET_PRICE_FREERIDE, StateData())
    
    bot.send_message(
        chat_id,
        "📝 *ИЗМЕНЕНИЕ ЦЕНЫ ФРИРАЙДА*\n\n"
        "Введите новую цену для фрирайда (в рублях за час):\n"
        "Пример: 3000\n\n"
        "Для отмены нажмите ❌ Отмена",
        parse_mode='Markdown',
        reply_markup=keyboards.cancel_button()
    )

def handle_admin_set_price_freeride_input(bot, message):
    """Обработка ввода цены фрирайда"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_price_settings(bot, message)
        return
    
    try:
        price = float(message.text.strip())
        if price <= 0:
            raise ValueError
        
        with next(get_db()) as db:
            # Сохраняем цену
            setting = db.query(Setting).filter_by(key='instructor_freeride_price').first()
            if setting:
                setting.value = str(price)
            else:
                setting = Setting(key='instructor_freeride_price', value=str(price))
                db.add(setting)
            
            db.commit()
            
            bot.send_message(
                chat_id,
                f"✅ Цена фрирайда успешно изменена на {price} руб./час!",
                reply_markup=keyboards.admin_price_settings_menu()
            )
            StateManager.set_state(user_id, UserStates.ADMIN_PRICE_SETTINGS, StateData())
            
    except (ValueError, TypeError):
        bot.send_message(
            chat_id,
            "❌ Неверный формат цены! Введите число больше 0:",
            reply_markup=keyboards.cancel_button()
        )

def handle_admin_set_price_carving(bot, message):
    """Изменение цены карвинга"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    StateManager.set_state(user_id, UserStates.ADMIN_SET_PRICE_CARVING, StateData())
    
    bot.send_message(
        chat_id,
        "📝 *ИЗМЕНЕНИЕ ЦЕНЫ КАРВИНГА*\n\n"
        "Введите новую цену для карвинга (в рублях за час):\n"
        "Пример: 3000\n\n"
        "Для отмены нажмите ❌ Отмена",
        parse_mode='Markdown',
        reply_markup=keyboards.cancel_button()
    )

def handle_admin_set_price_carving_input(bot, message):
    """Обработка ввода цены карвинга"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_price_settings(bot, message)
        return
    
    try:
        price = float(message.text.strip())
        if price <= 0:
            raise ValueError
        
        with next(get_db()) as db:
            # Сохраняем цену
            setting = db.query(Setting).filter_by(key='instructor_carving_price').first()
            if setting:
                setting.value = str(price)
            else:
                setting = Setting(key='instructor_carving_price', value=str(price))
                db.add(setting)
            
            db.commit()
            
            bot.send_message(
                chat_id,
                f"✅ Цена карвинга успешно изменена на {price} руб./час!",
                reply_markup=keyboards.admin_price_settings_menu()
            )
            StateManager.set_state(user_id, UserStates.ADMIN_PRICE_SETTINGS, StateData())
            
    except (ValueError, TypeError):
        bot.send_message(
            chat_id,
            "❌ Неверный формат цены! Введите число больше 0:",
            reply_markup=keyboards.cancel_button()
        )

def handle_admin_set_discount_group(bot, message):
    """Изменение скидки за группу"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    StateManager.set_state(user_id, UserStates.ADMIN_SET_DISCOUNT_GROUP, StateData())
    
    bot.send_message(
        chat_id,
        "📝 *ИЗМЕНЕНИЕ СКИДКИ ЗА ГРУППУ*\n\n"
        "Введите новую скидку за группу (в процентах):\n"
        "Пример: 15\n\n"
        "Для отмены нажмите ❌ Отмена",
        parse_mode='Markdown',
        reply_markup=keyboards.cancel_button()
    )

def handle_admin_set_discount_group_input(bot, message):
    """Обработка ввода скидки за группу"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_price_settings(bot, message)
        return
    
    try:
        discount = float(message.text.strip())
        if discount < 0 or discount > 100:
            raise ValueError
        
        with next(get_db()) as db:
            # Сохраняем скидку
            setting = db.query(Setting).filter_by(key='instructor_group_discount').first()
            if setting:
                setting.value = str(discount)
            else:
                setting = Setting(key='instructor_group_discount', value=str(discount))
                db.add(setting)
            
            db.commit()
            
            bot.send_message(
                chat_id,
                f"✅ Скидка за группу успешно изменена на {discount}%!",
                reply_markup=keyboards.admin_price_settings_menu()
            )
            StateManager.set_state(user_id, UserStates.ADMIN_PRICE_SETTINGS, StateData())
            
    except (ValueError, TypeError):
        bot.send_message(
            chat_id,
            "❌ Неверный формат скидки! Введите число от 0 до 100:",
            reply_markup=keyboards.cancel_button()
        )

def handle_admin_set_commission(bot, message):
    """Изменение комиссии"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    StateManager.set_state(user_id, UserStates.ADMIN_SET_COMMISSION, StateData())
    
    bot.send_message(
        chat_id,
        "📝 *ИЗМЕНЕНИЕ КОМИССИИ ПЛАТФОРМЫ*\n\n"
        "Введите новую комиссию (в процентах):\n"
        "Пример: 12\n\n"
        "Для отмены нажмите ❌ Отмена",
        parse_mode='Markdown',
        reply_markup=keyboards.cancel_button()
    )

def handle_admin_set_commission_input(bot, message):
    """Обработка ввода комиссии"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_price_settings(bot, message)
        return
    
    try:
        commission = float(message.text.strip())
        if commission < 0 or commission > 50:
            raise ValueError
        
        with next(get_db()) as db:
            # Сохраняем комиссию
            setting = db.query(Setting).filter_by(key='instructor_commission').first()
            if setting:
                setting.value = str(commission)
            else:
                setting = Setting(key='instructor_commission', value=str(commission))
                db.add(setting)
            
            db.commit()
            
            bot.send_message(
                chat_id,
                f"✅ Комиссия платформы успешно изменена на {commission}%!",
                reply_markup=keyboards.admin_price_settings_menu()
            )
            StateManager.set_state(user_id, UserStates.ADMIN_PRICE_SETTINGS, StateData())
            
    except (ValueError, TypeError):
        bot.send_message(
            chat_id,
            "❌ Неверный формат комиссии! Введите число от 0 до 50:",
            reply_markup=keyboards.cancel_button()
        )

def handle_admin_instructors_list(bot, message):
    """Список инструкторов"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    with next(get_db()) as db:
        # Получаем всех пользователей-инструкторов
        instructors = db.query(User).filter_by(is_instructor=True).all()
        
        if not instructors:
            bot.send_message(
                chat_id,
                "📋 *СПИСОК ИНСТРУКТОРОВ*\n\n"
                "Нет зарегистрированных инструкторов.",
                parse_mode='Markdown',
                reply_markup=keyboards.admin_instructors_menu()
            )
            return
        
        message_text = "📋 *СПИСОК ИНСТРУКТОРОВ*\n\n"
        for i, instructor in enumerate(instructors, 1):
            # Получаем статистику инструктора
            bookings_count = db.query(InstructorBooking).filter_by(instructor_id=instructor.user_id).count()
            offers_count = db.query(InstructorOffer).filter_by(instructor_id=instructor.user_id).count()
            
            message_text += f"*{i}. {instructor.first_name} {instructor.last_name}*\n"
            if instructor.username:
                message_text += f" @{instructor.username}\n"
            message_text += f" ID: {instructor.user_id}\n"
            if instructor.phone:
                message_text += f" Телефон: {instructor.phone}\n"
            message_text += f" Заявок: {bookings_count}\n"
            message_text += f" Предложений: {offers_count}\n"
            message_text += "─" * 20 + "\n"
        
        bot.send_message(
            chat_id,
            message_text,
            parse_mode='Markdown',
            reply_markup=keyboards.admin_instructors_menu()
        )

def handle_admin_instructor_stats(bot, message):
    """Статистика инструктора"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    StateManager.set_state(user_id, UserStates.ADMIN_INSTRUCTOR_STATS, StateData())
    
    bot.send_message(
        chat_id,
        "📊 *СТАТИСТИКА ИНСТРУКТОРА*\n\n"
        "Введите ID инструктора (Telegram user_id):\n\n"
        "Для отмены нажмите ❌ Отмена",
        parse_mode='Markdown',
        reply_markup=keyboards.cancel_button()
    )

def handle_admin_instructor_stats_input(bot, message):
    """Обработка ввода ID инструктора"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_instructors_menu(bot, message)
        return
    
    try:
        instructor_id = int(message.text.strip())
        
        with next(get_db()) as db:
            # Находим инструктора
            instructor = db.query(User).filter_by(user_id=instructor_id, is_instructor=True).first()
            if not instructor:
                bot.send_message(
                    chat_id,
                    f"❌ Инструктор с ID {instructor_id} не найден!",
                    reply_markup=keyboards.admin_instructors_menu()
                )
                StateManager.set_state(user_id, UserStates.ADMIN_INSTRUCTORS, StateData())
                return
            
            # Получаем статистику
            bookings = db.query(InstructorBooking).filter_by(instructor_id=instructor_id).all()
            offers = db.query(InstructorOffer).filter_by(instructor_id=instructor_id).all()
            
            # Статистика по статусам
            total_bookings = len(bookings)
            completed = len([b for b in bookings if b.status == 'completed'])
            cancelled = len([b for b in bookings if b.status == 'cancelled'])
            pending = len([b for b in bookings if b.status in ['searching', 'offers_received']])
            
            # Финансовая статистика
            total_revenue = sum([b.total_price for b in bookings if b.status == 'completed'])
            total_commission = sum([b.commission_amount for b in bookings if b.status == 'completed'])
            
            message_text = (
                f"📊 *СТАТИСТИКА ИНСТРУКТОРА*\n\n"
                f"*Информация:*\n"
                f"• Имя: {instructor.first_name} {instructor.last_name}\n"
                f"• Username: @{instructor.username if instructor.username else 'нет'}\n"
                f"• ID: {instructor.user_id}\n"
                f"• Телефон: {instructor.phone if instructor.phone else 'не указан'}\n\n"
                f"*Статистика заявок:*\n"
                f"• Всего заявок: {total_bookings}\n"
                f"• Завершено: {completed}\n"
                f"• Отменено: {cancelled}\n"
                f"• В ожидании: {pending}\n\n"
                f"*Финансовая статистика:*\n"
                f"• Общий доход: {total_revenue} руб.\n"
                f"• Комиссия платформы: {total_commission} руб.\n"
                f"• Чистый доход инструктора: {total_revenue - total_commission} руб.\n\n"
                f"*Предложения:*\n"
                f"• Всего предложений: {len(offers)}\n"
                f"• Принято: {len([o for o in offers if o.status == 'accepted'])}\n"
                f"• Отклонено: {len([o for o in offers if o.status == 'rejected'])}\n"
                f"• В ожидании: {len([o for o in offers if o.status == 'pending'])}"
            )
            
            bot.send_message(
                chat_id,
                message_text,
                parse_mode='Markdown',
                reply_markup=keyboards.admin_instructors_menu()
            )
            StateManager.set_state(user_id, UserStates.ADMIN_INSTRUCTORS, StateData())
            
    except ValueError:
        bot.send_message(
            chat_id,
            "❌ Неверный формат ID! Введите число:",
            reply_markup=keyboards.cancel_button()
        )

def handle_admin_cancel_instructor_booking(bot, message):
    """Отмена заказа инструктора"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    bot.send_message(
        chat_id,
        "❌ *ОТМЕНА ЗАКАЗА ИНСТРУКТОРА*\n\n"
        "Для отмена заказа используйте команду:\n"
        "`/cancel_booking [ID_заявки]`\n\n"
        "Например: `/cancel_booking 123`",
        parse_mode='Markdown',
        reply_markup=keyboards.admin_instructors_menu()
    )

# ========== ФУНКЦИИ ДЛЯ ЭКСКУРСИЙ (РАБОТАЮТ - НЕ МЕНЯТЬ) ==========

def handle_admin_add_excursion(bot, message):
    """Добавление экскурсии"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    StateManager.set_state(user_id, UserStates.ADMIN_ADD_EXCURSION_NAME, StateData())
    
    bot.send_message(
        chat_id,
        "➕ *ДОБАВЛЕНИЕ ЭКСКУРСИИ*\n\n"
        "Введите название экскурсии:\n\n"
        "Для отмены нажмите ❌ Отмена",
        parse_mode='Markdown',
        reply_markup=keyboards.cancel_button()
    )

def handle_admin_add_excursion_name_input(bot, message):
    """Обработка ввода названия экскурсии"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_excursions_menu(bot, message)
        return
    
    name = message.text.strip()
    if len(name) < 3:
        bot.send_message(
            chat_id,
            "❌ Название слишком короткое! Введите название минимум из 3 символов:",
            reply_markup=keyboards.cancel_button()
        )
        return
    
    StateManager.set_state(
        user_id,
        UserStates.ADMIN_ADD_EXCURSION_DESC,
        StateData(name=name)
    )
    
    bot.send_message(
        chat_id,
        "📝 *ВВЕДИТЕ ОПИСАНИЕ ЭКСКУРСИИ:*\n\n"
        "Опишите маршрут, достопримечательности, что включено:\n\n"
        "Для отмены нажмите ❌ Отмена",
        parse_mode='Markdown',
        reply_markup=keyboards.cancel_button()
    )

def handle_admin_add_excursion_desc_input(bot, message):
    """Обработка ввода описания экскурсии"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_excursions_menu(bot, message)
        return
    
    data = StateManager.get_data(user_id)
    description = message.text.strip()
    
    if len(description) < 10:
        bot.send_message(
            chat_id,
            "❌ Описание слишком короткое! Введите подробное описание:",
            reply_markup=keyboards.cancel_button()
        )
        return
    
    StateManager.set_state(
        user_id,
        UserStates.ADMIN_ADD_EXCURSION_PRICE,
        StateData(name=data.name, description=description)
    )
    
    bot.send_message(
        chat_id,
        "💰 *ВВЕДИТЕ ЦЕНУ ЗА ЧЕЛОВЕКА (в рублях):*\n\n"
        "Пример: 5000\n\n"
        "Для отмены нажмите ❌ Отмена",
        parse_mode='Markdown',
        reply_markup=keyboards.cancel_button()
    )

def handle_admin_add_excursion_price_input(bot, message):
    """Обработка ввода цены экскурсии"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_excursions_menu(bot, message)
        return
    
    try:
        price = float(message.text.strip())
        if price <= 0:
            raise ValueError
        
        data = StateManager.get_data(user_id)
        StateManager.set_state(
            user_id,
            UserStates.ADMIN_ADD_EXCURSION_MIN_PEOPLE,
            StateData(name=data.name, description=data.description, price=price)
        )
        
        bot.send_message(
            chat_id,
            "👥 *ВВЕДИТЕ МИНИМАЛЬНОЕ КОЛИЧЕСТВО ЧЕЛОВЕК:*\n\n"
            "Минимальное количество для проведения экскурсии:\n"
            "Пример: 2\n\n"
            "Для отмены нажмите ❌ Отмена",
            parse_mode='Markdown',
            reply_markup=keyboards.cancel_button()
        )
        
    except (ValueError, TypeError):
        bot.send_message(
            chat_id,
            "❌ Неверный формат цены! Введите число больше 0:",
            reply_markup=keyboards.cancel_button()
        )

def handle_admin_add_excursion_min_people_input(bot, message):
    """Обработка ввода минимального количества людей"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_excursions_menu(bot, message)
        return
    
    try:
        min_people = int(message.text.strip())
        if min_people <= 0:
            raise ValueError
        
        data = StateManager.get_data(user_id)
        StateManager.set_state(
            user_id,
            UserStates.ADMIN_ADD_EXCURSION_MAX_PEOPLE,
            StateData(
                name=data.name,
                description=data.description,
                price=data.price,
                min_people=min_people
            )
        )
        
        bot.send_message(
            chat_id,
            "👥 *ВВЕДИТЕ МАКСИМАЛЬНОЕ КОЛИЧЕСТВО ЧЕЛОВЕК:*\n\n"
            "Максимальное количество в группе:\n"
            "Пример: 10\n\n"
            "Для отмены нажмите ❌ Отмена",
            parse_mode='Markdown',
            reply_markup=keyboards.cancel_button()
        )
        
    except (ValueError, TypeError):
        bot.send_message(
            chat_id,
            "❌ Неверный формат! Введите целое число больше 0:",
            reply_markup=keyboards.cancel_button()
        )

def handle_admin_add_excursion_max_people_input(bot, message):
    """Обработка ввода максимального количества людей"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_excursions_menu(bot, message)
        return
    
    try:
        max_people = int(message.text.strip())
        data = StateManager.get_data(user_id)
        
        if max_people <= data.min_people:
            bot.send_message(
                chat_id,
                f"❌ Максимальное количество должно быть больше минимального ({data.min_people})!",
                reply_markup=keyboards.cancel_button()
            )
            return
        
        StateManager.set_state(
            user_id,
            UserStates.ADMIN_ADD_EXCURSION_DURATION,
            StateData(
                name=data.name,
                description=data.description,
                price=data.price,
                min_people=data.min_people,
                max_people=max_people
            )
        )
        
        bot.send_message(
            chat_id,
            "⏱️ *ВВЕДИТЕ ПРОДОЛЖИТЕЛЬНОСТЬ ЭКСКУРСИИ (в часах):*\n\n"
            "Пример: 3 (для трехчасовой экскурсии)\n\n"
            "Для отмены нажмите ❌ Отмена",
            parse_mode='Markdown',
            reply_markup=keyboards.cancel_button()
        )
        
    except (ValueError, TypeError):
        bot.send_message(
            chat_id,
            "❌ Неверный формат! Введите целое число:",
            reply_markup=keyboards.cancel_button()
        )

def handle_admin_add_excursion_duration_input(bot, message):
    """Обработка ввода продолжительности экскурсии"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_excursions_menu(bot, message)
        return
    
    try:
        duration = int(message.text.strip())
        if duration <= 0:
            raise ValueError
        
        data = StateManager.get_data(user_id)
        
        # Сохраняем экскурсию в базу данных
        with next(get_db()) as db:
            excursion = Excursion(
                name=data.name,
                description=data.description,
                price_per_person=data.price,
                min_people=data.min_people,
                max_people=data.max_people,
                duration_hours=duration,
                is_active=True
            )
            db.add(excursion)
            db.commit()
            
            message_text = (
                "✅ *ЭКСПЕДИЦИЯ УСПЕШНО ДОБАВЛЕНА!*\n\n"
                f"*Название:* {data.name}\n"
                f"*Описание:* {data.description}\n"
                f"*Цена за человека:* {data.price} руб.\n"
                f"*Минимальное количество:* {data.min_people} чел.\n"
                f"*Максимальное количество:* {data.max_people} чел.\n"
                f"*Продолжительность:* {duration} час.\n"
                f"*ID экскурсии:* {excursion.id}\n\n"
                "Экскурсия теперь доступна для бронирования клиентами."
            )
            
            bot.send_message(
                chat_id,
                message_text,
                parse_mode='Markdown',
                reply_markup=keyboards.admin_excursions_menu()
            )
            StateManager.set_state(user_id, UserStates.ADMIN_EXCURSIONS, StateData())
            
    except (ValueError, TypeError):
        bot.send_message(
            chat_id,
            "❌ Неверный формат! Введите целое число больше 0:",
            reply_markup=keyboards.cancel_button()
        )

def handle_admin_excursions_list(bot, message):
    """Список экскурсий"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    with next(get_db()) as db:
        # Получаем все экскурсии
        excursions = db.query(Excursion).order_by(Excursion.id.desc()).all()
        
        if not excursions:
            bot.send_message(
                chat_id,
                "📋 *СПИСОК ЭКСКУРСИЙ*\n\n"
                "Нет доступных экскурсий.",
                parse_mode='Markdown',
                reply_markup=keyboards.admin_excursions_menu()
            )
            return
        
        # Отправляем по 5 экскурсий за раз
        for i in range(0, len(excursions), 5):
            batch = excursions[i:i+5]
            message_text = "📋 *СПИСОК ЭКСКУРСИЙ*\n\n"
            
            for excursion in batch:
                status = "✅ Активна" if excursion.is_active else "❌ Не активна"
                bookings_count = db.query(ExcursionBooking).filter_by(excursion_id=excursion.id).count()
                
                message_text += f"*ID:* {excursion.id}\n"
                message_text += f"*Название:* {excursion.name}\n"
                message_text += f"*Цена:* {excursion.price_per_person} руб./чел.\n"
                message_text += f"*Группа:* {excursion.min_people}-{excursion.max_people} чел.\n"
                message_text += f"*Длительность:* {excursion.duration_hours} час.\n"
                message_text += f"*Статус:* {status}\n"
                message_text += f"*Бронирований:* {bookings_count}\n"
                message_text += "─" * 20 + "\n"
            
            if i + 5 < len(excursions):
                message_text += f"\nПоказано {i+1}-{i+len(batch)} из {len(excursions)}"
            
            bot.send_message(
                chat_id,
                message_text,
                parse_mode='Markdown'
            )
        
        # Добавляем кнопки управления
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton('📊 Экспорт в CSV', callback_data='admin_export_excursions'),
            types.InlineKeyboardButton('🔄 Обновить', callback_data='admin_refresh_excursions')
        )
        
        bot.send_message(
            chat_id,
            "Выберите действие:",
            reply_markup=markup
        )
        
        StateManager.set_state(user_id, UserStates.ADMIN_EXCURSIONS, StateData())

def handle_admin_edit_excursion(bot, message):
    """Редактирование экскурсии"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    StateManager.set_state(user_id, UserStates.ADMIN_EDIT_EXCURSION, StateData())
    
    bot.send_message(
        chat_id,
        "✏️ *РЕДАКТИРОВАНИЕ ЭКСКУРСИИ*\n\n"
        "Введите ID экскурсии для редактирования:\n\n"
        "Для отмены нажмите ❌ Отмена",
        parse_mode='Markdown',
        reply_markup=keyboards.cancel_button()
    )

def handle_admin_edit_excursion_input(bot, message):
    """Обработка ввода ID экскурсии для редактирования"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_excursions_menu(bot, message)
        return
    
    try:
        excursion_id = int(message.text.strip())
        
        with next(get_db()) as db:
            # Находим экскурсию
            excursion = db.query(Excursion).filter_by(id=excursion_id).first()
            if not excursion:
                bot.send_message(
                    chat_id,
                    f"❌ Экскурсия с ID {excursion_id} не найдена!",
                    reply_markup=keyboards.admin_excursions_menu()
                )
                StateManager.set_state(user_id, UserStates.ADMIN_EXCURSIONS, StateData())
                return
            
            # Сохраняем данные экскурсии
            StateManager.set_state(
                user_id,
                UserStates.ADMIN_EDIT_EXCURSION_DETAILS,
                StateData(
                    excursion_id=excursion_id,
                    excursion_name=excursion.name,
                    excursion_description=excursion.description,
                    excursion_price=excursion.price_per_person,
                    excursion_min_people=excursion.min_people,
                    excursion_max_people=excursion.max_people,
                    excursion_duration=excursion.duration_hours,
                    excursion_active=excursion.is_active
                )
            )
            
            # Показываем информацию об экскурсии
            message_text = (
                f"✏️ *РЕДАКТИРОВАНИЕ ЭКСКУРСИИ #{excursion_id}*\n\n"
                f"*Текущие данные:*\n"
                f"1. Название: {excursion.name}\n"
                f"2. Описание: {excursion.description[:100]}...\n"
                f"3. Цена: {excursion.price_per_person} руб./чел.\n"
                f"4. Минимальное количество: {excursion.min_people} чел.\n"
                f"5. Максимальное количество: {excursion.max_people} чел.\n"
                f"6. Длительность: {excursion.duration_hours} час.\n"
                f"7. Статус: {'Активна' if excursion.is_active else 'Не активна'}\n\n"
                "Введите номер поля для редактирования (1-7):\n"
                "Для отмены нажмите ❌ Отмена"
            )
            
            bot.send_message(
                chat_id,
                message_text,
                parse_mode='Markdown',
                reply_markup=keyboards.cancel_button()
            )
            
    except ValueError:
        bot.send_message(
            chat_id,
            "❌ Неверный формат ID! Введите число:",
            reply_markup=keyboards.cancel_button()
        )

def handle_admin_edit_excursion_details_input(bot, message):
    """Обработка редактирования деталей экскурсии"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_excursions_menu(bot, message)
        return
    
    data = StateManager.get_data(user_id)
    
    try:
        field_num = int(message.text.strip())
        
        if field_num == 1:
            bot.send_message(
                chat_id,
                "Введите новое название экскурсии:",
                reply_markup=keyboards.cancel_button()
            )
            StateManager.update_data(user_id, editing_field='name')
            
        elif field_num == 2:
            bot.send_message(
                chat_id,
                "Введите новое описание экскурсии:",
                reply_markup=keyboards.cancel_button()
            )
            StateManager.update_data(user_id, editing_field='description')
            
        elif field_num == 3:
            bot.send_message(
                chat_id,
                "Введите новую цену за человека (в рублях):",
                reply_markup=keyboards.cancel_button()
            )
            StateManager.update_data(user_id, editing_field='price')
            
        elif field_num == 4:
            bot.send_message(
                chat_id,
                "Введите новое минимальное количество человек:",
                reply_markup=keyboards.cancel_button()
            )
            StateManager.update_data(user_id, editing_field='min_people')
            
        elif field_num == 5:
            bot.send_message(
                chat_id,
                "Введите новое максимальное количество человек:",
                reply_markup=keyboards.cancel_button()
            )
            StateManager.update_data(user_id, editing_field='max_people')
            
        elif field_num == 6:
            bot.send_message(
                chat_id,
                "Введите новую продолжительность (в часах):",
                reply_markup=keyboards.cancel_button()
            )
            StateManager.update_data(user_id, editing_field='duration')
            
        elif field_num == 7:
            bot.send_message(
                chat_id,
                "Изменить статус экскурсии:\n"
                "1. Активировать\n"
                "2. Деактивировать\n\n"
                "Введите 1 или 2:",
                reply_markup=keyboards.cancel_button()
            )
            StateManager.update_data(user_id, editing_field='status')
            
        else:
            bot.send_message(
                chat_id,
                "❌ Неверный номер поля! Введите число от 1 до 7:",
                reply_markup=keyboards.cancel_button()
            )
            
    except ValueError:
        # Пользователь ввел текст для редактирования поля
        if hasattr(data, 'editing_field'):
            editing_field = data.editing_field
            try:
                with next(get_db()) as db:
                    excursion = db.query(Excursion).filter_by(id=data.excursion_id).first()
                    
                    if editing_field == 'name':
                        excursion.name = message.text.strip()
                    elif editing_field == 'description':
                        excursion.description = message.text.strip()
                    elif editing_field == 'price':
                        price = float(message.text.strip())
                        if price <= 0:
                            raise ValueError
                        excursion.price_per_person = price
                    elif editing_field == 'min_people':
                        min_people = int(message.text.strip())
                        if min_people <= 0:
                            raise ValueError
                        excursion.min_people = min_people
                    elif editing_field == 'max_people':
                        max_people = int(message.text.strip())
                        if max_people <= excursion.min_people:
                            bot.send_message(
                                chat_id,
                                f"❌ Максимальное количество должно быть больше минимального ({excursion.min_people})!",
                                reply_markup=keyboards.cancel_button()
                            )
                            return
                        excursion.max_people = max_people
                    elif editing_field == 'duration':
                        duration = int(message.text.strip())
                        if duration <= 0:
                            raise ValueError
                        excursion.duration_hours = duration
                    elif editing_field == 'status':
                        if message.text.strip() == '1':
                            excursion.is_active = True
                        elif message.text.strip() == '2':
                            excursion.is_active = False
                        else:
                            raise ValueError
                    
                    db.commit()
                    
                    # Показываем обновленные данные
                    message_text = (
                        f"✅ *ЭКСПЕДИЦИЯ ОБНОВЛЕНА!*\n\n"
                        f"*Текущие данные:*\n"
                        f"1. Название: {excursion.name}\n"
                        f"2. Описание: {excursion.description[:100]}...\n"
                        f"3. Цена: {excursion.price_per_person} руб./чел.\n"
                        f"4. Минимальное количество: {excursion.min_people} чел.\n"
                        f"5. Максимальное количество: {excursion.max_people} чел.\n"
                        f"6. Длительность: {excursion.duration_hours} час.\n"
                        f"7. Статус: {'Активна' if excursion.is_active else 'Не активна'}\n\n"
                        "Введите номер поля для редактирования (1-7) или 'готово' для завершения:\n"
                        "Для отмены нажмите ❌ Отмена"
                    )
                    
                    bot.send_message(
                        chat_id,
                        message_text,
                        parse_mode='Markdown',
                        reply_markup=keyboards.cancel_button()
                    )
                    
                    # Сбрасываем поле редактирования
                    StateManager.update_data(user_id, editing_field=None)
                    
            except ValueError:
                bot.send_message(
                    chat_id,
                    "❌ Неверный формат данных! Пожалуйста, введите корректные данные:",
                    reply_markup=keyboards.cancel_button()
                )
            except Exception as e:
                bot.send_message(
                    chat_id,
                    f"❌ Ошибка при обновлении: {str(e)}",
                    reply_markup=keyboards.cancel_button()
                )
        else:
            bot.send_message(
                chat_id,
                "❌ Неизвестная команда! Введите номер поля для редактирования (1-7):",
                reply_markup=keyboards.cancel_button()
            )

def handle_admin_excursion_price_settings(bot, message):
    """Настройка цен экскурсий"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    StateManager.set_state(user_id, UserStates.ADMIN_EXCURSION_PRICE_SETTINGS, StateData())
    
    with next(get_db()) as db:
        # Получаем текущие настройки
        commission = db.query(Setting).filter_by(key='guide_commission').first()
        
        message_text = (
            "💰 *НАСТРОЙКА ЦЕН ЭКСКУРСИЙ*\n\n"
            f"*Текущие настройки:*\n"
            f"• Комиссия для гидов: {commission.value if commission else '10'}%\n\n"
            "Выберите, что хотите изменить:"
        )
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(
            types.KeyboardButton('📝 Изменить комиссию гидов'),
            types.KeyboardButton('🔙 Назад')
        )
        
        bot.send_message(
            chat_id,
            message_text,
            parse_mode='Markdown',
            reply_markup=markup
        )

def handle_admin_set_guide_commission(bot, message):
    """Изменение комиссии гидов"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    StateManager.set_state(user_id, UserStates.ADMIN_SET_GUIDE_COMMISSION, StateData())
    
    bot.send_message(
        chat_id,
        "📝 *ИЗМЕНЕНИЕ КОМИССИИ ГИДОВ*\n\n"
        "Введите новую комиссию для гидов (в процентах):\n"
        "Пример: 12\n\n"
        "Для отмены нажмите ❌ Отмена",
        parse_mode='Markdown',
        reply_markup=keyboards.cancel_button()
    )

def handle_admin_set_guide_commission_input(bot, message):
    """Обработка ввода комиссии гидов"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_excursions_menu(bot, message)
        return
    
    try:
        commission = float(message.text.strip())
        if commission < 0 or commission > 50:
            raise ValueError
        
        with next(get_db()) as db:
            # Сохраняем комиссию
            setting = db.query(Setting).filter_by(key='guide_commission').first()
            if setting:
                setting.value = str(commission)
            else:
                setting = Setting(key='guide_commission', value=str(commission))
                db.add(setting)
            
            db.commit()
            
            bot.send_message(
                chat_id,
                f"✅ Комиссия для гидов успешно изменена на {commission}%!",
                reply_markup=keyboards.admin_excursions_menu()
            )
            StateManager.set_state(user_id, UserStates.ADMIN_EXCURSIONS, StateData())
            
    except (ValueError, TypeError):
        bot.send_message(
            chat_id,
            "❌ Неверный формат комиссии! Введите число от 0 до 50:",
            reply_markup=keyboards.cancel_button()
        )

# ========== ФУНКЦИИ ДЛЯ ЭКСПЕДИЦИЙ (ИСПРАВЛЕННЫЕ) ==========

def handle_admin_add_expedition(bot, message):
    """Добавление экспедиции"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    StateManager.set_state(user_id, UserStates.ADMIN_ADD_EXPEDITION_NAME, StateData())
    
    bot.send_message(
        chat_id,
        "➕ *ДОБАВЛЕНИЕ ЭКСПЕДИЦИИ*\n\n"
        "Введите название экспедиции:\n\n"
        "Для отмены нажмите ❌ Отмена",
        parse_mode='Markdown',
        reply_markup=keyboards.cancel_button()
    )

def handle_admin_add_expedition_name_input(bot, message):
    """Обработка ввода названия экспедиции"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_expeditions_menu(bot, message)
        return
    
    name = message.text.strip()
    if len(name) < 3:
        bot.send_message(
            chat_id,
            "❌ Название слишком короткое! Введите название минимум из 3 символов:",
            reply_markup=keyboards.cancel_button()
        )
        return
    
    StateManager.set_state(
        user_id,
        UserStates.ADMIN_ADD_EXPEDITION_DESC,
        StateData(name=name)
    )
    
    bot.send_message(
        chat_id,
        "📝 *ВВЕДИТЕ ОПИСАНИЕ ЭКСПЕДИЦИИ:*\n\n"
        "Опишите экспедицию, маршрут, цели:\n\n"
        "Для отмены нажмите ❌ Отмена",
        parse_mode='Markdown',
        reply_markup=keyboards.cancel_button()
    )

def handle_admin_add_expedition_desc_input(bot, message):
    """Обработка ввода описания экспедиции"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_expeditions_menu(bot, message)
        return
    
    data = StateManager.get_data(user_id)
    description = message.text.strip()
    
    if len(description) < 10:
        bot.send_message(
            chat_id,
            "❌ Описание слишком короткое! Введите подробное описание:",
            reply_markup=keyboards.cancel_button()
        )
        return
    
    StateManager.set_state(
        user_id,
        UserStates.ADMIN_ADD_EXPEDITION_PROGRAM,
        StateData(name=data.name, description=description)
    )
    
    bot.send_message(
        chat_id,
        "📋 *ВВЕДИТЕ ПРОГРАММУ ЭКСПЕДИЦИИ:*\n\n"
        "Опишите подробную программу по дням:\n"
        "Пример:\n"
        "День 1: Встреча, переезд в базовый лагерь\n"
        "День 2: Акклиматизация, тренировка\n"
        "День 3: Восхождение\n\n"
        "Для отмены нажмите ❌ Отмена",
        parse_mode='Markdown',
        reply_markup=keyboards.cancel_button()
    )

def handle_admin_add_expedition_program_input(bot, message):
    """Обработка ввода программы экспедиции"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_expeditions_menu(bot, message)
        return
    
    data = StateManager.get_data(user_id)
    program = message.text.strip()
    
    if len(program) < 20:
        bot.send_message(
            chat_id,
            "❌ Программа слишком короткая! Введите подробную программу:",
            reply_markup=keyboards.cancel_button()
        )
        return
    
    StateManager.set_state(
        user_id,
        UserStates.ADMIN_ADD_EXPEDITION_INCLUDED,
        StateData(name=data.name, description=data.description, program=program)
    )
    
    bot.send_message(
        chat_id,
        "📦 *ЧТО ВКЛЮЧЕНО В СТОИМОСТЬ:*\n\n"
        "Перечислите, что включено в стоимость экспедиции:\n"
        "Пример:\n"
        "• Проживание в палатках\n"
        "• Питание\n"
        "• Услуги гида\n"
        "• Трансфер\n\n"
        "Для отмены нажмите ❌ Отмена",
        parse_mode='Markdown',
        reply_markup=keyboards.cancel_button()
    )

def handle_admin_add_expedition_included_input(bot, message):
    """Обработка ввода включенных услуг"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_expeditions_menu(bot, message)
        return
    
    data = StateManager.get_data(user_id)
    included = message.text.strip()
    
    if len(included) < 10:
        bot.send_message(
            chat_id,
            "❌ Список слишком короткий! Введите подробный список:",
            reply_markup=keyboards.cancel_button()
        )
        return
    
    StateManager.set_state(
        user_id,
        UserStates.ADMIN_ADD_EXPEDITION_PRICE,
        StateData(
            name=data.name,
            description=data.description,
            program=data.program,
            included=included
        )
    )
    
    bot.send_message(
        chat_id,
        "💰 *ВВЕДИТЕ ЦЕНУ ЭКСПЕДИЦИИ (в рублях):*\n\n"
        "Пример: 25000\n\n"
        "Для отмены нажмите ❌ Отмена",
        parse_mode='Markdown',
        reply_markup=keyboards.cancel_button()
    )

def handle_admin_add_expedition_price_input(bot, message):
    """Обработка ввода цены экспедиции"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_expeditions_menu(bot, message)
        return
    
    try:
        price = float(message.text.strip())
        if price <= 0:
            raise ValueError
        
        data = StateManager.get_data(user_id)
        StateManager.set_state(
            user_id,
            UserStates.ADMIN_ADD_EXPEDITION_START_DATE,
            StateData(
                name=data.name,
                description=data.description,
                program=data.program,
                included=data.included,
                price=price
            )
        )
        
        bot.send_message(
            chat_id,
            "📅 *ВВЕДИТЕ ДАТУ НАЧАЛА ЭКСПЕДИЦИИ (в формате ДД.ММ.ГГГГ):*\n\n"
            "Пример: 15.02.2025\n\n"
            "Для отмены нажмите ❌ Отмена",
            parse_mode='Markdown',
            reply_markup=keyboards.cancel_button()
        )
        
    except (ValueError, TypeError):
        bot.send_message(
            chat_id,
            "❌ Неверный формат цены! Введите число больше 0:",
            reply_markup=keyboards.cancel_button()
        )

def handle_admin_add_expedition_start_date_input(bot, message):
    """Обработка ввода даты начала экспедиции"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_expeditions_menu(bot, message)
        return
    
    try:
        start_date = datetime.strptime(message.text.strip(), "%d.%m.%Y")
        data = StateManager.get_data(user_id)
        
        StateManager.set_state(
            user_id,
            UserStates.ADMIN_ADD_EXPEDITION_END_DATE,
            StateData(
                name=data.name,
                description=data.description,
                program=data.program,
                included=data.included,
                price=data.price,
                start_date_str=start_date.strftime("%d.%m.%Y")
            )
        )
        
        bot.send_message(
            chat_id,
            "📅 *ВВЕДИТЕ ДАТУ ОКОНЧАНИЯ ЭКСПЕДИЦИИ (в формате ДД.ММ.ГГГГ):*\n\n"
            "Пример: 20.02.2025\n\n"
            "Для отмены нажмите ❌ Отмена",
            parse_mode='Markdown',
            reply_markup=keyboards.cancel_button()
        )
        
    except ValueError:
        bot.send_message(
            chat_id,
            "❌ Неверный формат даты! Введите дату в формате ДД.ММ.ГГГГ:",
            reply_markup=keyboards.cancel_button()
        )

def handle_admin_add_expedition_end_date_input(bot, message):
    """Обработка ввода даты окончания экспедиции"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_expeditions_menu(bot, message)
        return
    
    try:
        end_date = datetime.strptime(message.text.strip(), "%d.%m.%Y")
        data = StateManager.get_data(user_id)
        start_date = datetime.strptime(data.start_date_str, "%d.%m.%Y")
        
        if end_date <= start_date:
            bot.send_message(
                chat_id,
                "❌ Дата окончания должна быть позже даты начала!",
                reply_markup=keyboards.cancel_button()
            )
            return
        
        StateManager.set_state(
            user_id,
            UserStates.ADMIN_ADD_EXPEDITION_MAX_PEOPLE,
            StateData(
                name=data.name,
                description=data.description,
                program=data.program,
                included=data.included,
                price=data.price,
                start_date_str=data.start_date_str,
                end_date_str=end_date.strftime("%d.%m.%Y")
            )
        )
        
        bot.send_message(
            chat_id,
            "👥 *ВВЕДИТЕ МАКСИМАЛЬНОЕ КОЛИЧЕСТВО УЧАСТНИКОВ:*\n\n"
            "Пример: 10\n\n"
            "Для отмены нажмите ❌ Отмена",
            parse_mode='Markdown',
            reply_markup=keyboards.cancel_button()
        )
        
    except ValueError:
        bot.send_message(
            chat_id,
            "❌ Неверный формат даты! Введите дату в формате ДД.ММ.ГГГГ:",
            reply_markup=keyboards.cancel_button()
        )

def handle_admin_add_expedition_max_people_input(bot, message):
    """Обработка ввода максимального количества участников"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_expeditions_menu(bot, message)
        return
    
    try:
        max_people = int(message.text.strip())
        if max_people <= 0:
            raise ValueError
        
        data = StateManager.get_data(user_id)
        
        # Сохраняем экспедицию в базу данных
        with next(get_db()) as db:
            start_date = datetime.strptime(data.start_date_str, "%d.%m.%Y")
            end_date = datetime.strptime(data.end_date_str, "%d.%m.%Y")
            
            expedition = Expedition(
                name=data.name,
                description=data.description,
                program=data.program,
                included=data.included,
                price=data.price,
                start_date=start_date,
                end_date=end_date,
                max_participants=max_people,
                is_active=True
            )
            db.add(expedition)
            db.commit()
            
            message_text = (
                "✅ *ЭКСПЕДИЦИЯ УСПЕШНО ДОБАВЛЕНА!*\n\n"
                f"*Название:* {data.name}\n"
                f"*Описание:* {data.description[:100]}...\n"
                f"*Программа:* {data.program[:100]}...\n"
                f"*Включено:* {data.included[:100]}...\n"
                f"*Цена:* {data.price} руб.\n"
                f"*Даты:* {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}\n"
                f"*Максимум участников:* {max_people} чел.\n"
                f"*ID экспедиции:* {expedition.id}\n\n"
                "Экспедиция теперь доступна для бронирования клиентами."
            )
            
            bot.send_message(
                chat_id,
                message_text,
                parse_mode='Markdown',
                reply_markup=keyboards.admin_expeditions_menu()
            )
            StateManager.set_state(user_id, UserStates.ADMIN_EXPEDITIONS, StateData())
            
    except (ValueError, TypeError):
        bot.send_message(
            chat_id,
            "❌ Неверный формат! Введите целое число больше 0:",
            reply_markup=keyboards.cancel_button()
        )

def handle_admin_expeditions_list(bot, message):
    """Список экспедиций"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    with next(get_db()) as db:
        # Получаем все экспедиции
        expeditions = db.query(Expedition).order_by(Expedition.start_date.desc()).all()
        
        if not expeditions:
            bot.send_message(
                chat_id,
                "📋 *СПИСОК ЭКСПЕДИЦИЙ*\n\n"
                "Нет доступных экскурсий.",
                parse_mode='Markdown',
                reply_markup=keyboards.admin_expeditions_menu()
            )
            return
        
        # Отправляем по 3 экспедиции за раз
        for i in range(0, len(expeditions), 3):
            batch = expeditions[i:i+3]
            message_text = "📋 *СПИСОК ЭКСПЕДИЦИЙ*\n\n"
            
            for expedition in batch:
                status = "✅ Активна" if expedition.is_active else "❌ Не активна"
                bookings_count = db.query(ExpeditionBooking).filter_by(expedition_id=expedition.id).count()
                
                message_text += f"*ID:* {expedition.id}\n"
                message_text += f"*Название:* {expedition.name}\n"
                message_text += f"*Цена:* {expedition.price} руб.\n"
                message_text += f"*Даты:* {expedition.start_date.strftime('%d.%m.%Y')} - {expedition.end_date.strftime('%d.%m.%Y')}\n"
                message_text += f"*Участников:* до {expedition.max_participants} чел.\n"
                message_text += f"*Статус:* {status}\n"
                message_text += f"*Бронирований:* {bookings_count}\n"
                message_text += "─" * 20 + "\n"
            
            if i + 3 < len(expeditions):
                message_text += f"\nПоказано {i+1}-{i+len(batch)} из {len(expeditions)}"
            
            bot.send_message(
                chat_id,
                message_text,
                parse_mode='Markdown'
            )
        
        # Добавляем кнопки управления
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton('📊 Экспорт в CSV', callback_data='admin_export_expeditions'),
            types.InlineKeyboardButton('🔄 Обновить', callback_data='admin_refresh_expeditions')
        )
        
        bot.send_message(
            chat_id,
            "Выберите действие:",
            reply_markup=markup
        )
        
        StateManager.set_state(user_id, UserStates.ADMIN_EXPEDITIONS, StateData())

def handle_admin_expeditions_list_from_callback(bot, call):
    """Обновление списка экспедиций из callback"""
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    # Удаляем предыдущее сообщение
    try:
        bot.delete_message(chat_id, call.message.message_id)
    except:
        pass
    
    with next(get_db()) as db:
        # Получаем все экспедиции
        expeditions = db.query(Expedition).order_by(Expedition.start_date.desc()).all()
        
        if not expeditions:
            bot.send_message(
                chat_id,
                "📋 *СПИСОК ЭКСПЕДИЦИЙ*\n\n"
                "Нет доступных экскурсий.",
                parse_mode='Markdown',
                reply_markup=keyboards.admin_expeditions_menu()
            )
            return
        
        # Отправляем по 3 экспедиции за раз
        for i in range(0, len(expeditions), 3):
            batch = expeditions[i:i+3]
            message_text = "📋 *СПИСОК ЭКСПЕДИЦИЙ*\n\n"
            
            for expedition in batch:
                status = "✅ Активна" if expedition.is_active else "❌ Не активна"
                bookings_count = db.query(ExpeditionBooking).filter_by(expedition_id=expedition.id).count()
                
                message_text += f"*ID:* {expedition.id}\n"
                message_text += f"*Название:* {expedition.name}\n"
                message_text += f"*Цена:* {expedition.price} руб.\n"
                message_text += f"*Даты:* {expedition.start_date.strftime('%d.%m.%Y')} - {expedition.end_date.strftime('%d.%m.%Y')}\n"
                message_text += f"*Участников:* до {expedition.max_participants} чел.\n"
                message_text += f"*Статус:* {status}\n"
                message_text += f"*Бронирований:* {bookings_count}\n"
                message_text += "─" * 20 + "\n"
            
            if i + 3 < len(expeditions):
                message_text += f"\nПоказано {i+1}-{i+len(batch)} из {len(expeditions)}"
            
            bot.send_message(
                chat_id,
                message_text,
                parse_mode='Markdown'
            )
        
        # Добавляем кнопки управления
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton('📊 Экспорт в CSV', callback_data='admin_export_expeditions'),
            types.InlineKeyboardButton('🔄 Обновить', callback_data='admin_refresh_expeditions')
        )
        
        bot.send_message(
            chat_id,
            "Выберите действие:",
            reply_markup=markup
        )
        
    bot.answer_callback_query(call.id, "✅ Список обновлен!")

def handle_admin_edit_expedition(bot, message):
    """Редактирование экспедиции"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    StateManager.set_state(user_id, UserStates.ADMIN_EDIT_EXPEDITION, StateData())
    
    bot.send_message(
        chat_id,
        "✏️ *РЕДАКТИРОВАНИЕ ЭКСПЕДИЦИИ*\n\n"
        "Введите ID экспедиции для редактирования:\n\n"
        "Для отмены нажмите ❌ Отмена",
        parse_mode='Markdown',
        reply_markup=keyboards.cancel_button()
    )

def handle_admin_edit_expedition_input(bot, message):
    """Обработка ввода ID экспедиции для редактирования (ИСПРАВЛЕННАЯ)"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_expeditions_menu(bot, message)
        return
    
    try:
        expedition_id = int(message.text.strip())
        
        with next(get_db()) as db:
            # Находим экспедицию
            expedition = db.query(Expedition).filter_by(id=expedition_id).first()
            if not expedition:
                bot.send_message(
                    chat_id,
                    f"❌ Экспедиция с ID {expedition_id} не найдена!",
                    reply_markup=keyboards.admin_expeditions_menu()
                )
                StateManager.set_state(user_id, UserStates.ADMIN_EXPEDITIONS, StateData())
                return
            
            # Сохраняем данные экспедиции в StateData БЕЗ datetime объектов
            StateManager.set_state(
                user_id,
                UserStates.ADMIN_EDIT_EXPEDITION_DETAILS,
                StateData(
                    expedition_id=expedition_id,
                    expedition_name=expedition.name,
                    expedition_description=expedition.description,
                    expedition_program=expedition.program,
                    expedition_included=expedition.included,
                    expedition_price=expedition.price,
                    expedition_start_date_str=expedition.start_date.strftime('%d.%m.%Y'),
                    expedition_end_date_str=expedition.end_date.strftime('%d.%m.%Y'),
                    expedition_max_people=expedition.max_participants,
                    expedition_active=expedition.is_active
                )
            )
            
            # Показываем информацию об экспедиции
            message_text = (
                f"✏️ *РЕДАКТИРОВАНИЕ ЭКСПЕДИЦИИ #{expedition_id}*\n\n"
                f"*Текущие данные:*\n"
                f"1. Название: {expedition.name}\n"
                f"2. Описание: {expedition.description[:100]}...\n"
                f"3. Программа: {expedition.program[:100]}...\n"
                f"4. Включено: {expedition.included[:100]}...\n"
                f"5. Цена: {expedition.price} руб.\n"
                f"6. Дата начала: {expedition.start_date.strftime('%d.%m.%Y')}\n"
                f"7. Дата окончания: {expedition.end_date.strftime('%d.%m.%Y')}\n"
                f"8. Максимум участников: {expedition.max_participants} чел.\n"
                f"9. Статус: {'Активна' if expedition.is_active else 'Не активна'}\n\n"
                "Введите номер поля для редактирования (1-9):\n"
                "Для отмены нажмите ❌ Отмена"
            )
            
            bot.send_message(
                chat_id,
                message_text,
                parse_mode='Markdown',
                reply_markup=keyboards.cancel_button()
            )
            
    except ValueError:
        bot.send_message(
            chat_id,
            "❌ Неверный формат ID! Введите число:",
            reply_markup=keyboards.cancel_button()
        )

def handle_admin_edit_expedition_details_input(bot, message):
    """Обработка редактирования деталей экспедиции (ИСПРАВЛЕННАЯ)"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_expeditions_menu(bot, message)
        return
    
    data = StateManager.get_data(user_id)
    
    try:
        # Пытаемся понять, вводит ли пользователь номер поля или значение
        field_num = int(message.text.strip())
        
        if field_num == 1:
            bot.send_message(
                chat_id,
                "Введите новое название экспедиции:",
                reply_markup=keyboards.cancel_button()
            )
            StateManager.update_data(user_id, editing_field='name')
            
        elif field_num == 2:
            bot.send_message(
                chat_id,
                "Введите новое описание экспедиции:",
                reply_markup=keyboards.cancel_button()
            )
            StateManager.update_data(user_id, editing_field='description')
            
        elif field_num == 3:
            bot.send_message(
                chat_id,
                "Введите новую программу экспедиции:",
                reply_markup=keyboards.cancel_button()
            )
            StateManager.update_data(user_id, editing_field='program')
            
        elif field_num == 4:
            bot.send_message(
                chat_id,
                "Введите новый список включенных услуг:",
                reply_markup=keyboards.cancel_button()
            )
            StateManager.update_data(user_id, editing_field='included')
            
        elif field_num == 5:
            bot.send_message(
                chat_id,
                "Введите новую цену экспедиции (в рублях):",
                reply_markup=keyboards.cancel_button()
            )
            StateManager.update_data(user_id, editing_field='price')
            
        elif field_num == 6:
            bot.send_message(
                chat_id,
                "Введите новую дату начала (в формате ДД.ММ.ГГГГ):",
                reply_markup=keyboards.cancel_button()
            )
            StateManager.update_data(user_id, editing_field='start_date')
            
        elif field_num == 7:
            bot.send_message(
                chat_id,
                "Введите новую дату окончания (в формате ДД.ММ.ГГГГ):",
                reply_markup=keyboards.cancel_button()
            )
            StateManager.update_data(user_id, editing_field='end_date')
            
        elif field_num == 8:
            bot.send_message(
                chat_id,
                "Введите новое максимальное количество участников:",
                reply_markup=keyboards.cancel_button()
            )
            StateManager.update_data(user_id, editing_field='max_people')
            
        elif field_num == 9:
            bot.send_message(
                chat_id,
                "Изменить статус экспедиции:\n"
                "1. Активировать\n"
                "2. Деактивировать\n\n"
                "Введите 1 или 2:",
                reply_markup=keyboards.cancel_button()
            )
            StateManager.update_data(user_id, editing_field='status')
            
        else:
            bot.send_message(
                chat_id,
                "❌ Неверный номер поля! Введите число от 1 до 9:",
                reply_markup=keyboards.cancel_button()
            )
            
    except ValueError:
        # Пользователь ввел текст для редактирования поля
        if hasattr(data, 'editing_field'):
            editing_field = data.editing_field
            try:
                with next(get_db()) as db:
                    expedition = db.query(Expedition).filter_by(id=data.expedition_id).first()
                    
                    if editing_field == 'name':
                        expedition.name = message.text.strip()
                    elif editing_field == 'description':
                        expedition.description = message.text.strip()
                    elif editing_field == 'program':
                        expedition.program = message.text.strip()
                    elif editing_field == 'included':
                        expedition.included = message.text.strip()
                    elif editing_field == 'price':
                        price = float(message.text.strip())
                        if price <= 0:
                            raise ValueError
                        expedition.price = price
                    elif editing_field == 'start_date':
                        start_date = datetime.strptime(message.text.strip(), "%d.%m.%Y")
                        expedition.start_date = start_date
                        # Обновляем строку в данных
                        data.expedition_start_date_str = start_date.strftime('%d.%m.%Y')
                    elif editing_field == 'end_date':
                        end_date = datetime.strptime(message.text.strip(), "%d.%m.%Y")
                        expedition.end_date = end_date
                        # Обновляем строку в данных
                        data.expedition_end_date_str = end_date.strftime('%d.%m.%Y')
                    elif editing_field == 'max_people':
                        max_people = int(message.text.strip())
                        if max_people <= 0:
                            raise ValueError
                        expedition.max_participants = max_people
                    elif editing_field == 'status':
                        if message.text.strip() == '1':
                            expedition.is_active = True
                        elif message.text.strip() == '2':
                            expedition.is_active = False
                        else:
                            raise ValueError
                    
                    db.commit()
                    
                    # Обновляем данные в состоянии
                    StateManager.update_data(
                        user_id,
                        expedition_name=expedition.name,
                        expedition_description=expedition.description,
                        expedition_program=expedition.program,
                        expedition_included=expedition.included,
                        expedition_price=expedition.price,
                        expedition_start_date_str=expedition.start_date.strftime('%d.%m.%Y'),
                        expedition_end_date_str=expedition.end_date.strftime('%d.%m.%Y'),
                        expedition_max_people=expedition.max_participants,
                        expedition_active=expedition.is_active,
                        editing_field=None  # Сбрасываем поле редактирования
                    )
                    
                    # Показываем обновленные данные
                    message_text = (
                        f"✅ *ЭКСПЕДИЦИЯ ОБНОВЛЕНА!*\n\n"
                        f"*Текущие данные:*\n"
                        f"1. Название: {expedition.name}\n"
                        f"2. Описание: {expedition.description[:100]}...\n"
                        f"3. Программа: {expedition.program[:100]}...\n"
                        f"4. Включено: {expedition.included[:100]}...\n"
                        f"5. Цена: {expedition.price} руб.\n"
                        f"6. Дата начала: {expedition.start_date.strftime('%d.%m.%Y')}\n"
                        f"7. Дата окончания: {expedition.end_date.strftime('%d.%m.%Y')}\n"
                        f"8. Максимум участников: {expedition.max_participants} чел.\n"
                        f"9. Статус: {'Активна' if expedition.is_active else 'Не активна'}\n\n"
                        "Введите номер поля для редактирования (1-9) или 'готово' для завершения:\n"
                        "Для отмены нажмите ❌ Отмена"
                    )
                    
                    bot.send_message(
                        chat_id,
                        message_text,
                        parse_mode='Markdown',
                        reply_markup=keyboards.cancel_button()
                    )
                    
            except ValueError as e:
                bot.send_message(
                    chat_id,
                    f"❌ Неверный формат данных! {str(e)}",
                    reply_markup=keyboards.cancel_button()
                )
            except Exception as e:
                bot.send_message(
                    chat_id,
                    f"❌ Ошибка при обновлении: {str(e)}",
                    reply_markup=keyboards.cancel_button()
                )
        else:
            bot.send_message(
                chat_id,
                "❌ Неизвестная команда! Введите номер поля для редактирования (1-9):",
                reply_markup=keyboards.cancel_button()
            )

def handle_admin_confirm_expedition_payment(bot, message):
    """Подтверждение оплаты экспедиции"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    StateManager.set_state(user_id, UserStates.ADMIN_CONFIRM_EXPEDITION_PAYMENT, StateData())
    
    bot.send_message(
        chat_id,
        "✅ *ПОДТВЕРЖДЕНИЕ ОПЛАТЫ ЭКСПЕДИЦИИ*\n\n"
        "Введите ID бронирования экспедиции:\n\n"
        "Для отмены нажмите ❌ Отмена",
        parse_mode='Markdown',
        reply_markup=keyboards.cancel_button()
    )

def handle_admin_confirm_expedition_payment_input(bot, message):
    """Обработка ввода ID бронирования для подтверждения оплаты"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_expeditions_menu(bot, message)
        return
    
    try:
        booking_id = int(message.text.strip())
        
        with next(get_db()) as db:
            # Находим бронирование
            booking = db.query(ExpeditionBooking).filter_by(id=booking_id).first()
            if not booking:
                bot.send_message(
                    chat_id,
                    f"❌ Бронирование с ID {booking_id} не найдено!",
                    reply_markup=keyboards.admin_expeditions_menu()
                )
                StateManager.set_state(user_id, UserStates.ADMIN_EXPEDITIONS, StateData())
                return
            
            # Подтверждаем оплату
            booking.payment_status = 'paid'
            booking.confirmed_at = datetime.now()
            db.commit()
            
            # Получаем экспедицию
            expedition = db.query(Expedition).filter_by(id=booking.expedition_id).first()
            
            # Уведомляем пользователя
            try:
                user = db.query(User).filter_by(id=booking.user_id).first()
                if user and user.user_id:
                    bot.send_message(
                        user.user_id,
                        f"✅ *ОПЛАТА ЭКСПЕДИЦИИ ПОДТВЕРЖДЕНА!*\n\n"
                        f"*Экспедиция:* {expedition.name if expedition else 'Не указана'}\n"
                        f"*Номер брони:* {booking.booking_id}\n"
                        f"*Количество человек:* {booking.people_count}\n"
                        f"*Дата подтверждения:* {booking.confirmed_at.strftime('%d.%m.%Y %H:%M')}\n\n"
                        f"*С вами свяжется куратор экспедиции для уточнения деталей.*\n\n"
                        f"Спасибо за выбор нашей экспедиции! 🧊",
                        parse_mode='Markdown'
                    )
            except Exception as e:
                print(f"Ошибка уведомления пользователя: {e}")
            
            bot.send_message(
                chat_id,
                f"✅ Оплата бронирования ID {booking_id} успешно подтверждена!\n"
                f"Пользователь уведомлен.",
                reply_markup=keyboards.admin_expeditions_menu()
            )
            StateManager.set_state(user_id, UserStates.ADMIN_EXPEDITIONS, StateData())
            
    except ValueError:
        bot.send_message(
            chat_id,
            "❌ Неверный формат ID! Введите число:",
            reply_markup=keyboards.cancel_button()
        )

# ========== ФУНКЦИИ ДЛЯ МАГАЗИНА (ИСПРАВЛЕННЫЕ) ==========

def handle_admin_add_product(bot, message):
    """Добавление товара"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    StateManager.set_state(user_id, UserStates.ADMIN_ADD_PRODUCT_NAME, StateData())
    
    bot.send_message(
        chat_id,
        "➕ *ДОБАВЛЕНИЕ ТОВАРА*\n\n"
        "Введите название товара:\n\n"
        "Для отмены нажмите ❌ Отмена",
        parse_mode='Markdown',
        reply_markup=keyboards.cancel_button()
    )

def handle_admin_add_product_name_input(bot, message):
    """Обработка ввода названия товара"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_shop_menu(bot, message)
        return
    
    name = message.text.strip()
    if len(name) < 2:
        bot.send_message(
            chat_id,
            "❌ Название слишком короткое! Введите название минимум из 2 символов:",
            reply_markup=keyboards.cancel_button()
        )
        return
    
    StateManager.set_state(
        user_id,
        UserStates.ADMIN_ADD_PRODUCT_TYPE,
        StateData(name=name)
    )
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('📦 Физический товар'),
        types.KeyboardButton('💻 Цифровой товар'),
        types.KeyboardButton('❌ Отмена')
    )
    
    bot.send_message(
        chat_id,
        "📦 *ВЫБЕРИТЕ ТИП ТОВАРА:*\n\n"
        "• *Физический товар* - требует доставки\n"
        "• *Цифровой товар* - отправляется по ссылке\n\n"
        "Выберите тип:",
        parse_mode='Markdown',
        reply_markup=markup
    )

def handle_admin_add_product_type_input(bot, message):
    """Обработка выбора типа товара"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_shop_menu(bot, message)
        return
    
    if message.text not in ['📦 Физический товар', '💻 Цифровой товар']:
        bot.send_message(
            chat_id,
            "❌ Пожалуйста, выберите тип товара из предложенных вариантов:",
            reply_markup=keyboards.cancel_button()
        )
        return
    
    data = StateManager.get_data(user_id)
    product_type = 'physical' if message.text == '📦 Физический товар' else 'digital'
    
    StateManager.set_state(
        user_id,
        UserStates.ADMIN_ADD_PRODUCT_DESC,
        StateData(name=data.name, product_type=product_type)
    )
    
    bot.send_message(
        chat_id,
        "📝 *ВВЕДИТЕ ОПИСАНИЕ ТОВАРА:*\n\n"
        "Опишите товар, его характеристики, преимущества:\n\n"
        "Для отмены нажмите ❌ Отмена",
        parse_mode='Markdown',
        reply_markup=keyboards.cancel_button()
    )

def handle_admin_add_product_desc_input(bot, message):
    """Обработка ввода описания товара"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_shop_menu(bot, message)
        return
    
    data = StateManager.get_data(user_id)
    description = message.text.strip()
    
    if len(description) < 5:
        bot.send_message(
            chat_id,
            "❌ Описание слишком короткое! Введите подробное описание:",
            reply_markup=keyboards.cancel_button()
        )
        return
    
    StateManager.set_state(
        user_id,
        UserStates.ADMIN_ADD_PRODUCT_PRICE,
        StateData(name=data.name, product_type=data.product_type, description=description)
    )
    
    bot.send_message(
        chat_id,
        "💰 *ВВЕДИТЕ ЦЕНУ ТОВАРА (в рублях):*\n\n"
        "Пример: 1500\n\n"
        "Для отмены нажмите ❌ Отмена",
        parse_mode='Markdown',
        reply_markup=keyboards.cancel_button()
    )

def handle_admin_add_product_price_input(bot, message):
    """Обработка ввода цены товара"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_shop_menu(bot, message)
        return
    
    try:
        price = float(message.text.strip())
        if price <= 0:
            raise ValueError
        
        data = StateManager.get_data(user_id)
        
        if data.product_type == 'physical':
            # Для физического товара запрашиваем количество на складе
            StateManager.set_state(
                user_id,
                UserStates.ADMIN_ADD_PRODUCT_STOCK,
                StateData(
                    name=data.name,
                    product_type=data.product_type,
                    description=data.description,
                    price=price
                )
            )
            
            bot.send_message(
                chat_id,
                "📊 *ВВЕДИТЕ КОЛИЧЕСТВО НА СКЛАДЕ:*\n\n"
                "Пример: 50\n\n"
                "Для отмены нажмите ❌ Отмена",
                parse_mode='Markdown',
                reply_markup=keyboards.cancel_button()
            )
        else:
            # Для цифрового товара запрашиваем ссылку на файл
            StateManager.set_state(
                user_id,
                UserStates.ADMIN_ADD_PRODUCT_FILE_URL,
                StateData(
                    name=data.name,
                    product_type=data.product_type,
                    description=data.description,
                    price=price
                )
            )
            
            bot.send_message(
                chat_id,
                "🔗 *ВВЕДИТЕ ССЫЛКУ НА ФАЙЛ (Google Drive или другой облачный сервис):*\n\n"
                "Пример: https://drive.google.com/file/d/...\n\n"
                "Для отмены нажмите ❌ Отмена",
                parse_mode='Markdown',
                reply_markup=keyboards.cancel_button()
            )
            
    except (ValueError, TypeError):
        bot.send_message(
            chat_id,
            "❌ Неверный формат цены! Введите число больше 0:",
            reply_markup=keyboards.cancel_button()
        )

def handle_admin_add_product_stock_input(bot, message):
    """Обработка ввода количества на складе"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_shop_menu(bot, message)
        return
    
    try:
        stock = int(message.text.strip())
        if stock < 0:
            raise ValueError
        
        data = StateManager.get_data(user_id)
        
        # Сохраняем товар в базу данных
        with next(get_db()) as db:
            product = ShopProduct(
                name=data.name,
                description=data.description,
                price=data.price,
                category=data.product_type,
                stock=stock,
                is_active=True
            )
            db.add(product)
            db.commit()
            
            message_text = (
                "✅ *ТОВАР УСПЕШНО ДОБАВЛЕН!*\n\n"
                f"*Название:* {data.name}\n"
                f"*Тип:* {'Физический товар' if data.product_type == 'physical' else 'Цифровой товар'}\n"
                f"*Описание:* {data.description[:100]}...\n"
                f"*Цена:* {data.price} руб.\n"
                f"*Количество на складе:* {stock} шт.\n"
                f"*ID товара:* {product.id}\n\n"
                "Товар теперь доступен в магазине."
            )
            
            bot.send_message(
                chat_id,
                message_text,
                parse_mode='Markdown',
                reply_markup=keyboards.admin_shop_menu()
            )
            StateManager.set_state(user_id, UserStates.ADMIN_SHOP, StateData())
            
    except (ValueError, TypeError):
        bot.send_message(
            chat_id,
            "❌ Неверный формат! Введите целое число (0 или больше):",
            reply_markup=keyboards.cancel_button()
        )

def handle_admin_add_product_file_url_input(bot, message):
    """Обработка ввода ссылки на файл"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_shop_menu(bot, message)
        return
    
    file_url = message.text.strip()
    if not file_url.startswith('http'):
        bot.send_message(
            chat_id,
            "❌ Неверный формат ссылки! Введите корректную URL-ссылку:",
            reply_markup=keyboards.cancel_button()
        )
        return
    
    data = StateManager.get_data(user_id)
    
    # Сохраняем товар в базу данных
    with next(get_db()) as db:
        product = ShopProduct(
            name=data.name,
            description=data.description,
            price=data.price,
            category=data.product_type,
            file_url=file_url,
            stock=999,  # Для цифровых товаров большое количество
            is_active=True
        )
        db.add(product)
        db.commit()
        
        message_text = (
            "✅ *ТОВАР УСПЕШНО ДОБАВЛЕН!*\n\n"
            f"*Название:* {data.name}\n"
            f"*Тип:* {'Физический товар' if data.product_type == 'physical' else 'Цифровой товар'}\n"
            f"*Описание:* {data.description[:100]}...\n"
            f"*Цена:* {data.price} руб.\n"
            f"*Ссылка на файл:* {file_url[:50]}...\n"
            f"*ID товара:* {product.id}\n\n"
            "Товар теперь доступен в магазине."
        )
        
        bot.send_message(
            chat_id,
            message_text,
            parse_mode='Markdown',
            reply_markup=keyboards.admin_shop_menu()
        )
        StateManager.set_state(user_id, UserStates.ADMIN_SHOP, StateData())

def handle_admin_products_list(bot, message):
    """Список товаров"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    with next(get_db()) as db:
        # Получаем все товары
        products = db.query(ShopProduct).order_by(ShopProduct.id.desc()).all()
        
        if not products:
            bot.send_message(
                chat_id,
                "📋 *СПИСОК ТОВАРОВ*\n\n"
                "Нет доступных товаров.",
                parse_mode='Markdown',
                reply_markup=keyboards.admin_shop_menu()
            )
            return
        
        # Отправляем по 5 товаров за раз
        for i in range(0, len(products), 5):
            batch = products[i:i+5]
            message_text = "📋 *СПИСОК ТОВАРОВ*\n\n"
            
            for product in batch:
                status = "✅ В наличии" if product.is_active else "❌ Не доступен"
                category = "📦 Физический" if product.category == 'physical' else "💻 Цифровой"
                stock_info = f"{product.stock} шт." if product.category == 'physical' else "∞"
                orders_count = db.query(ShopOrder).filter_by(product_id=product.id).count()
                
                message_text += f"*ID:* {product.id}\n"
                message_text += f"*Название:* {product.name}\n"
                message_text += f"*Тип:* {category}\n"
                message_text += f"*Цена:* {product.price} руб.\n"
                message_text += f"*На складе:* {stock_info}\n"
                message_text += f"*Статус:* {status}\n"
                message_text += f"*Заказов:* {orders_count}\n"
                message_text += "─" * 20 + "\n"
            
            if i + 5 < len(products):
                message_text += f"\nПоказано {i+1}-{i+len(batch)} из {len(products)}"
            
            bot.send_message(
                chat_id,
                message_text,
                parse_mode='Markdown'
            )
        
        # Добавляем кнопки управления
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton('📊 Экспорт в CSV', callback_data='admin_export_products'),
            types.InlineKeyboardButton('🔄 Обновить', callback_data='admin_refresh_products')
        )
        
        bot.send_message(
            chat_id,
            "Выберите действие:",
            reply_markup=markup
        )
        
        StateManager.set_state(user_id, UserStates.ADMIN_SHOP, StateData())

def handle_admin_products_list_from_callback(bot, call):
    """Обновление списка товаров из callback"""
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    # Удаляем предыдущее сообщение
    try:
        bot.delete_message(chat_id, call.message.message_id)
    except:
        pass
    
    with next(get_db()) as db:
        # Получаем все товары
        products = db.query(ShopProduct).order_by(ShopProduct.id.desc()).all()
        
        if not products:
            bot.send_message(
                chat_id,
                "📋 *СПИСОК ТОВАРОВ*\n\n"
                "Нет доступных товаров.",
                parse_mode='Markdown',
                reply_markup=keyboards.admin_shop_menu()
            )
            return
        
        # Отправляем по 5 товаров за раз
        for i in range(0, len(products), 5):
            batch = products[i:i+5]
            message_text = "📋 *СПИСОК ТОВАРОВ*\n\n"
            
            for product in batch:
                status = "✅ В наличии" if product.is_active else "❌ Не доступен"
                category = "📦 Физический" if product.category == 'physical' else "💻 Цифровой"
                stock_info = f"{product.stock} шт." if product.category == 'physical' else "∞"
                orders_count = db.query(ShopOrder).filter_by(product_id=product.id).count()
                
                message_text += f"*ID:* {product.id}\n"
                message_text += f"*Название:* {product.name}\n"
                message_text += f"*Тип:* {category}\n"
                message_text += f"*Цена:* {product.price} руб.\n"
                message_text += f"*На складе:* {stock_info}\n"
                message_text += f"*Статус:* {status}\n"
                message_text += f"*Заказов:* {orders_count}\n"
                message_text += "─" * 20 + "\n"
            
            if i + 5 < len(products):
                message_text += f"\nПоказано {i+1}-{i+len(batch)} из {len(products)}"
            
            bot.send_message(
                chat_id,
                message_text,
                parse_mode='Markdown'
            )
        
        # Добавляем кнопки управления
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton('📊 Экспорт в CSV', callback_data='admin_export_products'),
            types.InlineKeyboardButton('🔄 Обновить', callback_data='admin_refresh_products')
        )
        
        bot.send_message(
            chat_id,
            "Выберите действие:",
            reply_markup=markup
        )
        
    bot.answer_callback_query(call.id, "✅ Список обновлен!")

def handle_admin_edit_product(bot, message):
    """Редактирование товара"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    StateManager.set_state(user_id, UserStates.ADMIN_EDIT_PRODUCT, StateData())
    
    bot.send_message(
        chat_id,
        "✏️ *РЕДАКТИРОВАНИЕ ТОВАРА*\n\n"
        "Введите ID товара для редактирования:\n\n"
        "Для отмены нажмите ❌ Отмена",
        parse_mode='Markdown',
        reply_markup=keyboards.cancel_button()
    )

def handle_admin_edit_product_input(bot, message):
    """Обработка ввода ID товара для редактирования"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_shop_menu(bot, message)
        return
    
    try:
        product_id = int(message.text.strip())
        
        with next(get_db()) as db:
            # Находим товар
            product = db.query(ShopProduct).filter_by(id=product_id).first()
            if not product:
                bot.send_message(
                    chat_id,
                    f"❌ Товар с ID {product_id} не найден!",
                    reply_markup=keyboards.admin_shop_menu()
                )
                StateManager.set_state(user_id, UserStates.ADMIN_SHOP, StateData())
                return
            
            # Сохраняем данные товара
            StateManager.set_state(
                user_id,
                UserStates.ADMIN_EDIT_PRODUCT_DETAILS,
                StateData(
                    product_id=product_id,
                    product_name=product.name,
                    product_description=product.description,
                    product_price=product.price,
                    product_category=product.category,
                    product_stock=product.stock,
                    product_file_url=product.file_url,
                    product_active=product.is_active
                )
            )
            
            # Показываем информацию о товаре
            category = "📦 Физический" if product.category == 'physical' else "💻 Цифровой"
            stock_info = f"{product.stock} шт." if product.category == 'physical' else "Ссылка на файл"
            
            message_text = (
                f"✏️ *РЕДАКТИРОВАНИЕ ТОВАРА #{product_id}*\n\n"
                f"*Текущие данные:*\n"
                f"1. Название: {product.name}\n"
                f"2. Описание: {product.description[:100]}...\n"
                f"3. Цена: {product.price} руб.\n"
                f"4. Тип: {category}\n"
                f"5. Количество: {stock_info}\n"
                f"6. Статус: {'В наличии' if product.is_active else 'Не доступен'}\n\n"
                "Введите номер поля для редактирования (1-6):\n"
                "Для отмены нажмите ❌ Отмена"
            )
            
            bot.send_message(
                chat_id,
                message_text,
                parse_mode='Markdown',
                reply_markup=keyboards.cancel_button()
            )
            
    except ValueError:
        bot.send_message(
            chat_id,
            "❌ Неверный формат ID! Введите число:",
            reply_markup=keyboards.cancel_button()
        )

def handle_admin_edit_product_details_input(bot, message):
    """Обработка редактирования деталей товара"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_shop_menu(bot, message)
        return
    
    data = StateManager.get_data(user_id)
    
    try:
        field_num = int(message.text.strip())
        
        if field_num == 1:
            bot.send_message(
                chat_id,
                "Введите новое название товара:",
                reply_markup=keyboards.cancel_button()
            )
            StateManager.update_data(user_id, editing_field='name')
            
        elif field_num == 2:
            bot.send_message(
                chat_id,
                "Введите новое описание товара:",
                reply_markup=keyboards.cancel_button()
            )
            StateManager.update_data(user_id, editing_field='description')
            
        elif field_num == 3:
            bot.send_message(
                chat_id,
                "Введите новую цену товара (в рублях):",
                reply_markup=keyboards.cancel_button()
            )
            StateManager.update_data(user_id, editing_field='price')
            
        elif field_num == 4:
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
            markup.add(
                types.KeyboardButton('📦 Физический товар'),
                types.KeyboardButton('💻 Цифровой товар'),
                types.KeyboardButton('❌ Отмена')
            )
            bot.send_message(
                chat_id,
                "Выберите новый тип товара:",
                reply_markup=markup
            )
            StateManager.update_data(user_id, editing_field='category')
            
        elif field_num == 5:
            if data.product_category == 'physical':
                bot.send_message(
                    chat_id,
                    "Введите новое количество на складе:",
                    reply_markup=keyboards.cancel_button()
                )
                StateManager.update_data(user_id, editing_field='stock')
            else:
                bot.send_message(
                    chat_id,
                    "Введите новую ссылку на файл:",
                    reply_markup=keyboards.cancel_button()
                )
                StateManager.update_data(user_id, editing_field='file_url')
            
        elif field_num == 6:
            bot.send_message(
                chat_id,
                "Изменить статус товара:\n"
                "1. Активировать\n"
                "2. Деактивировать\n\n"
                "Введите 1 или 2:",
                reply_markup=keyboards.cancel_button()
            )
            StateManager.update_data(user_id, editing_field='status')
            
        else:
            bot.send_message(
                chat_id,
                "❌ Неверный номер поля! Введите число от 1 до 6:",
                reply_markup=keyboards.cancel_button()
            )
            
    except ValueError:
        # Пользователь ввел текст для редактирования поля
        if hasattr(data, 'editing_field'):
            editing_field = data.editing_field
            try:
                with next(get_db()) as db:
                    product = db.query(ShopProduct).filter_by(id=data.product_id).first()
                    
                    if editing_field == 'name':
                        product.name = message.text.strip()
                    elif editing_field == 'description':
                        product.description = message.text.strip()
                    elif editing_field == 'price':
                        price = float(message.text.strip())
                        if price <= 0:
                            raise ValueError
                        product.price = price
                    elif editing_field == 'category':
                        if message.text == '📦 Физический товар':
                            product.category = 'physical'
                        elif message.text == '💻 Цифровой товар':
                            product.category = 'digital'
                        else:
                            raise ValueError
                    elif editing_field == 'stock':
                        if product.category == 'physical':
                            stock = int(message.text.strip())
                            if stock < 0:
                                raise ValueError
                            product.stock = stock
                    elif editing_field == 'file_url':
                        if product.category == 'digital':
                            file_url = message.text.strip()
                            if not file_url.startswith('http'):
                                raise ValueError
                            product.file_url = file_url
                    elif editing_field == 'status':
                        if message.text.strip() == '1':
                            product.is_active = True
                        elif message.text.strip() == '2':
                            product.is_active = False
                        else:
                            raise ValueError
                    
                    db.commit()
                    
                    # Показываем обновленные данные
                    category = "📦 Физический" if product.category == 'physical' else "💻 Цифровой"
                    stock_info = f"{product.stock} шт." if product.category == 'physical' else "Ссылка на файл"
                    
                    message_text = (
                        f"✅ *ТОВАР ОБНОВЛЕН!*\n\n"
                        f"*Текущие данные:*\n"
                        f"1. Название: {product.name}\n"
                        f"2. Описание: {product.description[:100]}...\n"
                        f"3. Цена: {product.price} руб.\n"
                        f"4. Тип: {category}\n"
                        f"5. Количество: {stock_info}\n"
                        f"6. Статус: {'В наличии' if product.is_active else 'Не доступен'}\n\n"
                        "Введите номер поля для редактирования (1-6) или 'готово' для завершения:\n"
                        "Для отмены нажмите ❌ Отмена"
                    )
                    
                    bot.send_message(
                        chat_id,
                        message_text,
                        parse_mode='Markdown',
                        reply_markup=keyboards.cancel_button()
                    )
                    
                    # Сбрасываем поле редактирования
                    StateManager.update_data(user_id, editing_field=None)
                    
            except ValueError:
                bot.send_message(
                    chat_id,
                    "❌ Неверный формат данных! Пожалуйста, введите корректные данные:",
                    reply_markup=keyboards.cancel_button()
                )
            except Exception as e:
                bot.send_message(
                    chat_id,
                    f"❌ Ошибка при обновлении: {str(e)}",
                    reply_markup=keyboards.cancel_button()
                )
        else:
            bot.send_message(
                chat_id,
                "❌ Неизвестная команда! Введите номер поля для редактирования (1-6):",
                reply_markup=keyboards.cancel_button()
            )

def handle_admin_view_orders(bot, message):
    """Просмотр заказов магазина"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    StateManager.set_state(user_id, UserStates.ADMIN_VIEW_ORDERS, StateData())
    
    bot.send_message(
        chat_id,
        "📦 *ПРОСМОТР ЗАКАЗОВ МАГАЗИНА*\n\n"
        "Выберите статус заказов для просмотра:",
        parse_mode='Markdown',
        reply_markup=keyboards.create_orders_filter_keyboard()
    )

def handle_admin_view_orders_input(bot, message):
    """Обработка выбора фильтра заказов"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '🔙 Назад в меню':
        handle_admin_shop_menu(bot, message)
        return
    
    with next(get_db()) as db:
        # Определяем фильтр по статусу
        if message.text == '📋 Все заказы':
            orders = db.query(ShopOrder).order_by(ShopOrder.created_at.desc()).all()
            filter_text = "Все заказы"
            
        elif message.text == '⏳ Ожидают оплаты':
            orders = db.query(ShopOrder).filter_by(payment_status='unpaid').order_by(ShopOrder.created_at.desc()).all()
            filter_text = "Ожидают оплаты"
            
        elif message.text == '✅ Активные':
            orders = db.query(ShopOrder).filter(ShopOrder.status.in_(['paid', 'shipped'])).order_by(ShopOrder.created_at.desc()).all()
            filter_text = "Активные"
            
        elif message.text == '🏁 Завершенные':
            orders = db.query(ShopOrder).filter_by(status='delivered').order_by(ShopOrder.created_at.desc()).all()
            filter_text = "Завершенные"
            
        elif message.text == '❌ Отмененные':
            orders = db.query(ShopOrder).filter_by(status='cancelled').order_by(ShopOrder.created_at.desc()).all()
            filter_text = "Отмененные"
            
        else:
            orders = db.query(ShopOrder).order_by(ShopOrder.created_at.desc()).all()
            filter_text = "Все заказы"
        
        if not orders:
            bot.send_message(
                chat_id,
                f"📦 *ЗАКАЗЫ МАГАЗИНА ({filter_text})*\n\n"
                "Нет заказов с выбранным фильтром.",
                parse_mode='Markdown',
                reply_markup=keyboards.admin_shop_menu()
            )
            StateManager.set_state(user_id, UserStates.ADMIN_SHOP, StateData())
            return
        
        # Отправляем по 5 заказов за раз
        for i in range(0, len(orders), 5):
            batch = orders[i:i+5]
            message_text = f"📦 *ЗАКАЗЫ МАГАЗИНА ({filter_text})*\n\n"
            
            for order in batch:
                user = db.query(User).filter_by(id=order.user_id).first()
                product = db.query(ShopProduct).filter_by(id=order.product_id).first()
                user_info = f"{user.first_name} {user.last_name}" if user else "Неизвестно"
                product_name = product.name if product else "Товар удален"
                
                status_icons = {
                    'pending': '⏳',
                    'paid': '✅',
                    'shipped': '🚚',
                    'delivered': '🏁',
                    'cancelled': '❌'
                }
                status_icon = status_icons.get(order.status, '❓')
                
                message_text += f"*ID заказа:* {order.id}\n"
                message_text += f"*Клиент:* {user_info}\n"
                message_text += f"*Товар:* {product_name}\n"
                message_text += f"*Количество:* {order.quantity} шт.\n"
                message_text += f"*Стоимость:* {order.total_price} руб.\n"
                message_text += f"*Статус:* {status_icon} {order.status}\n"
                message_text += f"*Оплата:* {order.payment_status}\n"
                message_text += f"*Дата:* {order.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                message_text += "─" * 20 + "\n"
            
            if i + 5 < len(orders):
                message_text += f"\nПоказано {i+1}-{i+len(batch)} из {len(orders)}"
            
            bot.send_message(
                chat_id,
                message_text,
                parse_mode='Markdown'
            )
        
        # Добавляем кнопки управления
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton('📊 Экспорт в CSV', callback_data='admin_export_orders'),
            types.InlineKeyboardButton('🔄 Обновить', callback_data='admin_refresh_orders')
        )
        
        bot.send_message(
            chat_id,
            "Выберите действие:",
            reply_markup=markup
        )
        
        StateManager.set_state(user_id, UserStates.ADMIN_SHOP, StateData())

def handle_admin_view_orders_from_callback(bot, call):
    """Обновление списка заказов из callback"""
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    # Удаляем предыдущее сообщение
    try:
        bot.delete_message(chat_id, call.message.message_id)
    except:
        pass
    
    # Показываем меню фильтрации
    bot.send_message(
        chat_id,
        "📦 *ПРОСМОТР ЗАКАЗОВ МАГАЗИНА*\n\n"
        "Выберите статус заказов для просмотра:",
        parse_mode='Markdown',
        reply_markup=keyboards.create_orders_filter_keyboard()
    )
    
    bot.answer_callback_query(call.id, "✅ Выберите фильтр заказов")

# ========== ФУНКЦИИ ДЛЯ СТАТИСТИКИ (РАБОЧИЕ) ==========

def handle_admin_stats_daily(bot, message):
    """Отчет за сегодня"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    today = datetime.now().date()
    
    with next(get_db()) as db:
        # Создаем отчет за сегодня
        report_text = generate_daily_report(db, today)
        
        bot.send_message(
            chat_id,
            report_text,
            parse_mode='Markdown',
            reply_markup=keyboards.admin_statistics_menu()
        )
        
        StateManager.set_state(user_id, UserStates.ADMIN_STATISTICS, StateData())

def handle_admin_stats_weekly(bot, message):
    """Отчет за неделю"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    today = datetime.now().date()
    week_ago = today - timedelta(days=7)
    
    with next(get_db()) as db:
        # Генерируем недельный отчет
        report_text = generate_weekly_report(db, week_ago, today)
        
        bot.send_message(
            chat_id,
            report_text,
            parse_mode='Markdown',
            reply_markup=keyboards.admin_statistics_menu()
        )
        
        StateManager.set_state(user_id, UserStates.ADMIN_STATISTICS, StateData())

def handle_admin_stats_monthly(bot, message):
    """Отчет за месяц"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    today = datetime.now().date()
    month_ago = today - timedelta(days=30)
    
    with next(get_db()) as db:
        # Генерируем месячный отчет
        report_text = generate_monthly_report(db, month_ago, today)
        
        bot.send_message(
            chat_id,
            report_text,
            parse_mode='Markdown',
            reply_markup=keyboards.admin_statistics_menu()
        )
        
        StateManager.set_state(user_id, UserStates.ADMIN_STATISTICS, StateData())

def handle_admin_stats_financial(bot, message):
    """Финансовая статистика"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    with next(get_db()) as db:
        # Генерируем финансовую статистику
        report_text = generate_financial_report(db)
        
        bot.send_message(
            chat_id,
            report_text,
            parse_mode='Markdown',
            reply_markup=keyboards.admin_statistics_menu()
        )
        
        StateManager.set_state(user_id, UserStates.ADMIN_STATISTICS, StateData())

# ========== ФУНКЦИИ ДЛЯ РАССЫЛОК (ИСПРАВЛЕННЫЕ) ==========

def handle_admin_create_broadcast(bot, message):
    """Создание рассылки"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    StateManager.set_state(user_id, UserStates.ADMIN_CREATE_BROADCAST_TEXT, StateData())
    
    bot.send_message(
        chat_id,
        "📢 *СОЗДАНИЕ РАССЫЛКИ*\n\n"
        "Введите текст рассылки:\n\n"
        "Для отмены нажмите ❌ Отмена",
        parse_mode='Markdown',
        reply_markup=keyboards.cancel_button()
    )

def handle_admin_create_broadcast_text_input(bot, message):
    """Обработка ввода текста рассылки"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_broadcast_menu(bot, message)
        return
    
    text = message.text.strip()
    if len(text) < 5:
        bot.send_message(
            chat_id,
            "❌ Текст слишком короткий! Введите текст минимум из 5 символов:",
            reply_markup=keyboards.cancel_button()
        )
        return
    
    StateManager.set_state(
        user_id,
        UserStates.ADMIN_CREATE_BROADCAST_CONFIRM,
        StateData(broadcast_text=text)
    )
    
    markup = keyboards.create_broadcast_confirmation_buttons(user_id)
    
    bot.send_message(
        chat_id,
        f"📢 *ПРЕДПРОСМОТР РАССЫЛКИ*\n\n"
        f"{text}\n\n"
        f"*Выберите действие:*",
        parse_mode='Markdown',
        reply_markup=markup
    )

def handle_admin_create_broadcast_confirm_input(bot, message):
    """Обработка подтверждения рассылки"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    bot.send_message(
        chat_id,
        "Для отправки рассылки используйте кнопки под сообщением с предпросмотром.",
        reply_markup=keyboards.admin_broadcast_menu()
    )
    StateManager.set_state(user_id, UserStates.ADMIN_BROADCAST, StateData())

def handle_admin_create_promo(bot, message):
    """Создание промо-предложения"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    StateManager.set_state(user_id, UserStates.ADMIN_CREATE_PROMO_NAME, StateData())
    
    bot.send_message(
        chat_id,
        "🎁 *СОЗДАНИЕ ПРОМО-ПРЕДЛОЖЕНИЯ*\n\n"
        "Введите название предложения:\n\n"
        "Для отмены нажмите ❌ Отмена",
        parse_mode='Markdown',
        reply_markup=keyboards.cancel_button()
    )

def handle_admin_create_promo_name_input(bot, message):
    """Обработка ввода названия промо-предложения"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_broadcast_menu(bot, message)
        return
    
    name = message.text.strip()
    if len(name) < 3:
        bot.send_message(
            chat_id,
            "❌ Название слишком короткое! Введите название минимум из 3 символов:",
            reply_markup=keyboards.cancel_button()
        )
        return
    
    StateManager.set_state(
        user_id,
        UserStates.ADMIN_CREATE_PROMO_DESC,
        StateData(promo_name=name)
    )
    
    bot.send_message(
        chat_id,
        "📝 *ВВЕДИТЕ ОПИСАНИЕ ПРЕДЛОЖЕНИЯ:*\n\n"
        "Опишите предложение, условия, преимущества:\n\n"
        "Для отмены нажмите ❌ Отмена",
        parse_mode='Markdown',
        reply_markup=keyboards.cancel_button()
    )

def handle_admin_create_promo_desc_input(bot, message):
    """Обработка ввода описания промо-предложения"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_broadcast_menu(bot, message)
        return
    
    data = StateManager.get_data(user_id)
    description = message.text.strip()
    
    if len(description) < 10:
        bot.send_message(
            chat_id,
            "❌ Описание слишком короткое! Введите подробное описание:",
            reply_markup=keyboards.cancel_button()
        )
        return
    
    StateManager.set_state(
        user_id,
        UserStates.ADMIN_CREATE_PROMO_PRICE,
        StateData(promo_name=data.promo_name, promo_description=description)
    )
    
    bot.send_message(
        chat_id,
        "💰 *ВВЕДИТЕ ЦЕНУ ПРЕДЛОЖЕНИЯ (в рублях):*\n\n"
        "Пример: 15000\n"
        "Введите 0, если цена обсуждается индивидуально\n\n"
        "Для отмены нажмите ❌ Отмена",
        parse_mode='Markdown',
        reply_markup=keyboards.cancel_button()
    )

def handle_admin_create_promo_price_input(bot, message):
    """Обработка ввода цены промо-предложения"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_broadcast_menu(bot, message)
        return
    
    try:
        price = float(message.text.strip())
        if price < 0:
            raise ValueError
        
        data = StateManager.get_data(user_id)
        StateManager.set_state(
            user_id,
            UserStates.ADMIN_CREATE_PROMO_DATES,
            StateData(
                promo_name=data.promo_name,
                promo_description=data.promo_description,
                promo_price=price
            )
        )
        
        bot.send_message(
            chat_id,
            "📅 *ВВЕДИТЕ СРОКИ ДЕЙСТВИЯ ПРЕДЛОЖЕНИЯ:*\n\n"
            "Формат: ДД.ММ.ГГГГ - ДД.ММ.ГГГГ\n"
            "Пример: 01.12.2025 - 31.12.2025\n\n"
            "Для отмены нажмите ❌ Отмена",
            parse_mode='Markdown',
            reply_markup=keyboards.cancel_button()
        )
        
    except (ValueError, TypeError):
        bot.send_message(
            chat_id,
            "❌ Неверный формат цены! Введите число (0 или больше):",
            reply_markup=keyboards.cancel_button()
        )

def handle_admin_create_promo_dates_input(bot, message):
    """Обработка ввода сроков промо-предложения"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '❌ Отмена':
        handle_admin_broadcast_menu(bot, message)
        return
    
    dates_str = message.text.strip()
    try:
        # Парсим даты
        start_str, end_str = dates_str.split('-')
        start_date = datetime.strptime(start_str.strip(), "%d.%m.%Y")
        end_date = datetime.strptime(end_str.strip(), "%d.%m.%Y")
        
        if end_date <= start_date:
            raise ValueError
        
        data = StateManager.get_data(user_id)
        StateManager.set_state(
            user_id,
            UserStates.ADMIN_CREATE_PROMO_CONFIRM,
            StateData(
                promo_name=data.promo_name,
                promo_description=data.promo_description,
                promo_price=data.promo_price,
                promo_start_date_str=start_date.strftime('%d.%m.%Y'),
                promo_end_date_str=end_date.strftime('%d.%m.%Y')
            )
        )
        
        # Показываем предпросмотр
        price_text = f"{data.promo_price} руб." if data.promo_price > 0 else "Цена обсуждается индивидуально"
        
        preview_text = (
            f"🎁 *ПРЕДПРОСМОТР ПРОМО-ПРЕДЛОЖЕНИЯ*\n\n"
            f"*Название:* {data.promo_name}\n"
            f"*Описание:* {data.promo_description}\n"
            f"*Цена:* {price_text}\n"
            f"*Срок действия:* {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}\n\n"
            f"*Подтвердить создание предложения?*"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton('✅ Создать', callback_data=f'admin_promo_create_{user_id}'),
            types.InlineKeyboardButton('❌ Отменить', callback_data=f'admin_promo_cancel_{user_id}')
        )
        
        bot.send_message(
            chat_id,
            preview_text,
            parse_mode='Markdown',
            reply_markup=markup
        )
        
    except (ValueError, IndexError):
        bot.send_message(
            chat_id,
            "❌ Неверный формат дат! Введите даты в формате ДД.ММ.ГГГГ - ДД.ММ.ГГГГ:",
            reply_markup=keyboards.cancel_button()
        )

def handle_admin_create_promo_confirm_input(bot, message):
    """Обработка подтверждения создания промо-предложения"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    bot.send_message(
        chat_id,
        "Для подтверждения создания предложения используйте кнопки под сообщением с предпросмотром.",
        reply_markup=keyboards.admin_broadcast_menu()
    )
    StateManager.set_state(user_id, UserStates.ADMIN_BROADCAST, StateData())

def handle_admin_promo_create_confirm(bot, call, admin_id):
    """Подтверждение создания промо-предложения"""
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    if user_id != admin_id:
        bot.answer_callback_query(call.id, "❌ Это не ваше предложение!", show_alert=True)
        return
    
    data = StateManager.get_data(user_id)
    
    try:
        with next(get_db()) as db:
            start_date = datetime.strptime(data.promo_start_date_str, "%d.%m.%Y")
            end_date = datetime.strptime(data.promo_end_date_str, "%d.%m.%Y")
            
            # Создаем промо-предложение
            promo = PromoOffer(
                name=data.promo_name,
                description=data.promo_description,
                price=data.promo_price,
                start_date=start_date,
                end_date=end_date,
                is_active=True,
                created_by=user_id,
                created_at=datetime.now()
            )
            db.add(promo)
            db.commit()
            
            # Обновляем сообщение
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=call.message.message_id,
                text=f"✅ *ПРОМО-ПРЕДЛОЖЕНИЕ СОЗДАНО!*\n\n"
                     f"*Название:* {data.promo_name}\n"
                     f"*ID:* {promo.id}\n\n"
                     f"Предложение теперь доступно клиентам.",
                parse_mode='Markdown'
            )
            
            bot.answer_callback_query(call.id, "✅ Предложение создано!")
            
            # Возвращаем в меню
            StateManager.set_state(user_id, UserStates.ADMIN_BROADCAST, StateData())
            
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ Ошибка: {str(e)}", show_alert=True)

def handle_admin_promo_cancel(bot, call, admin_id):
    """Отмена создания промо-предложения"""
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    if user_id != admin_id:
        bot.answer_callback_query(call.id, "❌ Это не ваше предложение!", show_alert=True)
        return
    
    # Обновляем сообщение
    bot.edit_message_text(
        chat_id=chat_id,
        message_id=call.message.message_id,
        text="❌ *СОЗДАНИЕ ПРЕДЛОЖЕНИЯ ОТМЕНЕНО*",
        parse_mode='Markdown'
    )
    
    bot.answer_callback_query(call.id, "❌ Создание отменено")
    
    # Возвращаем в меню
    handle_admin_broadcast_menu_from_callback(bot, call)

def handle_admin_promo_list(bot, message):
    """Список промо-предложений"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    with next(get_db()) as db:
        # Получаем все промо-предложения
        promos = db.query(PromoOffer).order_by(PromoOffer.start_date.desc()).all()
        
        if not promos:
            bot.send_message(
                chat_id,
                "📋 *СПИСОК ПРОМО-ПРЕДЛОЖЕНИЙ*\n\n"
                "Нет активных промо-предложений.",
                parse_mode='Markdown',
                reply_markup=keyboards.admin_broadcast_menu()
            )
            return
        
        # Отправляем по 3 предложения за раз
        for i in range(0, len(promos), 3):
            batch = promos[i:i+3]
            message_text = "📋 *СПИСОК ПРОМО-ПРЕДЛОЖЕНИЙ*\n\n"
            
            for promo in batch:
                status = "✅ Активно" if promo.is_active else "❌ Не активно"
                price_text = f"{promo.price} руб." if promo.price > 0 else "Цена обсуждается"
                
                message_text += f"*ID:* {promo.id}\n"
                message_text += f"*Название:* {promo.name}\n"
                message_text += f"*Описание:* {promo.description[:100]}...\n"
                message_text += f"*Цена:* {price_text}\n"
                message_text += f"*Сроки:* {promo.start_date.strftime('%d.%m.%Y')} - {promo.end_date.strftime('%d.%m.%Y')}\n"
                message_text += f"*Статус:* {status}\n"
                message_text += "─" * 20 + "\n"
            
            if i + 3 < len(promos):
                message_text += f"\nПоказано {i+1}-{i+len(batch)} из {len(promos)}"
            
            bot.send_message(
                chat_id,
                message_text,
                parse_mode='Markdown'
            )
        
        StateManager.set_state(user_id, UserStates.ADMIN_BROADCAST, StateData())

def handle_admin_broadcast_confirm(bot, call, admin_id):
    """Подтверждение и отправка рассылки"""
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    if user_id != admin_id:
        bot.answer_callback_query(call.id, "❌ Это не ваша рассылка!", show_alert=True)
        return
    
    data = StateManager.get_data(user_id)
    if not hasattr(data, 'broadcast_text'):
        bot.answer_callback_query(call.id, "❌ Текст рассылки не найден!", show_alert=True)
        return
    
    # Обновляем сообщение
    bot.edit_message_text(
        chat_id=chat_id,
        message_id=call.message.message_id,
        text="📢 *РАССЫЛКА ОТПРАВЛЯЕТСЯ...*\n\n"
             "Пожалуйста, подождите...",
        parse_mode='Markdown'
    )
    
    # Отправляем рассылку всем пользователям
    sent_count = 0
    failed_count = 0
    
    with next(get_db()) as db:
        # Получаем всех пользователей
        users = db.query(User).all()
        total_users = len(users)
        
        for user in users:
            try:
                bot.send_message(
                    user.user_id,
                    f"📢 *СПЕЦИАЛЬНОЕ ПРЕДЛОЖЕНИЕ!*\n\n"
                    f"{data.broadcast_text}\n\n"
                    f"_Для отключения рассылки используйте команду /unsubscribe_",
                    parse_mode='Markdown'
                )
                sent_count += 1
            except Exception as e:
                print(f"Ошибка отправки пользователю {user.user_id}: {e}")
                failed_count += 1
        
        # Сохраняем статистику рассылки
        broadcast = BroadcastMessage(
            title=f"Рассылка от {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            message=data.broadcast_text,
            message_type='text',
            sent_count=sent_count,
            failed_count=failed_count,
            total_count=total_users,
            status='completed',
            sent_at=datetime.now(),
            created_by=user_id,
            created_at=datetime.now()
        )
        db.add(broadcast)
        db.commit()
        
        # Обновляем сообщение с результатами
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text=f"✅ *РАССЫЛКА ЗАВЕРШЕНА!*\n\n"
                 f"*Статистика:*\n"
                 f"• Всего пользователей: {total_users}\n"
                 f"• Успешно отправлено: {sent_count}\n"
                 f"• Не отправлено: {failed_count}\n"
                 f"• Процент доставки: {sent_count/max(1, total_users)*100:.1f}%\n\n"
                 f"Рассылка сохранена в истории.",
            parse_mode='Markdown'
        )
        
        bot.answer_callback_query(call.id, "✅ Рассылка отправлена!")
        
        # Возвращаем в меню
        StateManager.set_state(user_id, UserStates.ADMIN_BROADCAST, StateData())

def handle_admin_broadcast_cancel(bot, call, admin_id):
    """Отмена рассылки"""
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    if user_id != admin_id:
        bot.answer_callback_query(call.id, "❌ Это не ваша рассылка!", show_alert=True)
        return
    
    # Обновляем сообщение
    bot.edit_message_text(
        chat_id=chat_id,
        message_id=call.message.message_id,
        text="❌ *РАССЫЛКА ОТМЕНЕНА*",
        parse_mode='Markdown'
    )
    
    bot.answer_callback_query(call.id, "❌ Рассылка отменена")
    
    # Возвращаем в меню
    handle_admin_broadcast_menu_from_callback(bot, call)

def handle_admin_broadcast_menu_from_callback(bot, call):
    """Возврат в меню рассылок из callback"""
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    # Удаляем предыдущее сообщение
    try:
        bot.delete_message(chat_id, call.message.message_id)
    except:
        pass
    
    StateManager.set_state(user_id, UserStates.ADMIN_BROADCAST, StateData())
    
    bot.send_message(
        chat_id,
        "📢 *РАССЫЛКИ И ПРЕДЛОЖЕНИЯ*\n\n"
        "Выберите действие:",
        parse_mode='Markdown',
        reply_markup=keyboards.admin_broadcast_menu()
    )

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def generate_daily_report(db, date):
    """Генерация ежедневного отчета"""
    # Начало следующего дня
    next_day = date + timedelta(days=1)
    
    # Статистика отеля
    hotel_bookings = db.query(HotelBooking).filter(
        HotelBooking.created_at >= datetime.combine(date, datetime.min.time()),
        HotelBooking.created_at < datetime.combine(next_day, datetime.min.time())
    ).count()
    
    hotel_revenue = db.query(HotelBooking).filter(
        HotelBooking.created_at >= datetime.combine(date, datetime.min.time()),
        HotelBooking.created_at < datetime.combine(next_day, datetime.min.time()),
        HotelBooking.payment_status == 'paid'
    ).with_entities(func.sum(HotelBooking.total_price)).scalar() or 0
    
    # Статистика инструкторов
    instructor_bookings = db.query(InstructorBooking).filter(
        InstructorBooking.created_at >= datetime.combine(date, datetime.min.time()),
        InstructorBooking.created_at < datetime.combine(next_day, datetime.min.time())
    ).count()
    
    instructor_revenue = db.query(InstructorBooking).filter(
        InstructorBooking.created_at >= datetime.combine(date, datetime.min.time()),
        InstructorBooking.created_at < datetime.combine(next_day, datetime.min.time()),
        InstructorBooking.payment_status == 'paid'
    ).with_entities(func.sum(InstructorBooking.total_price)).scalar() or 0
    
    # Статистика экскурсий
    excursion_bookings = db.query(ExcursionBooking).filter(
        ExcursionBooking.created_at >= datetime.combine(date, datetime.min.time()),
        ExcursionBooking.created_at < datetime.combine(next_day, datetime.min.time())
    ).count()
    
    excursion_revenue = db.query(ExcursionBooking).filter(
        ExcursionBooking.created_at >= datetime.combine(date, datetime.min.time()),
        ExcursionBooking.created_at < datetime.combine(next_day, datetime.min.time()),
        ExcursionBooking.payment_status == 'paid'
    ).with_entities(func.sum(ExcursionBooking.total_price)).scalar() or 0
    
    # Статистика магазина
    shop_orders = db.query(ShopOrder).filter(
        ShopOrder.created_at >= datetime.combine(date, datetime.min.time()),
        ShopOrder.created_at < datetime.combine(next_day, datetime.min.time())
    ).count()
    
    shop_revenue = db.query(ShopOrder).filter(
        ShopOrder.created_at >= datetime.combine(date, datetime.min.time()),
        ShopOrder.created_at < datetime.combine(next_day, datetime.min.time()),
        ShopOrder.payment_status == 'paid'
    ).with_entities(func.sum(ShopOrder.total_price)).scalar() or 0
    
    # Новые пользователи
    new_users = db.query(User).filter(
        User.created_at >= datetime.combine(date, datetime.min.time()),
        User.created_at < datetime.combine(next_day, datetime.min.time())
    ).count()
    
    # Общая статистика
    total_revenue = hotel_revenue + instructor_revenue + excursion_revenue + shop_revenue
    total_bookings = hotel_bookings + instructor_bookings + excursion_bookings + shop_orders
    
    report_text = (
        f"📊 *ОТЧЕТ ЗА {date.strftime('%d.%m.%Y')}*\n\n"
        f"*🏨 ОТЕЛЬ:*\n"
        f"• Новых бронирований: {hotel_bookings}\n"
        f"• Выручка: {hotel_revenue} руб.\n\n"
        f"*🎿 ИНСТРУКТОРЫ:*\n"
        f"• Новых заявок: {instructor_bookings}\n"
        f"• Выручка: {instructor_revenue} руб.\n\n"
        f"*🗺️ ЭКСКУРСИИ:*\n"
        f"• Новых бронирований: {excursion_bookings}\n"
        f"• Выручка: {excursion_revenue} руб.\n\n"
        f"*🛒 МАГАЗИН:*\n"
        f"• Новых заказов: {shop_orders}\n"
        f"• Выручка: {shop_revenue} руб.\n\n"
        f"*👤 ПОЛЬЗОВАТЕЛИ:*\n"
        f"• Новых пользователей: {new_users}\n\n"
        f"*📈 ИТОГО:*\n"
        f"• Всего заказов: {total_bookings}\n"
        f"• Общая выручка: {total_revenue} руб.\n\n"
        f"*⏰ Время генерации:* {datetime.now().strftime('%H:%M')}"
    )
    
    return report_text

def generate_weekly_report(db, start_date, end_date):
    """Генерация недельного отчета"""
    # Начало следующего дня
    next_day = end_date + timedelta(days=1)
    
    # Статистика отеля за неделю
    hotel_bookings = db.query(HotelBooking).filter(
        HotelBooking.created_at >= datetime.combine(start_date, datetime.min.time()),
        HotelBooking.created_at < datetime.combine(next_day, datetime.min.time())
    ).count()
    
    hotel_revenue = db.query(HotelBooking).filter(
        HotelBooking.created_at >= datetime.combine(start_date, datetime.min.time()),
        HotelBooking.created_at < datetime.combine(next_day, datetime.min.time()),
        HotelBooking.payment_status == 'paid'
    ).with_entities(func.sum(HotelBooking.total_price)).scalar() or 0
    
    # Статистика инструкторов за неделю
    instructor_bookings = db.query(InstructorBooking).filter(
        InstructorBooking.created_at >= datetime.combine(start_date, datetime.min.time()),
        InstructorBooking.created_at < datetime.combine(next_day, datetime.min.time())
    ).count()
    
    instructor_revenue = db.query(InstructorBooking).filter(
        InstructorBooking.created_at >= datetime.combine(start_date, datetime.min.time()),
        InstructorBooking.created_at < datetime.combine(next_day, datetime.min.time()),
        InstructorBooking.payment_status == 'paid'
    ).with_entities(func.sum(InstructorBooking.total_price)).scalar() or 0
    
    # Статистика экскурсий за неделю
    excursion_bookings = db.query(ExcursionBooking).filter(
        ExcursionBooking.created_at >= datetime.combine(start_date, datetime.min.time()),
        ExcursionBooking.created_at < datetime.combine(next_day, datetime.min.time())
    ).count()
    
    excursion_revenue = db.query(ExcursionBooking).filter(
        ExcursionBooking.created_at >= datetime.combine(start_date, datetime.min.time()),
        ExcursionBooking.created_at < datetime.combine(next_day, datetime.min.time()),
        ExcursionBooking.payment_status == 'paid'
    ).with_entities(func.sum(ExcursionBooking.total_price)).scalar() or 0
    
    # Статистика магазина за неделю
    shop_orders = db.query(ShopOrder).filter(
        ShopOrder.created_at >= datetime.combine(start_date, datetime.min.time()),
        ShopOrder.created_at < datetime.combine(next_day, datetime.min.time())
    ).count()
    
    shop_revenue = db.query(ShopOrder).filter(
        ShopOrder.created_at >= datetime.combine(start_date, datetime.min.time()),
        ShopOrder.created_at < datetime.combine(next_day, datetime.min.time()),
        ShopOrder.payment_status == 'paid'
    ).with_entities(func.sum(ShopOrder.total_price)).scalar() or 0
    
    # Новые пользователи за неделю
    new_users = db.query(User).filter(
        User.created_at >= datetime.combine(start_date, datetime.min.time()),
        User.created_at < datetime.combine(next_day, datetime.min.time())
    ).count()
    
    # Всего пользователей
    total_users = db.query(User).count()
    
    # Общая статистика
    total_revenue = hotel_revenue + instructor_revenue + excursion_revenue + shop_revenue
    total_bookings = hotel_bookings + instructor_bookings + excursion_bookings + shop_orders
    
    # Средний чек
    avg_check = total_revenue / max(1, total_bookings)
    
    report_text = (
        f"📈 *НЕДЕЛЬНЫЙ ОТЧЕТ ЗА {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}*\n\n"
        f"*🏨 ОТЕЛЬ:*\n"
        f"• Бронирований: {hotel_bookings}\n"
        f"• Выручка: {hotel_revenue:.0f} руб.\n"
        f"• Средний чек: {hotel_revenue/max(1, hotel_bookings):.0f} руб.\n\n"
        f"*🎿 ИНСТРУКТОРЫ:*\n"
        f"• Заявок: {instructor_bookings}\n"
        f"• Выручка: {instructor_revenue:.0f} руб.\n"
        f"• Средний чек: {instructor_revenue/max(1, instructor_bookings):.0f} руб.\n\n"
        f"*🗺️ ЭКСКУРСИИ:*\n"
        f"• Бронирований: {excursion_bookings}\n"
        f"• Выручка: {excursion_revenue:.0f} руб.\n"
        f"• Средний чек: {excursion_revenue/max(1, excursion_bookings):.0f} руб.\n\n"
        f"*🛒 МАГАЗИН:*\n"
        f"• Заказов: {shop_orders}\n"
        f"• Выручка: {shop_revenue:.0f} руб.\n"
        f"• Средний чек: {shop_revenue/max(1, shop_orders):.0f} руб.\n\n"
        f"*👤 ПОЛЬЗОВАТЕЛИ:*\n"
        f"• Новых пользователей: {new_users}\n"
        f"• Всего пользователей: {total_users}\n\n"
        f"*📈 ИТОГО ЗА НЕДЕЛЮ:*\n"
        f"• Всего заказов: {total_bookings}\n"
        f"• Общая выручка: {total_revenue:.0f} руб.\n"
        f"• Средний чек: {avg_check:.0f} руб.\n"
        f"• Средний доход в день: {total_revenue/7:.0f} руб.\n\n"
        f"*⏰ Время генерации:* {datetime.now().strftime('%H:%M')}"
    )
    
    return report_text

def generate_monthly_report(db, start_date, end_date):
    """Генерация месячного отчета"""
    # Начало следующего дня
    next_day = end_date + timedelta(days=1)
    
    # Статистика отеля за месяц
    hotel_bookings = db.query(HotelBooking).filter(
        HotelBooking.created_at >= datetime.combine(start_date, datetime.min.time()),
        HotelBooking.created_at < datetime.combine(next_day, datetime.min.time())
    ).count()
    
    hotel_revenue = db.query(HotelBooking).filter(
        HotelBooking.created_at >= datetime.combine(start_date, datetime.min.time()),
        HotelBooking.created_at < datetime.combine(next_day, datetime.min.time()),
        HotelBooking.payment_status == 'paid'
    ).with_entities(func.sum(HotelBooking.total_price)).scalar() or 0
    
    # Статистика инструкторов за месяц
    instructor_bookings = db.query(InstructorBooking).filter(
        InstructorBooking.created_at >= datetime.combine(start_date, datetime.min.time()),
        InstructorBooking.created_at < datetime.combine(next_day, datetime.min.time())
    ).count()
    
    instructor_revenue = db.query(InstructorBooking).filter(
        InstructorBooking.created_at >= datetime.combine(start_date, datetime.min.time()),
        InstructorBooking.created_at < datetime.combine(next_day, datetime.min.time()),
        InstructorBooking.payment_status == 'paid'
    ).with_entities(func.sum(InstructorBooking.total_price)).scalar() or 0
    
    # Статистика экскурсий за месяц
    excursion_bookings = db.query(ExcursionBooking).filter(
        ExcursionBooking.created_at >= datetime.combine(start_date, datetime.min.time()),
        ExcursionBooking.created_at < datetime.combine(next_day, datetime.min.time())
    ).count()
    
    excursion_revenue = db.query(ExcursionBooking).filter(
        ExcursionBooking.created_at >= datetime.combine(start_date, datetime.min.time()),
        ExcursionBooking.created_at < datetime.combine(next_day, datetime.min.time()),
        ExcursionBooking.payment_status == 'paid'
    ).with_entities(func.sum(ExcursionBooking.total_price)).scalar() or 0
    
    # Статистика магазина за месяц
    shop_orders = db.query(ShopOrder).filter(
        ShopOrder.created_at >= datetime.combine(start_date, datetime.min.time()),
        ShopOrder.created_at < datetime.combine(next_day, datetime.min.time())
    ).count()
    
    shop_revenue = db.query(ShopOrder).filter(
        ShopOrder.created_at >= datetime.combine(start_date, datetime.min.time()),
        ShopOrder.created_at < datetime.combine(next_day, datetime.min.time()),
        ShopOrder.payment_status == 'paid'
    ).with_entities(func.sum(ShopOrder.total_price)).scalar() or 0
    
    # Новые пользователи за месяц
    new_users = db.query(User).filter(
        User.created_at >= datetime.combine(start_date, datetime.min.time()),
        User.created_at < datetime.combine(next_day, datetime.min.time())
    ).count()
    
    # Всего пользователей
    total_users = db.query(User).count()
    
    # Общая статистика
    total_revenue = hotel_revenue + instructor_revenue + excursion_revenue + shop_revenue
    total_bookings = hotel_bookings + instructor_bookings + excursion_bookings + shop_orders
    
    # Средний чек
    avg_check = total_revenue / max(1, total_bookings)
    
    # Количество дней в отчетном периоде
    days_count = (end_date - start_date).days + 1
    
    report_text = (
        f"📉 *МЕСЯЧНЫЙ ОТЧЕТ ЗА {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}*\n\n"
        f"*🏨 ОТЕЛЬ:*\n"
        f"• Бронирований: {hotel_bookings}\n"
        f"• Выручка: {hotel_revenue:.0f} руб.\n"
        f"• Средний чек: {hotel_revenue/max(1, hotel_bookings):.0f} руб.\n\n"
        f"*🎿 ИНСТРУКТОРЫ:*\n"
        f"• Заявок: {instructor_bookings}\n"
        f"• Выручка: {instructor_revenue:.0f} руб.\n"
        f"• Средний чек: {instructor_revenue/max(1, instructor_bookings):.0f} руб.\n\n"
        f"*🗺️ ЭКСКУРСИИ:*\n"
        f"• Бронирований: {excursion_bookings}\n"
        f"• Выручка: {excursion_revenue:.0f} руб.\n"
        f"• Средний чек: {excursion_revenue/max(1, excursion_bookings):.0f} руб.\n\n"
        f"*🛒 МАГАЗИН:*\n"
        f"• Заказов: {shop_orders}\n"
        f"• Выручка: {shop_revenue:.0f} руб.\n"
        f"• Средний чек: {shop_revenue/max(1, shop_orders):.0f} руб.\n\n"
        f"*👤 ПОЛЬЗОВАТЕЛИ:*\n"
        f"• Новых пользователей: {new_users}\n"
        f"• Всего пользователей: {total_users}\n"
        f"• Прирост: {(new_users/total_users*100):.1f}%\n\n"
        f"*📈 ИТОГО ЗА МЕСЯЦ:*\n"
        f"• Всего заказов: {total_bookings}\n"
        f"• Общая выручка: {total_revenue:.0f} руб.\n"
        f"• Средний чек: {avg_check:.0f} руб.\n"
        f"• Средний доход в день: {total_revenue/days_count:.0f} руб.\n"
        f"• Среднее количество заказов в день: {total_bookings/days_count:.1f}\n\n"
        f"*⏰ Время генерации:* {datetime.now().strftime('%H:%M')}"
    )
    
    return report_text

def generate_financial_report(db):
    """Генерация финансового отчета"""
    today = datetime.now().date()
    month_start = today.replace(day=1)
    
    # Текущий месяц
    current_month_revenue = db.query(HotelBooking).filter(
        HotelBooking.created_at >= datetime.combine(month_start, datetime.min.time()),
        HotelBooking.payment_status == 'paid'
    ).with_entities(func.sum(HotelBooking.total_price)).scalar() or 0
    
    current_month_revenue += db.query(InstructorBooking).filter(
        InstructorBooking.created_at >= datetime.combine(month_start, datetime.min.time()),
        InstructorBooking.payment_status == 'paid'
    ).with_entities(func.sum(InstructorBooking.total_price)).scalar() or 0
    
    current_month_revenue += db.query(ExcursionBooking).filter(
        ExcursionBooking.created_at >= datetime.combine(month_start, datetime.min.time()),
        ExcursionBooking.payment_status == 'paid'
    ).with_entities(func.sum(ExcursionBooking.total_price)).scalar() or 0
    
    current_month_revenue += db.query(ShopOrder).filter(
        ShopOrder.created_at >= datetime.combine(month_start, datetime.min.time()),
        ShopOrder.payment_status == 'paid'
    ).with_entities(func.sum(ShopOrder.total_price)).scalar() or 0
    
    # Ожидаемые платежи
    pending_payments = db.query(HotelBooking).filter(
        HotelBooking.payment_status == 'unpaid'
    ).with_entities(func.sum(HotelBooking.total_price)).scalar() or 0
    
    pending_payments += db.query(InstructorBooking).filter(
        InstructorBooking.payment_status == 'unpaid'
    ).with_entities(func.sum(InstructorBooking.total_price)).scalar() or 0
    
    pending_payments += db.query(ExcursionBooking).filter(
        ExcursionBooking.payment_status == 'unpaid'
    ).with_entities(func.sum(ExcursionBooking.total_price)).scalar() or 0
    
    pending_payments += db.query(ShopOrder).filter(
        ShopOrder.payment_status == 'unpaid'
    ).with_entities(func.sum(ShopOrder.total_price)).scalar() or 0
    
    # Ожидаемые комиссии
    pending_commissions = db.query(InstructorBooking).filter(
        InstructorBooking.payment_status == 'paid',
        InstructorBooking.commission_amount > 0
    ).with_entities(func.sum(InstructorBooking.commission_amount)).scalar() or 0
    
    pending_commissions += db.query(ExcursionBooking).filter(
        ExcursionBooking.payment_status == 'paid'
    ).with_entities(func.sum(ExcursionBooking.total_price * 0.1)).scalar() or 0  # 10% комиссия гидам
    
    # Общая выручка за все время
    total_revenue_all_time = db.query(HotelBooking).filter(
        HotelBooking.payment_status == 'paid'
    ).with_entities(func.sum(HotelBooking.total_price)).scalar() or 0
    
    total_revenue_all_time += db.query(InstructorBooking).filter(
        InstructorBooking.payment_status == 'paid'
    ).with_entities(func.sum(InstructorBooking.total_price)).scalar() or 0
    
    total_revenue_all_time += db.query(ExcursionBooking).filter(
        ExcursionBooking.payment_status == 'paid'
    ).with_entities(func.sum(ExcursionBooking.total_price)).scalar() or 0
    
    total_revenue_all_time += db.query(ShopOrder).filter(
        ShopOrder.payment_status == 'paid'
    ).with_entities(func.sum(ShopOrder.total_price)).scalar() or 0
    
    report_text = (
        f"💰 *ФИНАНСОВАЯ СТАТИСТИКА*\n\n"
        f"*📅 ТЕКУЩИЙ МЕСЯЦ ({month_start.strftime('%B %Y')}):*\n"
        f"• Выручка: {current_month_revenue:.0f} руб.\n"
        f"• Дней в месяце: {(today - month_start).days + 1}\n"
        f"• Средний доход в день: {current_month_revenue/max(1, (today - month_start).days + 1):.0f} руб.\n\n"
        f"*⏳ ОЖИДАЕМЫЕ ПЛАТЕЖИ:*\n"
        f"• Сумма ожидаемых платежей: {pending_payments:.0f} руб.\n"
        f"• Ожидаемые комиссии гидам/инструкторам: {pending_commissions:.0f} руб.\n"
        f"• Чистый ожидаемый доход: {pending_payments - pending_commissions:.0f} руб.\n\n"
        f"*📊 ОБЩАЯ СТАТИСТИКА:*\n"
        f"• Общая выручка за все время: {total_revenue_all_time:.0f} руб.\n"
        f"• Среднемесячная выручка: {total_revenue_all_time/max(1, (today.year - 2024)*12 + today.month):.0f} руб.\n\n"
        f"*💡 РЕКОМЕНДАЦИИ:*\n"
        f"• Напоминайте о просроченных платежах\n"
        f"• Анализируйте популярные услуги\n"
        f"• Оптимизируйте ценообразование\n\n"
        f"*⏰ Время генерации:* {datetime.now().strftime('%H:%M')}"
    )
    
    return report_text

# ========== CALLBACK ОБРАБОТЧИКИ ДЛЯ INLINE КНОПОК ==========

def handle_admin_booking_detail(bot, call, booking_id):
    """Показать детали бронирования"""
    with next(get_db()) as db:
        booking = db.query(HotelBooking).filter_by(id=booking_id).first()
        if not booking:
            bot.answer_callback_query(call.id, "❌ Бронирование не найдено", show_alert=True)
            return
        
        user = db.query(User).filter_by(id=booking.user_id).first()
        
        message_text = (
            f"📋 *ДЕТАЛИ БРОНИРОВАНИЯ #{booking_id}*\n\n"
            f"*Клиент:* {user.first_name} {user.last_name if user else ''}\n"
            f"*Телефон:* {booking.phone}\n"
            f"*TG:* @{user.username if user and user.username else 'нет'}\n\n"
            f"*Даты:* {booking.check_in.strftime('%d.%m.%Y')} - {booking.check_out.strftime('%d.%m.%Y')}\n"
            f"*Ночей:* {booking.nights}\n"
            f"*Стоимость:* {booking.total_price} руб.\n\n"
            f"*Статус:* {booking.status}\n"
            f"*Оплата:* {booking.payment_status}\n"
            f"*Создано:* {booking.created_at.strftime('%d.%m.%Y %H:%M')}"
        )
        
        bot.send_message(
            call.from_user.id,
            message_text,
            parse_mode='Markdown'
        )
        
        bot.answer_callback_query(call.id)

def handle_admin_booking_cancel_confirm(bot, call, booking_id):
    """Подтверждение отмены бронирования"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton('✅ Да, отменить', callback_data=f'admin_booking_cancel_confirm_{booking_id}'),
        types.InlineKeyboardButton('❌ Нет', callback_data=f'admin_booking_cancel_no_{booking_id}')
    )
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"❓ *ПОДТВЕРЖДЕНИЕ ОТМЕНЫ*\n\nВы уверены, что хотите отменить бронирование #{booking_id}?",
        parse_mode='Markdown',
        reply_markup=markup
    )

# Экспортируем только основные функции
__all__ = [
    'handle_admin_start',
    'handle_admin_states',
    'handle_admin_callback'
]
