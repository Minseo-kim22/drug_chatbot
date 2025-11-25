import streamlit as st
import pandas as pd
import re

# 1. 데이터 로드 
@st.cache_data
def load_data():
    """druglist.csv 파일을 로드하고 캐시에 저장합니다."""
    # 파일 경로는 bot_v9.11.py를 따릅니다.
    file_path = r'druglist.csv' 
    try:    
        df = pd.read_csv(file_path, encoding='utf-8', dtype=str) 
        df['상세정보'] = df['상세정보'].fillna('상호작용 정보 없음')
    
        # 소문자 컬럼 미리 생성 (bot_v9.11.py 방식)
        df['제품명A_lower'] = df['제품명A'].str.lower()
        df['성분명A_lower'] = df['성분명A'].str.lower()
        df['제품명B_lower'] = df['제품명B'].str.lower()
        df['성분명B_lower'] = df['성분명B'].str.lower()
        print("✅ (Streamlit) 약물 상호작용 데이터 로드 성공!")
        return df
    except FileNotFoundError:
        st.error(f"❌ '{file_path}' 파일을 찾을 수 없습니다. .py 파일과 같은 폴더에 있는지 확인해주세요.")
        return None
    except UnicodeDecodeError:
        st.error(f"❌ '{file_path}' 파일 인코딩이 'utf-8'이 아닌 것 같습니다. (파일 인코딩을 'utf-8'로 변환해주세요)")
        return None
    except Exception as e:
        st.error(f"❌ 파일 로드 중 오류 발생: {e}")
        return None

df = load_data()

# 2. 약물 검색 및 상호작용 함수들
def clean_query(query):
    """검색어 정제 함수: 괄호, 특정 제형 단어를 제거하고 소문자로 변환합니다."""
    if not query:
        return ""
    # bot_v9.11.py의 clean_query 함수 사용
    cleaned = re.sub(r'\(.*?\)|\[.*?\]|(주사제|정제|캡슐|시럽)$', '', str(query)).strip().lower() 
    return cleaned

@st.cache_data 
def find_drug_info_optimized(df, query):
    """[V6] (상호작용 검색용) 쿼리한 약물 '자체'의 제품명/성분명만 효율적으로 검색합니다."""
    # bot_v9.11.py 함수 그대로 유지
    cleaned_query = clean_query(query)
    original_query_lower = str(query).strip().lower()
    search_patterns = {cleaned_query, original_query_lower}
    search_patterns.discard('')
    
    if not search_patterns: return None
    
    valid_patterns = [re.escape(item) for item in search_patterns if item]
    if not valid_patterns: return None
    search_pattern_re = "|".join(valid_patterns)

    drugs_set = set()

    try:
        mask_A = df['제품명A_lower'].str.contains(search_pattern_re, na=False) | df['성분명A_lower'].str.contains(search_pattern_re, na=False)
        results_A = df[mask_A]
        if not results_A.empty:
            drugs_set.update(results_A['제품명A_lower'].dropna())
            drugs_set.update(results_A['성분명A_lower'].dropna())

        mask_B = df['제품명B_lower'].str.contains(search_pattern_re, na=False) | df['성분명B_lower'].str.contains(search_pattern_re, na=False)
        results_B = df[mask_B]
        if not results_B.empty:
            drugs_set.update(results_B['제품명B_lower'].dropna())
            drugs_set.update(results_B['성분명B_lower'].dropna())

    except re.error as e:
        print(f"DEBUG: RegEx error in find_drug_info_optimized - {e} (Pattern: {search_pattern_re})")
        return None 
        
    if not drugs_set: return None 
    
    final_set = {item for item in drugs_set if item and pd.notna(item) and str(item) != 'nan'}
    if not final_set: return None
    return final_set
    
