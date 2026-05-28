import os
import json
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_mistralai import ChatMistralAI
from openai import OpenAI  # Импортируем универсальный клиент для работы с Groq STT

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


# === 2. JSON-АНАЛИТИК СИТУАЦИИ (С пониманием светофоров и попутных аварий) ===

analyzer_prompt = ChatPromptTemplate.from_messages([
    ("system", (
        "Ты — эксперт-аналитик ДТП. Твоя задача — изучить историю диалога и зафиксировать параметры происшествия.\n\n"
        "КРИТИЧЕСКИЕ ПРАВИЛА ДЛЯ РАЗНЫХ ТИПОВ ДТП:\n"
        "1. ПОПУТНЫЕ СТОЛКНОВЕНИЯ (Наезд сзади, 'догнал', врезался в заднюю часть): В этом случае понятия перекрестка, направления участников и знаков приоритета ТЕРЯЮТ СМЫСЛ. Если один ехал за другим и врезался, ты ОБЯЗАН выставить ВСЕ четыре поля (my_direction_known, my_priority_known, other_direction_known, other_priority_known) в значение true! Так как для фиксации наезда сзади (п. 9.10 ПДД) данных уже абсолютно достаточно.\n"
        "2. РЕГУЛИРУЕМЫЙ ПЕРЕКРЕСТОК: Если горит зеленый/красный или работает светофор, знаки приоритета теряют значение. Отмечай 'my_priority_known' и 'other_priority_known' как true.\n"
        "3. Если направление движения или приоритеты понятны из контекста, смело ставь true.\n\n"
        "Ты должен вернуть СТРОГО JSON-объект следующего формата:\n"
        "{{\n"
        "  \"my_direction_known\": true/false,\n"
        "  \"my_priority_known\": true/false,\n"
        "  \"other_direction_known\": true/false,\n"
        "  \"other_priority_known\": true/false,\n"
        "  \"missing_info_question\": \"Строка с вежливым вопросом только по тем пунктам, где стоит false. Если все true или это попутное ДТП/наезд сзади, оставь пустой.\"\n"
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
    
    # Получаем историю, чтобы узнать количество реплик
    history = get_session_history(session_id)
    # Если в истории уже больше 4 сообщений (2 круга диалога), даем ИИ волю ответить на основе того, что есть
    is_long_dialogue = len(history.messages) > 4

    # Проверяем, собраны ли все 4 критических факта
    all_info_gathered = (
        analysis.get('my_direction_known', False) and
        analysis.get('my_priority_known', False) and
        analysis.get('other_direction_known', False) and
        analysis.get('other_priority_known', False)
    )
    
    # Изменяем условие: если инфа не собрана И диалог еще короткий — уточняем детали
    if not all_info_gathered and not is_long_dialogue:
        return analysis.get('missing_info_question', "Уточните, пожалуйста, детали дорожной обстановки.")
        
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


# === 4. ФУНКЦИЯ БЕСПЛАТНОЙ ТРАНСКРИБАЦИИ ГОЛОСА (GROQ) ===

def transcribe_audio(audio_bytes: bytes) -> str:
    """Принимает байты аудиофайла и возвращает распознанный текст через бесплатный Groq API."""
    groq_api_key = os.environ.get("GROQ_API_KEY")
    
    if not groq_api_key:
        print("[ОШИБКА] Переменная GROQ_API_KEY не найдена в окружении!")
        return ""
        
    try:
        # Инициализируем клиент (Groq совместим с библиотекой openai, меняется только base_url)
        client = OpenAI(
            api_key=groq_api_key,
            base_url="https://api.groq.com/openai/v1"
        )
        
        # Передаем байты аудио под видом файла voice.ogg (формат Телеграма)
        transcription = client.audio.transcriptions.create(
            file=("voice.ogg", audio_bytes),
            model="whisper-large-v3",  # Бесплатная и сверхточная модель Whisper
            language="ru"              # Явно указываем русский язык для точности
        )
        return transcription.text
    except Exception as e:
        print(f"[ОШИБКА ТРАНСКРИБАЦИИ] {e}")
        return ""