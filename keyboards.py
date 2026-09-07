from telebot import types
from database import get_db, Excursion

# ========== ГЛАВНОЕ МЕНЮ ==========

def main_menu():
    """Главное меню бота"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('🏨 Бабл Отель'),
        types.KeyboardButton('🎿 Инструкторы'),
        types.KeyboardButton('🗺️ Экскурсии'),
        types.KeyboardButton('🧊 Экспедиции'),
        types.KeyboardButton('🛒 Магазин'),
        types.KeyboardButton('📋 Мои заказы'),
        types.KeyboardButton('✉️ Написать менеджеру')
    )
    return markup

# ========== ОБЩИЕ КНОПКИ ==========

def back_button():
    """Кнопка 'Назад'"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton('🔙 Назад'))
    return markup

def cancel_button():
    """Кнопка 'Отмена'"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton('❌ Отмена'))
    return markup

# ========== ПОДТВЕРЖДЕНИЕ БРОНИРОВАНИЯ ==========

def confirmation_buttons():
    """Кнопки для подтверждения бронирования"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('✅ Подтвердить бронирование'),
        types.KeyboardButton('✏️ Изменить данные'),
        types.KeyboardButton('🔙 Назад'),
        types.KeyboardButton('❌ Отмена')
    )
    return markup

# ========== ИНСТРУКТОРЫ ==========

def instructors_sport_keyboard():
    """Клавиатура выбора вида спорта"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('🎿 Горные лыжи'),
        types.KeyboardButton('🏂 Сноуборд'),
        types.KeyboardButton('🤸 Другое'),
        types.KeyboardButton('🔙 Назад'),
        types.KeyboardButton('❌ Отмена')
    )
    return markup

def instructors_program_keyboard():
    """Клавиатура для выбора программы обучения"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('🎿 Новичок'),
        types.KeyboardButton('⛷️ Продолжающий'),
        types.KeyboardButton('🏂 Карвинг'),
        types.KeyboardButton('🏔️ Фрирайд'),
        types.KeyboardButton('🔙 Назад'),
        types.KeyboardButton('❌ Отмена')
    )
    return markup

def instructors_people_keyboard():
    """Две кнопки: Количество человек и Хочу в группу"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(
        types.KeyboardButton('👤 Количество человек'),
        types.KeyboardButton('👥 Хочу в группу'),
        types.KeyboardButton('🔙 Назад'),
        types.KeyboardButton('❌ Отмена')
    )
    return markup

def instructors_children_keyboard():
    """Есть ли дети в компании"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(
        types.KeyboardButton('👨 Только взрослые (18+)'),
        types.KeyboardButton('👶 Есть дети (до 18 лет)'),
        types.KeyboardButton('🔙 Назад'),
        types.KeyboardButton('❌ Отмена')
    )
    return markup

def create_group_slots_keyboard(slots, recommended):
    """INLINE-кнопки для выбора группового слота"""
    markup = types.InlineKeyboardMarkup(row_width=1)
    if recommended:
        for s in recommended:
            markup.add(types.InlineKeyboardButton(
                f"✅ {s['display']} — {s['count']} чел.", 
                callback_data=f"group_slot_{s['date']}"
            ))
    for s in slots:
        markup.add(types.InlineKeyboardButton(
            s['display'], 
            callback_data=f"group_slot_{s['date']}"
        ))
    return markup

def instructors_type_keyboard():
    """Клавиатура для выбора типа занятия (оставлена для совместимости)"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('👤 Индивидуально'),
        types.KeyboardButton('👥 Группа'),
        types.KeyboardButton('🔙 Назад'),
        types.KeyboardButton('❌ Отмена')
    )
    return markup

def instructors_group_size_keyboard():
    """Клавиатура для выбора размера группы (оставлена для совместимости)"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    markup.add(
        types.KeyboardButton('2'),
        types.KeyboardButton('3'),
        types.KeyboardButton('4'),
        types.KeyboardButton('5'),
        types.KeyboardButton('6'),
        types.KeyboardButton('🔙 Назад'),
        types.KeyboardButton('❌ Отмена')
    )
    return markup

