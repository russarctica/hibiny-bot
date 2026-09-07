import calendar
from datetime import datetime, timedelta
from telebot import types

class HotelCalendar:
    def __init__(self, blocked_dates=None):
        self.blocked_dates = blocked_dates or []
    
    def create_calendar(self, year=None, month=None):
        now = datetime.now()
        if year is None:
            year = now.year
        if month is None:
            month = now.month
        
        markup = types.InlineKeyboardMarkup(row_width=7)
        
        # Заголовок с месяцем и годом
        month_name = calendar.month_name[month]
        header = f"{month_name} {year}"
        markup.add(types.InlineKeyboardButton(header, callback_data="ignore"))
        
        # Дни недели
        days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        row = []
        for day in days:
            row.append(types.InlineKeyboardButton(day, callback_data="ignore"))
        markup.add(*row)
        
        # Дни месяца
        month_calendar = calendar.monthcalendar(year, month)
        for week in month_calendar:
            row = []
            for day in week:
                if day == 0:
                    row.append(types.InlineKeyboardButton(" ", callback_data="ignore"))
                else:
                    date_str = f"{year}-{month:02d}-{day:02d}"
                    date_obj = datetime(year, month, day)
                    
                    # Проверяем, не прошедшая ли дата
                    if date_obj.date() < now.date():
                        row.append(types.InlineKeyboardButton("✖️", callback_data="ignore"))
                    # Проверяем, не заблокирована ли дата
                    elif date_str in self.blocked_dates:
                        row.append(types.InlineKeyboardButton("❌", callback_data=f"blocked_{date_str}"))
                    else:
                        row.append(types.InlineKeyboardButton(str(day), callback_data=f"date_{date_str}"))
            markup.add(*row)
        
        # Кнопки навигации
        navigation_row = []
        
        # Предыдущий месяц
        prev_month = month - 1
        prev_year = year
        if prev_month == 0:
            prev_month = 12
            prev_year -= 1
        navigation_row.append(types.InlineKeyboardButton("◀️", callback_data=f"nav_{prev_year}_{prev_month}"))
        
        # Текущая дата
        navigation_row.append(types.InlineKeyboardButton("Сегодня", callback_data=f"date_{now.date()}"))
        
        # Следующий месяц (максимум +4 месяца)
        next_month = month + 1
        next_year = year
        if next_month == 13:
            next_month = 1
            next_year += 1
        
        # Проверяем, не превышает ли 4 месяца вперед
        max_date = now + timedelta(days=120)  # ~4 месяца
        if datetime(next_year, next_month, 1).date() <= max_date.date():
            navigation_row.append(types.InlineKeyboardButton("▶️", callback_data=f"nav_{next_year}_{next_month}"))
        else:
            navigation_row.append(types.InlineKeyboardButton(" ", callback_data="ignore"))
        
        markup.add(*navigation_row)
        
        # Кнопка отмены
        markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_calendar"))
        
        return markup