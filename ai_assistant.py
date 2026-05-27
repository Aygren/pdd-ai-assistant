import os
import json
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_mistralai import ChatMistralAI

# Импортируем поиск по Supabase
from search_pdd import search_pdd

load_dotenv()

# Инициализируем стандартную модель и модель со строгим JSON-ответом с защитой от зависания (таймаут 10 секунд)
llm = ChatMistralAI(model="mistral-small-latest", temperature=0.1, timeout=10)
llm_json = ChatMistralAI(model="mistral-small-latest", temperature=0.1, response_format={"type": "json_object"}, timeout=10)
# Хранилище историй чата в памяти
chats_storage = {}

def get_session_history(session_id: str) -> InMemoryChatMessageHistory:
    if session_id not in chats_storage:
        chats_storage[session_id] = InMemoryChatMessageHistory()
    return chats_storage[session_id]


# === 1. ЦЕПОЧКА ОПТИМИЗАТОРА ЗАПРОСОВ ===

optimizer_prompt = ChatPromptTemplate.from_messages([
    ("system", (
        "Ты — синтаксический анализатор. Выведи ровно 2-3 КЛЮЧЕВЫХ СЛОВА из сообщения водителя для поиска в ПДД.\n"
        "Правила: ТОЛЬКО слова через пробел, без знаков препинания. Игнорируй слова 'дтп', 'авария', 'виновник'."
    )),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{raw_user_text}")
])

optimizer_chain = optimizer_prompt | llm | StrOutputParser()

optimizer_with_history = RunnableWithMessageHistory(
    optimizer_chain,
    get_session_history,
    input_messages_key="raw_user_text",
    history_messages_key="chat_history"
)


# === 2. JSON-АНАЛИТИК СИТУАЦИИ (Исправленный вариант с экранированием скобок) ===

# === 2. JSON-АНАЛИТИК СИТУАЦИИ (С пониманием светофоров) ===

analyzer_prompt = ChatPromptTemplate.from_messages([
    ("system", (
        "Ты — эксперт-аналитик ДТП. Твоя задача — внимательно изучить историю диалога и текущее сообщение водителя, "
        "чтобы зафиксировать параметры ДТП на перекрестке.\n\n"
        "КРИТИЧЕСКИЕ ПРАВИЛА ДОРОЖНОЙ ИЕРАРХИИ:\n"
        "1. Если водитель указывает, что перекресток РЕГУЛИРУЕМЫЙ (горит зеленый, красный или работает светофор), то знаки приоритета (главная/второстепенная) ТЕРЯЮТ ЗНАЧЕНИЕ. В этом случае пункты 'my_priority_known' и 'other_priority_known' ты ОБЯЗАН отметить как true, так как их приоритет определен светофором!\n"
        "2. Будь гибок: если водитель написал 'у меня главная, у второго тоже главная', значит приоритеты ОБЕИХ машин известны (отмечай true).\n"
        "3. Если направление движения второго участника понятно из контекста (например, 'повернул передо мной налево', значит он ехал со встречного направления), отмечай 'other_direction_known' как true.\n\n"
        "Ты должен вернуть СТРОГО JSON-объект следующего формата:\n"
        "{{\n"
        "  \"my_direction_known\": true/false,\n"
        "  \"my_priority_known\": true/false,\n"
        "  \"other_direction_known\": true/false,\n"
        "  \"other_priority_known\": true/false,\n"
        "  \"missing_info_question\": \"Строка с вежливым вопросом только по тем пунктам, где стоит false. Если все true, оставь пустой.\"\n"
        "}}\n\n"
        "Запрещено выводить любой текст, кроме этого JSON-объекта."
    )),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{raw_user_text}")
])

analyzer_chain = analyzer_prompt | llm_json | StrOutputParser()

analyzer_with_history = RunnableWithMessageHistory(
    analyzer_chain,
    get_session_history,
    input_messages_key="raw_user_text",
    history_messages_key="chat_history"
)


# === 3. ЦЕПОЧКА ФИНАЛЬНОГО ЮРИДИЧЕСКОГО ОТВЕТА ===

final_prompt = ChatPromptTemplate.from_messages([
    ("system", (
        "Ты — профессиональный автоюрист. Выдай подробный разбор ДТП на основе предоставленных статей ПДД и истории диалога.\n\n"
        "НАЙДЕННЫЕ СТАТЬИ ПДД (Опирайся строго на них):\n{context}\n\n"
        "СПИСОК РАЗРЕШЕННЫХ ССЫЛОК:\n{allowed_links}"
    )),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{raw_user_text}")
])

final_chain = final_prompt | llm | StrOutputParser()

final_with_history = RunnableWithMessageHistory(
    final_chain,
    get_session_history,
    input_messages_key="raw_user_text",
    history_messages_key="chat_history"
)


# === ГЛАВНАЯ ФУНКЦИЯ КОНВЕЙЕРА ===

def run_full_rag_with_memory(user_speech: str, session_id: str = "default_user") -> str:
    config = {"configurable": {"session_id": session_id}}
    
    # 1. Запускаем JSON-анализатор с перехватом таймаутов и ошибок
    try:
        analysis_raw = analyzer_with_history.invoke(
            {"raw_user_text": user_speech}, 
            config=config
        )
        print(f"[ИИ Внутренности] Сгенерированная карточка JSON:\n{analysis_raw}")
        analysis = json.loads(analysis_raw)
    except Exception as e:
        print(f"[КРИТИЧЕСКАЯ ОШИБКА ИИ] Не удалось получить валидный JSON или вышел таймаут: {e}")
        return "Мне не удалось распознать структуру ситуации. Пожалуйста, опишите ДТП чуть подробнее: где вы находились и куда направлялись?"
    
    # Проверяем, собраны ли все 4 критических факта
    all_info_gathered = (
        analysis.get('my_direction_known', False) and
        analysis.get('my_priority_known', False) and
        analysis.get('other_direction_known', False) and
        analysis.get('other_priority_known', False)
    )
    
    # 2. Если данных не хватает — возвращаем сформированный моделью вопрос
    if not all_info_gathered:
        return analysis.get('missing_info_question', "Уточните, пожалуйста, детали дорожной обстановки.")
        
    # ... (дальше идет твой стандартный код RAG-поиска и финального ответа)
        
    # 3. Если ВСЕ данные на месте — запускаем классический RAG с Supabase
    keywords = optimizer_with_history.invoke(
        {"raw_user_text": user_speech}, 
        config=config
    )
    print(f"[ИИ Внутренности] Поисковый запрос в Supabase: '{keywords}'")
    
    raw_docs = search_pdd(keywords, limit=3)
    
    context_text = ""
    links_list = []
    
    if raw_docs:
        for doc in raw_docs:
            context_text += f"--- Статья: {doc['title']} ---\n{doc['content']}\n\n"
            if doc.get('url') and doc['url'] not in links_list:
                links_list.append(f"- [{doc['title']}]({doc['url']})")
                
    allowed_links_string = "\n".join(links_list) if links_list else "Нет доступных ссылок."
    
    if not context_text:
        context_text = "Подходящие статьи в базе данных ПДД не найдены."

    # 4. Передаем собранный контекст в финальный юридический разбор
    final_response = final_with_history.invoke(
        {
            "raw_user_text": user_speech,
            "context": context_text,
            "allowed_links": allowed_links_string
        },
        config=config
    )
    
    return final_response