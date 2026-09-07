import telebot
from telebot import types
import json
from datetime import datetime
import random
import string
import re
from database import get_db, User, ShopProduct, ShopOrder, Setting
from state_manager import StateManager
from states import UserStates, StateData
import keyboards
from config import MANAGER_CHAT_ID

def handle_shop_start(bot, message):
    """Начало работы с магазином"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Устанавливаем состояние
    StateManager.set_state(user_id, UserStates.SHOP_START, StateData(step=1))
    
    shop_text = """
🛒 *МАГАЗИН "ХИБИНЫ"*

Здесь вы можете приобрести:
• Цифровые товары (гиды, карты, инструкции)
• Физические товары (сувениры, одежда, оборудование)

*Выберите категорию:*
"""
    
    bot.send_message(
        chat_id,
        shop_text,
        parse_mode='Markdown',
        reply_markup=keyboards.shop_categories_keyboard()
    )

def handle_shop_categories(bot, message):
    """Обработка выбора категории магазина"""
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
    
    # Определяем выбранную категорию
    category_mapping = {
        '📱 Цифровые товары': 'digital',
        '📦 Физические товары': 'physical'
    }
    
    if message.text not in category_mapping:
        bot.send_message(
            chat_id,
            "❌ Пожалуйста, выберите категорию из предложенных вариантов:",
            reply_markup=keyboards.shop_categories_keyboard()
        )
        return
    
    category = category_mapping[message.text]
    
    # Получаем товары выбранной категории
    with next(get_db()) as db:
        products = db.query(ShopProduct).filter_by(
            category=category,
            is_active=True
        ).all()
        
        if not products:
            bot.send_message(
                chat_id,
                f"😔 *В категории пока нет товаров*\n\n"
                f"Скоро здесь появятся новые товары!",
                parse_mode='Markdown',
                reply_markup=keyboards.shop_categories_keyboard()
            )
            return
        
        # Сохраняем данные и переходим к выбору товара
        StateManager.set_state(
            user_id,
            UserStates.SHOP_PRODUCTS,
            StateData(
                category=category,
                product_ids=[p.id for p in products],
                current_page=0,
                step=2
            )
        )
        
        # Отображаем товары первой страницы
        show_shop_products(bot, chat_id, products, page=0)

def show_shop_products(bot, chat_id, products, page=0):
    """Отображает список товаров с пагинацией"""
    per_page = 5
    start = page * per_page
    end = start + per_page
    
    products_text = f"""
