import streamlit as st
import pandas as pd
import re

# 1. 데이터 로드 (페이지가 로드될 때 한 번만 실행됨)
@st.cache_data
def load_data():
    """druglist.csv 파일을 로드하고 캐시에 저장합니다."""
    file_path = r'druglist.csv'
    try:
        df = pd.read_csv(file_path, encoding='utf-8')
        df['상세정보'] = df['상세정보'].fillna('상호작용 정보 없음')
        print("✅ (Streamlit) 약물 상호작용 데이터 로드 성공!")
        # [성능개선] 검색을 위해 모든 텍스트 컬럼을 미리 'str' 타입으로 변경
        for col in ['제품명A', '성분명A', '제품명B', '성분명B']:
            # .str.lower()로 미리 소문자화
            df[col] = df[col].astype(str).str.lower() 
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

# 데이터 로드 실행
df = load_data()

# 2. 약물 검색 및 상호작용 함수들
def find_drug_info(df, query):
    """(수정) 사용자 쿼리로부터 약물 관련 정보를 유연하게 검색합니다."""
    
    # 쿼리 전처리: 괄호 및 특정 제형 단어만 제거
    cleaned_query = re.sub(r'\(.*?\)|\[.*?\]|주사제|정제|캡슐|시럽', '', query).strip().lower()
    
    if not cleaned_query:
        return None 
    
    try:
        # [수정] 정규표현식 사용 제거 및 regex=False 추가로 부분 문자열 검색 유연화
        search_pattern = cleaned_query 
        
        # regex=False로 설정하여 정규 표현식이 아닌 일반 문자열 검색을 수행
        search_results = df[
            df['제품명A'].str.contains(search_pattern, regex=False, na=False) |
            df['성분명A'].str.contains(search_pattern, regex=False, na=False) |
            df['제품명B'].str.contains(search_pattern, regex=False, na=False) |
            df['성분명B'].str.contains(search_pattern, regex=False, na=False)
        ]

        if search_results.empty:
            return None # 진짜 검색 결과 없음

        # 검색된 약물의 모든 이름/성분 집합을 반환
        drugs_set = set(search_results['제품명A']).union(set(search_results['성분명A'])).union(set(search_results['제품명B'])).union(set(search_results['성분명B']))
        drugs_set.discard('nan') # 'nan' 문자열 제거
        drugs_set.add(cleaned_query) # 원본 쿼리도 추가
        
        return drugs_set

    except Exception as e:
        print(f"DEBUG: find_drug_info에서 오류 발생 - {e}")
        return None


# --------------------------------------------------------------------------------------------------
# 🌟 (최종 수정) 성분 검색 함수: 주성분만 정확히 추출하도록 로직 개선
# --------------------------------------------------------------------------------------------------
def get_main_component(df, drug_query):
    """(최종 수정) 사용자 쿼리로부터 주성분을 정확히 추출합니다. 용량 정보의 숫자만 남겨서 비교 유연성을 확보합니다."""
    
    # 1. 쿼리 전처리: 괄호, 제형, 단위 단어 제거. 숫자/소수점은 유지.
    cleaned_query = re.sub(r'\(.*?\)|\[.*?\]|주사제|정제|캡슐|시럽|시럽제|시럽액|정|주|액|제\b|밀리그램|그램|mg|g|ml|l', '', drug_query, flags=re.IGNORECASE).strip().lower()
    cleaned_query = cleaned_query.replace('_', '').replace(' ', '')
    
    if not cleaned_query:
        return set()

    try:
        # 2. 데이터프레임 제품명 전처리 함수 (숫자만 남기도록 공격적으로 전처리)
        def preprocess_product_name_for_match(name):
             if pd.isna(name): return ''
             name_str = str(name).lower()
             
             # ① 괄호 안의 내용 (성분명, 용량 정보 등)을 모두 제거합니다.
             name_str = re.sub(r'\((.*?)\)|\[.*?\]', '', name_str).strip() 
             
             # ② 단위 단어 제거 (밀리그램, 정, 주 등)
             name_str = re.sub(r'밀리그램|그램|mg|g|ml|l|정|주|캡슐|액|제|\b', '', name_str, flags=re.IGNORECASE)

             # ③ 남은 공백과 '_' 제거 (예: "엘리퀴스2.5")
             name_str = name_str.replace('_', '').replace(' ', '')
             
             return name_str

        # 3. 제품명 컬럼을 전처리하여 비교를 위한 Series 생성 (전체 df 기준)
        product_names_a = df['제품명A'].apply(preprocess_product_name_for_match)
        product_names_b = df['제품명B'].apply(preprocess_product_name_for_match)
        
        # 4. 🌟 조건부 성분 추출 로직 (핵심 수정) 🌟
        # 중간 필터링 없이, 전체 df에서 정확히 일치하는 행의 성분만 추출합니다.
        valid_components = set()

        # 제품명 A (C열)와 일치한 경우, 성분 A (A열)의 값만 추출
        match_A_condition = product_names_a == cleaned_query
        
        # 전체 df에 조건을 적용하여 '성분명A'만 추출합니다.
        components_A = df[match_A_condition]['성분명A'].dropna().str.lower().tolist()
        valid_components.update(components_A)

        # 제품명 B (F열)와 일치한 경우, 성분 B (D열)의 값만 추출
        match_B_condition = product_names_b == cleaned_query
        
        # 전체 df에 조건을 적용하여 '성분명B'만 추출합니다.
        components_B = df[match_B_condition]['성분명B'].dropna().str.lower().tolist()
        valid_components.update(components_B)
        
        # 'nan' 문자열과 빈 값을 제거
        valid_components.discard('nan') 
        final_components = {str(c) for c in valid_components if str(c).strip()}
        
        # 최종 결과가 비어있는지 확인 (성분 추출 실패)
        if not final_components:
             # 성분은 찾지 못했지만, 제품명 자체는 DB에 등록되어 있을 수 있으므로 빈 set 반환
             return set()
             
        return final_components

    except Exception as e:
        print(f"DEBUG: get_main_component에서 오류 발생 - {e}")
        return set()

