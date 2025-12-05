import streamlit as st
import pandas as pd
import re
from fuzzywuzzy import process 

# 1. 데이터 로드 (페이지가 로드될 때 한 번만 실행됨)
@st.cache_data
def load_data():
    file_path = r'druglist.csv'
    try:
        # dtype=str을 추가하여 DtypeWarning을 방지합니다.
        df = pd.read_csv(file_path, encoding='utf-8', dtype=str)
        df['상세정보'] = df['상세정보'].fillna('상호작용 정보 없음')
        
        # [V6] 성능을 위해 모든 검색 대상 컬럼을 소문자로 미리 변환
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

# 데이터 로드 실행
df = load_data()

# [V10] 오타 보정(fuzzy matching)을 위한 전체 약물/성분 리스트 준비
all_drug_names_set = set()
if df is not None:
    try:
        # 모든 제품명과 성분명을 하나로 합친 후, 중복을 제거합니다.
        combined_names = pd.concat([
            df['제품명A_lower'], df['성분명A_lower'],
            df['제품명B_lower'], df['성분명B_lower']
        ]).dropna().unique()
        
        # 'nan' 문자열이나 너무 짧은 단어(2글자 이하)는 제외
        all_drug_names_set = {str(name) for name in combined_names if pd.notna(name) and len(str(name)) > 2}
        print(f"✅ (Streamlit) 오타 보정용 약물/성분 DB 준비 완료 (총 {len(all_drug_names_set)}개)")
    except Exception as e:
        print(f"❌ (Streamlit) 오타 보정용 DB 생성 실패: {e}")


# 2. 약물 검색 및 상호작용 함수들

def clean_query(query):
    """
    검색어 정제 함수
    괄호, 특정 제형 단어를 제거하고 소문자로 변환합니다.
    """
    if not query:
        return ""
    cleaned = re.sub(r'\(.*?\)|\[.*?\]|(주사제|정제|캡슐|시럽)$', '', str(query)).strip().lower()
    return cleaned

@st.cache_data # [V6] find_drug_info 결과도 캐시하여 속도 향상
def find_drug_info_optimized(df, query):
    """
    [V6] 쿼리한 약물 '자체'의 제품명/성분명만 효율적으로 검색합니다.
    (상호작용 '상대방'을 포함하지 않습니다.)
    """
    cleaned_query = clean_query(query)
    original_query_lower = str(query).strip().lower()

    # 검색 패턴 생성 (정제된 쿼리와 원본 쿼리 모두 포함)
    search_patterns = {cleaned_query, original_query_lower}
    search_patterns.discard('') # 빈 문자열 제거
    
    if not search_patterns:
        return None
    
    # | (OR) 정규식 패턴
    # [V7 수정] 빈 패턴으로 인한 re.error 방지
    valid_patterns = [re.escape(item) for item in search_patterns if item]
    if not valid_patterns:
        return None
    search_pattern_re = "|".join(valid_patterns)


    drugs_set = set()

    try:
        # 1. A컬럼에서 검색
        mask_A = df['제품명A_lower'].str.contains(search_pattern_re, na=False) | \
                 df['성분명A_lower'].str.contains(search_pattern_re, na=False)
        results_A = df[mask_A]
        
        if not results_A.empty:
            drugs_set.update(results_A['제품명A_lower'].dropna())
            drugs_set.update(results_A['성분명A_lower'].dropna())

        # 2. B컬럼에서 검색
        mask_B = df['제품명B_lower'].str.contains(search_pattern_re, na=False) | \
                 df['성분명B_lower'].str.contains(search_pattern_re, na=False)
        results_B = df[mask_B]
        
        if not results_B.empty:
            drugs_set.update(results_B['제품명B_lower'].dropna())
            drugs_set.update(results_B['성분명B_lower'].dropna())

    except re.error as e:
        print(f"DEBUG: RegEx error in find_drug_info_optimized - {e} (Pattern: {search_pattern_re})")
        return None # 잘못된 정규식 오류 방지
        
    if not drugs_set:
        return None # DB에서 약물 정보를 전혀 찾을 수 없음

    # 3. 원본 쿼리 이름도 최종 셋에 추가
    drugs_set.update(search_patterns)
    
    # 'nan' 문자열이나 빈 문자열 최종 제거
    final_set = {item for item in drugs_set if item and pd.notna(item) and str(item) != 'nan'}

    if not final_set:
        return None

    return final_set
    