📋 *Товары (страница {page + 1}):*
"""
    
    for i, product in enumerate(products[start:end], start=1):
        stock_info = ""
        if product.category == 'physical' and product.stock > 0:
            stock_info = f" | 📦 В наличии: {product.stock} шт."
        elif product.category == 'physical' and product.stock <= 0:
            stock_info = " | ❌ Нет в наличии"
        
        products_text += f"\n{i}. *{product.name}*\n"
        products_text += f"   💰 {int(product.price)} руб.{stock_info}\n"
    
    products_text += f"\nВсего товаров: {len(products)}"
    
    # Создаем клавиатуру с товарами
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    
    # Добавляем кнопки товаров
    for product in products[start:end]:
        markup.add(types.KeyboardButton(f"🛒 {product.name} - {int(product.price)} руб."))
    
    # Навигация
    buttons = []
    if page > 0:
        buttons.append(types.KeyboardButton('◀️ Предыдущие'))
    if end < len(products):
        buttons.append(types.KeyboardButton('▶️ Следующие'))
    
    if buttons:
        if len(buttons) == 2:
            markup.row(buttons[0], buttons[1])
        else:
            markup.row(buttons[0])
    
    markup.row(
        types.KeyboardButton('🔙 Назад в категории'),
        types.KeyboardButton('❌ Отмена')
    )
    
    bot.send_message(
        chat_id,
        products_text,
        parse_mode='Markdown',
        reply_markup=markup
    )

def handle_shop_products(bot, message):
    """Обработка выбора товара или навигации"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверка на кнопку "Назад"
    if message.text == '🔙 Назад в категории':
        handle_shop_start(bot, message)
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
                product_ids = data.product_ids
                products = db.query(ShopProduct).filter(
                    ShopProduct.id.in_(product_ids),
                    ShopProduct.is_active == True
                ).all()
                
                show_shop_products(bot, chat_id, products, data.current_page)
        return
    
    elif message.text == '▶️ Следующие':
        data = StateManager.get_data(user_id)
        per_page = 5
        total_pages = (len(data.product_ids) + per_page - 1) // per_page
        
        if data.current_page < total_pages - 1:
            data.current_page += 1
            StateManager.update_data(user_id, current_page=data.current_page)
            
            with next(get_db()) as db:
                product_ids = data.product_ids
                products = db.query(ShopProduct).filter(
                    ShopProduct.id.in_(product_ids),
                    ShopProduct.is_active == True
                ).all()
                
                show_shop_products(bot, chat_id, products, data.current_page)
        return
    
    # Проверяем, выбрал ли пользователь товар
    # Формат: "🛒 Название товара - 500 руб."
    if message.text.startswith('🛒 '):
        # Извлекаем название товара
        import re
        match = re.search(r'🛒 (.+?) - \d+ руб\.', message.text)
        if match:
            product_name = match.group(1).strip()
        else:
            # Альтернативный способ извлечения
            product_name = message.text[3:].split(' - ')[0].strip()
        
        with next(get_db()) as db:
            product = db.query(ShopProduct).filter_by(
                name=product_name,
                is_active=True
            ).first()
            
            if not product:
                bot.send_message(
                    chat_id,
                    "❌ Товар не найден. Пожалуйста, выберите товар из списка:",
                    reply_markup=keyboards.back_button()
                )
                return
            
            # Проверяем наличие для физических товаров
            if product.category == 'physical' and product.stock <= 0:
                bot.send_message(
                    chat_id,
                    f"❌ *Товар временно отсутствует*\n\n"
                    f"Товар '{product.name}' закончился на складе.\n"
                    f"Пожалуйста, выберите другой товар.",
                    parse_mode='Markdown',
                    reply_markup=keyboards.back_button()
                )
                return
            
            # Сохраняем данные о выбранном товаре
            StateManager.set_state(
                user_id,
                UserStates.SHOP_PRODUCT_DETAILS,
                StateData(
                    product_id=product.id,
                    product_name=product.name,
                    product_price=product.price,
                    product_category=product.category,
                    product_stock=product.stock,
                    product_description=product.description,
                    step=3
                )
            )
            
            # Формируем описание товара
            stock_info = ""
            max_quantity = 10  # По умолчанию
            
            if product.category == 'physical':
                if product.stock > 0:
                    stock_info = f"📦 *В наличии:* {product.stock} шт.\n"
                    max_quantity = min(product.stock, 10)
                else:
                    stock_info = "❌ *Нет в наличии*\n"
            else:
                stock_info = "📱 *Цифровой товар* - доставка мгновенно после оплаты\n"
                max_quantity = 1  # Для цифровых обычно 1
            
            product_text = f"""
🛒 *{product.name}*

{product.description}

{stock_info}
💰 *Цена:* {int(product.price)} руб.

*Выберите количество:*
"""
            
            bot.send_message(
                chat_id,
                product_text,
                parse_mode='Markdown',
                reply_markup=keyboards.shop_product_details_keyboard(product, max_quantity)
            )
    else:
        bot.send_message(
            chat_id,
            "❌ Пожалуйста, выберите товар из списка:",
            reply_markup=keyboards.back_button()
        )

