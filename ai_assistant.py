import os
import json
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_mistralai import ChatMistralAI

# Импортируем твой поиск по Supabase
from search_pdd import search_pdd

load_dotenv()

# Инициализируем Mistral
llm = ChatMistralAI(model="mistral-small-latest", temperature=0.1)

# Хранилище историй чата в памяти
chats_storage = {}

def get_session_history(session_id: str) -> InMemoryChatMessageHistory:
    if session_id not in chats_storage:
        chats_storage[session_id] = InMemoryChatMessageHistory()
    return chats_storage[session_id]


# === 1. ЦЕПОЧКА ОПТИМИЗАТОРА ЗАПРОСОВ ===

optimizer_prompt = ChatPromptTemplate.from_messages([
    ("system", (
        "Ты — синтаксический анализатор. Выведи ровно 2-3 КЛЮЧЕВЫХ СЛОВА из нового сообщения водителя для поиска в базе данных ПДД.\n"
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


# === 2. НОВАЯ ЦЕПОЧКА: ИНСПЕКТОР-РАССЛЕДОВАТЕЛЬ ===

inspector_prompt = ChatPromptTemplate.from_messages([
    ("system", (
        "Ты — дотошный инспектор ГИБДД. Твоя цель — собрать ПОЛНУЮ картину ДТП на перекрестке, прежде чем назвать виновного.\n"
        "Пока ты не знаешь точный статус ОБЕИХ машин, ты НЕ ИМЕЕШЬ ПРАВА выносить вердикт.\n\n"
        "ЖЕСТКИЙ ЧЕК-ЛИСТ ДЛЯ ПЕРЕКРЕСТКА (Проверь себя):\n"
        "1. Известен ли статус КАЗДОЙ машины? (Кто на главной, кто на второстепенной, меняет ли главная направление?)\n"
        "2. Известно ли точное направление КАЗДОЙ машины? (Один поворачивал налево, а второй? Он ехал навстречу, попутно или сбоку?)\n"
        "3. Если пользователь говорит 'у меня главная', это НЕ значит, что у второго второстепенная! Встречный тоже мог быть на главной. Ты обязан это уточнить!\n\n"
        "ТВОИ ДЕЙСТВИЯ:\n"
        "- Если в истории диалога нет точного ответа хотя бы на ОДИН вопрос из чек-листа — ты обязан выбрать ВАРИАНТ А. Не фантазируй, задай водителю конкретный вопрос (например: 'В каком направлении ехал второй участник и какой знак висел у него?').\n"
        "- Если ВСЕ данные о траекториях и знаках ОБЕИХ сторон известны на 100% — выбери ВАРИАНТ Б.\n\n"
        "ФОРМАТ ОТВЕТА:\n"
        "ВАРИАНТ А: [Твои уточняющие вопросы]\n"
        "ВАРИАНТ Б:\nГОТОВО\n[Полный юридический разбор на основе контекста ПДД:\n{context}\nСсылки:\n{allowed_links}]"
    )),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{raw_user_text}")
])

inspector_chain = inspector_prompt | llm | StrOutputParser()

inspector_with_history = RunnableWithMessageHistory(
    inspector_chain,
    get_session_history,
    input_messages_key="raw_user_text",
    history_messages_key="chat_history"
)


# === ГЛАВНАЯ ФУНКЦИЯ КОНВЕЙЕРА ===

def run_full_rag_with_memory(user_speech: str, session_id: str = "default_user") -> str:
    config = {"configurable": {"session_id": session_id}}
    
    # 1. Извлекаем ключевые слова для Supabase
    keywords = optimizer_with_history.invoke(
        {"raw_user_text": user_speech}, 
        config=config
    )
    print(f"[ИИ Внутренности] Поисковый запрос: '{keywords}'")
    
    # 2. Поиск в Supabase
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

    # 3. Запуск Инспектора, который решает: спрашивать дальше или давать ответ
    response = inspector_with_history.invoke(
        {
            "raw_user_text": user_speech,
            "context": context_text,
            "allowed_links": allowed_links_string
        },
        config=config
    )
    
    # Очищаем маркер "ГОТОВО", если модель решила выдать финальный вердикт
    if response.startswith("ГОТОВО"):
        response = response.replace("ГОТОВО", "").strip()
    
    return response