def instructors_student_type_keyboard():
    """Клавиатура для выбора типа ученика"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('👨 Взрослый'),
        types.KeyboardButton('👶 Ребенок'),
        types.KeyboardButton('🔙 Назад'),
        types.KeyboardButton('❌ Отмена')
    )
    return markup

def instructors_freeride_level_keyboard():
    """Клавиатура для выбора уровня во фрирайде"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('🏔️ Начинающий (фрирайд возле трасс)'),
        types.KeyboardButton('⛷️ Продолжающий (имеет опыт фрирайда)'),
        types.KeyboardButton('🔙 Назад'),
        types.KeyboardButton('❌ Отмена')
    )
    return markup

def instructors_freeride_duration_keyboard():
    """Клавиатура для выбора формата фрирайда"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('4 часа'),
        types.KeyboardButton('1 день'),
        types.KeyboardButton('Несколько дней'),
        types.KeyboardButton('Хочу в тур!'),
        types.KeyboardButton('🔙 Назад'),
        types.KeyboardButton('❌ Отмена')
    )
    return markup

def instructors_hours_keyboard():
    """Клавиатура для выбора продолжительности"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('1 час'),
        types.KeyboardButton('2 часа'),
        types.KeyboardButton('4 часа'),
        types.KeyboardButton('6 часов'),
        types.KeyboardButton('🔙 Назад'),
        types.KeyboardButton('❌ Отмена')
    )
    return markup

def instructors_note_keyboard():
    """Клавиатура для ввода примечания"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('✉️ Пропустить'),
        types.KeyboardButton('🔙 Назад'),
        types.KeyboardButton('❌ Отмена')
    )
    return markup

def instructors_confirmation_keyboard():
    """Клавиатура для подтверждения заявки инструктора"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('✅ Подтвердить заявку'),
        types.KeyboardButton('✏️ Изменить данные'),
        types.KeyboardButton('🔙 Назад'),
        types.KeyboardButton('❌ Отмена')
    )
    return markup

def instructors_main_menu():
    """Главное меню инструктора"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        '📋 Мои заявки',
        '✅ Завершить занятие',
        '🔙 Назад'
    )
    return markup

# ========== ЭКСКУРСИИ ==========

def excursions_list_keyboard():
    """Клавиатура со списком экскурсий"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('🗺️ Териберка'),
        types.KeyboardButton('🗺️ Кандалакша'),
        types.KeyboardButton('🗺️ Айс-флоатинг'),
        types.KeyboardButton('🌌 Северное сияние'),
        types.KeyboardButton('🏔️ Другие экскурсии'),
        types.KeyboardButton('🧭 Туры')
    )
    markup.row(
        types.KeyboardButton('🔙 Назад'),
        types.KeyboardButton('❌ Отмена')
    )
    return markup

def excursions_other_keyboard():
    """Клавиатура для 'Другие экскурсии'"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('❄️ Зимние'),
        types.KeyboardButton('☀️ Летние'),
        types.KeyboardButton('🔙 Назад'),
        types.KeyboardButton('❌ Отмена')
    )
    return markup

def excursions_children_keyboard():
    """Клавиатура для вопроса о детях"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(
        types.KeyboardButton('👨 Только взрослые'),
        types.KeyboardButton('👶 Есть дети'),
        types.KeyboardButton('🔙 Назад'),
        types.KeyboardButton('❌ Отмена')
    )
    return markup

def join_group_keyboard():
    """Клавиатура для присоединения к группе"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('✅ Забронировать'),
        types.KeyboardButton('🔙 Назад')
    )
    return markup

def existing_groups_keyboard(groups, target_date):
    """Создает инлайн-клавиатуру с существующими группами"""
    markup = types.InlineKeyboardMarkup(row_width=1)
    for group in groups:
        markup.add(types.InlineKeyboardButton(
            f"🗺️ {group['date']} {group['location']} Гид {group['guide_name']} ({group['current_people']} чел.)",
            callback_data=f'join_existing_group_{group["booking_id"]}'
        ))
    markup.add(types.InlineKeyboardButton(
        f"📅 Оставить свою дату {target_date}",
        callback_data=f'keep_my_date_{target_date}'
    ))
    return markup

def excursion_detail_keyboard():
    """Клавиатура для деталей экскурсии"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('✅ Забронировать'),
        types.KeyboardButton('🔙 Назад'),
        types.KeyboardButton('❌ Отмена')
    )
    return markup

