import os
import telebot
from flask import Flask

# ===== НАСТРОЙКИ =====
TOKEN = os.environ.get('TOKEN', 'ВАШ_ТОКЕН_ЗДЕСЬ')

if TOKEN == 'ВАШ_ТОКЕН_ЗДЕСЬ':
    print("❌ ОШИБКА: Токен не задан!")
    print("👉 Добавьте TOKEN в настройках Render")
    exit(1)

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# ===== КОМАНДА /start =====
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = telebot.types.KeyboardButton('🏨 Бабл Отель')
    btn2 = telebot.types.KeyboardButton('🚗 Трансфер')
    btn3 = telebot.types.KeyboardButton('👨‍🏫 Инструктор')
    markup.add(btn1, btn2, btn3)
    
    bot.send_message(
        message.chat.id,
        "✅ Бот для бронирования Хибины работает!\n\nВыберите услугу:",
        reply_markup=markup
    )

# ===== FLASK ДЛЯ RENDER =====
@app.route('/')
def home():
    return "✅ Бот для бронирования Хибины работает! Отправьте /start в Telegram"

# ===== ЗАПУСК =====
if __name__ == '__main__':
    print("=" * 50)
    print("🚀 ТЕСТОВЫЙ БОТ ЗАПУЩЕН")
    print(f"✅ Токен: {'ЕСТЬ' if TOKEN != 'ВАШ_ТОКЕН_ЗДЕСЬ' else 'НЕТ!'}")
    print("=" * 50)
    
    # Запускаем бота
    import threading
    def run_bot():
        bot.polling(none_stop=True)
    
    threading.Thread(target=run_bot).start()
    
    # Запускаем Flask для Render
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)