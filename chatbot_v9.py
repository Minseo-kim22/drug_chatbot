import streamlit as st
import pandas as pd 
import re


@st.cache_data
def load_data():
 
    """druglist.csv 파일을 로드하고 캐시에 저장합니다."""
 
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
 
        st.error(f"❌ '{file_path}' 파일을 찾을 수 없습니다. .py 파일과 같은 폴더에 있는지 확인해주세요.")
        return None
    except UnicodeDecodeError:
        st.error(f"❌ '{file_path}' 파일 인코딩이 'utf-8'이 아닌 것 같습니다. (파일 인코딩을 'utf-8'로 변환해주세요)")
        return None
    except Exception as e:
        st.error(f"❌ 파일 로드 중 오류 발생: {e}")
        return None


df = load_data()



def clean_query(query):
 
    """
    검색어 정제 함수
 
    괄호, 특정 제형 단어를 제거하고 소문자로 변환합니다.
    """
    if not query:
        return ""
    cleaned = re.sub(r'\(.*?\)|\[.*?\]|(주사제|정제|캡슐|시럽)$', '', str(query)).strip().lower()
    return cleaned

@st.cache_data 
def find_drug_info_optimized(df, query):
 
    """
    [V6] 쿼리한 약물 '자체'의 제품명/성분명만 효율적으로 검색합니다.
 
    (상호작용 '상대방'을 포함하지 않습니다.)
    """
    cleaned_query = clean_query(query)
 
    original_query_lower = str(query).strip().lower()

 
    search_patterns = {cleaned_query, original_query_lower}
 
    search_patterns.discard('') # 빈 문자열 제거
    
    if not search_patterns:
        return None
    
    # | (OR) 정규식 패턴

    valid_patterns = [re.escape(item) for item in search_patterns if item]
    if not valid_patterns:
        return None
    search_pattern_re = "|".join(valid_patterns)


    drugs_set = set()

    try:
      
        mask_A = df['제품명A_lower'].str.contains(search_pattern_re, na=False) | \
                 df['성분명A_lower'].str.contains(search_pattern_re, na=False)
 
        results_A = df[mask_A]
        
        if not results_A.empty:
            drugs_set.update(results_A['제품명A_lower'].dropna())
            drugs_set.update(results_A['성분명A_lower'].dropna())

      
        mask_B = df['제품명B_lower'].str.contains(search_pattern_re, na=False) | \
                 df['성분명B_lower'].str.contains(search_pattern_re, na=False)
 
        results_B = df[mask_B]
        
        if not results_B.empty:
            drugs_set.update(results_B['제품명B_lower'].dropna())
            drugs_set.update(results_B['성분명B_lower'].dropna())

    except re.error as e:
 
        print(f"DEBUG: RegEx error in find_drug_info_optimized - {e} (Pattern: {search_pattern_re})")
        return None 
        
    if not drugs_set:
 
        return None 
    
    
    final_set = {item for item in drugs_set if item and pd.notna(item) and str(item) != 'nan'}

    if not final_set:
 
        return None

    return final_set
    

def check_drug_interaction_flexible(df, drug_A_query, drug_B_query):
 
    """ [V8] 성분 검색 후, '제품명' 일치 결과를 우선적으로 필터링 """
    
   
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

   
    query_A_lower = drug_A_query.lower()
 
    query_B_lower = drug_B_query.lower()
    

    pattern_A_specific = re.escape(query_A_lower)
 
    pattern_B_specific = re.escape(query_B_lower)


    cols_A_specific = (interactions['제품명A_lower'].str.contains(pattern_A_specific, na=False) | interactions['성분명A_lower'].str.contains(pattern_A_specific, na=False))
 
    cols_D_specific = (interactions['제품명B_lower'].str.contains(pattern_A_specific, na=False) | interactions['성분명B_lower'].str.contains(pattern_A_specific, na=False))
    mask_A_specific = cols_A_specific | cols_D_specific
    

    cols_B_specific = (interactions['제품명B_lower'].str.contains(pattern_B_specific, na=False) | interactions['성분명B_lower'].str.contains(pattern_B_specific, na=False))
 
    cols_C_specific = (interactions['제품명A_lower'].str.contains(pattern_B_specific, na=False) | interactions['성분명A_lower'].str.contains(pattern_B_specific, na=False))
    mask_B_specific = cols_B_specific | cols_C_specific


    specific_interactions = interactions[mask_A_specific & mask_B_specific]
 
    
    interactions_to_display = interactions # 기본값 = 모든 성분 일치 결과
    
    if not specific_interactions.empty:
 
        interactions_to_display = specific_interactions
    
 
    # 중복 제거
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

# 3. Streamlit 웹사이트 UI 코드 
st.title("💊 약물 상호작용 챗봇")
 
 
st.caption("캡스톤 프로젝트: 약물 상호작용 정보 검색 챗봇")

