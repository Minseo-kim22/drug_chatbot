import streamlit as st
import pandas as pd
import re

# --------------------------------------------------------------------------------------------------
# 1. 데이터 로드 및 유틸리티 함수 (변경 없음, 이전 수정 사항 포함)
# --------------------------------------------------------------------------------------------------
@st.cache_data
def load_data():
    # ... (load_data 함수 내용은 유지) ...
    file_path = r'druglist.csv' 
    try:    
        df = pd.read_csv(file_path, encoding='utf-8', dtype=str) 
        df['상세정보'] = df['상세정보'].fillna('상호작용 정보 없음')
        df['제품명A_lower'] = df['제품명A'].str.lower()
        df['성분명A_lower'] = df['성분명A'].str.lower()
        df['제품명B_lower'] = df['제품명B'].str.lower()
        df['성분명B_lower'] = df['성분명B'].str.lower()
        print("✅ (Streamlit) 약물 상호작용 데이터 로드 성공!")
        return df
    except FileNotFoundError:
        st.error(f"❌ '{file_path}' 파일을 찾을 수 없습니다.")
        return None
    except Exception as e:
        st.error(f"❌ 파일 로드 중 오류 발생: {e}")
        return None

df = load_data()

# clean_query, find_drug_info_optimized 함수는 유지

# get_product_list 함수 (숫자/단위 제거 전처리 로직 수정된 버전 유지)
def get_product_list(df, drug_query):
    # ... (이전 코드의 수정된 get_product_list 함수 내용 유지) ...
    # 쿼리 전처리: 숫자, 용량/제형 단위를 제거하고 비교 유연성 확보 (오류 수정 반영)
    cleaned_query = re.sub(r'\(.*?\)|\[.*?\]', '', drug_query, flags=re.IGNORECASE).strip().lower()
    cleaned_query = re.sub(r'\d+[a-zA-Z]+|\d+|주사제|정제|캡슐|시럽|시럽액|정|주|액|제\b|밀리그램|그램|mg|g|ml|l', '', cleaned_query, flags=re.IGNORECASE).strip()
    cleaned_query = cleaned_query.replace('_', '').replace(' ', '').strip()
    
    if not cleaned_query: return set()

    try:
        def preprocess_product_name_for_match(name):
             if pd.isna(name): return ''
             name_str = str(name).lower()
             name_str = re.sub(r'\((.*?)\)|\[.*?\]', '', name_str).strip() 
             name_str = re.sub(r'\d+[a-zA-Z]+|\d+|주사제|정제|캡슐|시럽|시럽액|정|주|액|제\b|밀리그램|그램|mg|g|ml|l', '', name_str, flags=re.IGNORECASE)
             name_str = name_str.replace('_', '').replace(' ', '')
             return name_str.strip()

        product_names_a = df['제품명A'].apply(preprocess_product_name_for_match)
        product_names_b = df['제품명B'].apply(preprocess_product_name_for_match)
        
        search_condition = (product_names_a == cleaned_query) | (product_names_b == cleaned_query)
        search_results = df[search_condition]

        if search_results.empty: return set()

        products = set(search_results['제품명A'].dropna()).union(set(search_results['제품명B'].dropna()))
        final_products = {str(p) for p in products if str(p).strip()}
        
        return final_products

    except Exception as e:
        print(f"DEBUG: get_product_list에서 오류 발생 - {e}")
        return set()

