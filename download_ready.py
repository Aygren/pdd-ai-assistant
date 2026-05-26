import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("FIRECRAWL_API_KEY")

# ВСТАВЬ СЮДА ID СЕССИИ ИЗ СВОЕЙ ОШИБКИ:
CRAWL_ID = "019e6409-3f8d-7098-bcd6-96797c11a0ec"

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

print(f"Проверяем статус запущенной задачи {CRAWL_ID}...")

# Стучимся напрямую к ID нашей прошлой задачи
response = requests.get(
    f"https://api.firecrawl.dev/v1/crawl/{CRAWL_ID}", 
    headers=headers
)

if response.status_code == 200:
    status_data = response.json()
    status = status_data.get("status")
    
    print(f"Текущий статус на сервере: {status}")
    
    if status == "completed":
        pages_count = len(status_data.get("data", []))
        print(f"Отлично! Найдено спарсенных страниц: {pages_count}")
        
        # Сохраняем готовый результат в json
        with open("pdd_base.json", "w", encoding="utf-8") as f:
            json.dump(status_data.get("data", []), f, ensure_ascii=False, indent=4)
            
        print("Файл pdd_base.json успешно скачан без повторного парсинга!")
        
    elif status == "scraping":
        print(f"Робот еще работает. Прогресс: {status_data.get('completed', 0)} страниц. Подожди пару минут и запусти этот скрипт снова.")
    else:
        print(f"Увы, статус задачи: {status}. Похоже, придется перезапустить основной scraper.py.")
else:
    print(f"Не удалось получить данные. Ошибка сервера: {response.text}")