def excursion_people_keyboard():
    """Клавиатура для выбора количества человек"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    buttons = []
    for i in range(1, 11):
        buttons.append(types.KeyboardButton(str(i)))
    
    for i in range(0, len(buttons), 3):
        row_buttons = buttons[i:i+3]
        markup.row(*row_buttons)
    
    markup.row(
        types.KeyboardButton('🔙 Назад'),
        types.KeyboardButton('❌ Отмена')
    )
    return markup

def excursion_confirmation_keyboard():
    """Клавиатура для подтверждения брони экскурсии"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('✅ Подтвердить бронирование'),
        types.KeyboardButton('✏️ Изменить данные'),
        types.KeyboardButton('🔙 Назад'),
        types.KeyboardButton('❌ Отмена')
    )
    return markup

# ========== ГИДЫ ==========

def guide_menu_keyboard():
    """Меню для гидов"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('➕ Создать экскурсию'),
        types.KeyboardButton('📋 Мои заявки'),
        types.KeyboardButton('📊 Статистика'),
        types.KeyboardButton('🔙 Назад')
    )
    return markup

def guide_create_cancel_keyboard():
    """Клавиатура для отмены создания экскурсии"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(
        types.KeyboardButton('❌ Отменить создание')
    )
    return markup

# ========== КНОПКИ ДЛЯ ПРЕДЛОЖЕНИЙ ==========

def create_offer_buttons(offer_id):
    """Создает inline-кнопки для предложения гида"""
    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(
        types.InlineKeyboardButton('✅ Принять', callback_data=f'exc_accept_{offer_id}'),
        types.InlineKeyboardButton('❌ Отклонить', callback_data=f'exc_reject_{offer_id}'),
        types.InlineKeyboardButton('⏳ Подождать другие', callback_data=f'exc_wait_{offer_id}')
    )
    return markup

def create_guide_offer_button(booking_id):
    """Создает кнопку 'Предложить' для чата гидов"""
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton('✅ Предложить', callback_data=f'guide_offer_{booking_id}')
    )
    return markup

def guide_confirm_join_keyboard(booking_id):
    """Inline-кнопки для гида при подтверждении нового участника"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton('✅ Подтвердить', callback_data=f'guide_confirm_join_{booking_id}'),
        types.InlineKeyboardButton('❌ Отклонить', callback_data=f'guide_reject_join_{booking_id}')
    )
    return markup

# ========== КНОПКИ ДЛЯ ИЗМЕНЕНИЯ ЭКСКУРСИЙ ГИДОМ ==========

def create_guide_modify_keyboard(excursion_id):
    """Клавиатура для изменения экскурсии гидом"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton('✏️ Изменить описание', callback_data=f'guide_modify_desc_{excursion_id}'),
        types.InlineKeyboardButton('💰 Изменить цену', callback_data=f'guide_modify_price_{excursion_id}'),
        types.InlineKeyboardButton('👥 Изменить места', callback_data=f'guide_modify_seats_{excursion_id}'),
        types.InlineKeyboardButton('📅 Изменить даты', callback_data=f'guide_modify_dates_{excursion_id}'),
        types.InlineKeyboardButton('🕒 Изменить время', callback_data=f'guide_modify_time_{excursion_id}'),
        types.InlineKeyboardButton('✅ Сохранить', callback_data=f'guide_modify_save_{excursion_id}'),
        types.InlineKeyboardButton('❌ Отменить', callback_data=f'guide_modify_cancel_{excursion_id}')
    )
    return markup

# ========== АДМИНКА ==========

def admin_main_menu():
    """Главное меню админки"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('🏨 Управление отелем'),
        types.KeyboardButton('🎿 Управление инструкторами'),
        types.KeyboardButton('🗺️ Управление экскурсиями'),
        types.KeyboardButton('🧊 Управление экспедициями'),
        types.KeyboardButton('🛒 Управление магазином'),
        types.KeyboardButton('📊 Статистика и отчеты'),
        types.KeyboardButton('📢 Рассылки и предложения'),
        types.KeyboardButton('🔙 Выход из админки')
    )
    return markup

def admin_hotel_menu():
    """Меню управления отелем"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('📅 Заблокировать дату'),
        types.KeyboardButton('✅ Разблокировать дату'),
        types.KeyboardButton('📋 Все бронирования'),
        types.KeyboardButton('❌ Отменить бронирование'),
        types.KeyboardButton('🔙 Назад в админку')
    )
    return markup