# get_main_component 함수 (숫자/단위 제거 전처리 로직 수정된 버전 유지)
def get_main_component(df, drug_query):
    # ... (이전 코드의 수정된 get_main_component 함수 내용 유지) ...
    cleaned_query = re.sub(r'\(.*?\)|\[.*?\]', '', drug_query, flags=re.IGNORECASE).strip().lower()
    cleaned_query = re.sub(r'\d+[a-zA-Z]+|\d+|주사제|정제|캡슐|시럽|시럽액|정|주|액|제\b|밀리그램|그램|mg|g|ml|l', '', cleaned_query, flags=re.IGNORECASE).strip()
    cleaned_query = cleaned_query.replace('_', '').replace(' ', '')
    
    if not cleaned_query: return set()

    try:
        def preprocess_product_name_for_match(name):
             if pd.isna(name): return ''
             name_str = str(name).lower()
             name_str = re.sub(r'\((.*?)\)|\[.*?\]', '', name_str).strip() 
             name_str = re.sub(r'\d+[a-zA-Z]+|\d+|주사제|정제|캡슐|시럽|시럽액|정|주|액|제\b|밀리그램|그램|mg|g|ml|l', '', name_str, flags=re.IGNORECASE)
             name_str = name_str.replace('_', '').replace(' ', '')
             return name_str.strip()

        product_names_a = df['제품명A'].apply(preprocess_product_name_for_match)
        product_names_b = df['제품명B'].apply(preprocess_product_name_for_match)
        
        valid_components = set()

        match_A_condition = product_names_a == cleaned_query
        components_A = df[match_A_condition]['성분명A'].dropna().str.lower().tolist()
        valid_components.update(components_A)

        match_B_condition = product_names_b == cleaned_query
        components_B = df[match_B_condition]['성분명B'].dropna().str.lower().tolist()
        valid_components.update(components_B)
        
        final_components = {str(c) for c in valid_components if str(c).strip() and str(c) != 'nan'}
        
        return final_components

    except Exception as e:
        print(f"DEBUG: get_main_component에서 오류 발생 - {e}")
        return set()

# check_drug_interaction_flexible 함수는 유지

# --------------------------------------------------------------------------------------------------
# 2. Streamlit UI 및 로직 (전면 수정)
# --------------------------------------------------------------------------------------------------
st.title("💊 약물 상호작용 챗봇")
st.caption("캡스톤 프로젝트: 기능 분리형 약물 정보 검색 챗봇")

# 🌟 세션 상태 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []
# 🌟 새로운 상태 변수: 현재 챗봇 모드 ("initial", "component", "interaction")
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
    # 모드 변경 후 st.rerun()을 호출하여 UI를 즉시 업데이트
    st.rerun() 