if "messages" not in st.session_state:
 
    st.session_state.messages = []

if not st.session_state.messages:
    st.session_state.messages.append(
 
        {"role": "assistant", "content": "안녕하세요! 약물 상호작용 챗봇입니다.\n\n[질문 예시]\n1. 타이레놀 성분이 뭐야?\n2. 타이레놀과 부루펜을 같이 복용해도 돼?"}
    )

for message in st.session_state.messages:
 
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if df is None:
 
    st.error("데이터 로드 실패로 챗봇을 실행할 수 없습니다.")
else:
    if prompt := st.chat_input("질문을 입력하세요... (예: 타이레놀(500mg)과 아스피린)"):
 
        
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
 
            st.markdown(prompt)

        reply_message = ""
        
        # 성분 질문
        match_component = re.match(r'(.+?)\s*성분[이]?[ ]?(뭐야|알려줘)\??', prompt.strip())
 
        if match_component:
            drug_name = match_component.group(1).strip()
            if drug_name:
 
                
              
                drugs_set = find_drug_info_optimized(df, drug_name)
                
                if drugs_set is not None:
 
                    components = {str(d) for d in drugs_set if pd.notna(d) and str(d).strip() and len(str(d)) > 1 and str(d) != 'nan'}
                    if components:
                        reply_message = f"✅ '{drug_name}'의 관련 성분/제품명은 다음과 같습니다:\n\n* {', '.join(components)}"
 
                    else:
                        reply_message = f"ℹ️ '{drug_name}'을(를) 찾았으나, 연관된 성분 정보를 추출하지 못했습니다."
                else:
                    reply_message = f"ℹ️ '{drug_name}'에 대한 정보를 상호작용 데이터베이스에서 찾을 수 없습니다."
 
            else:
                reply_message = "❌ 어떤 약물의 성분을 알고 싶으신가요? 약물 이름을 입력해주세요."
        
        # 상호작용 질문
        
        # 1. "같이 먹어도 돼?"가 포함된 '복잡한' 질문
        match_interaction = re.match(r'(.+?)\s*(?:이랑|랑|과|와|하고)\s+(.+?)(?:를|을)?\s+(?:같이|함께)\s+(?:복용해도|먹어도)\s+(?:돼|되나|될까|되나요)\??', prompt.strip())
        
        # 2. '복잡한' 질문이 아니면, 'A랑 B' 형태의 '중간' 질문
        if not match_interaction:
             # "이랑", "랑" 등의 구분자가 명확히 있는 경우
             match_interaction_sep = re.match(r'^\s*(.+?)\s*(?:이랑|랑|과|와|하고)\s+(.+?)\s*$', prompt.strip())
             if match_interaction_sep:
                 match_interaction = match_interaction_sep

        # 3. '중간' 질문도 아니면, 'A B' 형태의 '단순' 질문
        if not match_interaction:
             # 그냥 공백으로만 구분된 경우 
             match_interaction_simple = re.match(r'^\s*([^\s].*?)\s+([^\s].*?)\s*$', prompt.strip())
             if match_interaction_simple:
                 match_interaction = match_interaction_simple

        if match_interaction and not reply_message:
            drug_A_query = match_interaction.group(1).strip()
 
            drug_B_query = match_interaction.group(2).strip()
            
            if drug_A_query and drug_B_query:
                with st.spinner(f"🔄 '{drug_A_query}'와 '{drug_B_query}' 상호작용 검색 중..."):
 
                    # '제품명 필터링' 함수 호출
                    risk, explanation = check_drug_interaction_flexible(df, drug_A_query, drug_B_query)
                
                if risk == "정보 없음":
 
                     reply_message = f"**💊 약물 상호작용 위험도: 정보 없음**\n\n**💡 상세 정보:**\n\n{explanation}"
                elif risk == "안전" and "정보가 없습니다" in explanation:
                    reply_message = f"**💊 약물 상호작용 위험도: 정보 없음**\n\n**💡 상세 정보:**\n\n'{drug_A_query}'와 '{drug_B_query}' 간의 상호작용 정보가 등록되지 않았습니다."
 
                else:
                    reply_message = f"**💊 약물 상호작용 위험도: {risk}**\n\n**💡 상세 정보:**\n\n{explanation}"
            else:
 
                reply_message = "❌ 두 약물 이름을 정확히 입력해주세요. 예: (A)약물과 (B)약물을 같이 복용해도 돼?"
        
        elif not match_component and not match_interaction:
            reply_message = "🤔 죄송합니다. 질문 형식을 이해하지 못했습니다.\n\n  **[질문 예시]**\n  * 타이레놀과 아스피린\n  * 타이레놀 성분이 뭐야?"

        st.session_state.messages.append({"role": "assistant", "content": reply_message})
 
        with st.chat_message("assistant"):
            st.markdown(reply_message)