def admin_instructors_menu():
    """Меню управления инструкторами"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('💰 Настройка цен'),
        types.KeyboardButton('📋 Список инструкторов'),
        types.KeyboardButton('📊 Статистика инструктора'),
        types.KeyboardButton('❌ Отменить заказ'),
        types.KeyboardButton('🔙 Назад в админку')
    )
    return markup

def admin_excursions_menu():
    """Меню управления экскурсиями"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('➕ Добавить экскурсию'),
        types.KeyboardButton('📋 Список экскурсий'),
        types.KeyboardButton('✏️ Редактировать экскурсию'),
        types.KeyboardButton('💰 Настройка цен'),
        types.KeyboardButton('🔙 Назад в админку')
    )
    return markup

def admin_expeditions_menu():
    """Меню управления экспедициями"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('➕ Добавить экспедицию'),
        types.KeyboardButton('📋 Список экспедиций'),
        types.KeyboardButton('✏️ Редактировать экспедицию'),
        types.KeyboardButton('✅ Подтвердить оплату'),
        types.KeyboardButton('🔙 Назад в админку')
    )
    return markup

def admin_shop_menu():
    """Меню управления магазином"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('➕ Добавить товар'),
        types.KeyboardButton('📋 Список товаров'),
        types.KeyboardButton('✏️ Редактировать товар'),
        types.KeyboardButton('📦 Управление заказами'),
        types.KeyboardButton('🔙 Назад в админку')
    )
    return markup

def admin_statistics_menu():
    """Меню статистики и отчетов"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('📊 Отчет за сегодня'),
        types.KeyboardButton('📈 Отчет за неделю'),
        types.KeyboardButton('📉 Отчет за месяц'),
        types.KeyboardButton('💰 Финансовая статистика'),
        types.KeyboardButton('🔙 Назад в админку')
    )
    return markup

def admin_broadcast_menu():
    """Меню рассылок и предложений"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('📢 Создать рассылку'),
        types.KeyboardButton('🎁 Создать промо-предложение'),
        types.KeyboardButton('📋 Список предложений'),
        types.KeyboardButton('🔙 Назад в админку')
    )
    return markup

def admin_price_settings_menu():
    """Меню настройки цен"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('📝 Изменить базовую цену'),
        types.KeyboardButton('📝 Изменить цену для детей'),
        types.KeyboardButton('📝 Изменить цену фрирайда'),
        types.KeyboardButton('📝 Изменить цену карвинга'),
        types.KeyboardButton('📝 Изменить скидку группы'),
        types.KeyboardButton('📝 Изменить комиссию'),
        types.KeyboardButton('🔙 Назад')
    )
    return markup

# ========== INLINE КНОПКИ ДЛЯ АДМИНКИ ==========

def create_booking_management_buttons(booking_id):
    """Создает inline-кнопки для управления бронированием"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton('📝 Подробнее', callback_data=f'admin_booking_detail_{booking_id}'),
        types.InlineKeyboardButton('❌ Отменить', callback_data=f'admin_booking_cancel_{booking_id}'),
        types.InlineKeyboardButton('✅ Подтвердить', callback_data=f'admin_booking_confirm_{booking_id}'),
        types.InlineKeyboardButton('💰 Оплачено', callback_data=f'admin_booking_paid_{booking_id}')
    )
    return markup

