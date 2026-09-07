import calendar
from datetime import datetime, timedelta
from telebot import types

def create_calendar(year=None, month=None, blocked_dates=None):
    """
    Создает нормальный inline-календарь на месяц
    Без дублирования названий месяцев
    """
    now = datetime.now()
    if year is None:
        year = now.year
    if month is None:
        month = now.month
    
    if blocked_dates is None:
        blocked_dates = []
    
    # Создаем разметку
    markup = types.InlineKeyboardMarkup(row_width=7)
    
    # Заголовок с месяцем и годом
    month_names = [
        'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
        'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
    ]
    
    # Добавляем заголовок
    markup.row(
        types.InlineKeyboardButton(
            f'{month_names[month-1]} {year}',
            callback_data='ignore'
        )
    )
    
    # Добавляем дни недели в ОДНУ строку
    week_days = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
    row = []
    for day in week_days:
        row.append(types.InlineKeyboardButton(day, callback_data='ignore'))
    markup.row(*row)
    
    # Получаем календарь на месяц
    month_cal = calendar.monthcalendar(year, month)
    
    # Добавляем каждую неделю
    for week in month_cal:
        row = []
        for day in week:
            if day == 0:
                row.append(types.InlineKeyboardButton(' ', callback_data='ignore'))
            else:
                date_str = f'{year}-{month:02d}-{day:02d}'
                date_obj = datetime(year, month, day)
                
                # Проверяем условия
                is_past = date_obj.date() < now.date()
                is_blocked = date_str in blocked_dates
                
                if is_past:
                    row.append(types.InlineKeyboardButton('✖️', callback_data='ignore'))
                elif is_blocked:
                    row.append(types.InlineKeyboardButton('❌', callback_data=f'blocked_{date_str}'))
                else:
                    row.append(types.InlineKeyboardButton(str(day), callback_data=f'date_{date_str}'))
        markup.row(*row)
    
    # Кнопки навигации
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    
    markup.row(
        types.InlineKeyboardButton('◀️', callback_data=f'prev_{prev_year}_{prev_month}'),
        types.InlineKeyboardButton('▶️', callback_data=f'next_{next_year}_{next_month}')
    )
    
    markup.row(types.InlineKeyboardButton('❌ Отмена', callback_data='cancel_calendar'))
    
    return markup

def format_date(date_str):
    """Форматирует дату для отображения"""
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d')
        days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        months = [
            'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
            'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'
        ]
        return f"{date.day} {months[date.month-1]} {date.year} ({days[date.weekday()]})"
    except:
        return date_str

def calculate_nights(checkin_str, checkout_str):
    """Рассчитывает количество ночей"""
    try:
        checkin = datetime.strptime(checkin_str, '%Y-%m-%d')
        checkout = datetime.strptime(checkout_str, '%Y-%m-%d')
        return (checkout - checkin).days
    except:
        return 0

def get_blocked_dates():
    """Получает заблокированные даты из базы данных"""
    from database import get_db, BlockedDate
    with next(get_db()) as db:
        blocked = db.query(BlockedDate).all()
        return [bd.date.strftime('%Y-%m-%d') for bd in blocked]

def is_date_available(date_str, blocked_dates):
    """Проверяет, доступна ли дата"""
    return date_str not in blocked_dates

def get_available_months():
    """Возвращает список доступных месяцев"""
    now = datetime.now()
    months = []
    
    for i in range(6):  # Текущий месяц + 5 следующих
        month_date = now.replace(day=1) + timedelta(days=30*i)
        months.append({
            'year': month_date.year,
            'month': month_date.month
        })
    
    return months