# --------------------------------------------------------------------------------------------------
# 🌟 (수정) 제품 목록 추출 함수: 성분 꼬리 질문을 위해 사용
# --------------------------------------------------------------------------------------------------
def get_product_list(df, drug_query):
    """사용자 쿼리로부터 관련 제품명 목록을 추출합니다."""
    
    # 쿼리 전처리: 숫자, 용량/제형 단위를 제거하고 비교 유연성 확보 (오류 수정 반영)
    cleaned_query = re.sub(r'\(.*?\)|\[.*?\]', '', drug_query, flags=re.IGNORECASE).strip().lower()
    # 숫자 및 용량/제형 단어를 제거합니다.
    cleaned_query = re.sub(r'\d+[a-zA-Z]+|\d+|주사제|정제|캡슐|시럽|시럽액|정|주|액|제\b|밀리그램|그램|mg|g|ml|l', '', cleaned_query, flags=re.IGNORECASE).strip()
    cleaned_query = cleaned_query.replace('_', '').replace(' ', '').strip() # 불필요한 문자 및 공백 제거
    
    if not cleaned_query: return set()

    try:
        # 데이터프레임 제품명 전처리 함수
        def preprocess_product_name_for_match(name):
             if pd.isna(name): return ''
             name_str = str(name).lower()
             name_str = re.sub(r'\((.*?)\)|\[.*?\]', '', name_str).strip() 
             # 숫자 및 용량/제형 단어 제거
             name_str = re.sub(r'\d+[a-zA-Z]+|\d+|주사제|정제|캡슐|시럽|시럽액|정|주|액|제\b|밀리그램|그램|mg|g|ml|l', '', name_str, flags=re.IGNORECASE)
             name_str = name_str.replace('_', '').replace(' ', '')
             return name_str.strip()

        # 캐싱된 전처리 결과가 없으므로 임시로 .apply() 사용
        # (성능 개선을 위해 실제 앱에서는 이 전처리 결과를 미리 df에 저장하는 것이 좋습니다.)
        product_names_a = df['제품명A'].apply(preprocess_product_name_for_match)
        product_names_b = df['제품명B'].apply(preprocess_product_name_for_match)
        
        # 쿼리 전처리 결과와 전처리된 제품명이 정확히 일치하는 행을 찾습니다.
        search_condition = (product_names_a == cleaned_query) | (product_names_b == cleaned_query)
        search_results = df[search_condition]

        if search_results.empty: return set()

        # 제품명 A와 제품명 B 컬럼의 유니크한 '실제 값'을 추출 (전처리 전의 값)
        products = set(search_results['제품명A'].dropna()).union(set(search_results['제품명B'].dropna()))
        final_products = {str(p) for p in products if str(p).strip()}
        
        return final_products

    except Exception as e:
        print(f"DEBUG: get_product_list에서 오류 발생 - {e}")
        return set()

# --------------------------------------------------------------------------------------------------
# 🌟 (수정) 주성분 추출 함수: 단일 제품에 대한 성분 추출 시 사용
# --------------------------------------------------------------------------------------------------
def get_main_component(df, drug_query):
    """사용자 쿼리로부터 주성분을 정확히 추출합니다. (단일 제품 선택 시 사용)"""
    
    # 쿼리 전처리 (get_product_list와 동일하게 수정)
    cleaned_query = re.sub(r'\(.*?\)|\[.*?\]', '', drug_query, flags=re.IGNORECASE).strip().lower()
    # 숫자 및 용량/제형 단어를 제거합니다.
    cleaned_query = re.sub(r'\d+[a-zA-Z]+|\d+|주사제|정제|캡슐|시럽|시럽액|정|주|액|제\b|밀리그램|그램|mg|g|ml|l', '', cleaned_query, flags=re.IGNORECASE).strip()
    cleaned_query = cleaned_query.replace('_', '').replace(' ', '')
    
    if not cleaned_query: return set()

    try:
        # 제품명 전처리 함수 (get_product_list와 동일하게 수정)
        def preprocess_product_name_for_match(name):
             if pd.isna(name): return ''
             name_str = str(name).lower()
             name_str = re.sub(r'\((.*?)\)|\[.*?\]', '', name_str).strip() 
             # 숫자 및 용량/제형 단어 제거
             name_str = re.sub(r'\d+[a-zA-Z]+|\d+|주사제|정제|캡슐|시럽|시럽액|정|주|액|제\b|밀리그램|그램|mg|g|ml|l', '', name_str, flags=re.IGNORECASE)
             name_str = name_str.replace('_', '').replace(' ', '')
             return name_str.strip()

        product_names_a = df['제품명A'].apply(preprocess_product_name_for_match)
        product_names_b = df['제품명B'].apply(preprocess_product_name_for_match)
        
        valid_components = set()

        # 제품명 A (C열)와 일치한 경우, 성분 A (A열)의 값만 추출
        match_A_condition = product_names_a == cleaned_query
        components_A = df[match_A_condition]['성분명A'].dropna().str.lower().tolist()
        valid_components.update(components_A)

        # 제품명 B (F열)와 일치한 경우, 성분 B (D열)의 값만 추출
        match_B_condition = product_names_b == cleaned_query
        components_B = df[match_B_condition]['성분명B'].dropna().str.lower().tolist()
        valid_components.update(components_B)
        
        final_components = {str(c) for c in valid_components if str(c).strip() and str(c) != 'nan'}
        
        return final_components

    except Exception as e:
        print(f"DEBUG: get_main_component에서 오류 발생 - {e}")
        return set()