def handle_shop_product_details(bot, message):
    """Обработка выбора количества товара"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверка на кнопку "Назад"
    if message.text == '🔙 Назад к товарам':
        data = StateManager.get_data(user_id)
        
        with next(get_db()) as db:
            products = db.query(ShopProduct).filter_by(
                category=data.product_category,
                is_active=True
            ).all()
            
            if products:
                StateManager.set_state(
                    user_id,
                    UserStates.SHOP_PRODUCTS,
                    StateData(
                        category=data.product_category,
                        product_ids=[p.id for p in products],
                        current_page=0,
                        step=2
                    )
                )
                show_shop_products(bot, chat_id, products, page=0)
            else:
                bot.send_message(
                    chat_id,
                    "🛒 *Выберите категорию:*",
                    parse_mode='Markdown',
                    reply_markup=keyboards.shop_categories_keyboard()
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
    
    # Проверка на ввод количества вручную
    if message.text == '✏️ Ввести количество':
        bot.send_message(
            chat_id,
            "✏️ *Введите количество товара:*\n\n"
            "Введите число от 1 до 10:",
            parse_mode='Markdown',
            reply_markup=keyboards.back_button()
        )
        return
    
    # Проверяем, выбрано ли количество через кнопку
    quantity = None
    if message.text.endswith(' шт'):
        try:
            quantity = int(message.text.replace(' шт', ''))
        except:
            quantity = None
    
    # Если не через кнопку, проверяем ввод вручную
    if not quantity:
        try:
            quantity = int(message.text)
        except:
            bot.send_message(
                chat_id,
                "❌ Неверный формат количества. Введите число от 1 до 10:",
                reply_markup=keyboards.back_button()
            )
            return
    
    # Проверяем допустимый диапазон
    data = StateManager.get_data(user_id)
    max_quantity = 10
    
    if data.product_category == 'physical':
        max_quantity = min(data.product_stock, 10)
    elif data.product_category == 'digital':
        max_quantity = 1
    
    if quantity < 1 or quantity > max_quantity:
        bot.send_message(
            chat_id,
            f"❌ Количество должно быть от 1 до {max_quantity}. Введите снова:",
            reply_markup=keyboards.back_button()
        )
        return
    
    # Сохраняем количество и переходим к следующему шагу
    StateManager.update_data(user_id, quantity=quantity)
    
    # Рассчитываем общую стоимость
    total_price = data.product_price * quantity
    
    # Для физических товаров запрашиваем адрес доставки
    if data.product_category == 'physical':
        StateManager.set_state(user_id, UserStates.SHOP_ENTER_ADDRESS, StateData(
            product_id=data.product_id,
            product_name=data.product_name,
            product_price=data.product_price,
            product_category=data.product_category,
            product_stock=data.product_stock,
            quantity=quantity,
            total_price=total_price,
            step=4
        ))
        
        bot.send_message(
            chat_id,
            f"📦 *Введите адрес доставки:*\n\n"
            f"Товар: {data.product_name}\n"
            f"Количество: {quantity} шт.\n"
            f"Стоимость: {int(total_price)} руб.\n\n"
            f"Пожалуйста, укажите полный адрес (город, улица, дом, квартира, индекс):",
            parse_mode='Markdown',
            reply_markup=keyboards.back_button()
        )
    else:
        # Для цифровых товаров сразу переходим к подтверждению
        StateManager.set_state(user_id, UserStates.SHOP_CONFIRMATION, StateData(
            product_id=data.product_id,
            product_name=data.product_name,
            product_price=data.product_price,
            product_category=data.product_category,
            quantity=quantity,
            total_price=total_price,
            delivery_address=None,
            step=5
        ))
        
        show_shop_confirmation(bot, chat_id, data, quantity, total_price)

def handle_shop_address(bot, message):
    """Обработка ввода адреса доставки"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверка на кнопку "Назад"
    if message.text == '🔙 Назад':
        data = StateManager.get_data(user_id)
        StateManager.set_state(user_id, UserStates.SHOP_PRODUCT_DETAILS, data)
        
        # Показываем снова выбор количества
        bot.send_message(
            chat_id,
            f"🛒 *{data.product_name}*\n\n"
            f"Цена: {int(data.product_price)} руб.\n"
            f"Выберите количество:",
            parse_mode='Markdown',
            reply_markup=keyboards.shop_product_details_keyboard(None, min(data.product_stock, 10))
        )
        return
    
    address = message.text.strip()
    if len(address) < 10:
        bot.send_message(
            chat_id,
            "❌ Адрес слишком короткий. Пожалуйста, укажите полный адрес доставки:",
            reply_markup=keyboards.back_button()
        )
        return
    
    # Сохраняем адрес и переходим к подтверждению
    data = StateManager.get_data(user_id)
    data.delivery_address = address
    StateManager.set_state(user_id, UserStates.SHOP_CONFIRMATION, data)
    
    show_shop_confirmation(bot, chat_id, data, data.quantity, data.total_price)

