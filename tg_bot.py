import os
import telebot
from dotenv import load_dotenv

# Импортируем твою готовую ИИ-логику из проекта
from ai_assistant import run_full_rag_with_memory

# Подгружаем локальные переменные (для тестов на компьютере)
load_dotenv()

# Получаем токен из переменных окружения
BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")

if not BOT_TOKEN:
    print("Ошибка: Переменная TG_BOT_TOKEN не найдена!")
    exit(1)

bot = telebot.TeleBot(BOT_TOKEN)

# 1. Обработка команды /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        "Привет! 🚗 Я твой цифровой автоюрист.\n\n"
        "Опиши своими словами спорную или аварийную ситуацию на дороге, "
        "и я помогу разобраться, кто прав по ПДД, используя базу знаний."
    )
    bot.reply_to(message, welcome_text)

# 2. Обработка всех текстовых сообщений (вопросов по ПДД)
@bot.message_handler(content_types=['text'])
def handle_pdd_question(message):
    user_input = message.text
    
    # Используем уникальный ID чата Телеграма как session_id.
    # Благодаря этому ИИ будет помнить контекст беседы с каждым конкретным пользователем!
    session_id = f"tg_{message.chat.id}"
    
    # Отправляем в чат статус "печатает...", пока ИИ формулирует ответ
    bot.send_chat_action(message.chat.id, 'typing')
    
    try:
        # Вызываем твой RAG-конвейер
        answer = run_full_rag_with_memory(user_input, session_id=session_id)
        # Отправляем ответ пользователю
        bot.send_message(message.chat.id, answer)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Произошла ошибка при обработке запроса: {e}")

import requests

# Обработка ГОЛОСОВЫХ сообщений
@bot.message_handler(content_types=['voice'])
def handle_voice_message(message):
    # 1. Отправляем статус "печатает...", чтобы пользователь видел активность
    bot.send_chat_action(message.chat.id, 'typing')
    
    try:
        # 2. Получаем информацию о файле из Telegram
        file_info = bot.get_file(message.voice.file_id)
        # Формируем ссылку на скачивание файла (.ogg)
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
        
        # Скачиваем файл в память
        voice_bytes = requests.get(file_url).content
        
        # 3. Переводим голос в текст (Транскрибация)
        # Здесь мы используем гипотетическую функцию transcribe_audio. 
        # Ниже я покажу, как её сделать минимальными усилиями.
        user_text = transcribe_audio(voice_bytes)
        
        if not user_text:
            bot.reply_to(message, "Извини, не удалось распознать речь. Попробуй сказать четче или напиши текстом.")
            return
            
        # Показываем пользователю, что мы его поняли
        bot.reply_to(message, f"🗣️ *Вы сказали:* {user_text}", parse_mode="Markdown")
        
        # 4. Передаем распознанный текст в твой готовый RAG-конвейер!
        session_id = f"tg_{message.chat.id}"
        answer = run_full_rag_with_memory(user_text, session_id=session_id)
        
        bot.send_message(message.chat.id, answer)
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка при обработке голосового сообщения: {e}")

# Запуск постоянного опроса Telegram
if __name__ == "__main__":
    print("🤖 Telegram-бот успешно запущен и слушает сообщения...")
    bot.infinity_polling()