# (check_drug_interaction_flexible 함수는 변경 없음)
def check_drug_interaction_flexible(df, drug_A_query, drug_B_query):
    """ [V8] 상호작용 검색 로직 (bot_v9.11.py 로직 유지) """
    
    set_A = find_drug_info_optimized(df, drug_A_query)
    set_B = find_drug_info_optimized(df, drug_B_query)

    if set_A is None:
        return "정보 없음", f"'{drug_A_query}'에 대한 약물 정보를 DB에서 찾을 수 없습니다."
    if set_B is None:
        return "정보 없음", f"'{drug_B_query}'에 대한 약물 정보를 DB에서 찾을 수 없습니다."

    valid_patterns_A = [re.escape(item) for item in set_A if item]
    valid_patterns_B = [re.escape(item) for item in set_B if item]

    if not valid_patterns_A or not valid_patterns_B:
          return "정보 없음", f"'{drug_A_query}' 또는 '{drug_B_query}'의 유효한 검색어를 생성하지 못했습니다."

    pattern_A = "|".join(valid_patterns_A)
    pattern_B = "|".join(valid_patterns_B)

    try:
        cols_A = (df['제품명A_lower'].str.contains(pattern_A, na=False, case=False) | df['성분명A_lower'].str.contains(pattern_A, na=False, case=False))
        cols_B = (df['제품명B_lower'].str.contains(pattern_B, na=False, case=False) | df['성분명B_lower'].str.contains(pattern_B, na=False, case=False))

        cols_C = (df['제품명A_lower'].str.contains(pattern_B, na=False, case=False) | df['성분명A_lower'].str.contains(pattern_B, na=False, case=False))
        cols_D = (df['제품명B_lower'].str.contains(pattern_A, na=False, case=False) | df['성분명B_lower'].str.contains(pattern_A, na=False, case=False))
        
    except re.error as e:
        print(f"DEBUG: RegEx error in check_drug_interaction - {e}")
        return "정보 없음", f"검색어 처리 중 오류 발생: {e}"

    
    interactions = df[(cols_A & cols_B) | (cols_C & cols_D)]

    if interactions.empty:
        return "안전", f"'{drug_A_query}'와 '{drug_B_query}' 간의 상호작용 정보가 없습니다."

    
    # 쿼리 자체에 대한 Specific 필터링 
    query_A_lower = clean_query(drug_A_query)
    query_B_lower = clean_query(drug_B_query)

    pattern_A_specific = re.escape(query_A_lower)
    pattern_B_specific = re.escape(query_B_lower)

    cols_A_specific = (interactions['제품명A_lower'].str.contains(pattern_A_specific, na=False) | interactions['성분명A_lower'].str.contains(pattern_A_specific, na=False))
    cols_D_specific = (interactions['제품명B_lower'].str.contains(pattern_A_specific, na=False) | interactions['성분명B_lower'].str.contains(pattern_A_specific, na=False))
    mask_A_specific = cols_A_specific | cols_D_specific
    
    cols_B_specific = (interactions['제품명B_lower'].str.contains(pattern_B_specific, na=False) | interactions['성분명B_lower'].str.contains(pattern_B_specific, na=False))
    cols_C_specific = (interactions['제품명A_lower'].str.contains(pattern_B_specific, na=False) | interactions['성분명A_lower'].str.contains(pattern_B_specific, na=False))
    mask_B_specific = cols_B_specific | cols_C_specific

    specific_interactions = interactions[mask_A_specific & mask_B_specific]
    
    interactions_to_display = interactions 
    
    if not specific_interactions.empty:
        interactions_to_display = specific_interactions
    
    # 위험도 판단 로직
    interactions_to_display = interactions_to_display.drop_duplicates(subset=['제품명A', '성분명A', '제품명B', '성분명B', '상세정보'])

    dangerous_keywords = [
        "금기", "투여 금지", "독성 증가", "치명적인", "심각한", "유산 산성증", 
        "고칼륨혈증", "심실성 부정맥", "위험성 증가", "위험 증가", "심장 부정맥", 
        "QT간격 연장 위험 증가", "QT연장", "심부정맥", "중대한", "심장 모니터링", 
        "병용금기", "Torsade de pointes 위험 증가", "위험이 증가함", 
        "약물이상반응 발생 위험", "독성", "허혈", "혈관경련",
        "횡문근융해와 같은 중증의 근육이상 보고" 
    ]
    caution_keywords = [
        "치료 효과가 제한적", "중증의 위장관계 이상반응", "Alfuzosin 혈중농도 증가", 
        "양쪽 약물 모두 혈장농도 상승 가능", "Amiodarone 혈중농도 증가", 
        "혈중농도 증가", "혈장 농도 증가", 
        "Finerenone 혈중농도의 현저한 증가가 예상됨"
    ]

    highest_risk_level = -1 
    reasons = []
    
    for index, row in interactions_to_display.iterrows():
        detail_str = str(row['상세정보'])
        if detail_str == '상호작용 정보 없음':
            continue

        prod_A = row['제품명A'] if pd.notna(row['제품명A']) else row['성분명A']
        prod_B = row['제품명B'] if pd.notna(row['제품명B']) else row['성분명B']
        
        if not pd.notna(prod_A): prod_A = "?"
        if not pd.notna(prod_B): prod_B = "?"
        
        label = f"({prod_A} / {prod_B})"
        
        classified = False
        
        for keyword in dangerous_keywords:
            if keyword in detail_str:
                reasons.append(f"🚨 **위험 {label}**: {detail_str}")
                highest_risk_level = max(highest_risk_level, 2)
                classified = True
                break 
        
        if classified:
            continue
            
        for keyword in caution_keywords:
            if keyword in detail_str:
                reasons.append(f"⚠️ **주의 {label}**: {detail_str}")
                highest_risk_level = max(highest_risk_level, 1)
                classified = True
                break
        
        if classified:
            continue
        
        reasons.append(f"ℹ️ **정보 {label}**: {detail_str}")
        highest_risk_level = max(highest_risk_level, 0)
    
    if highest_risk_level == 2:
        risk_label = "위험"
    elif highest_risk_level == 1:
        risk_label = "주의"
    elif highest_risk_level == 0:
        risk_label = "정보 확인"
    else:
          return "안전", f"'{drug_A_query}'와 '{drug_B_query}' 간의 상호작용 정보가 없습니다."
    
    return risk_label, "\n\n".join(reasons)

