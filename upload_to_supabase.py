import os
import json
from dotenv import load_dotenv
from postgrest import SyncPostgrestClient

# Загружаем переменные из файла .env в окружение
load_dotenv()

# Получаем настройки из переменных окружения
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# Проверяем, что переменные действительно загрузились
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError(
        "Ошибка: Переменные SUPABASE_URL или SUPABASE_KEY не найдены в окружении! "
        "Проверь, что файл .env создан и заполнен правильно."
    )

# Инициализируем клиент базы данных
client = SyncPostgrestClient(f"{SUPABASE_URL}/rest/v1", headers={
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}"
})

def chunk_markdown(text, max_chars=1500):
    """
    Разбивает большой текст на чанки (кусочки).
    Пытается ререзать красиво — по абзацам (\n\n), чтобы не разрывать предложения.
    """
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = ""
    
    for paragraph in paragraphs:
        if len(current_chunk) + len(paragraph) < max_chars:
            current_chunk += paragraph + "\n\n"
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = paragraph + "\n\n"
            
    if current_chunk:
        chunks.append(current_chunk.strip())
        
    return chunks

def main():
    json_path = "pdd_base.json"
    
    # Проверяем, на месте ли наш файл базы ПДД
    if not os.path.exists(json_path):
        print(f"Ошибка: Файл {json_path} не найден в текущей директории!")
        return

    print("Загрузка и чтение pdd_base.json...")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"Найдено страниц в исходном файле: {len(data)}")
    
    documents_to_insert = []
    
    # Обрабатываем каждую страницу
    for page in data:
        markdown_text = page.get("markdown", "")
        url = page.get("sourceURL", "")
        title = page.get("title", "")
        
        if not markdown_text:
            continue
            
        # Нарезаем длинный markdown страницы на кусочки
        chunks = chunk_markdown(markdown_text)
        
        for chunk in chunks:
            documents_to_insert.append({
                "content": chunk,
                "url": url,
                "title": title
            })

    print(f"Текст успешно разбит на {len(documents_to_insert)} чанков.")
    print("Начинается загрузка в Supabase...")

    # Загружаем данные пачками (батчами) по 50 штук
    batch_size = 50
    total_inserted = 0
    
    for i in range(0, len(documents_to_insert), batch_size):
        batch = documents_to_insert[i:i + batch_size]
        
        try:
            # Делаем insert в таблицу pdd_documents
            client.from_("pdd_documents").insert(batch).execute()
            total_inserted += len(batch)
            print(f"Успешно загружено: {total_inserted}/{len(documents_to_insert)}")
        except Exception as e:
            print(f"Ошибка при загрузке пачки: {e}")
            print("Продолжаем загрузку остальных пачек...")

    print("\n🎉 Все готово! База ПДД успешно перенесена в Supabase.")

if __name__ == "__main__":
    main()