def check_drug_interaction_flexible(df, drug_A_query, drug_B_query):
    """ [V8] 성분 검색 후, '제품명' 일치 결과를 우선적으로 필터링 """
    
    # 1. [V6] 최적화된 함수 호출
    set_A = find_drug_info_optimized(df, drug_A_query)
    set_B = find_drug_info_optimized(df, drug_B_query)

    # 2. 둘 중 하나라도 DB에 정보가 없으면 검색 불가
    if set_A is None:
        return "정보 없음", f"'{drug_A_query}'에 대한 약물 정보를 DB에서 찾을 수 없습니다."
    if set_B is None:
        return "정보 없음", f"'{drug_B_query}'에 대한 약물 정보를 DB에서 찾을 수 없습니다."

    # 3. 각 집합에 대한 | (OR) 정규식 패턴을 생성합니다.
    valid_patterns_A = [re.escape(item) for item in set_A if item]
    valid_patterns_B = [re.escape(item) for item in set_B if item]

    if not valid_patterns_A or not valid_patterns_B:
         return "정보 없음", f"'{drug_A_query}' 또는 '{drug_B_query}'의 유효한 검색어를 생성하지 못했습니다."

    pattern_A = "|".join(valid_patterns_A)
    pattern_B = "|".join(valid_patterns_B)

    try:
        # 4. [V6] 미리 소문자로 변환해둔 컬럼에서 검색
        cols_A = (df['제품명A_lower'].str.contains(pattern_A, na=False, case=False) | df['성분명A_lower'].str.contains(pattern_A, na=False, case=False))
        cols_B = (df['제품명B_lower'].str.contains(pattern_B, na=False, case=False) | df['성분명B_lower'].str.contains(pattern_B, na=False, case=False))

        # 5. B/A 순서
        cols_C = (df['제품명A_lower'].str.contains(pattern_B, na=False, case=False) | df['성분명A_lower'].str.contains(pattern_B, na=False, case=False))
        
        # --- [V14] SyntaxError 버그 수정 ---
        cols_D = (df['제품명B_lower'].str.contains(pattern_A, na=False, case=False) | df['성분명B_lower'].str.contains(pattern_A, na=False, case=False))
        # --- [V14] ---
        
    except re.error as e:
        print(f"DEBUG: RegEx error in check_drug_interaction - {e}")
        return "정보 없음", f"검색어 처리 중 오류 발생: {e}"

    # 6. (A & B) 또는 (B & A) 조합에 해당하는 모든 상호작용을 한 번에 찾습니다.
    interactions = df[(cols_A & cols_B) | (cols_C & cols_D)]

    if interactions.empty:
        # 원본 쿼리 이름으로 반환
        return "안전", f"'{drug_A_query}'와 '{drug_B_query}' 간의 상호작용 정보가 없습니다."

    # --- [V8] '제품명' 우선 필터링 로직 ---
    
    # 1. 사용자 원본 쿼리(소문자)로 '특정 제품명' 검색 패턴 생성
    query_A_lower = drug_A_query.lower()
    query_B_lower = drug_B_query.lower()
    
    # 쿼리 자체가 정규식 특수문자를 포함할 경우를 대비해 re.escape 사용
    pattern_A_specific = re.escape(query_A_lower)
    
    # --- [V13] 'NameError' 버그 수정 (유지) ---
    pattern_B_specific = re.escape(query_B_lower) 
    # --- [V13] ---

    # 2. 1차 결과(interactions) 내에서 '특정 제품명 A'가 포함된 행을 찾음
    cols_A_specific = (interactions['제품명A_lower'].str.contains(pattern_A_specific, na=False) | interactions['성분명A_lower'].str.contains(pattern_A_specific, na=False))
    cols_D_specific = (interactions['제품명B_lower'].str.contains(pattern_A_specific, na=False) | interactions['성분명B_lower'].str.contains(pattern_A_specific, na=False))
    mask_A_specific = cols_A_specific | cols_D_specific
    
    # 3. 1차 결과(interactions) 내에서 '특정 제품명 B'가 포함된 행을 찾음
    cols_B_specific = (interactions['제품명B_lower'].str.contains(pattern_B_specific, na=False) | interactions['성분명B_lower'].str.contains(pattern_B_specific, na=False))
    cols_C_specific = (interactions['제품명A_lower'].str.contains(pattern_B_specific, na=False) | interactions['성분명A_lower'].str.contains(pattern_B_specific, na=False))
    mask_B_specific = cols_B_specific | cols_C_specific

    # 4. A와 B 특정 제품명이 '모두' 포함된 행으로 필터링
    specific_interactions = interactions[mask_A_specific & mask_B_specific]
    
    interactions_to_display = interactions # 기본값 = 모든 성분 일치 결과
    
    if not specific_interactions.empty:
        # 5. '특정 제품명' 일치 결과가 있다면, 그것만 사용
        interactions_to_display = specific_interactions
    
    # --- [V8] 위험도 판단 로직 (V7과 동일하나, interactions_to_display 사용) ---
    
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
    
    # [V8] 필터링된 'interactions_to_display'를 순회합니다.
    for index, row in interactions_to_display.iterrows():
        detail_str = str(row['상세정보'])
        if detail_str == '상호작용 정보 없음':
            continue

        # [V7] 상세정보에 어떤 제품명이 연관되었는지 추출
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
                # [V7] 제품명 라벨 포함하여 추가
                reasons.append(f"🚨 **위험 {label}**: {detail_str}")
                highest_risk_level = max(highest_risk_level, 2)
                classified = True
                break 
        
        if classified:
            continue
            
        # 2. '주의' 키워드 검사
        for keyword in caution_keywords:
            if keyword in detail_str:
                # [V7] 제품명 라벨 포함하여 추가
                reasons.append(f"⚠️ **주의 {label}**: {detail_str}")
                highest_risk_level = max(highest_risk_level, 1)
                classified = True
                break
        
        if classified:
            continue
        
        # 3. '정보'
        reasons.append(f"ℹ️ **정보 {label}**: {detail_str}")
        highest_risk_level = max(highest_risk_level, 0)
    
    # --- [V7] 최종 위험도 및 결과 반환 (V6와 동일) ---
    if highest_risk_level == 2:
        risk_label = "위험"
    elif highest_risk_level == 1:
        risk_label = "주의"
    elif highest_risk_level == 0:
        risk_label = "정보 확인"
    else:
         return "안전", f"'{drug_A_query}'와 '{drug_B_query}' 간의 상호작용 정보가 없습니다."
    
    return risk_label, "\n\n".join(reasons)