def create_excursion_management_buttons(excursion_id):
    """Создает inline-кнопки для управления экскурсией"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton('✏️ Редактировать', callback_data=f'admin_excursion_edit_{excursion_id}'),
        types.InlineKeyboardButton('❌ Удалить', callback_data=f'admin_excursion_delete_{excursion_id}'),
        types.InlineKeyboardButton('✅ Активировать', callback_data=f'admin_excursion_toggle_{excursion_id}'),
        types.InlineKeyboardButton('📊 Статистика', callback_data=f'admin_excursion_stats_{excursion_id}')
    )
    return markup

def create_instructor_management_buttons(instructor_id):
    """Создает inline-кнопки для управления инструктором"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton('📊 Подробная статистика', callback_data=f'admin_instructor_stats_{instructor_id}'),
        types.InlineKeyboardButton('✏️ Редактировать', callback_data=f'admin_instructor_edit_{instructor_id}'),
        types.InlineKeyboardButton('❌ Удалить', callback_data=f'admin_instructor_delete_{instructor_id}'),
        types.InlineKeyboardButton('💰 Выплатить', callback_data=f'admin_instructor_pay_{instructor_id}')
    )
    return markup

def create_product_management_buttons(product_id):
    """Создает inline-кнопки для управления товаром"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton('✏️ Редактировать', callback_data=f'admin_product_edit_{product_id}'),
        types.InlineKeyboardButton('❌ Удалить', callback_data=f'admin_product_delete_{product_id}'),
        types.InlineKeyboardButton('✅ В наличии', callback_data=f'admin_product_toggle_{product_id}'),
        types.InlineKeyboardButton('📊 Статистика', callback_data=f'admin_product_stats_{product_id}')
    )
    return markup

def create_expedition_management_buttons(expedition_id):
    """Создает inline-кнопки для управления экспедицией"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton('✏️ Редактировать', callback_data=f'admin_expedition_edit_{expedition_id}'),
        types.InlineKeyboardButton('❌ Удалить', callback_data=f'admin_expedition_delete_{expedition_id}'),
        types.InlineKeyboardButton('✅ Активировать', callback_data=f'admin_expedition_toggle_{expedition_id}'),
        types.InlineKeyboardButton('📊 Статистика', callback_data=f'admin_expedition_stats_{expedition_id}')
    )
    return markup

def create_order_management_buttons(order_id):
    """Создает inline-кнопки для управления заказом"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton('📝 Подробнее', callback_data=f'admin_order_detail_{order_id}'),
        types.InlineKeyboardButton('✅ Отправлен', callback_data=f'admin_order_shipped_{order_id}'),
        types.InlineKeyboardButton('🏁 Доставлен', callback_data=f'admin_order_delivered_{order_id}'),
        types.InlineKeyboardButton('❌ Отменить', callback_data=f'admin_order_cancel_{order_id}')
    )
    return markup

def create_broadcast_confirmation_buttons(admin_id):
    """Создает кнопки для подтверждения рассылки"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton('✅ Отправить всем', callback_data=f'admin_broadcast_confirm_{admin_id}'),
        types.InlineKeyboardButton('✅ Только активным', callback_data=f'admin_broadcast_active_{admin_id}'),
        types.InlineKeyboardButton('✅ С превью', callback_data=f'admin_broadcast_preview_{admin_id}'),
        types.InlineKeyboardButton('❌ Отмена', callback_data=f'admin_broadcast_cancel_{admin_id}')
    )
    return markup

# ========== ДЛЯ КЛИЕНТСКИХ ЗАКАЗОВ ==========

def create_client_offer_buttons(offer_id):
    """Создает кнопки для клиента при получении предложения"""
    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(
        types.InlineKeyboardButton('✅ Принять', callback_data=f'accept_offer_{offer_id}'),
        types.InlineKeyboardButton('❌ Отклонить', callback_data=f'reject_offer_{offer_id}'),
        types.InlineKeyboardButton('⏳ Подождать другие', callback_data=f'wait_offer_{offer_id}')
    )
    return markup

def create_instructor_actions_buttons(booking_id):
    """Создает кнопки для инструктора в чате"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton('✅ Беру', callback_data=f'instructor_take_{booking_id}'),
        types.InlineKeyboardButton('✏️ Изменить условия', callback_data=f'instructor_modify_{booking_id}')
    )
    return markup

def create_extension_buttons(booking_id):
    """Создает кнопки для продления занятия"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton('➕ +1 час', callback_data=f'extend_1h_{booking_id}'),
        types.InlineKeyboardButton('➕ +2 часа', callback_data=f'extend_2h_{booking_id}'),
        types.InlineKeyboardButton('📅 Другой день', callback_data=f'extend_other_{booking_id}'),
        types.InlineKeyboardButton('✅ Завершить', callback_data=f'extend_finish_{booking_id}')
    )
    return markup

