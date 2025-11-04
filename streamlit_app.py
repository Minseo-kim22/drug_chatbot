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
        return pd.DataFrame(), None 
    
    try:
        # [수정] '아세'가 '파라세타몰'에도 걸리도록, 단순하지만 넓은 검색(substring) 사용
        search_pattern = re.escape(cleaned_query)
        
        search_results = df[
            df['제품명A'].str.contains(search_pattern, na=False) |
            df['성분명A'].str.contains(search_pattern, na=False) |
            df['제품명B'].str.contains(search_pattern, na=False) |
            df['성분명B'].str.contains(search_pattern, na=False)
        ]

        if search_results.empty:
            return pd.DataFrame(), None # 진짜 검색 결과 없음

        # 검색된 약물의 모든 이름/성분 집합을 반환
        drugs_set = set(search_results['제품명A']).union(set(search_results['성분명A'])).union(set(search_results['제품명B'])).union(set(search_results['성분명B']))
        drugs_set.discard('nan') # 'nan' 문자열 제거
        drugs_set.add(cleaned_query) # 원본 쿼리도 추가
        
        # [수정] results_A가 아닌, drugs_set (이름 집합)만 반환
        return drugs_set

    except Exception as e:
        print(f"DEBUG: find_drug_info에서 오류 발생 - {e}")
        return None
    

def check_drug_interaction_flexible(df, drug_A_query, drug_B_query):
    """ [진짜진짜 성능개선] isin()을 전체 df에 적용하여 정확한 상호작용만 검색 """
    
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
        # 4. [로직 수정] 전체 df에 대해 isin()을 사용하여 A-B 조합을 직접 찾기
        
        # (A in Col 1) AND (B in Col 2)
        A_in_col1 = df['제품명A'].isin(valid_drugs_A) | df['성분명A'].isin(valid_drugs_A)
        B_in_col2 = df['제품명B'].isin(valid_drugs_B) | df['성분명B'].isin(valid_drugs_B)
        
        # (B in Col 1) AND (A in Col 2)
        B_in_col1 = df['제품명A'].isin(valid_drugs_B) | df['성분명A'].isin(valid_drugs_B)
        A_in_col2 = df['제품명B'].isin(valid_drugs_A) | df['성분명B'].isin(valid_drugs_A)

        # 두 케이스를 OR로 결합
        interactions = df[ (A_in_col1 & B_in_col2) | (B_in_col1 & A_in_col2) ]

    except Exception as e:
        print(f"DEBUG: 상호작용 검색 중 오류 - {e}")
        return "오류", "상호작용 검색 중 오류가 발생했습니다."


    if interactions.empty:
        # [수정-P2] 약물은 찾았으나, 상호작용이 없는 경우
        return "안전", f"'{drug_A_query}'와 '{drug_B_query}' 간의 **등록된 상호작용 정보**가 없습니다."

    # 중복 제거
    interactions = interactions.drop_duplicates(subset=['상세정보'])

    # 5. 위험도 판단 로직 (기존과 동일)
    dangerous_keywords = ["금기", "투여 금지", "독성 증가", "치명적인", "심각한", "유산 산성증", "고칼륨혈증", "심실성 부정맥", "위험성 증가", "위험 증가", "심장 부정맥", "QT간격 연장 위험 증가", "QT연장", "심부정맥", "중대한", "심장 모니터링", "병용금기", "Torsade de pointes 위험 증가", "위험이 증가함", "약물이상반응 발생 위험", "독성", "허혈", "혈관경련", ]
    caution_keywords = ["치료 효과가 제한적", "중증의 위장관계 이상반응", "Alfuzosin 혈중농도 증가", "양쪽 약물 모두 혈장농도 상승 가능", "Amiodarone 혈중농도 증가", "혈중농도 증가", "횡문근융해와 같은 중증의 근육이상 보고",  "혈장 농도 증가", "Finerenone 혈중농도의 현저한 증가가 예상됨"]

    risk_level = "안전" # 기본값
    reasons = []
    processed_details = set() 

    for detail in interactions['상세정보'].unique():
        if detail in processed_details: continue
        detail_str = str(detail)
        processed_details.add(detail)
        
        found_danger = False
        for keyword in dangerous_keywords:
            if keyword in detail_str:
                risk_level = "위험" 
                reasons.append(f"🚨 **위험**: {detail_str}")
                found_danger = True
                break 
        
        if not found_danger:
            for keyword in caution_keywords:
                if keyword in detail_str:
                    if risk_level != "위험": risk_level = "주의"
                    reasons.append(f"⚠️ **주의**: {detail_str}")
                    break 
    
    if not reasons:
        risk_level = "정보 확인"
        reasons.append("ℹ️ 상호작용 정보가 있으나, 지정된 위험/주의 키워드는 발견되지 않았습니다. 전문가와 상담하세요.")
        for detail in interactions['상세정보'].unique():
             if str(detail) not in processed_details:
                reasons.append(f"ℹ️ **정보**: {str(detail)}")
            
    return risk_level, "\n\n".join(reasons)