# [V19] 오타 보정(fuzzy) 검색 함수
def get_fuzzy_match(query, choices_set, score_cutoff=65): # [V19] 75점을 65점으로 수정
    """ 
    [V15] 사용자 쿼리와 가장 유사한 약물명을 찾습니다. 
    'partial_ratio'를 사용하여 짧은 쿼리가 긴 DB 항목의 '일부'와 일치하는지 확인합니다.
    
    [V19] 컷오프를 65점으로 낮춰 '부르펜'(67점) 케이스를 포함합니다.
    """
    if not query or not choices_set:
        return None
        
    try:
        # [V15 수정] 'partial_ratio'를 사용합니다.
        best_match = process.extractOne(query.lower(), choices_set, scorer=fuzz.partial_ratio) 
        
        if best_match and best_match[1] >= score_cutoff: # [V19] 기준점이 65점으로 낮아짐
            return best_match[0] # 유사도가 65점 이상인 약물명 반환
            
    except Exception as e:
        print(f"DEBUG: Fuzzy matching error - {e}")
        
    return None # 적절한 매칭을 찾지 못함


# 3. Streamlit 웹사이트 UI 코드
# [V14] V11 (기본 UI) + V13/V14 (버그 수정)
st.title("💊 약물 상호작용 챗봇 (V17)")
st.caption("캡스톤 프로젝트: 약물 상호작용 정보 검색 챗봇 (성분 검색 수정)")

if "messages" not in st.session_state:
    st.session_state.messages = []

if not st.session_state.messages:
    st.session_state.messages.append(
        {"role": "assistant", "content": "안녕하세요! 약물 상호작용 챗봇입니다.\n\n[질문 예시]\n1. 타이레놀 성분이 뭐야?\n2. 타이레놀과 아스피린을 같이 복용해도 돼?"}
    )

# [V11] 채팅 기록 표시 (기본 UI)
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if df is None:
    st.error("데이터 로드 실패로 챗봇을 실행할 수 없습니다.")
