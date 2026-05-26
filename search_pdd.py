import os
from dotenv import load_dotenv
from postgrest import SyncPostgrestClient

# Загружаем настройки из .env
load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# Подключаемся к REST API Supabase
client = SyncPostgrestClient(f"{SUPABASE_URL}/rest/v1", headers={
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}"
})

def search_pdd(query_text, limit=3):
    try:
        # Очищаем от мусорных предлогов
        STOP_WORDS = {'через', 'для', 'под', 'над', 'при', 'или', 'около', 'вместе', 'после', 'всех', 'если', 'до', 'на', 'по', 'в', 'и', 'а', 'но', 'что', 'как'}
        
        words = [w.strip().lower() for w in query_text.split() if w.strip()]
        filtered_words = [w for w in words if w not in STOP_WORDS]
        
        if not filtered_words:
            return []
            
        # Соединяем через логическое ИЛИ (|)
        # Теперь если в чанке есть ХОТЯ БЫ одно слово (например, только "обгон"), он попадет в выдачу
        or_query = " | ".join(filtered_words)
        
        response = client.from_("pdd_documents") \
            .select("title, content, url") \
            .fts("search_vector", or_query) \
            .limit(10) \
            .execute()
            
        clean_results = []
        for doc in response.data:
            # Добавили букву r перед строкой, чтобы убрать SyntaxWarning в Python 3.14
            if r"1\. Общие положения" in doc['content'] and r"2\. Общие обязанности" in doc['content']:
                continue 
            clean_results.append(doc)
            
        # Возвращаем только нужное количество (топ-3) из отфильтрованных чистых результатов
        return clean_results[:limit]
    except Exception as e:
        print(f"Ошибка при поиске: {e}")
        return []

def main():
    print("=== Тест полнотекстового поиска по базе ПДД ===")
    
    while True:
        user_query = input("\nВведите поисковый запрос (или 'exit' для выхода): ")
        if user_query.lower() == 'exit':
            break
            
        if not user_query.strip():
            continue
            
        print(f"Ищу: '{user_query}'...")
        results = search_pdd(user_query)
        
        if not results:
            print("Ничего не найдено 🤷‍♂️")
            continue
            
        print(f"\nНайдено совпадений: {len(results)}")
        print("-" * 50)
        
        for idx, doc in enumerate(results, 1):
            print(f"[{idx}] Источник: {doc['title']}")
            print(f"Ссылка: {doc['url']}")
            print(f"Текст куска:\n{doc['content']}")
            print("-" * 50)

if __name__ == "__main__":
    main()