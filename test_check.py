import os
import json
from dotenv import load_dotenv
from postgrest import SyncPostgrestClient

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

client = SyncPostgrestClient(f"{SUPABASE_URL}/rest/v1", headers={
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}"
})

# 1. Проверяем файл
with open("pdd_base.json", "r", encoding="utf-8") as f:
    data = json.load(f)
print(f"Элементов в JSON: {len(data)}")

# 2. Пробуем вставить ОДНУ тестовую строку напрямую и вывести ответ сервера
test_data = {
    "content": "Тестовый текст для проверки записи",
    "url": "https://test.ru",
    "title": "Тестовый заголовок"
}

try:
    print("Пробуем отправить тестовую запись...")
    response = client.from_("pdd_documents").insert(test_data).execute()
    print("СТАТУС ОТВЕТА СЕРВЕРА:", response)
except Exception as e:
    print("ОШИБКА ПРИ ОТПРАВКЕ:", e)