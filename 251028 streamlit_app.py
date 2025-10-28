import streamlit as st
import pandas as pd
import re

# 1. 데이터 로드 (페이지가 로드될 때 한 번만 실행됨)
# @st.cache_data : 데이터를 캐시에 저장해서 매번 다시 읽지 않도록 함
@st.cache_data
def load_data():
    file_path = r'druglist.csv'
    try:
        df = pd.read_csv(file_path, encoding='utf-8')
        df['상세정보'] = df['상세정보'].fillna('상호작용 정보 없음')
        print("✅ (Streamlit) 약물 상호작용 데이터 로드 성공!")
        return df
    except FileNotFoundError:
        st.error(f"❌ '{file_path}' 파일을 찾을 수 없습니다. .py 파일과 같은 폴더에 있는지 확인해주세요.")
        return None
    except Exception as e:
        st.error(f"❌ 파일 로드 중 오류 발생: {e}")
        return None

# 데이터 로드 실행
df = load_data()

# 2. 기존의 약물 검색 및 상호작용 함수들 (그대로 복사)
# (find_drug_info, check_drug_interaction_flexible 함수...)
# (이 함수들은 Flask, Streamlit 상관없이 동일하게 작동합니다)

def find_drug_info(df, query):
    """사용자 쿼리로부터 약물 관련 정보를 유연하게 검색합니다."""
    # 쿼리 전처리: 괄호, 용량 정보, 제형 관련 단어 제거
    cleaned_query = re.sub(r'\(.*?\)|\[.*?\]|\d+m?g?l?|주사제|정제|정|약|캡슐|시럽', '', query).strip()
    if not cleaned_query:
        return pd.DataFrame() # 빈 쿼리 처리

    try:
        search_pattern = re.escape(cleaned_query)
        search_results = df[
            df['제품명A'].str.contains(search_pattern, na=False, case=False) |
            df['성분명A'].str.contains(search_pattern, na=False, case=False) |
            df['제품명B'].str.contains(search_pattern, na=False, case=False) |
            df['성분명B'].str.contains(search_pattern, na=False, case=False)
        ]
    except Exception as e:
        print(f"DEBUG: find_drug_info에서 오류 발생 - {e}")
        return pd.DataFrame()
    return search_results

def check_drug_interaction_flexible(df, drug_A_query, drug_B_query):
    """두 약물 쿼리에 대해 상호작용 위험도를 평가합니다."""
    
    results_A = find_drug_info(df, drug_A_query)
    results_B = find_drug_info(df, drug_B_query)

    if results_A.empty:
        return "정보 없음", f"'{drug_A_query}'에 대한 약물 정보를 찾을 수 없습니다."
    if results_B.empty:
        return "정보 없음", f"'{drug_B_query}'에 대한 약물 정보를 찾을 수 없습니다."

    drugs_A = set(results_A['제품명A']).union(set(results_A['성분명A'])).union(set(results_A['제품명B'])).union(set(results_A['성분명B']))
    drugs_B = set(results_B['제품명A']).union(set(results_B['성분명A'])).union(set(results_B['제품명B'])).union(set(results_B['성분명B']))

    drugs_A.discard(pd.NA); drugs_A.discard(None)
    drugs_B.discard(pd.NA); drugs_B.discard(None)
    
    cleaned_A = re.sub(r'\(.*?\)|\[.*?\]|\d+m?g?l?|주사제|정제|정|약|캡슐|시럽', '', drug_A_query).strip()
    cleaned_B = re.sub(r'\(.*?\)|\[.*?\]|\d+m?g?l?|주사제|정제|정|약|캡슐|시럽', '', drug_B_query).strip()
    if cleaned_A: drugs_A.add(cleaned_A)
    if cleaned_B: drugs_B.add(cleaned_B)

    interactions = pd.DataFrame()

    for a in drugs_A:
        for b in drugs_B:
            if a == b or not a or not b: continue 
            
            try:
                a_pattern = re.escape(str(a))
                b_pattern = re.escape(str(b))

                interaction_rows_1 = df[
                    (df['제품명A'].str.contains(a_pattern, na=False, case=False) | df['성분명A'].str.contains(a_pattern, na=False, case=False)) &
                    (df['제품명B'].str.contains(b_pattern, na=False, case=False) | df['성분명B'].str.contains(b_pattern, na=False, case=False))
                ]
                interaction_rows_2 = df[
                    (df['제품명A'].str.contains(b_pattern, na=False, case=False) | df['성분명A'].str.contains(b_pattern, na=False, case=False)) &
                    (df['제품명B'].str.contains(a_pattern, na=False, case=False) | df['성분명B'].str.contains(a_pattern, na=False, case=False))
                ]
                
                if not interaction_rows_1.empty: interactions = pd.concat([interactions, interaction_rows_1])
                if not interaction_rows_2.empty: interactions = pd.concat([interactions, interaction_rows_2])
            except re.error as e:
                print(f"DEBUG: 정규식 오류 발생 (a='{a}', b='{b}') - {e}")
                continue

    if interactions.empty:
        return "안전", f"'{drug_A_query}'와 '{drug_B_query}' 간의 상호작용 정보가 없습니다."

    interactions = interactions.drop_duplicates()

    dangerous_keywords = ["금기", "투여 금지", "독성 증가", "치명적인", "심각한", "유산 산성증", "고칼륨혈증", "심실성 부정맥", "위험성 증가", "위험 증가", "심장 부정맥", "QT간격 연장 위험 증가", "QT연장", "심부정맥", "중대한", "심장 모니터링", "병용금기", "Torsade de pointes 위험 증가", "위험이 증가함", "약물이상반응 발생 위험", "독성", "허혈", "혈관경련", ]
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
        for detail in interactions['상세정보'].unique():
             if str(detail) not in processed_details: 
                reasons.append(f"ℹ️ **정보**: {str(detail)}")
            
    # Streamlit은 \n (줄바꿈)을 자동으로 인식합니다. (Flask처럼 <br>로 바꿀 필요 없음)
    return risk_level, "\n\n".join(reasons) # 답변의 가독성을 위해 줄바꿈 2번

