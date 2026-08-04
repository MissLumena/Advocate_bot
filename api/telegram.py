import os
import json
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Я твой карьерный стратег.\n"
        "Отправь мне текст вакансии, и я помогу тебе подготовиться к собеседованию."
    )

# Обработчик текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    # Здесь можно добавить логику с OpenAI, но пока просто ответим
    await update.message.reply_text(f"Ты написал: {user_message}\n\n(Пока я просто эхо, но скоро научусь помогать!)")

# Главная функция для Vercel (вебхук)
async def webhook(request):
    # Получаем данные от Telegram
    body = await request.json()
    
    # Извлекаем chat_id из данных
    chat_id = body.get('message', {}).get('chat', {}).get('id')
    if not chat_id:
        return {"status": "error", "message": "No chat_id found"}

    # Создаём объект Update для работы с библиотекой python-telegram-bot
    update = Update.de_json(body, None)
    
    # Запускаем обработку сообщения (как в обычном боте)
    # Но в вебхуке нужно создать контекст и вызвать обработчики вручную
    # Здесь упрощённо: просто ответим на сообщение
    # (Полноценная обработка через библиотеку требует больше кода)
    
    # Отправляем ответ (простой пример)
    await request.app.state.bot.send_message(chat_id=chat_id, text="Я получил твоё сообщение!")

    return {"status": "ok"}

# Для локального запуска (не для Vercel)
if __name__ == "__main__":
    from telegram.ext import ApplicationBuilder
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()