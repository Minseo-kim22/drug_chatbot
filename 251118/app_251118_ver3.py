# app.py

import streamlit as st
import re
# 🌟 drug_functions_251118.py 파일에서 모든 필요한 함수를 가져옵니다.
from drug_functions_251118 import (
    load_data, 
    get_product_list, 
    get_main_component, 
    check_drug_interaction_flexible
)

# --------------------------------------
# 1. 데이터 로드 및 초기화
# --------------------------------------
df = load_data()

st.title("💊 약물 상호작용 챗봇")
st.caption("캡스톤 프로젝트: 약물 정보 검색 챗봇")

# 🌟 세션 상태 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []
if "chat_mode" not in st.session_state:
    st.session_state.chat_mode = "initial" 
if "waiting_for_product_selection" not in st.session_state:
    st.session_state.waiting_for_product_selection = False
if "product_options" not in st.session_state:
    st.session_state.product_options = set()


# 🌟 콜백 함수: 모드 변경
def set_chat_mode(mode):
    """챗봇 모드를 변경하고, 꼬리 질문 상태를 초기화하며, 챗봇 메시지를 시작합니다."""
    st.session_state.chat_mode = mode
    st.session_state.waiting_for_product_selection = False
    st.session_state.product_options = set()
    st.session_state.messages = [] # 새 모드 시작 시 메시지 초기화
    
    if mode == "component":
        initial_msg = "어떤 약물의 **주성분**이 궁금하신가요? 약물 이름을 입력해주세요."
    elif mode == "interaction":
        initial_msg = "어떤 **약물들 간의 상호작용**이 궁금하신가요? 두 약물 이름을 입력해주세요."
    else: # initial mode
        initial_msg = "안녕하세요! 약물 정보 챗봇입니다. 먼저 **원하시는 검색 모드를 선택**해주세요."
        
    st.session_state.messages.append({"role": "assistant", "content": initial_msg})
    st.rerun() 

# 🌟 콜백 함수: 제품 선택 처리
def handle_selection(product_name):
    # 🌟 df를 인수로 전달
    components = get_main_component(df, product_name)
    
    if components:
        result_message = f"✅ 선택하신 제품 '{product_name}'의 **주요 성분**은 다음과 같습니다:\n\n* {', '.join(components)}"
    else:
        result_message = f"ℹ️ 선택하신 제품 '{product_name}'의 주요 성분 정보를 추출하지 못했습니다."

    st.session_state.messages.append({"role": "user", "content": f"선택: {product_name}"})
    st.session_state.messages.append({"role": "assistant", "content": result_message})
    
    st.session_state.waiting_for_product_selection = False
    st.session_state.product_options = set()
    st.session_state.chat_mode = "initial" 
    st.rerun()


# 챗 메시지 출력
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if df is None:
    st.error("데이터 로드 실패로 챗봇을 실행할 수 없습니다.")