# --------------------------------------------------------------------------------------------------
# 🌟 상호작용 로직 수정 (불필요한 상세정보 중복 제거 라인 삭제)
# --------------------------------------------------------------------------------------------------
def check_drug_interaction_flexible(df, drug_A_query, drug_B_query):
    """ isin()을 전체 df에 적용하여 정확한 상호작용만 검색 """
    
    # 1. 각 약물에 대한 관련 이름/성분 집합(set) 찾기
    drugs_A_set = find_drug_info(df, drug_A_query)
    drugs_B_set = find_drug_info(df, drug_B_query)

    # 2. 약물 검색 결과에 따른 메시지 분기
    if drugs_A_set is None:
        return "정보 없음", f"'{drug_A_query}'" 
    if drugs_B_set is None:
        return "정보 없음", f"'{drug_B_query}'" 

    # 3. 'nan'이나 빈 문자열이 아닌 유효한 집합 생성
    valid_drugs_A = {str(d) for d in drugs_A_set if pd.notna(d) and str(d).strip() and str(d) != 'nan'}
    valid_drugs_B = {str(d) for d in drugs_B_set if pd.notna(d) and str(d).strip() and str(d) != 'nan'}

    if not valid_drugs_A or not valid_drugs_B:
        return "정보 없음", f"'{drug_A_query}' 또는 '{drug_B_query}'"

    try:
        # 4. 전체 df에 대해 isin()을 사용하여 A-B 조합을 직접 찾기
        A_in_col1 = df['제품명A'].isin(valid_drugs_A) | df['성분명A'].isin(valid_drugs_A)
        B_in_col2 = df['제품명B'].isin(valid_drugs_B) | df['성분명B'].isin(valid_drugs_B)
        
        B_in_col1 = df['제품명A'].isin(valid_drugs_B) | df['성분명A'].isin(valid_drugs_B)
        A_in_col2 = df['제품명B'].isin(valid_drugs_A) | df['성분명B'].isin(valid_drugs_A)

        # 두 케이스를 OR로 결합
        interactions = df[ (A_in_col1 & B_in_col2) | (B_in_col1 & A_in_col2) ]

    except Exception as e:
        print(f"DEBUG: 상호작용 검색 중 오류 - {e}")
        return "오류", "상호작용 검색 중 오류가 발생했습니다."


    if interactions.empty:
        return "안전", f"'{drug_A_query}'와 '{drug_B_query}' 간의 **등록된 상호작용 정보**가 없습니다."



    # 5. 위험도 판단 로직 
    dangerous_keywords = ["금기", "투여 금지", "독성 증가", "치명적인", "심각한", "유산 산성증", "고칼륨혈증", "심실성 부정맥", "위험성 증가", "위험 증가", "심장 부정맥", "QT간격 연장 위험 증가", "QT연장", "심부정맥", "중대한", "심장 모니터링", "병용금기", "Torsade de pointes 위험 증가", "위험이 증가함", "약물이상반응 발생 위험", "독성", "허혈", "혈관경련", "횡문근융해와 같은 중중의 근육이상 보고"]
    caution_keywords = ["치료 효과가 제한적", "중증의 위장관계 이상반응", "Alfuzosin 혈중농도 증가", "양쪽 약물 모두 혈장농도 상승 가능", "Amiodarone 혈중농도 증가", "혈중농도 증가", "횡문근융해와 같은 중증의 근육이상 보고",  "혈장 농도 증가", "Finerenone 혈중농도의 현저한 증가가 예상됨"]

    highest_risk_level = -1 # -1=안전, 0=정보확인, 1=주의, 2=위험
 
    reasons = []
    

    for index, row in interactions_to_display.iterrows():
 
        detail_str = str(row['상세정보'])
        if detail_str == '상호작용 정보 없음':
 
 
            continue


 
        # (소문자 컬럼이 아닌 원본 컬럼 '제품명A' 등에서 가져옴)
        prod_A = row['제품명A'] if pd.notna(row['제품명A']) else row['성분명A']
        prod_B = row['제품명B'] if pd.notna(row['제품명B']) else row['성분명B']
 
        
        # (nan 방지)
        if not pd.notna(prod_A): prod_A = "?"
 
        if not pd.notna(prod_B): prod_B = "?"
        
        # 제품명/성분명 라벨 생성
        label = f"({prod_A} / {prod_B})"
 
        
        classified = False
        
        # 1. '위험' 키워드 검사
 
        for keyword in dangerous_keywords:
            if keyword in detail_str:
            
                reasons.append(f"🚨 **위험 {label}**: {detail_str}")
 
                highest_risk_level = max(highest_risk_level, 2)
                classified = True
                break 
 
        
        if classified:
            continue
            
        # 2. '주의' 키워드 검사
 
        for keyword in caution_keywords:
            if keyword in detail_str:
             
                reasons.append(f"⚠️ **주의 {label}**: {detail_str}")
 
                highest_risk_level = max(highest_risk_level, 1)
                classified = True
                break
 
        
        if classified:
            continue
        
        # 3. '정보'
 
      
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
# --------------------------------------------------------------------------------------------------
# 3. Streamlit 웹사이트 UI 코드 
# --------------------------------------------------------------------------------------------------
st.title("💊 약물 상호작용 챗봇")
st.caption("캡스톤 프로젝트: 약물 상호작용 정보 검색 챗봇")

