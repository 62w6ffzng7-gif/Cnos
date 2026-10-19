import telebot
import random
import os
import sqlite3
from telebot import types

# --- 1. Мини-сервер для Render ---
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

def run_server():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()

threading.Thread(target=run_server, daemon=True).start()

# --- 2. Подключение к Telegram ---
TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

# --- 3. Инициализация баз данных ---
def init_db():
    conn = sqlite3.connect('oracle.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, balance INTEGER DEFAULT 0, free_tries INTEGER DEFAULT 5)''')
    c.execute('''CREATE TABLE IF NOT EXISTS complaints
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, reporter_id INTEGER, target_username TEXT, report_time DATETIME DEFAULT CURRENT_TIMESTAMP, status TEXT DEFAULT 'new')''')
    conn.commit()
    conn.close()

init_db()

def get_user(user_id):
    conn = sqlite3.connect('oracle.db')
    c = conn.cursor()
    c.execute("SELECT balance, free_tries FROM users WHERE user_id = ?", (user_id,))
    res = c.fetchone()
    if not res:
        c.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()
        res = (0, 5)
    conn.close()
    return res

def update_user(user_id, balance_delta=0, free_delta=0):
    conn = sqlite3.connect('oracle.db')
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ?, free_tries = free_tries + ? WHERE user_id = ?", 
              (balance_delta, free_delta, user_id))
    conn.commit()
    conn.close()

# --- 4. Тексты предсказаний ---
STARS = ["⭐ Звёзды сегодня на твоей стороне — да.", "🌑 Луна в тени — ответ «нет».", "✨ Созвездия шепчут: «скорее да, чем нет».", "🌠 Падающая звезда говорит: «скорее нет, чем да».", "🔭 Звёзды просят подождать — спроси позже.", "🌌 Небо молчит. Сейчас предсказать нельзя."]
CURRENCY = ["💱 Курс пойдёт вверх — покупай сейчас.", "📉 Валюта просядет — подожди немного.", "💰 Рынок стабилен, резких скачков не будет.", "⚖️ Курс качнётся, но вернётся к прежнему.", "🚀 Доллар/евро рванёт вверх — момент удачный."]
TELEGRAM = ["✈️ Канал взлетит — подписчики придут.", "📉 Пост не зайдёт — переделай заголовок.", "🔥 Контент сработает — публикуй смело.", "💤 Аудитория сейчас пассивна — подожди.", "🚀 Реклама окупится — запускай."]
INTROS = ["Смотрю на звёзды...", "Раскладываю созвездия...", "Слушаю шёпот галактик..."]
user_topic = {}

# --- 5. Клавиатуры ---
def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🔮 Гадать", "👤 Профиль")
    kb.add("💎 Пополнить баланс", "🚨 Пожаловаться")
    return kb

def topic_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("⭐ Звёзды", callback_data="topic_stars"))
    kb.add(types.InlineKeyboardButton("💱 Валюта", callback_data="topic_currency"))
    kb.add(types.InlineKeyboardButton("✈️ Telegram", callback_data="topic_telegram"))
    return kb

def shop_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🌟 5 гаданий — 15 Stars", callback_data="buy_5"))
    kb.add(types.InlineKeyboardButton("🌟 10 гаданий — 30 Stars", callback_data="buy_10"))
    kb.add(types.InlineKeyboardButton("🌟 20 гаданий — 55 Stars", callback_data="buy_20"))
    return kb

# --- 6. Хендлеры (команды бота) ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    get_user(message.from_user.id)
    bot.reply_to(message, "🌟 Привет! Я звёздный оракул.\nУ тебя есть 5 бесплатных гаданий. Выбирай действие!", reply_markup=main_menu())

@bot.message_handler(func=lambda message: message.text == "👤 Профиль")
def show_profile(message):
    balance, free = get_user(message.from_user.id)
    text = f"👤 Твой профиль:\n\n🆔 ID: {message.from_user.id}\n🎁 Бесплатных: {free}\n💎 Куплено: {balance}\n\nВсего доступно: {free + balance}"
    bot.reply_to(message, text)

