import streamlit as st
from ai_assistant import run_full_rag_with_memory

st.set_page_config(
    page_title="Помощник ПДД | Чат-бот",
    page_icon="🚗",
    layout="centered"
)

st.title("🚗 Интеллектуальный чат-ассистент по ПДД")
st.markdown("Задайте вопрос или опишите дорожную ситуацию. ИИ разберет её на основе базы знаний Supabase.")

st.divider()

# Инициализируем историю сообщений в сессии Streamlit, если её еще нет
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Привет! Я твой цифровой автоюрист. Опиши своими словами аварийную или спорную ситуацию, и я помогу разобраться, кто прав по ПДД."}
    ]

# Отображаем все прошлые сообщения из истории
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Поле для ввода сообщения (кастомный элемент чата Streamlit)
if user_input := st.chat_input("Напишите, что произошло..."):
    
    # 1. Отображаем сообщение пользователя в интерфейсе
    with st.chat_message("user"):
        st.markdown(user_input)
    
    # Добавляем его в историю сессии
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # 2. Генерируем ответ ИИ
    with st.chat_message("assistant"):
        with st.spinner("🤖 Сверяюсь с базой ПДД..."):
            try:
                # Вызываем наш обновленный RAG-конвейер с памятью
                answer = run_full_rag_with_memory(user_input, session_id="streamlit_session")
                
                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
            except Exception as e:
                st.error(f"Ошибка: {e}")