if "messages" not in st.session_state:
    st.session_state.messages = []

if not st.session_state.messages:
    st.session_state.messages.append(
        {"role": "assistant", "content": "안녕하세요! 약물 상호작용 챗봇입니다.\n\n[질문 예시]\n1. 타이레놀 주성분\n2. 타이레놀과 부루펜을 같이 복용해도 돼?"}
    )

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if df is None:
    st.error("데이터 로드 실패로 챗봇을 실행할 수 없습니다.")
else:
    if prompt := st.chat_input("질문을 입력하세요... (예: 타이레놀과 부루펜)"):
        
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        reply_message = ""
        
        # 1. 성분 질문
        match_component = re.match(r'(.+?)\s*(?:주성분|성분)[이]?\s*(?:뭐야|알려줘)?\??$', prompt.strip())


        if match_component:
            drug_name = match_component.group(1).strip('() ')
            
            # 추출된 약물 이름 뒤에 불필요하게 붙은 '의'를 제거합니다.
            drug_name = re.sub(r'[의]$', '', drug_name).strip()
            
            if drug_name:
                components = get_main_component(df, drug_name) 
                
                if components:
                    # 답변 메시지를 '주요 성분'으로 명시하여 일관성 유지
                    reply_message = f"✅ '{drug_name}'의 **주요 성분**은 다음과 같습니다:\n\n* {', '.join(components)}"
                else:
                    reply_message = f"ℹ️ '{drug_name}'에 대한 주요 성분 정보를 상호작용 데이터베이스에서 찾을 수 없습니다. (제품명은 있으나 성분명 미등록 또는 검색 실패)"
            else:
                reply_message = "❌ 어떤 약물의 성분을 알고 싶으신가요? 약물 이름을 입력해주세요."
        # 2. 상호작용 질문 (reply_message가 비어있을 때만 실행)
        match_interaction = re.match(r'(.+?)\s*(?:이랑|랑|과|와|하고)\s+(.+?)(?:를|을)?\s+(?:같이|함께)\s+(?:복용해도|먹어도)\s+(?:돼|되나|될까|되나요)\??', prompt.strip())
        
        if not match_interaction:
            match_interaction_simple = re.match(r'^\s*([^\s]+)\s+([^\s]+)\s*$', prompt.strip())
            if match_interaction_simple:
                if not reply_message: 
                    match_interaction = match_interaction_simple


        if match_interaction and not reply_message: # reply_message가 비어있을 때만 실행
            drug_A_query = match_interaction.group(1).strip('() ')
            drug_B_query = match_interaction.group(2).strip('() ')
            
            if drug_A_query and drug_B_query:
                with st.spinner(f"🔄 '{drug_A_query}'와 '{drug_B_query}' 상호작용 검색 중..."):
                    risk, explanation = check_drug_interaction_flexible(df, drug_A_query, drug_B_query)
                
                if risk == "정보 없음":
                    reply_message = f"**💊 약물 상호작용 위험도: 정보 없음**\n\n**💡 상세 정보:**\n\n{explanation}에 대한 정보를 상호작용 데이터베이스에서 찾을 수 없습니다. (정보가 등록되지 않았습니다.)"
                else:
                    reply_message = f"**💊 약물 상호작용 위험도: {risk}**\n\n**💡 상세 정보:**\n\n{explanation}"
            else:
                reply_message = "❌ 두 약물 이름을 정확히 입력해주세요. 예: (A)약물과 (B)약물을 같이 복용해도 돼?"
        
        # 3. 일반적인 응답
        elif not reply_message:
            reply_message = "🤔 죄송합니다. 질문 형식을 이해하지 못했습니다.\n\n   **[질문 예시]**\n   * 타이레놀과 부루펜\n   * 타이레놀 성분"

        st.session_state.messages.append({"role": "assistant", "content": reply_message})
        with st.chat_message("assistant"):
            st.markdown(reply_message)
