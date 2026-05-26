import os
import json
import time
import requests
from dotenv import load_dotenv

# 1. Загружаем переменные окружения
load_dotenv()
api_key = os.getenv("FIRECRAWL_API_KEY")

if not api_key:
    raise ValueError("Ошибка: API-ключ не найден! Проверь файл .env")

print("Запуск прямого парсинга ПДД через API Firecrawl...")

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

# 2. Безопасные настройки без конфликтов с регулярными выражениями
payload = {
    "url": "https://avtonauka.ru/pdd",
    "includePaths": ["pdd/"], 
    "excludePaths": [
        "pdd/bility-pdd",     
        "voprosy-pdd"         
    ],
    "maxDepth": 2,
    "limit": 100,
    "scrapeOptions": {
        "formats": ["markdown"]
    }
}

# 3. Отправляем запрос на запуск задачи
response = requests.post(
    "https://api.firecrawl.dev/v1/crawl", 
    headers=headers, 
    json=payload
)

if response.status_code != 200:
    raise RuntimeError(f"Не удалось запустить краулер: {response.text}")

crawl_id = response.json().get("id")
print(f"Задача успешно запущена! ID сессии: {crawl_id}")
print("Ожидаем сбор данных (проверка каждые 10 секунд)...")

# 4. Отказоустойчивый цикл ожидания (try-except предохраняет от падений сети)
errors_in_a_row = 0

while True:
    try:
        # Добавляем timeout=15, чтобы скрипт не завис, если сервер долго молчит
        status_response = requests.get(
            f"https://api.firecrawl.dev/v1/crawl/{crawl_id}", 
            headers=headers,
            timeout=15
        )
        
        if status_response.status_code != 200:
            print(f"\nСервер вернул ошибку: {status_response.text}. Пробуем еще раз...")
            time.sleep(10)
            continue
            
        status_data = status_response.json()
        status = status_data.get("status")
        
        # Успешный ответ обнуляет счетчик ошибок сети
        errors_in_a_row = 0
        
        if status == "completed":
            pages_count = len(status_data.get("data", []))
            print(f"\nУспешно завершено! Скачано страниц: {pages_count}")
            
            with open("pdd_base.json", "w", encoding="utf-8") as f:
                json.dump(status_data.get("data", []), f, ensure_ascii=False, indent=4)
                
            print("Данные сохранены в 'pdd_base.json'")
            break
            
        elif status == "failed":
            print(f"\nОшибка на стороне Firecrawl: {status_data.get('error')}")
            break
            
        else:
            completed_pages = status_data.get("completed", 0)
            print(f"В процессе... Спарсено страниц: {completed_pages}", end="\r")
            time.sleep(10)

    except (requests.exceptions.RequestException, Exception) as e:
        errors_in_a_row += 1
        print(f"\n[Предупреждение] Проблема с сетью ({errors_in_a_row}/5). Защита сработала. Ошибка: {e}")
        
        if errors_in_a_row >= 5:
            print("\nСлишком много ошибок сети подряд. Принудительный выход для защиты лимитов.")
            break
            
        time.sleep(10)