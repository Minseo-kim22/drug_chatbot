# drug_functions_251118.py

import pandas as pd
import re
import streamlit as st # @st.cache_data 데코레이터 때문에 필요합니다.

# --------------------------------------------------------------------------------------------------
# 1. 데이터 로드 (Streamlit 캐싱 데코레이터 유지)
# --------------------------------------------------------------------------------------------------
@st.cache_data
def load_data():
    """druglist.csv 파일을 로드하고 캐시에 저장합니다."""
    file_path = r'druglist.csv' 
    try:    
        df = pd.read_csv(file_path, encoding='utf-8', dtype=str) 
        df['상세정보'] = df['상세정보'].fillna('상호작용 정보 없음')
    
        # 소문자 컬럼 미리 생성
        df['제품명A_lower'] = df['제품명A'].str.lower()
        df['성분명A_lower'] = df['제품명A'].str.lower() # 성분명A로 수정
        df['성분명A_lower'] = df['성분명A'].str.lower() # 성분명A로 수정
        df['제품명B_lower'] = df['제품명B'].str.lower()
        df['성분명B_lower'] = df['성분명B'].str.lower()
        print("✅ (functions) 약물 상호작용 데이터 로드 성공!")
        return df
    except FileNotFoundError:
        st.error(f"❌ '{file_path}' 파일을 찾을 수 없습니다.")
        return None
    except Exception as e:
        # Streamlit UI 없이 실행될 경우를 대비해 print도 추가
        print(f"❌ 파일 로드 중 오류 발생: {e}")
        return None

# --------------------------------------------------------------------------------------------------
# 2. 약물 검색 및 상호작용 함수들
# --------------------------------------------------------------------------------------------------

def clean_query(query):
    """검색어 정제 함수: 괄호, 특정 제형 단어를 제거하고 소문자로 변환합니다."""
    if not query:
        return ""
    # bot_v9.11.py의 clean_query 함수 사용
    cleaned = re.sub(r'\(.*?\)|\[.*?\]|(주사제|정제|캡슐|시럽)$', '', str(query)).strip().lower() 
    return cleaned

def find_drug_info_optimized(df, query):
    """[V6] (상호작용 검색용) 쿼리한 약물 '자체'의 제품명/성분명만 효율적으로 검색합니다."""
    # (내용 유지)
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
    
def get_product_list(df, drug_query):
    """사용자 쿼리로부터 관련 제품명 목록을 추출합니다."""
    # (내용 유지: 숫자/단위 제거 전처리 로직 수정된 버전)
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

        # NOTE: 이 부분은 app.py에서 df를 로드한 후 사용됩니다.
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

def get_main_component(df, drug_query):
    """사용자 쿼리로부터 주성분을 정확히 추출합니다. (단일 제품 선택 시 사용)"""
    # (내용 유지: 숫자/단위 제거 전처리 로직 수정된 버전)
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

def check_drug_interaction_flexible(df, drug_A_query, drug_B_query):
    """ [V8] 상호작용 검색 로직 """
    # (내용 유지)
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

    # ... (중략: 상호작용 검색 및 위험도 판단 로직은 그대로 유지) ...
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