@bot.message_handler(func=lambda message: message.text == "💎 Пополнить баланс")
def show_shop(message):
    bot.reply_to(message, "💎 Выбери пакет гаданий (оплата через Telegram Stars):", reply_markup=shop_keyboard())

@bot.message_handler(func=lambda message: message.text == "🔮 Гадать")
def ask_topic(message):
    bot.reply_to(message, "Выбери тему для гадания:", reply_markup=topic_keyboard())

@bot.callback_query_handler(func=lambda call: call.data.startswith("topic_"))
def set_topic(call):
    topic = call.data.replace("topic_", "")
    user_topic[call.from_user.id] = topic
    names = {"stars": "⭐ Звёзды", "currency": "💱 Валюта", "telegram": "✈️ Telegram"}
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, f"Тема выбрана: {names[topic]}. Задавай вопрос!")

@bot.message_handler(func=lambda message: message.text not in ["🔮 Гадать", "👤 Профиль", "💎 Пополнить баланс", "🚨 Пожаловаться"] and not message.text.startswith('/') and not message.text.startswith('@'))
def predict(message):
    user_id = message.from_user.id
    balance, free = get_user(user_id)
    
    if free > 0:
        update_user(user_id, free_delta=-1)
        status_msg = f"(Бесплатных осталось: {free - 1})"
    elif balance > 0:
        update_user(user_id, balance_delta=-1)
        status_msg = f"(Списано с баланса. Осталось: {balance - 1})"
    else:
        bot.reply_to(message, "У тебя закончились гадания! 😢\nПополни баланс кнопкой ниже.", reply_markup=main_menu())
        return

    topic = user_topic.get(user_id) or "stars"
    pools = {"stars": STARS, "currency": CURRENCY, "telegram": TELEGRAM}
    bot.reply_to(message, f"{random.choice(INTROS)}\n\n{random.choice(pools[topic])}\n\n{status_msg}")

# --- 7. Оплата Stars ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def process_buy(call):
    pack = call.data.split("_")[1]
    if pack == "5": amount, price = 5, 15
    elif pack == "10": amount, price = 10, 30
    elif pack == "20": amount, price = 20, 55
    
    bot.send_invoice(chat_id=call.message.chat.id, title=f"Пакет гаданий ({amount} шт.)",
        description=f"Покупка {amount} гаданий.", invoice_payload=f"buy_{amount}",
        provider_token="", currency="XTR", prices=[types.LabeledPrice(label=f"{amount} гаданий", amount=price)])
    bot.answer_callback_query(call.id)

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    amount = int(message.successful_payment.invoice_payload.split("_")[1])
    update_user(message.from_user.id, balance_delta=amount)
    bot.reply_to(message, f"✅ Успешно! Начислено {amount} гаданий.", reply_markup=main_menu())

# --- 8. Модуль жалоб ---
@bot.message_handler(func=lambda message: message.text == "🚨 Пожаловаться")
def start_complaint(message):
    msg = bot.reply_to(message, "Введите юзернейм нарушителя (например, @spamer123):")
    bot.register_next_step_handler(msg, process_complaint)

def process_complaint(message):
    username = message.text.strip()
    if not username.startswith('@'):
        bot.reply_to(message, "Ошибка: юзернейм должен начинаться с @.", reply_markup=main_menu())
        return
    try:
        chat = bot.get_chat(username)
        target_id = chat.id
    except Exception as e:
        bot.reply_to(message, f"❌ Пользователь {username} не найден.", reply_markup=main_menu())
        return

    conn = sqlite3.connect('oracle.db')
    c = conn.cursor()
    c.execute("INSERT INTO complaints (reporter_id, target_username) VALUES (?, ?)", (message.from_user.id, username))
    conn.commit()
    conn.close()

    bot.reply_to(message, f"✅ Жалоба на {username} зарегистрирована.\n📌 ID: {target_id}", reply_markup=main_menu())

# --- 9. ЗАПУСК БОТА (строго в самом конце!) ---
bot.polling(none_stop=True)