# 3. Streamlit 웹사이트 UI 코드
st.title("💊 약물 상호작용 챗봇")
st.caption("캡스톤 프로젝트: 약물 상호작용 정보 검색 챗봇")

# 채팅 기록을 st.session_state에 저장하여 유지
if "messages" not in st.session_state:
    st.session_state.messages = []

# 채팅 기록이 비어있으면, 초기 안내 메시지 추가
if not st.session_state.messages:
    st.session_state.messages.append(
        {"role": "assistant", "content": "안녕하세요! 약물 상호작용 챗봇입니다.\n\n[질문 예시]\n1. 타이레놀 성분이 뭐야?\n2. 타이레놀과 아스피린을 같이 복용해도 돼?"}
    )

# 이전 채팅 기록을 화면에 표시
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"]) # markdown을 사용해 **위험** 같은 서식 표시

# 데이터 로드에 실패했으면, 챗봇 입력을 막음
if df is None:
    st.error("데이터 로드 실패로 챗봇을 실행할 수 없습니다.")
else:
    # 4. 사용자 채팅 입력 받기
    # st.chat_input이 HTML의 <input> + <button> 역할을 모두 함
    if prompt := st.chat_input("질문을 입력하세요... (예: 타이레놀과 아스피린)"):
        
        # 1. 사용자의 메시지를 채팅 기록에 추가하고 화면에 표시
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 2. 챗봇의 응답 생성 (기존 콘솔/Flask 로직 재활용)
        reply_message = ""
        
        # 성분 질문
        match_component = re.match(r'(.+?)(?: 성분이 뭐야| 성분 뭐야| 성분 알려줘)\??', prompt)
        if match_component:
            drug_name = match_component.group(1).strip('() ').strip()
            if drug_name:
                results = find_drug_info(df, drug_name)
                if not results.empty:
                    components = set()
                    pattern = re.escape(drug_name)
                    for _, row in results.iterrows():
                        if pd.notna(row['제품명A']) and re.search(pattern, row['제품명A'], re.IGNORECASE):
                            if pd.notna(row['성분명A']): components.add(row['성분명A'])
                        if pd.notna(row['제품명B']) and re.search(pattern, row['제품명B'], re.IGNORECASE):
                            if pd.notna(row['성분명B']): components.add(row['성분명B'])
                        if pd.notna(row['성분명A']) and re.search(pattern, row['성분명A'], re.IGNORECASE):
                            components.add(row['성분명A'])
                        if pd.notna(row['성분명B']) and re.search(pattern, row['성분명B'], re.IGNORECASE):
                            components.add(row['성분명B'])

                    if components:
                        reply_message = f"✅ '{drug_name}'의 관련 성분은 다음과 같습니다:\n\n* {', '.join(components)}"
                    else:
                        reply_message = f"ℹ️ '{drug_name}'을(를) 찾았으나, 연관된 성분 정보를 추출하지 못했습니다."
                else:
                    reply_message = f"❌ '{drug_name}' 정보를 찾을 수 없습니다."
            else:
                reply_message = "❌ 어떤 약물의 성분을 알고 싶으신가요? 약물 이름을 입력해주세요."
        
        # 상호작용 질문
        match_interaction = re.match(r'(.+?)(?:과|와|랑|하고)\s+(.+?)(?:를|을)?\s+(?:같이|함께)\s+(?:복용해도|먹어도)\s+(?:돼|되나|될까|되나요)\??', prompt)
        if not match_interaction:
             match_interaction_simple = re.match(r'^\s*([^\s]+)\s+([^\s]+)\s*$', prompt)
             if match_interaction_simple:
                 match_interaction = match_interaction_simple

        if match_interaction and not reply_message:
            drug_A_query = match_interaction.group(1).strip('() ').strip()
            drug_B_query = match_interaction.group(2).strip('() ').strip()
            
            if drug_A_query and drug_B_query:
                with st.spinner(f"🔄 '{drug_A_query}'와 '{drug_B_query}' 상호작용 검색 중..."):
                    risk, explanation = check_drug_interaction_flexible(df, drug_A_query, drug_B_query)
                
                reply_message = f"**💊 약물 상호작용 위험도: {risk}**\n\n**💡 상세 정보:**\n\n{explanation}"
            else:
                reply_message = "❌ 두 약물 이름을 정확히 입력해주세요. 예: (A)약물과 (B)약물을 같이 복용해도 돼?"
        
        # 아무 패턴에도 해당하지 않는 경우
        elif not match_component and not match_interaction:
            reply_message = "🤔 죄송합니다. 질문 형식을 이해하지 못했습니다.\n\n   **[질문 예시]**\n   * 타이레놀과 아스피린\n   * 타이레놀 성분이 뭐야?"

        # 3. 챗봇의 응답을 채팅 기록에 추가하고 화면에 표시
        st.session_state.messages.append({"role": "assistant", "content": reply_message})
        with st.chat_message("assistant"):
            st.markdown(reply_message)