# ========== ДЛЯ УПРАВЛЕНИЯ ЗАКАЗАМИ (ИНСТРУКТОР/ГИД) ==========

def create_instructor_order_actions(booking_id):
    """Inline кнопки для инструктора в разделе 'Мои заявки'"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton('❌ Отменить', callback_data=f'instr_cancel_{booking_id}'),
        types.InlineKeyboardButton('📅 Перенести', callback_data=f'instr_reschedule_{booking_id}')
    )
    return markup

def create_guide_order_actions(booking_id):
    """Inline кнопки для гида в разделе 'Мои заявки'"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton('❌ Отменить', callback_data=f'guide_cancel_{booking_id}'),
        types.InlineKeyboardButton('📅 Перенести', callback_data=f'guide_reschedule_{booking_id}')
    )
    return markup

def create_reschedule_response_buttons(booking_id, new_date, new_time, role='instructor'):
    """Кнопки для подтверждения/отклонения переноса"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    prefix = 'instr' if role == 'instructor' else 'guide'
    markup.add(
        types.InlineKeyboardButton('✅ Согласен', callback_data=f'{prefix}_reschedule_accept_{booking_id}_{new_date}_{new_time}'),
        types.InlineKeyboardButton('❌ Отклонить', callback_data=f'{prefix}_reschedule_reject_{booking_id}')
    )
    return markup

# ========== ДЛЯ ФОРМАТИРОВАНИЯ ==========

def create_month_navigation(year, month):
    """Создает кнопки для навигации по месяцам"""
    markup = types.InlineKeyboardMarkup(row_width=3)
    
    if month == 1:
        prev_year = year - 1
        prev_month = 12
    else:
        prev_year = year
        prev_month = month - 1
    
    if month == 12:
        next_year = year + 1
        next_month = 1
    else:
        next_year = year
        next_month = month + 1
    
    markup.add(
        types.InlineKeyboardButton('◀️', callback_data=f'prev_{prev_year}_{prev_month}'),
        types.InlineKeyboardButton(f'{month:02d}.{year}', callback_data='ignore'),
        types.InlineKeyboardButton('▶️', callback_data=f'next_{next_year}_{next_month}')
    )
    
    return markup

def create_date_selection_buttons(dates, action_prefix):
    """Создает кнопки для выбора дат"""
    markup = types.InlineKeyboardMarkup(row_width=7)
    
    weekdays = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
    markup.row(*[types.InlineKeyboardButton(day, callback_data='ignore') for day in weekdays])
    
    rows = []
    current_row = []
    
    for date_info in dates:
        date_str = date_info['date'].strftime('%Y-%m-%d')
        day = date_info['day']
        is_blocked = date_info.get('blocked', False)
        is_today = date_info.get('today', False)
        
        if is_blocked:
            btn = types.InlineKeyboardButton('❌', callback_data=f'blocked_{date_str}')
        elif is_today:
            btn = types.InlineKeyboardButton(f'[{day}]', callback_data=f'{action_prefix}_{date_str}')
        else:
            btn = types.InlineKeyboardButton(str(day), callback_data=f'{action_prefix}_{date_str}')
        
        current_row.append(btn)
        
        if len(current_row) == 7:
            rows.append(current_row)
            current_row = []
    
    if current_row:
        rows.append(current_row)
    
    for row in rows:
        markup.row(*row)
    
    markup.row(
        types.InlineKeyboardButton('❌ Отмена', callback_data='cancel_calendar'),
        types.InlineKeyboardButton('✅ Выбрать', callback_data='confirm_selection')
    )
    
    return markup

# ========== ДЛЯ КАТЕГОРИЙ ==========

def create_category_keyboard(categories):
    """Создает клавиатуру с категориями"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    buttons = []
    for category in categories:
        buttons.append(types.KeyboardButton(category['name']))
    
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            markup.row(buttons[i], buttons[i + 1])
        else:
            markup.row(buttons[i])
    
    markup.row(types.KeyboardButton('🔙 Назад'), types.KeyboardButton('❌ Отмена'))
    return markup

