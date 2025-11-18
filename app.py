import streamlit as st
import pandas as pd
import re
import sqlite3
import gdown
import os
from itertools import combinations # [추가됨] 짝꿍 만들기용 도구

# 1. 데이터 로드
@st.cache_resource
def load_data():
    """druglist.db 파일을 다운로드하고 연결합니다."""
    file_path = r'druglist.db'
    try:
        if not os.path.exists(file_path):
            GDRIVE_FILE_ID = '11B6_WtJWs5AIfCAbN67F2sqaAkWCyJob' 
            st.info(f"'{file_path}' 파일이 없어 Google Drive에서 다운로드합니다... (시간이 걸릴 수 있습니다)")
            gdown.download(id=GDRIVE_FILE_ID, output=file_path, quiet=False, fuzzy=True)
            st.info("데이터베이스 다운로드 완료!")

        conn = sqlite3.connect(file_path, check_same_thread=False)
        
        def normalize_text(text):
            if text is None: return None
            return re.sub(r'[\s\(\)\[\]_/-]|주사제|정제|정|약|캡슐|시럽', '', str(text)).strip().lower()
        conn.create_function("normalize", 1, normalize_text)
        
        print("✅ (Streamlit) 약물 데이터베이스 로드 성공!")
        return conn
    except Exception as e:
        st.error(f"❌ 데이터베이스 로드 실패: {e}")
        return None

conn = load_data()

# 2. 검색 함수들
def find_drug_info(db_conn, query):
    cleaned_query = re.sub(r'[\s\(\)\[\]_/-]|주사제|정제|정|약|캡슐|시럽', '', query).strip().lower()
    if len(cleaned_query) < 2: return pd.DataFrame() 
    
    try:
        search_pattern = f"%{cleaned_query}%"
        sql_query = """
        SELECT DISTINCT 제품명A, 성분명A, 제품명B, 성분명B 
        FROM druglist 
        WHERE normalize(제품명A) LIKE ? OR normalize(성분명A) LIKE ? OR normalize(제품명B) LIKE ? OR normalize(성분명B) LIKE ?
        """
        return pd.read_sql(sql_query, db_conn, params=(search_pattern, search_pattern, search_pattern, search_pattern))
    except Exception as e:
        print(f"DEBUG: find_drug_info 오류 - {e}")
        return pd.DataFrame()

def check_drug_interaction_flexible(db_conn, drug_A_query, drug_B_query):
    cleaned_A = re.sub(r'[\s\(\)\[\]_/-]|주사제|정제|정|약|캡슐|시럽', '', drug_A_query).strip().lower()
    cleaned_B = re.sub(r'[\s\(\)\[\]_/-]|주사제|정제|정|약|캡슐|시럽', '', drug_B_query).strip().lower()

    if len(cleaned_A) < 2 or len(cleaned_B) < 2:
        return "정보 없음", "약물 이름이 너무 짧습니다. (2글자 이상 입력)"

    pattern_A = f"%{cleaned_A}%"
    pattern_B = f"%{cleaned_B}%"

    try:
        query_a_cols = "(normalize(제품명A) LIKE ? OR normalize(성분명A) LIKE ?)"
        query_b_cols = "(normalize(제품명B) LIKE ? OR normalize(성분명B) LIKE ?)"
        
        sql_query = f"""
        SELECT DISTINCT 제품명A, 제품명B, 상세정보 
        FROM druglist 
        WHERE 
            ({query_a_cols} AND {query_b_cols}) 
            OR 
            ({query_b_cols.replace('B', 'A')} AND {query_a_cols.replace('A', 'B')})
        """
        interactions = pd.read_sql(sql_query, db_conn, params=(pattern_A, pattern_A, pattern_B, pattern_B, pattern_B, pattern_B, pattern_A, pattern_A))

    except Exception as e:
        return "오류", "데이터베이스 검색 중 오류가 발생했습니다."

    if interactions.empty:
        return "안전", f"상호작용 정보 없음"

    unique_products = set(interactions['제품명A']).union(set(interactions['제품명B']))
    if len(unique_products) > 2:
        risk_level = "정보 확인" 
        warning_msg = f"🔍 **'{drug_A_query}' & '{drug_B_query}' 결과가 너무 많습니다.**\n\n해당하는 제품/용량이 여러 개 있습니다. 약물 이름을 더 정확하게 입력해주세요.\n(예: '구주염산페치딘주 50mg')"
        return risk_level, warning_msg

    interactions = interactions.drop_duplicates(subset=['상세정보'])
    
    dangerous_keywords = ["사망", "흥분", "정신착란", "금기", "투여 금지", "독성 증가", "치명적인", "심각한", "유산 산성증", "고칼륨혈증", "심실성 부정맥", "위험성 증가", "위험 증가", "심장 부정맥", "QT간격 연장 위험 증가", "QT연장", "심부정맥", "중대한", "심장 모니터링", "병용금기", "Torsade de pointes 위험 증가", "위험이 증가함", "약물이상반응 발생 위험", "독성", "허혈", "혈관경련", ]
    caution_keywords = ["치료 효과가 제한적", "중증의 위장관계 이상반응", "Alfuzosin 혈중농도 증가", "양쪽 약물 모두 혈장농도 상승 가능", "Amiodarone 혈중농도 증가", "혈중농도 증가", "횡문근융해와 같은 중증의 근육이상 보고",  "혈장 농도 증가", "Finerenone 혈중농도의 현저한 증가가 예상됨"]
    
    risk_level = "안전"
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
    
    return risk_level, "\n\n".join(reasons)