# 3. Streamlit 웹사이트 UI 코드 (기존과 동일)
st.title("💊 약물 상호작용 챗봇")
st.caption("캡스톤 프로젝트: 약물 상호작용 정보 검색 챗봇")

if "messages" not in st.session_state:
    st.session_state.messages = []

if not st.session_state.messages:
    st.session_state.messages.append(
        {"role": "assistant", "content": "안녕하세요! 약물 상호작용 챗봇입니다.\n\n[질문 예시]\n1. 타이레놀 성분이 뭐야?\n2. 타이레놀과 아스피린을 같이 복용해도 돼?"}
    )

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if df is None:
    st.error("데이터 로드 실패로 챗봇을 실행할 수 없습니다.")
else:
    if prompt := st.chat_input("질문을 입력하세요... (예: 타이레놀과 아스피린)"):
        
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        reply_message = ""
        
        # 성분 질문
        match_component = re.match(r'(.+?)\s*성분[이]?[ ]?(뭐야|알려줘)\??', prompt.strip())
        if match_component:
            drug_name = match_component.group(1).strip('() ')
            if drug_name:
                # [수정] find_drug_info 반환값 변경됨
                drugs_set = find_drug_info(df, drug_name)
                if drugs_set is not None:
                    components = {str(d) for d in drugs_set if pd.notna(d) and len(str(d)) > 3 and str(d) != 'nan'}
                    if components:
                        reply_message = f"✅ '{drug_name}'의 관련 성분은 다음과 같습니다:\n\n* {', '.join(components)}"
                    else:
                        reply_message = f"ℹ️ '{drug_name}'을(를) 찾았으나, 연관된 성분 정보를 추출하지 못했습니다."
                else:
                    reply_message = f"ℹ️ '{drug_name}'에 대한 정보를 상호작용 데이터베이스에서 찾을 수 없습니다."
            else:
                reply_message = "❌ 어떤 약물의 성분을 알고 싶으신가요? 약물 이름을 입력해주세요."
        
        # 상호작용 질문
        match_interaction = re.match(r'(.+?)\s*(?:이랑|랑|과|와|하고)\s+(.+?)(?:를|을)?\s+(?:같이|함께)\s+(?:복용해도|먹어도)\s+(?:돼|되나|될까|되나요)\??', prompt.strip())
        
        if not match_interaction:
             match_interaction_simple = re.match(r'^\s*([^\s]+)\s+([^\s]+)\s*$', prompt.strip())
             if match_interaction_simple:
                 match_interaction = match_interaction_simple

        if match_interaction and not reply_message:
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
        
        elif not match_component and not match_interaction:
            reply_message = "🤔 죄송합니다. 질문 형식을 이해하지 못했습니다.\n\n   **[질문 예시]**\n   * 타이레놀과 아스피린\n   * 타이레놀 성분이 뭐야?"

        st.session_state.messages.append({"role": "assistant", "content": reply_message})
        with st.chat_message("assistant"):
            st.markdown(reply_message)