def show_shop_confirmation(bot, chat_id, data, quantity, total_price):
    """Показывает подтверждение заказа"""
    confirmation_text = f"""
✅ *ПРОВЕРЬТЕ ДАННЫЕ ЗАКАЗА:*

*Товар:* {data.product_name}
*Категория:* {'📱 Цифровой товар' if data.product_category == 'digital' else '📦 Физический товар'}
*Количество:* {quantity} шт.
*Цена за шт.:* {int(data.product_price)} руб.
*Общая стоимость:* {int(total_price)} руб.
"""
    
    if data.product_category == 'physical' and hasattr(data, 'delivery_address'):
        confirmation_text += f"\n*Адрес доставки:*\n{data.delivery_address}"
    
    confirmation_text += "\n\nВсё верно?"
    
    bot.send_message(
        chat_id,
        confirmation_text,
        parse_mode='Markdown',
        reply_markup=keyboards.shop_confirmation_keyboard()
    )

def handle_shop_confirmation(bot, message):
    """Обработка подтверждения заказа"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text == '✅ Подтвердить заказ':
        # Получаем данные
        data = StateManager.get_data(user_id)
        
        # Проверяем наличие обязательных полей
        required_fields = ['product_id', 'product_name', 'product_price',
                          'product_category', 'quantity', 'total_price']
        missing_fields = []
        
        for field in required_fields:
            if not hasattr(data, field):
                missing_fields.append(field)
        
        if missing_fields:
            bot.send_message(
                chat_id,
                f"❌ Не хватает данных: {', '.join(missing_fields)}. Начните заказ заново.",
                reply_markup=keyboards.main_menu()
            )
            StateManager.clear_state(user_id)
            return
        
        # Проверяем наличие товара (особенно для физических)
        with next(get_db()) as db:
            product = db.query(ShopProduct).filter_by(id=data.product_id).first()
            
            if not product or not product.is_active:
                bot.send_message(
                    chat_id,
                    "❌ Товар больше не доступен. Пожалуйста, выберите другой товар.",
                    reply_markup=keyboards.main_menu()
                )
                StateManager.clear_state(user_id)
                return
            
            # Для физических товаров проверяем наличие
            if product.category == 'physical' and product.stock < data.quantity:
                bot.send_message(
                    chat_id,
                    f"❌ К сожалению, осталось только {product.stock} шт. этого товара.\n"
                    f"Пожалуйста, выберите другое количество.",
                    reply_markup=keyboards.main_menu()
                )
                StateManager.clear_state(user_id)
                return
            
            # Создаем заказ в базе данных
            try:
                # Получаем или создаем пользователя
                user = db.query(User).filter_by(user_id=user_id).first()
                if not user:
                    user = User(
                        user_id=user_id,
                        username=message.from_user.username,
                        first_name=message.from_user.first_name,
                        last_name=message.from_user.last_name
                    )
                    db.add(user)
                    db.commit()
                    db.refresh(user)
                
                # Генерируем ID заказа
                order_id = 'SHOP' + ''.join(random.choices(string.digits, k=8))
                
                # Создаем заказ
                order = ShopOrder(
                    user_id=user.id,
                    order_id=order_id,
                    product_id=data.product_id,
                    quantity=data.quantity,
                    total_price=data.total_price,
                    delivery_address=getattr(data, 'delivery_address', None),
                    status='pending',
                    payment_status='unpaid'
                )
                db.add(order)
                
                # Уменьшаем остаток для физических товаров
                if product.category == 'physical':
                    product.stock -= data.quantity
                
                db.commit()
                
                # Отправляем подтверждение клиенту
                if product.category == 'digital':
                    # Для цифровых товаров сразу отправляем файл
                    bot.send_message(
                        chat_id,
                        f"🎉 *ЗАКАЗ ПОДТВЕРЖДЕН!*\n\n"
                        f"📋 Номер заказа: {order_id}\n"
                        f"🛒 Товар: {data.product_name}\n"
                        f"📦 Количество: {data.quantity} шт.\n"
                        f"💰 Сумма: {int(data.total_price)} руб.\n\n"
                        f"*Цифровой товар отправлен!*\n"
                        f"Если файл не пришел, свяжитесь с менеджером.",
                        parse_mode='Markdown',
                        reply_markup=keyboards.main_menu()
                    )
                    
                    # Отправляем файл, если есть
                    if product.file_url:
                        try:
                            bot.send_document(chat_id, product.file_url)
                        except:
                            bot.send_message(
                                chat_id,
                                "❌ Файл временно недоступен. Менеджер свяжется с вами для отправки.",
                                reply_markup=keyboards.main_menu()
                            )
                else:
                    # Для физических товаров
                    bot.send_message(
                        chat_id,
                        f"🎉 *ЗАКАЗ ПОДТВЕРЖДЕН!*\n\n"
                        f"📋 Номер заказа: {order_id}\n"
                        f"🛒 Товар: {data.product_name}\n"
                        f"📦 Количество: {data.quantity} шт.\n"
                        f"💰 Сумма: {int(data.total_price)} руб.\n\n"
                        f"*Следующие шаги:*\n"
                        f"1. Оплатите заказ по реквизитам ниже\n"
                        f"2. После оплаты менеджер свяжется с вами\n"
                        f"3. Товар будет отправлен на указанный адрес\n\n"
                        f"*Реквизиты для оплаты:*\n"
                        f"Сбербанк: 40817810099910004312\n"
                        f"БИК: 044525225\n"
                        f"Назначение: Заказ {order_id}",
                        parse_mode='Markdown',
                        reply_markup=keyboards.main_menu()
                    )
                
                # Отправляем уведомление менеджеру
                if MANAGER_CHAT_ID:
                    try:
                        category_display = '📱 Цифровой товар' if product.category == 'digital' else '📦 Физический товар'
                        address_info = f"\n*Адрес доставки:* {data.delivery_address}" if hasattr(data, 'delivery_address') and data.delivery_address else ""
                        
                        manager_text = f"""