# --- 3. UI 및 로직 ---
st.title("💊 약물 상호작용 챗봇")
st.caption("캡스톤 프로젝트: 약물 상호작용 정보 검색 챗봇")

# 상태 변수 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []
if "search_mode" not in st.session_state:
    st.session_state.search_mode = None 
if "selection_mode" not in st.session_state:
    st.session_state.selection_mode = False
if "selection_options" not in st.session_state:
    st.session_state.selection_options = []

# 모드 선택 버튼
col1, col2 = st.columns(2)
with col1:
    if st.button("💊 성분 정보 검색", use_container_width=True):
        st.session_state.search_mode = "ingredient"
        st.session_state.messages = [{"role": "assistant", "content": "💊 **성분 정보 검색** 모드입니다.\n\n궁금한 약물 이름을 입력해주세요. (예: 타이레놀)"}]
        st.session_state.selection_mode = False
        st.rerun()

with col2:
    if st.button("⚠️ 상호작용 분석 (다중)", use_container_width=True):
        st.session_state.search_mode = "interaction"
        st.session_state.messages = [{"role": "assistant", "content": "⚠️ **상호작용 분석** 모드입니다.\n\n확인하고 싶은 약물들을 **쉼표(,)**나 **띄어쓰기**로 구분해서 모두 입력해주세요.\n(예: 타이레놀, 아스피린, 겔포스)"}]
        st.session_state.selection_mode = False
        st.rerun()

# 이전 대화 기록 표시
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# [성분 검색] 선택지가 있을 경우 버튼 표시
if st.session_state.selection_mode and st.session_state.search_mode == "ingredient":
    st.write("👇 **원하는 제품을 선택해주세요:**")
    cols = st.columns(min(len(st.session_state.selection_options), 3))
    for i, option in enumerate(st.session_state.selection_options):
        if st.button(option, key=f"btn_{i}"):
            st.session_state.messages.append({"role": "user", "content": f"{option} 선택"})
            
            results = find_drug_info(conn, option)
            components = set()
            # [수정됨] 선택한 약물(option)과 정확히 일치하는 성분만 추출하는 로직
            target_clean = re.sub(r'[\s\(\)\[\]_/-]|주사제|정제|정|약|캡슐|시럽', '', option).strip().lower()
            
            for _, row in results.iterrows():
                prod_A_clean = re.sub(r'[\s\(\)\[\]_/-]|주사제|정제|정|약|캡슐|시럽', '', str(row['제품명A'])).strip().lower()
                prod_B_clean = re.sub(r'[\s\(\)\[\]_/-]|주사제|정제|정|약|캡슐|시럽', '', str(row['제품명B'])).strip().lower()
                
                # A열에 해당 약물이 있으면 A성분만 가져옴
                if target_clean in prod_A_clean:
                    if pd.notna(row['성분명A']): components.add(row['성분명A'])
                
                # B열에 해당 약물이 있으면 B성분만 가져옴
                if target_clean in prod_B_clean:
                    if pd.notna(row['성분명B']): components.add(row['성분명B'])
            
            components = {str(d) for d in components if pd.notna(d) and len(str(d)) > 1 and str(d) != 'nan'}
            
            if components:
                final_response = f"✅ **'{option}'**의 성분은 다음과 같습니다:\n\n* {', '.join(components)}"
            else:
                final_response = f"ℹ️ '{option}'을(를) 선택하셨으나, 성분 정보를 찾을 수 없습니다."

            st.session_state.messages.append({"role": "assistant", "content": final_response})
            st.session_state.selection_mode = False
            st.rerun()