# 🌟 콜백 함수: 제품 선택 처리 (이전과 동일, st.rerun 사용)
def handle_selection(product_name):
    components = get_main_component(df, product_name)
    
    if components:
        result_message = f"✅ 선택하신 제품 '{product_name}'의 **주요 성분**은 다음과 같습니다:\n\n* {', '.join(components)}"
    else:
        result_message = f"ℹ️ 선택하신 제품 '{product_name}'의 주요 성분 정보를 추출하지 못했습니다."

    st.session_state.messages.append({"role": "user", "content": f"선택: {product_name}"})
    st.session_state.messages.append({"role": "assistant", "content": result_message})
    
    # 최종 답변 후 모드 선택 화면으로 돌아가기 위해 초기화
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
        # 챗봇 메시지 출력 후 버튼 표시
        if not st.session_state.messages: 
            set_chat_mode("initial") # 초기 메시지 없으면 생성
            
        col1, col2 = st.columns(2)
        col1.button("🔬 주성분 질문", on_click=set_chat_mode, args=("component",))
        col2.button("🤝 상호작용 검색", on_click=set_chat_mode, args=("interaction",))
        
        # chat_input 비활성화 (모드 선택만 가능)
        st.chat_input(disabled=True, placeholder="검색 모드를 선택해주세요.")


    # 🌟 B. 주성분 모드: 주성분 검색 로직 실행
    elif st.session_state.chat_mode == "component":
        # 꼬리 질문 상태일 때는 입력창 비활성화
        input_disabled = st.session_state.waiting_for_product_selection
        input_placeholder = "타이레놀 주성분이 뭐야?" if not input_disabled else "위에서 제품을 선택해주세요."
        prompt = st.chat_input(input_placeholder, disabled=input_disabled)
        
        # '초기 화면으로' 버튼 추가
        st.button("↩️ 모드 선택으로 돌아가기", on_click=set_chat_mode, args=("initial",))

        if prompt and not input_disabled:
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            drug_name = prompt.strip('() ')
            drug_name = re.sub(r'(주성분|성분)[이]?\s*(뭐야|알려줘)?\??$', '', drug_name, flags=re.IGNORECASE).strip()
            drug_name = re.sub(r'[의]$', '', drug_name).strip() # 불필요한 조사 '의' 제거
            
            reply_message = ""
            if drug_name:
                with st.spinner(f"🔄 '{drug_name}' 제품 검색 중..."):
                    products = get_product_list(df, drug_name) 
                
                    if not products:
                        reply_message = f"ℹ️ '{drug_name}'에 대한 제품 정보를 상호작용 데이터베이스에서 찾을 수 없습니다."
                    
                    elif len(products) > 1:
                        # 꼬리 질문 상태 설정
                        st.session_state.product_options = products
                        st.session_state.waiting_for_product_selection = True
                        reply_message = f"✅ '{drug_name}'과(와) 관련된 여러 제품이 검색되었습니다. **찾으시는 제품을 선택**해 주세요."
                        
                    else:
                        # 제품이 하나만 검색된 경우, 바로 성분 추출
                        selected_product = list(products)[0]
                        components = get_main_component(df, selected_product) 
                        
                        if components:
                            reply_message = f"✅ '{selected_product}'의 **주요 성분**은 다음과 같습니다:\n\n* {', '.join(components)}"
                            st.session_state.chat_mode = "initial" # 답변 후 초기화
                        else:
                            reply_message = f"ℹ️ '{selected_product}'의 주요 성분 정보를 추출하지 못했습니다."
            else:
                reply_message = "❌ 어떤 약물의 성분을 알고 싶으신가요? 약물 이름을 입력해주세요."
            
            st.session_state.messages.append({"role": "assistant", "content": reply_message})
            st.rerun() # 새로운 답변을 출력하기 위해 새로고침

    # 🌟 C. 상호작용 모드: 상호작용 검색 로직 실행
    elif st.session_state.chat_mode == "interaction":
        input_placeholder = "타이레놀과 부루펜을 같이 복용해도 돼?"
        prompt = st.chat_input(input_placeholder)
        
        # '초기 화면으로' 버튼 추가
        st.button("↩️ 모드 선택으로 돌아가기", on_click=set_chat_mode, args=("initial",))
        
        if prompt:
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            # 2. 상호작용 질문 (이전 로직 유지)
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
                        risk, explanation = check_drug_interaction_flexible(df, drug_A_query, drug_B_query)
                    
                    if risk == "정보 없음":
                        reply_message = f"**💊 약물 상호작용 위험도: 정보 없음**\n\n**💡 상세 정보:**\n\n{explanation}"
                    elif risk == "안전" and "정보가 없습니다" in explanation:
                        reply_message = f"**💊 약물 상호작용 위험도: 정보 없음**\n\n**💡 상세 정보:**\n\n'{drug_A_query}'와 '{drug_B_query}' 간의 상호작용 정보가 등록되지 않았습니다."
                    else:
                        reply_message = f"**💊 약물 상호작용 위험도: {risk}**\n\n**💡 상세 정보:**\n\n{explanation}"
                        
                    st.session_state.chat_mode = "initial" # 답변 후 초기화
                else:
                    reply_message = "❌ 두 약물 이름을 정확히 입력해주세요. 예: (A)약물과 (B)약물을 같이 복용해도 돼?"
            
            else:
                 reply_message = "🤔 두 약물 이름을 '타이레놀과 부루펜'처럼 **띄어쓰기**하거나 **'과', '랑'**을 사용하여 다시 입력해주세요."

            st.session_state.messages.append({"role": "assistant", "content": reply_message})
            st.rerun() # 새로운 답변을 출력하기 위해 새로고침

    # 🌟 D. 모드별 후처리 (버튼 출력)
    if st.session_state.chat_mode == "component" and st.session_state.waiting_for_product_selection:
        # 꼬리 질문 상태일 때만 버튼을 생성 (메시지 출력 후)
        with st.chat_message("assistant"):
            st.markdown("⬆️ 위에서 제품명을 선택해주세요.") 
            # 버튼을 두 열로 나누어 출력
            cols = st.columns(2) 
            
            for i, product in enumerate(sorted(list(st.session_state.product_options))):
                cols[i % 2].button(
                    product, 
                    key=f"select_{product}", 
                    on_click=handle_selection, 
                    args=(product,)
                )