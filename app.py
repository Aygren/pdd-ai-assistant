import os
import streamlit as st
from ai_assistant import run_full_rag_with_memory

st.set_page_config(
    page_title="Помощник ПДД | Чат-бот",
    page_icon="🚗",
    layout="centered"
)


# --- ФУНКЦИЯ ДЛЯ ВЫВОДА SVG-ИКОНОК ИЗ ПАПКИ ASSETS ---
# --- ФУНКЦИЯ ДЛЯ ВЫВОДА SVG-ИКОНОК ИЗ ПАПКИ ASSETS ---
def render_svg(filename):
    """Читает SVG-файл из папки assets, центрирует его и выводит в интерфейс."""
    filepath = os.path.join("assets", filename)
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            svg_content = f.read()
        
        # Оборачиваем SVG в центрирующий контейнер
        centered_svg = f"""
        <div style="display: flex; justify-content: center; align-items: center; width: 100%; padding: 10px 0;">
            {svg_content}
        </div>
        """
        st.markdown(centered_svg, unsafe_allow_html=True)
    else:
        st.warning(f"Иконка {filename} не найдена в папке assets")


# --- ОФОРМЛЕНИЕ ШАПКИ САЙТА ---

# Отображаем твой кастомный логотип из v0
render_svg("car_logo2.svg")

st.divider()

st.markdown(
    "<p style='text-align: center; color: #191a1b;'>Задайте вопрос или опишите дорожную ситуацию. ИИ разберет её на основе базы знаний.</p>", 
    unsafe_allow_html=True
)

# --- ЛОГИКА ЧАТ-БОТА ---

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