# --------------------------------------
# 3. Streamlit 웹사이트 UI 코드 
# --------------------------------------
st.title("💊 약물 상호작용 챗봇")
st.caption("캡스톤 프로젝트: 약물 상호작용 정보 검색 챗봇")

# 🌟 꼬리 질문 상태를 위한 세션 상태 추가
if "messages" not in st.session_state:
    st.session_state.messages = []
if "waiting_for_product_selection" not in st.session_state:
    st.session_state.waiting_for_product_selection = False
if "product_options" not in st.session_state:
    st.session_state.product_options = set()
if "initial_query" not in st.session_state:
      st.session_state.initial_query = ""


if not st.session_state.messages:
    st.session_state.messages.append(
        {"role": "assistant", "content": "안녕하세요! 약물 상호작용 챗봇입니다.\n\n[질문 예시]\n1. 타이레놀 주성분이 뭐야?\n2. 타이레놀과 부루펜을 같이 복용해도 돼?"}
    )

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 🌟 버튼 클릭 시 호출될 콜백 함수 정의 (st.experimental_rerun -> st.rerun 변경)
def handle_selection(product_name):
    # 성분 추출
    components = get_main_component(df, product_name)
    
    if components:
        result_message = f"✅ 선택하신 제품 '{product_name}'의 **주요 성분**은 다음과 같습니다:\n\n* {', '.join(components)}"
    else:
        result_message = f"ℹ️ 선택하신 제품 '{product_name}'의 주요 성분 정보를 추출하지 못했습니다."

    # 메시지 리스트에 사용자의 선택과 봇의 최종 응답을 추가합니다.
    st.session_state.messages.append({"role": "user", "content": f"선택: {product_name}"})
    st.session_state.messages.append({"role": "assistant", "content": result_message})
    
    # 꼬리 질문 상태를 종료하고 옵션을 초기화합니다.
    st.session_state.waiting_for_product_selection = False
    st.session_state.product_options = set()
    st.session_state.initial_query = ""
    
    # st.rerun()으로 변경하여 안정성 확보
    st.rerun() 

if df is None:
    st.error("데이터 로드 실패로 챗봇을 실행할 수 없습니다.")