def create_quantity_keyboard(max_quantity=10):
    """Создает клавиатуру для выбора количества"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=5)
    
    buttons = []
    for i in range(1, min(max_quantity, 10) + 1):
        buttons.append(types.KeyboardButton(str(i)))
    
    for i in range(0, len(buttons), 5):
        row_buttons = buttons[i:i+5]
        markup.row(*row_buttons)
    
    markup.row(
        types.KeyboardButton('🔙 Назад'),
        types.KeyboardButton('❌ Отмена')
    )
    return markup

# ========== ДЛЯ РЕДАКТИРОВАНИЯ ==========

def create_edit_options_keyboard():
    """Создает клавиатуру с опциями редактирования"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('✏️ Изменить название'),
        types.KeyboardButton('📝 Изменить описание'),
        types.KeyboardButton('💰 Изменить цену'),
        types.KeyboardButton('📸 Изменить фото'),
        types.KeyboardButton('📊 Изменить количество'),
        types.KeyboardButton('🔙 Назад'),
        types.KeyboardButton('❌ Отмена')
    )
    return markup

def create_yes_no_keyboard():
    """Создает клавиатуру с кнопками Да/Нет"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('✅ Да'),
        types.KeyboardButton('❌ Нет'),
        types.KeyboardButton('🔙 Назад')
    )
    return markup

# ========== ДЛЯ ОТЗЫВОВ ==========

def create_rating_keyboard():
    """Создает клавиатуру для оценки"""
    markup = types.InlineKeyboardMarkup(row_width=5)
    markup.add(
        types.InlineKeyboardButton('1 ⭐', callback_data='rating_1'),
        types.InlineKeyboardButton('2 ⭐', callback_data='rating_2'),
        types.InlineKeyboardButton('3 ⭐', callback_data='rating_3'),
        types.InlineKeyboardButton('4 ⭐', callback_data='rating_4'),
        types.InlineKeyboardButton('5 ⭐', callback_data='rating_5')
    )
    return markup

def create_feedback_keyboard():
    """Создает клавиатуру для обратной связи"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('👍 Отлично'),
        types.KeyboardButton('👎 Плохо'),
        types.KeyboardButton('📝 Написать отзыв'),
        types.KeyboardButton('🔙 Пропустить')
    )
    return markup

# ========== ДЛЯ ОПЛАТЫ ==========

def create_payment_keyboard(payment_url, amount, booking_id):
    """Создает клавиатуру для оплаты"""
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(f'💳 Оплатить {amount} руб.', url=payment_url),
        types.InlineKeyboardButton('✅ Я оплатил', callback_data=f'payment_confirmed_{booking_id}'),
        types.InlineKeyboardButton('❌ Отменить оплату', callback_data=f'payment_canceled_{booking_id}')
    )
    return markup

def create_payment_method_keyboard():
    """Создает клавиатуру для выбора способа оплаты"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('💳 СБП'),
        types.KeyboardButton('💳 Карта'),
        types.KeyboardButton('💵 Наличные'),
        types.KeyboardButton('🔙 Назад')
    )
    return markup

# ========== ДЛЯ МОИХ ЗАКАЗОВ ==========

def create_orders_filter_keyboard():
    """Создает клавиатуру для фильтрации заказов"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('📋 Все заказы'),
        types.KeyboardButton('⏳ Ожидают оплаты'),
        types.KeyboardButton('✅ Активные'),
        types.KeyboardButton('🏁 Завершенные'),
        types.KeyboardButton('❌ Отмененные'),
        types.KeyboardButton('🔙 Назад в меню')
    )
    return markup

