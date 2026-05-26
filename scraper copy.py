import os
import json
from firecrawl import Firecrawl

# 1-1. Импортируем инструмент для работы с .env файлами
from dotenv import load_dotenv

# 1-2. Загружаем переменные из файла .env в систему
load_dotenv()

# 1-3. Вытаскиваем ключ из системы безопасности
api_key = os.getenv("FIRECRAWL_API_KEY")

# Проверка на всякий случай, чтобы скрипт не упал без ключа
if not api_key:
    raise ValueError("Ошибка: API-ключ не найден! Проверь файл .env")

# 1-4. Инициализируем Firecrawl, передавая ему переменную
app = Firecrawl(api_key=api_key)

# 2. Настраиваем параметры ползания (Crawl) с жесткой фильтрацией
crawl_params = {
    # includePaths говорит боту: "Заходи только по ссылкам, которые начинаются так"
    "includePaths": [
        "pdd/*"  # Забираем всё, что лежит внутри папки pdd (главы и комментарии)
    ],
    # excludePaths говорит: "А вот сюда заходить запрещено, даже если очень хочется"
    "excludePaths": [
        "pdd/bility-pdd*",  # Игнорируем страницы экзаменационных билетов
        "*.php",            # Игнорируем динамические скрипты форумов
        "voprosy-pdd*"      # Игнорируем страницы с вопросами пользователей
    ],
    "maxDepth": 2,          # Глубина перехода по ссылкам (главная -> статья)
    "limit": 100,           # Максимальное количество страниц (для безопасности лимитов)
    "scrapeOptions": {
        "formats": ["markdown"]  # Нам нужен чистый Markdown для RAG-системы
    }
}

print("Запуск умного парсинга ПДД... Это может занять пару минут.")

# 3. Запускаем задачу на скрапинг
crawl_status = app.crawl_url(
    url="https://avtonauka.ru/pdd", 
    params=crawl_params,
    wait_until_done=True  # Скрипт будет ждать, пока Firecrawl всё соберет
)

# 4. Сохраняем полученный результат в JSON файл
if crawl_status.get("status") == "completed":
    print(f"Успешно скачано страниц: {len(crawl_status.get('data', []))}")
    
    with open("pdd_base.json", "w", encoding="utf-8") as f:
        json.dump(crawl_status["data"], f, ensure_ascii=False, indent=4)
        
    print("База знаний успешно сохранена в файл 'pdd_base.json'!")
else:
    print("Что-то пошло не так:", crawl_status.get("error"))