else:
    if prompt := st.chat_input("질문을 입력하세요... (예: 타이레놀(500mg)과 아스피린)"):
        
        # [V11] 사용자 질문을 채팅 기록에 추가
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # [V11] 어시스턴트 응답 (마크다운으로 생성)
        reply_message = ""
        
        # --- [V17] '성분' 질문 정규식 수정 ---
        match_component = re.match(r'(.+?)\s*(?:주)?성분[이]?[ ]?(?:뭐야|알려줘)?\??$', prompt.strip())
        
        # --- [V11] 1. 성분 질문 처리 (V10 오타보정 로직 포함) ---
        if match_component:
            drug_name = match_component.group(1).strip()
            
            if drug_name:
                with st.spinner(f"🔄 '{drug_name}' 성분 검색 중..."):
                    drugs_set = find_drug_info_optimized(df, drug_name)
                
                if drugs_set is not None:
                    components = {str(d) for d in drugs_set if pd.notna(d) and str(d).strip() and len(str(d)) > 1 and str(d) != 'nan'}
                    if components:
                        reply_message = f"**✅ '{drug_name}'의 관련 성분/제품명**\n\n* {', '.join(components)}"
                    else:
                        reply_message = f"ℹ️ '{drug_name}'을(를) 찾았으나, 연관된 성분 정보를 추출하지 못했습니다."
                else:
                    # [V10] 오타 보정 로직
                    suggestion = get_fuzzy_match(drug_name, all_drug_names_set)
                    if suggestion:
                        reply_message = f"ℹ️ '{drug_name}'(을)를 찾을 수 없습니다.\n\n혹시 **'{suggestion}'**(으)로 검색하시겠어요?"
                    else:
                        reply_message = f"❌ '{drug_name}'에 대한 정보를 상호작용 데이터베이스에서 찾을 수 없습니다."
            else:
                reply_message = "❌ 어떤 약물의 성분을 알고 싶으신가요? 약물 이름을 입력해주세요."
        
        # --- [V11] 2. 상호작용 질문 처리 (V10 오타보정 로직 포함) ---
        else:
            # (V11과 동일한 정규식)
            match_interaction = re.match(r'(.+?)\s*(?:이랑|랑|과|와|하고)\s+(.+?)(?:를|을)?\s+(?:같이|함께)\s+(?:복용해도|먹어도)\s+(?:돼|되나|될까|되나요)\??', prompt.strip())
            if not match_interaction:
                 match_interaction_sep = re.match(r'^\s*(.+?)\s*(?:이랑|랑|과|와|하고)\s+(.+?)\s*$', prompt.strip())
                 if match_interaction_sep:
                       match_interaction = match_interaction_sep
            if not match_interaction:
                 match_interaction_simple = re.match(r'^\s*([^\s].*?)\s+([^\s].*?)\s*$', prompt.strip())
                 if match_interaction_simple:
                       match_interaction = match_interaction_simple

            if match_interaction:
                drug_A_query = match_interaction.group(1).strip()
                drug_B_query = match_interaction.group(2).strip()
                
                if drug_A_query and drug_B_query:
                    # [V14] 모든 버그가 수정된 함수를 호출합니다.
                    with st.spinner(f"🔄 '{drug_A_query}'와 '{drug_B_query}' 상호작용 검색 중..."):
                        risk, explanation = check_drug_interaction_flexible(df, drug_A_query, drug_B_query)
                    
                    if risk == "정보 없음":
                        # [V10] 오타 보정 로직
                        suggestion_A = None
                        suggestion_B = None
                        if f"'{drug_A_query}'" in explanation:
                            suggestion_A = get_fuzzy_match(drug_A_query, all_drug_names_set)
                        if f"'{drug_B_query}'" in explanation:
                            suggestion_B = get_fuzzy_match(drug_B_query, all_drug_names_set)
                        
                        suggestion_text = ""
                        if suggestion_A:
                            suggestion_text += f"\n\n* '{drug_A_query}'(은)는 혹시 **'{suggestion_A}'**(이)인가요?"
                        if suggestion_B:
                            suggestion_text += f"\n\n* '{drug_B_query}'(은)는 혹시 **'{suggestion_B}'**(이)인가요?"

                        if suggestion_text:
                            reply_message = f"**⚠️ 약물 정보 없음 (오타 제안)**\n\n{explanation}{suggestion_text}"
                        else:
                            reply_message = f"**❌ 약물 정보 없음**\n\n{explanation}"
                            
                    elif risk == "안전":
                        reply_message = f"**✅ 약물 상호작용 위험도: 안전**\n\n**💡 상세 정보:**\n\n'{drug_A_query}'와 '{drug_B_query}' 간의 상호작용 정보가 없습니다."
                    
                    else: # 위험, 주의, 정보 확인
                        details = f"**💡 상세 정보:**\n\n{explanation}"
                        if risk == "위험":
                            reply_message = f"**🚨 약물 상호작용 위험도: {risk}**\n\n{details}"
                        elif risk == "주의":
                            reply_message = f"**⚠️ 약물 상호작용 위험도: {risk}**\n\n{details}"
                        else: # "정보 확인"
                            reply_message = f"**ℹ️ 약물 상호작용 위험도: {risk}**\n\n{details}"
                else:
                    reply_message = "❌ 두 약물 이름을 정확히 입력해주세요. 예: (A)약물과 (B)약물을 같이 복용해도 돼?"
            
            # --- [V11] 3. 이해할 수 없는 질문 ---
            else:
                reply_message = "🤔 죄송합니다. 질문 형식을 이해하지 못했습니다.\n\n**[질문 예시]**\n* 타이레놀과 아스피린\n* 타이레놀 성분이 뭐야?"

        # [V11] 최종 답변을 채팅 기록에 저장
        st.session_state.messages.append({"role": "assistant", "content": reply_message})
        with st.chat_message("assistant"):
            st.markdown(reply_message)
            
        # [V11] st.rerun()을 사용하지 않아 답변이 유지됩니다.