else:
    
    # 🌟 A. 초기 모드: 모드 선택 버튼 표시
    if st.session_state.chat_mode == "initial":
        if not st.session_state.messages: 
            set_chat_mode("initial")
            
        col1, col2 = st.columns(2)
        col1.button("🔬 주성분 질문", on_click=set_chat_mode, args=("component",))
        col2.button("🤝 상호작용 검색", on_click=set_chat_mode, args=("interaction",))
        
        st.chat_input(disabled=True, placeholder="검색 모드를 선택해주세요.")


    # 🌟 B. 주성분 모드: 주성분 검색 로직 실행
    elif st.session_state.chat_mode == "component":
        input_disabled = st.session_state.waiting_for_product_selection
        input_placeholder = "타이레놀 주성분이 뭐야?" if not input_disabled else "위에서 제품을 선택해주세요."
        prompt = st.chat_input(input_placeholder, disabled=input_disabled)
        
        st.button("↩️ 모드 선택으로 돌아가기", on_click=set_chat_mode, args=("initial",))

        if prompt and not input_disabled:
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            drug_name = prompt.strip('() ')
            drug_name = re.sub(r'(주성분|성분)[이]?\s*(뭐야|알려줘)?\??$', '', drug_name, flags=re.IGNORECASE).strip()
            drug_name = re.sub(r'[의]$', '', drug_name).strip()
            
            reply_message = ""
            if drug_name:
                with st.spinner(f"🔄 '{drug_name}' 제품 검색 중..."):
                    # 🌟 df를 인수로 전달
                    products = get_product_list(df, drug_name) 
                
                    if not products:
                        reply_message = f"ℹ️ '{drug_name}'에 대한 제품 정보를 상호작용 데이터베이스에서 찾을 수 없습니다."
                    
                    elif len(products) > 1:
                        st.session_state.product_options = products
                        st.session_state.waiting_for_product_selection = True
                        reply_message = f"✅ '{drug_name}'과(와) 관련된 여러 제품이 검색되었습니다. **찾으시는 제품을 선택**해 주세요."
                        
                    else:
                        selected_product = list(products)[0]
                        # 🌟 df를 인수로 전달
                        components = get_main_component(df, selected_product) 
                        
                        if components:
                            reply_message = f"✅ '{selected_product}'의 **주요 성분**은 다음과 같습니다:\n\n* {', '.join(components)}"
                            st.session_state.chat_mode = "initial" 
                        else:
                            reply_message = f"ℹ️ '{selected_product}'의 주요 성분 정보를 추출하지 못했습니다."
            else:
                reply_message = "❌ 어떤 약물의 성분을 알고 싶으신가요? 약물 이름을 입력해주세요."
            
            st.session_state.messages.append({"role": "assistant", "content": reply_message})
            st.rerun()

    # 🌟 C. 상호작용 모드: 상호작용 검색 로직 실행
    elif st.session_state.chat_mode == "interaction":
        input_placeholder = "타이레놀과 부루펜을 같이 복용해도 돼?"
        prompt = st.chat_input(input_placeholder)
        
        st.button("↩️ 모드 선택으로 돌아가기", on_click=set_chat_mode, args=("initial",))
        
        if prompt:
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            match_interaction = re.match(r'(.+?)\s*(?:이랑|랑|과|와|하고)\s+(.+?)(?:를|을)?\s+(?:같이|함께)\s+(?:복용해도|먹어도)\s+(?:돼|되나|될까|되나요)\??', prompt.strip())
            
            if not match_interaction:
                match_interaction_sep = re.match(r'^\s*(.+?)\s*(?:이랑|랑|과|와|하고)\s+(.+?)\s*$', prompt.strip())
                if match_interaction_sep:
                     match_interaction = match_interaction_sep

            if not match_interaction:
                 match_interaction_simple = re.match(r'^\s*([^\s].*?)\s+([^\s].*?)\s*$', prompt.strip())
                 if match_interaction_simple:
                     match_interaction = match_interaction_simple

            reply_message = ""
            if match_interaction:
                drug_A_query = match_interaction.group(1).strip('() ')
                drug_B_query = match_interaction.group(2).strip('() ')
                
                if drug_A_query and drug_B_query:
                    with st.spinner(f"🔄 '{drug_A_query}'와 '{drug_B_query}' 상호작용 검색 중..."):
                        # 🌟 df를 인수로 전달
                        risk, explanation = check_drug_interaction_flexible(df, drug_A_query, drug_B_query)
                    
                    if risk == "정보 없음":
                        reply_message = f"**💊 약물 상호작용 위험도: 정보 없음**\n\n**💡 상세 정보:**\n\n{explanation}"
                    elif risk == "안전" and "정보가 없습니다" in explanation:
                        reply_message = f"**💊 약물 상호작용 위험도: 정보 없음**\n\n**💡 상세 정보:**\n\n'{drug_A_query}'와 '{drug_B_query}' 간의 상호작용 정보가 등록되지 않았습니다."
                    else:
                        reply_message = f"**💊 약물 상호작용 위험도: {risk}**\n\n**💡 상세 정보:**\n\n{explanation}"
                        
                    st.session_state.chat_mode = "initial" 
                else:
                    reply_message = "❌ 두 약물 이름을 정확히 입력해주세요. 예: (A)약물과 (B)약물을 같이 복용해도 돼?"
            
            else:
                 reply_message = "🤔 두 약물 이름을 '타이레놀과 부루펜'처럼 **띄어쓰기**하거나 **'과', '랑'**을 사용하여 다시 입력해주세요."

            st.session_state.messages.append({"role": "assistant", "content": reply_message})
            st.rerun()

    # 🌟 D. 모드별 후처리 (버튼 출력)
    if st.session_state.chat_mode == "component" and st.session_state.waiting_for_product_selection:
        with st.chat_message("assistant"):
            st.markdown("⬆️ 위에서 제품명을 선택해주세요.") 
            cols = st.columns(2) 
            
            for i, product in enumerate(sorted(list(st.session_state.product_options))):
                cols[i % 2].button(
                    product, 
                    key=f"select_{product}", 
                    on_click=handle_selection, 
                    args=(product,)
                )