def create_order_actions_keyboard(order_id):
    """Создает inline-кнопки для действий с заказом"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton('📝 Подробнее', callback_data=f'order_detail_{order_id}'),
        types.InlineKeyboardButton('❌ Отменить', callback_data=f'order_cancel_{order_id}'),
        types.InlineKeyboardButton('🔄 Повторить', callback_data=f'order_repeat_{order_id}'),
        types.InlineKeyboardButton('📞 Связаться', callback_data=f'order_contact_{order_id}')
    )
    return markup

# ========== УТИЛИТЫ ==========

def create_pagination_keyboard(current_page, total_pages, prefix):
    """Создает кнопки для пагинации"""
    markup = types.InlineKeyboardMarkup(row_width=5)
    
    buttons = []
    
    if current_page > 1:
        buttons.append(types.InlineKeyboardButton('⏮️', callback_data=f'{prefix}_page_1'))
    
    if current_page > 1:
        buttons.append(types.InlineKeyboardButton('◀️', callback_data=f'{prefix}_page_{current_page-1}'))
    
    buttons.append(types.InlineKeyboardButton(f'{current_page}/{total_pages}', callback_data='ignore'))
    
    if current_page < total_pages:
        buttons.append(types.InlineKeyboardButton('▶️', callback_data=f'{prefix}_page_{current_page+1}'))
    
    if current_page < total_pages:
        buttons.append(types.InlineKeyboardButton('⏭️', callback_data=f'{prefix}_page_{total_pages}'))
    
    markup.row(*buttons)
    return markup

def create_action_confirmation_buttons(action, item_id):
    """Создает кнопки для подтверждения действия"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton('✅ Подтвердить', callback_data=f'confirm_{action}_{item_id}'),
        types.InlineKeyboardButton('❌ Отмена', callback_data=f'cancel_{action}_{item_id}')
    )
    return markup

# ========== ДЛЯ ПОИСКА ==========

def create_search_filters_keyboard():
    """Создает клавиатуру для фильтров поиска"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('📅 По дате'),
        types.KeyboardButton('💰 По цене'),
        types.KeyboardButton('⭐ По рейтингу'),
        types.KeyboardButton('📍 По местоположению'),
        types.KeyboardButton('🔙 Назад'),
        types.KeyboardButton('❌ Отмена')
    )
    return markup

def create_sort_options_keyboard():
    """Создает клавиатуру для сортировки"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('⬆️ По возрастанию цены'),
        types.KeyboardButton('⬇️ По убыванию цены'),
        types.KeyboardButton('🆕 Сначала новые'),
        types.KeyboardButton('⭐ По рейтингу'),
        types.KeyboardButton('🔙 Назад')
    )
    return markup

# ========== МАГАЗИН ==========

def shop_categories_keyboard():
    """Клавиатура для выбора категорий магазина"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('📱 Цифровые товары'),
        types.KeyboardButton('📦 Физические товары'),
        types.KeyboardButton('🔙 Назад'),
        types.KeyboardButton('❌ Отмена')
    )
    return markup

def shop_products_keyboard(products, page=0):
    """Клавиатура для отображения товаров с пагинацией"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    
    per_page = 5
    start = page * per_page
    end = start + per_page
    
    for product in products[start:end]:
        markup.add(types.KeyboardButton(f"🛒 {product.name} - {int(product.price)} руб."))
    
    buttons = []
    if page > 0:
        buttons.append(types.KeyboardButton('◀️ Предыдущие'))
    if end < len(products):
        buttons.append(types.KeyboardButton('▶️ Следующие'))
    
    if buttons:
        markup.row(*buttons)
    
    markup.row(
        types.KeyboardButton('🔙 Назад в категории'),
        types.KeyboardButton('❌ Отмена')
    )
    
    return markup

def shop_product_details_keyboard(product, max_quantity=10):
    """Клавиатура для выбора количества товара"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    
    buttons = []
    for i in range(1, min(max_quantity, 5) + 1):
        buttons.append(types.KeyboardButton(f"{i} шт"))
    
    for i in range(0, len(buttons), 3):
        row_buttons = buttons[i:i+3]
        markup.row(*row_buttons)
    
    markup.row(types.KeyboardButton('✏️ Ввести количество'))
    markup.row(
        types.KeyboardButton('🔙 Назад к товарам'),
        types.KeyboardButton('❌ Отмена')
    )
    
    return markup

def shop_confirmation_keyboard():
    """Клавиатура для подтверждения заказа в магазине"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('✅ Подтвердить заказ'),
        types.KeyboardButton('✏️ Изменить данные'),
        types.KeyboardButton('🔙 Назад'),
        types.KeyboardButton('❌ Отмена')
    )
    return markup