else:
    # 꼬리 질문 상태일 때는 일반적인 chat_input 처리를 건너뜜
    if not st.session_state.waiting_for_product_selection:
        prompt = st.chat_input("질문을 입력하세요... (예: 타이레놀과 부루펜)")
    else:
        # 꼬리 질문 상태일 때는 입력창 비활성화 (버튼만 사용)
        prompt = None
        # 마지막 봇 메시지 아래에만 "선택해주세요" 힌트 출력
        if st.session_state.messages[-1]['role'] == 'assistant': 
            with st.chat_message("assistant"):
                st.write("⬆️ 위에서 제품명을 선택해주세요.") 
        

    if prompt: # 일반적인 프롬프트가 입력되었을 때만 처리
        
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        reply_message = ""
        st.session_state.initial_query = prompt # 초기 쿼리 저장
        
        # 1. 성분 질문
        # 🌟 RegEx 수정: "뭐야?/알려줘"로 끝남
        match_component = re.match(r'(.+?)\s*(?:주성분|성분)[이]?\s*(?:뭐야|알려줘)?\??$', prompt.strip())

        if match_component:
            drug_name = match_component.group(1).strip('() ')
            drug_name = re.sub(r'[의]$', '', drug_name).strip() # 불필요한 조사 '의' 제거
            
            if drug_name:
                # 🌟 get_product_list를 사용하여 모든 관련 제품 목록을 가져옵니다.
                products = get_product_list(df, drug_name) 
                
                if not products:
                    reply_message = f"ℹ️ '{drug_name}'에 대한 제품 정보를 상호작용 데이터베이스에서 찾을 수 없습니다."
                
                elif len(products) > 1:
                    # 🌟 제품이 여러 개일 경우, 선택 버튼을 위한 세션 상태를 저장합니다.
                    st.session_state.product_options = products
                    st.session_state.waiting_for_product_selection = True
                    reply_message = f"✅ '{drug_name}'과(와) 관련된 여러 제품이 검색되었습니다. **찾으시는 제품을 선택**해 주세요."
                    
                else:
                    # 제품이 하나만 검색된 경우, 바로 성분을 추출합니다.
                    selected_product = list(products)[0]
                    components = get_main_component(df, selected_product) 
                    
                    if components:
                        reply_message = f"✅ '{selected_product}'의 **주요 성분**은 다음과 같습니다:\n\n* {', '.join(components)}"
                    else:
                        reply_message = f"ℹ️ '{selected_product}'의 주요 성분 정보를 추출하지 못했습니다."
            else:
                reply_message = "❌ 어떤 약물의 성분을 알고 싶으신가요? 약물 이름을 입력해주세요."
        
        # 2. 상호작용 질문 (bot_v9.11.py 로직 유지)
        match_interaction = re.match(r'(.+?)\s*(?:이랑|랑|과|와|하고)\s+(.+?)(?:를|을)?\s+(?:같이|함께)\s+(?:복용해도|먹어도)\s+(?:돼|되나|될까|되나요)\??', prompt.strip())
        
        if not match_interaction:
            match_interaction_sep = re.match(r'^\s*(.+?)\s*(?:이랑|랑|과|와|하고)\s+(.+?)\s*$', prompt.strip())
            if match_interaction_sep:
                 match_interaction = match_interaction_sep

        if not match_interaction:
             match_interaction_simple = re.match(r'^\s*([^\s].*?)\s+([^\s].*?)\s*$', prompt.strip())
             if match_interaction_simple:
                 match_interaction = match_interaction_simple


        if match_interaction and not reply_message: # reply_message가 비어있을 때만 실행
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
            else:
                reply_message = "❌ 두 약물 이름을 정확히 입력해주세요. 예: (A)약물과 (B)약물을 같이 복용해도 돼?"
        
        # 3. 일반적인 응답
        elif not match_component and not match_interaction:
            reply_message = "🤔 죄송합니다. 질문 형식을 이해하지 못했습니다.\n\n   **[질문 예시]**\n   * 타이레놀과 부루펜\n   * 타이레놀 주성분이 뭐야?"

        st.session_state.messages.append({"role": "assistant", "content": reply_message})
        
        # 🌟 응답 메시지 출력 시, 버튼을 함께 출력합니다.
        with st.chat_message("assistant"):
            st.markdown(reply_message)
            
            # 🌟 꼬리 질문 상태일 때만 버튼을 생성합니다.
            if st.session_state.waiting_for_product_selection:
                # 버튼을 두 열로 나누어 출력
                cols = st.columns(2) 
                
                # 제품 목록을 순회하며 버튼을 생성합니다.
                for i, product in enumerate(sorted(list(st.session_state.product_options))):
                    cols[i % 2].button(
                        product, 
                        key=f"select_{product}", 
                        on_click=handle_selection, 
                        args=(product,)
                    )