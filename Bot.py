import sqlite3
from datetime import datetime

# --- База данных для жалоб ---
def init_report_table():
    conn = sqlite3.connect('oracle.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS complaints
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  reporter_id INTEGER,
                  target_username TEXT,
                  report_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                  status TEXT DEFAULT 'new')''')
    conn.commit()
    conn.close()

init_report_table()

# --- Клавиатура ---
def report_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🚨 Пожаловаться", "📊 Мои жалобы")
    kb.add("🔙 Назад")
    return kb

# --- Обработчик кнопки "Пожаловаться" ---
@bot.message_handler(func=lambda message: message.text == "🚨 Пожаловаться")
def start_complaint(message):
    msg = bot.reply_to(message, "Введите юзернейм нарушителя (например, @spamer123):")
    bot.register_next_step_handler(msg, process_complaint)

def process_complaint(message):
    username = message.text.strip()
    if not username.startswith('@'):
        bot.reply_to(message, "Ошибка: юзернейм должен начинаться с @. Попробуйте снова.", reply_markup=report_keyboard())
        return

    try:
        # Проверка существования пользователя
        chat = bot.get_chat(username)
        target_id = chat.id
    except Exception as e:
        bot.reply_to(message, f"❌ Пользователь {username} не найден. Ошибка: {e}", reply_markup=report_keyboard())
        return

    # Запись жалобы в базу
    conn = sqlite3.connect('oracle.db')
    c = conn.cursor()
    c.execute("INSERT INTO complaints (reporter_id, target_username, status) VALUES (?, ?, 'new')",
              (message.from_user.id, username))
    conn.commit()
    conn.close()

    # Уведомление администратору (если у вас есть свой ID, впишите его сюда)
    ADMIN_ID = None  # замените на ваш Telegram ID, чтобы получать уведомления
    if ADMIN_ID:
        try:
            bot.send_message(ADMIN_ID, f"🚨 Новая жалоба!\n👤 Нарушитель: {username}\n🆔 ID: {target_id}\n👤 От: {message.from_user.username or message.from_user.id}")
        except:
            pass

    bot.reply_to(
        message,
        f"✅ Жалоба на {username} зарегистрирована.\n"
        f"📌 ID нарушителя: {target_id}\n"
        f"Для официальной жалобы перешлите боту любое сообщение от этого пользователя.",
        reply_markup=report_keyboard()
    )

# --- Статистика жалоб ---
@bot.message_handler(func=lambda message: message.text == "📊 Мои жалобы")
def show_my_complaints(message):
    conn = sqlite3.connect('oracle.db')
    c = conn.cursor()
    c.execute("SELECT target_username, report_time, status FROM complaints WHERE reporter_id = ? ORDER BY report_time DESC LIMIT 10",
              (message.from_user.id,))
    rows = c.fetchall()
    conn.close()

    if not rows:
        bot.reply_to(message, "У вас пока нет зарегистрированных жалоб.", reply_markup=report_keyboard())
        return

    text = "📊 Ваши последние жалобы:\n\n"
    for username, ts, status in rows:
        text += f"👤 {username} — {ts[:16]} ({status})\n"
    bot.reply_to(message, text, reply_markup=report_keyboard())

# --- Возврат в главное меню ---
@bot.message_handler(func=lambda message: message.text == "🔙 Назад")
def back_to_main(message):
    bot.reply_to(message, "Главное меню:", reply_markup=main_menu())
bot.polling(none_stop=True).
