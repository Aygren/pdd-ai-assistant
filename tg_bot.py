import os
import requests
import telebot
from dotenv import load_dotenv

# Импортируем обе функции: RAG-конвейер и функцию перевода голоса в текст
from ai_assistant import run_full_rag_with_memory, transcribe_audio

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
        "и я помогу разобраться, кто прав по ПДД, используя базу знаний Supabase.\n\n"
        "🎙️ Ты можешь нажать на микрофон и просто надиктовать мне свою ситуацию голосом!"
    )
    bot.reply_to(message, welcome_text)

# 2. Обработка ГОЛОСОВЫХ сообщений (Голос -> Текст -> ПДД-ответ)
@bot.message_handler(content_types=['voice'])
def handle_voice_message(message):
    # Отправляем в чат статус "печатает...", показывая, что ИИ обрабатывает аудио
    bot.send_chat_action(message.chat.id, 'typing')
    
    try:
        # Скачиваем голосовой файл с серверов Telegram в оперативную память
        file_info = bot.get_file(message.voice.file_id)
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
        voice_bytes = requests.get(file_url).content
        
        # Распознаем аудио через Whisper на Groq API
        user_text = transcribe_audio(voice_bytes)
        
        if not user_text:
            bot.reply_to(message, "❌ Извини, мне не удалось распознать речь. Попробуй сказать четче или напиши текстом.")
            return
            
        # Показываем водителю распознанный текст, чтобы он видел, что всё распознано правильно
        bot.reply_to(message, f"🗣️ **Вы сказали:**\n_{user_text}_", parse_mode="Markdown")
        
        # Запускаем статус повторно перед долгой работой ИИ-анализатора
        bot.send_chat_action(message.chat.id, 'typing')
        
        # Передаем текст в RAG-конвейер с сохранением памяти
        session_id = f"tg_{message.chat.id}"
        answer = run_full_rag_with_memory(user_text, session_id=session_id)
        
        # Отправляем разбор ПДД пользователю
        bot.send_message(message.chat.id, answer)
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Произошла ошибка при обработке голосового сообщения: {e}")

# 3. Обработка всех текстовых сообщений (вопросов по ПДД)
@bot.message_handler(content_types=['text'])
def handle_pdd_question(message):
    user_input = message.text
    session_id = f"tg_{message.chat.id}"
    
    bot.send_chat_action(message.chat.id, 'typing')
    
    try:
        # Вызываем твой RAG-конвейер
        answer = run_full_rag_with_memory(user_input, session_id=session_id)
        bot.send_message(message.chat.id, answer)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Произошла ошибка при обработке запроса: {e}")

# Запуск постоянного опроса Telegram
if __name__ == "__main__":
    print("🤖 Telegram-бот успешно запущен и слушает сообщения...")
    bot.infinity_polling()