# 입력창
if st.session_state.search_mode:
    placeholder_text = "약물 이름을 입력하세요..." if st.session_state.search_mode == "ingredient" else "약물들을 입력하세요 (예: A, B, C)"
    
    if prompt := st.chat_input(placeholder_text):
        if conn is None:
            st.error("데이터베이스 연결 실패")
            st.stop()

        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        reply_message = ""

        # --- 1. 성분 검색 모드 (기존 로직 유지) ---
        if st.session_state.search_mode == "ingredient":
            drug_name = prompt.strip()
            results = find_drug_info(conn, drug_name)
            
            if not results.empty:
                found_products = set()
                target_clean = re.sub(r'[\s\(\)\[\]_/-]|주사제|정제|정|약|캡슐|시럽', '', drug_name).strip().lower()
                
                for _, row in results.iterrows():
                    val_a = str(row['제품명A']).lower()
                    clean_a = re.sub(r'[\s\(\)\[\]_/-]|주사제|정제|정|약|캡슐|시럽', '', val_a)
                    if target_clean in clean_a and pd.notna(row['제품명A']): found_products.add(row['제품명A'])
                    
                    val_b = str(row['제품명B']).lower()
                    clean_b = re.sub(r'[\s\(\)\[\]_/-]|주사제|정제|정|약|캡슐|시럽', '', val_b)
                    if target_clean in clean_b and pd.notna(row['제품명B']): found_products.add(row['제품명B'])
                
                found_products = sorted(list(found_products))

                if len(found_products) > 1:
                    reply_message = f"🔍 **'{drug_name}'** 관련 제품이 **{len(found_products)}개** 발견되었습니다.\n아래에서 원하시는 제품을 선택해주세요."
                    st.session_state.selection_mode = True
                    st.session_state.selection_options = found_products
                elif len(found_products) == 1:
                    product = found_products[0]
                    components = set()
                    # [수정됨] 1개일 때도 정확한 컬럼 매칭 로직 적용
                    t_pat_clean = re.sub(r'[\s\(\)\[\]_/-]|주사제|정제|정|약|캡슐|시럽', '', product).strip().lower()
                    for _, row in results.iterrows():
                        prod_A_clean = re.sub(r'[\s\(\)\[\]_/-]|주사제|정제|정|약|캡슐|시럽', '', str(row['제품명A'])).strip().lower()
                        prod_B_clean = re.sub(r'[\s\(\)\[\]_/-]|주사제|정제|정|약|캡슐|시럽', '', str(row['제품명B'])).strip().lower()
                        
                        if t_pat_clean in prod_A_clean and pd.notna(row['성분명A']): components.add(row['성분명A'])
                        if t_pat_clean in prod_B_clean and pd.notna(row['성분명B']): components.add(row['성분명B'])
                    
                    components = {str(d) for d in components if pd.notna(d) and len(str(d)) > 1 and str(d) != 'nan'}
                    reply_message = f"✅ **'{product}'**의 성분은 다음과 같습니다:\n\n* {', '.join(components)}"
                else:
                    reply_message = f"ℹ️ '{drug_name}'에 대한 정확한 제품 정보를 찾을 수 없습니다."
            else:
                reply_message = f"❌ '{drug_name}' 정보를 찾을 수 없습니다."

        # --- 2. 상호작용 분석 모드 (다중 약물 지원) ---
        elif st.session_state.search_mode == "interaction":
            # 쉼표, 공백, '과', '와' 등으로 분리
            parts = re.split(r'[,\s]+|과|와|랑|하고', prompt)
            parts = [p.strip() for p in parts if p.strip()] # 빈 문자열 제거
            
            if len(parts) >= 2:
                reply_buffer = []
                found_interaction = False
                
                with st.spinner(f"🔄 {len(parts)}개 약물의 상호작용을 분석 중..."):
                    # [핵심] combinations를 사용해 모든 가능한 짝꿍을 만듦
                    for drug_A, drug_B in combinations(parts, 2):
                        risk, explanation = check_drug_interaction_flexible(conn, drug_A, drug_B)
                        
                        # '정보 없음'이나 '안전'은 생략하고 문제가 있는 것만 모으기 (너무 길어지는 것 방지)
                        if risk == "위험":
                            reply_buffer.append(f"🚨 **[{drug_A} ↔ {drug_B}] 위험!**\n{explanation}")
                            found_interaction = True
                        elif risk == "주의":
                            reply_buffer.append(f"⚠️ **[{drug_A} ↔ {drug_B}] 주의**\n{explanation}")
                            found_interaction = True
                        elif risk == "정보 확인" and "검색 결과가 너무 많습니다" in explanation:
                             # 모호성 경고는 중요하므로 표시
                            reply_buffer.append(f"{explanation}")
                            found_interaction = True

                if found_interaction:
                    reply_message = "### ⚠️ 상호작용 분석 결과\n\n" + "\n\n---\n\n".join(reply_buffer)
                else:
                    reply_message = f"✅ 입력하신 **{len(parts)}개 약물** 간에 발견된 위험/주의 상호작용이 없습니다."
            else:
                reply_message = "❌ **두 개 이상**의 약물 이름을 입력해주세요."

        st.session_state.messages.append({"role": "assistant", "content": reply_message})
        with st.chat_message("assistant"):
            st.markdown(reply_message)
        
        if st.session_state.selection_mode:
            st.rerun()

else:
    if not st.session_state.messages:
        st.info("👆 위의 버튼을 눌러 원하는 기능을 선택해주세요!")