🛒 *НОВЫЙ ЗАКАЗ В МАГАЗИНЕ*

*Номер заказа:* {order_id}
*Клиент:* {user.first_name or ''} {user.last_name or ''}
*TG:* @{message.from_user.username if message.from_user.username else 'нет'}
*ID:* {user_id}

*Детали заказа:*
• Товар: {data.product_name}
• Категория: {category_display}
• Количество: {data.quantity} шт.
• Сумма: {int(data.total_price)} руб.{address_info}

*Статус:* Ожидает оплаты
"""
                        bot.send_message(
                            MANAGER_CHAT_ID,
                            manager_text,
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        print(f"❌ Ошибка отправки менеджеру: {e}")
                
            except Exception as e:
                print(f"Ошибка создания заказа: {e}")
                import traceback
                traceback.print_exc()
                
                bot.send_message(
                    chat_id,
                    "❌ Произошла ошибка при создании заказа. Пожалуйста, попробуйте еще раз или свяжитесь с менеджером.",
                    reply_markup=keyboards.main_menu()
                )
        
        # Очищаем состояние
        StateManager.clear_state(user_id)
    
    elif message.text == '✏️ Изменить данные':
        # Возвращаем к началу магазина
        handle_shop_start(bot, message)
    
    elif message.text == '🔙 Назад':
        # Возвращаем на предыдущий шаг
        data = StateManager.get_data(user_id)
        
        if data.product_category == 'physical' and hasattr(data, 'delivery_address'):
            # Возвращаем к вводу адреса
            StateManager.set_state(user_id, UserStates.SHOP_ENTER_ADDRESS, data)
            bot.send_message(
                chat_id,
                "📦 *Введите адрес доставки:*",
                parse_mode='Markdown',
                reply_markup=keyboards.back_button()
            )
        else:
            # Возвращаем к выбору количества
            StateManager.set_state(user_id, UserStates.SHOP_PRODUCT_DETAILS, data)
            # Показываем снова выбор количества
            bot.send_message(
                chat_id,
                f"🛒 *{data.product_name}*\n\n"
                f"Цена: {int(data.product_price)} руб.\n"
                f"Выберите количество:",
                parse_mode='Markdown',
                reply_markup=keyboards.shop_product_details_keyboard(None, min(getattr(data, 'product_stock', 10), 10))
            )
    
    elif message.text == '❌ Отмена':
        StateManager.clear_state(user_id)
        bot.send_message(
            chat_id,
            "❌ Заказ отменен. Возвращаемся в главное меню:",
            reply_markup=keyboards.main_menu()
        )
