import streamlit as st
import google.generativeai as genai
import time

# --- API 키 설정 ---
# .streamlit/secrets.toml 파일에서 API 키를 불러옵니다.
genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

# --- 모델 설정 ---
# 사용할 제미나이 모델을 지정합니다.
model = genai.GenerativeModel('gemini-1.5-flash-latest')


st.title("나만의 약물 상호작용 경고 챗봇 💊 (Gemini Ver.)")

# 세션 상태에 'messages'가 없으면 초기화합니다.
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "안녕하세요! 저는 약물 상호작용에 대해 알려드리는 AI 챗봇입니다. 궁금한 점을 물어보세요."}
    ]

# 이전 대화 기록을 모두 보여줍니다.
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 사용자로부터 입력을 받습니다.
if prompt := st.chat_input("타이레놀과 아스피린을 함께 복용해도 되나요?"):
    # 사용자의 메시지를 대화 기록에 추가하고 화면에 보여줍니다.
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # --- Gemini 답변 생성 ---
    with st.spinner('Gemini AI가 답변을 생성 중입니다... 🤔'):
        # AI에게 역할을 부여하고, 사용자의 질문을 전달합니다.
        instruction = "당신은 약물 상호작용 및 건강 정보에 대해 설명해주는 전문가입니다. 다음 질문에 대해 의학적 근거를 바탕으로 친절하고 명확하게 설명해주세요:\n"
        response = model.generate_content(instruction + prompt)
        
        # 최종 답변 텍스트를 추출합니다.
        final_response = response.text

    # AI의 답변을 화면에 보여줍니다.
    with st.chat_message("assistant"):
        st.markdown(final_response)
        
    # AI의 답변을 대화 기록에 추가합니다.
    st.session_state.messages.append({"role": "assistant", "content": final_response})