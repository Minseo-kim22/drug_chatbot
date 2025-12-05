import streamlit as st
import pandas as pd
import re
import os
from itertools import combinations
from fuzzywuzzy import process, fuzz  # [추가] 오타 보정 라이브러리

# --- 1. 데이터 로드 (CSV 읽기 + 오타 보정용 DB 생성) ---
@st.cache_data
def load_data():
    """CSV 파일을 읽고 검색 최적화 및 오타 보정용 리스트를 생성합니다."""
    file_path = 'druglist.csv'
    
    if not os.path.exists(file_path):
        st.error(f"❌ '{file_path}' 파일이 없습니다. 같은 폴더에 넣어주세요.")
        return None, None
        
    try:
        # CSV 읽기 (UTF-8)
        df = pd.read_csv(file_path, encoding='utf-8', dtype=str)
        df['상세정보'] = df['상세정보'].fillna('상호작용 정보 없음')
        
        # [속도 향상] 검색용 'clean' 컬럼 미리 생성
        clean_rule = r'[\s\(\)\[\]_/\-\.]|주사제|정제|정|약|캡슐|시럽|약물'
        for col in ['제품명A', '성분명A', '제품명B', '성분명B']:
            df[col + '_clean'] = df[col].astype(str).str.lower().str.replace(clean_rule, '', regex=True)
            
        # [추가] 오타 보정용 전체 이름 리스트 생성
        combined_names = pd.concat([
            df['제품명A'], df['성분명A'],
            df['제품명B'], df['성분명B']
        ]).dropna().unique()
        
        # 너무 짧은 단어 제외하고 집합 생성
        all_names = {str(name) for name in combined_names if len(str(name)) > 1}
        
        print(f"✅ 데이터 로드 완료! (총 {len(all_names)}개 약물명)")
        return df, all_names

    except Exception as e:
        st.error(f"파일 로드 실패: {e}")
        return None, None

# 데이터 로드 실행
df, all_drug_names = load_data()

# --- 2. 핵심 기능 함수들 ---

def search_products(df, query):
    """약물 이름으로 '제품명' 리스트를 검색합니다."""
    clean_rule = r'[\s\(\)\[\]_/\-\.]|주사제|정제|정|약|캡슐|시럽|약물'
    clean_q = re.sub(clean_rule, '', query).strip().lower()
    
    if len(clean_q) < 2: return []

    try:
        pattern = re.escape(clean_q)
        # clean 컬럼에서 검색
        mask = df['제품명A_clean'].str.contains(pattern) | df['제품명B_clean'].str.contains(pattern)
        
        # 검색된 행에서 제품명 추출
        res_a = df.loc[df['제품명A_clean'].str.contains(pattern), '제품명A']
        res_b = df.loc[df['제품명B_clean'].str.contains(pattern), '제품명B']
        
        # 합치고 정렬
        candidates = sorted(list(set(res_a).union(set(res_b))))
        return candidates
    except:
        return []

def get_ingredients(df, exact_product_name):
    """확정된 제품명의 성분을 가져옵니다."""
    try:
        mask = (df['제품명A'] == exact_product_name) | (df['제품명B'] == exact_product_name)
        rows = df[mask]
        
        ingredients = set()
        for _, r in rows.iterrows():
            if r['제품명A'] == exact_product_name: ingredients.add(r['성분명A'])
            if r['제품명B'] == exact_product_name: ingredients.add(r['성분명B'])
            
        return {x for x in ingredients if pd.notna(x) and x != 'nan'}
    except:
        return set()

def check_interaction(df, prod_A, prod_B):
    """확정된 두 제품 간의 상호작용을 확인합니다."""
    try:
        # 정확한 이름으로 매칭
        mask = ((df['제품명A'] == prod_A) & (df['제품명B'] == prod_B)) | \
               ((df['제품명A'] == prod_B) & (df['제품명B'] == prod_A))
        
        interactions = df[mask]
        
        if interactions.empty:
            return "안전", f"'{prod_A}'와 '{prod_B}' 간의 보고된 상호작용 정보가 없습니다."
        
        # 위험도 분석
        details = interactions['상세정보'].unique()
        danger = ["금기", "투여 금지", "독성 증가", "치명적인", "심각한", "유산 산성증", 
        "고칼륨혈증", "심실성 부정맥", "위험성 증가", "위험 증가", "심장 부정맥", 
        "QT간격 연장 위험 증가", "QT연장", "심부정맥", "중대한", "심장 모니터링", 
        "병용금기", "Torsade de pointes 위험 증가", "위험이 증가함", 
        "약물이상반응 발생 위험", "독성", "허혈", "혈관경련",
        "횡문근융해와 같은 중증의 근육이상 보고"]
        caution = ["치료 효과가 제한적", "중증의 위장관계 이상반응", "Alfuzosin 혈중농도 증가", 
        "양쪽 약물 모두 혈장농도 상승 가능", "Amiodarone 혈중농도 증가", 
        "혈중농도 증가", "혈장 농도 증가", 
        "Finerenone 혈중농도의 현저한 증가가 예상됨"]
        
        risk, msgs = "안전", []
        for d in details:
            d_str = str(d)
            found = False
            for k in danger:
                if k in d_str:
                    risk = "위험"; msgs.append(f"🚨 **위험**: {d_str}"); found=True; break
            if not found:
                for k in caution:
                    if k in d_str:
                        if risk!="위험": risk="주의"
                        msgs.append(f"⚠️ **주의**: {d_str}"); break
        
        if not msgs:
            risk = "정보 확인"
            msgs.append(f"ℹ️ **정보**: {details[0]}")
            
        return risk, "\n\n".join(msgs)
    except:
        return "오류", "분석 중 오류 발생"

# [추가] 오타 보정 함수 (먼저 보낸 코드에서 가져옴)
def get_fuzzy_match(query, choices_set, score_cutoff=65):
    """사용자 입력과 가장 유사한 약물명을 찾습니다."""
    if not query or not choices_set:
        return None
    try:
        # partial_ratio를 사용하여 부분 일치 유사도 검사
        best_match = process.extractOne(query, choices_set, scorer=fuzz.partial_ratio)
        if best_match and best_match[1] >= score_cutoff:
            return best_match[0]
    except Exception as e:
        print(f"DEBUG: Fuzzy matching error - {e}")
    return None


# --- 3. UI 및 상태 관리 ---

st.title("💊 약물 상호작용 챗봇")

# 세션 상태 초기화
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "기능을 선택해주세요."}]
if "mode" not in st.session_state: st.session_state.mode = None
if "queue" not in st.session_state: st.session_state.queue = []       
if "resolved" not in st.session_state: st.session_state.resolved = [] 
if "selecting" not in st.session_state: st.session_state.selecting = False 
if "options" not in st.session_state: st.session_state.options = []

# 상단 버튼
c1, c2 = st.columns(2)
if c1.button("💊 성분 검색", use_container_width=True):
    st.session_state.mode = "ing"
    st.session_state.messages = [{"role": "assistant", "content": "💊 **성분 검색** 모드입니다. 약물 이름을 입력하세요."}]
    st.session_state.selecting = False
    st.session_state.resolved = [] # 초기화
    st.rerun()

if c2.button("⚠️ 상호작용 분석", use_container_width=True):
    st.session_state.mode = "int"
    st.session_state.messages = [{"role": "assistant", "content": "⚠️ **상호작용 분석** 모드입니다. 약물들을 입력해주세요.\n(예: 네시나, 보노렉스, 이지엔)"}]
    st.session_state.selecting = False
    st.session_state.resolved = [] # 초기화
    st.rerun()

# 대화 기록 표시
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]): st.markdown(msg["content"])

# --- 4. 선택지 처리 (사용자 입력 대기) ---
if st.session_state.selecting:
    # 큐의 첫 번째 아이템이 오타였을 수도 있고, 여러 검색 결과일 수도 있음
    target = st.session_state.queue[0]
    
    # 옵션이 하나뿐인 경우 (오타 보정 제안인 경우)
    if len(st.session_state.options) == 1:
        st.info(f"❓ **'{target}'**을(를) 찾을 수 없습니다. 혹시 아래 약물인가요?")
    else:
        st.info(f"👇 **'{target}'** 검색 결과가 여러 개입니다. 선택해주세요:")
    
    cols = st.columns(min(len(st.session_state.options), 3))
    for i, opt in enumerate(st.session_state.options):
        # 버튼을 누르면 해당 옵션으로 확정
        if st.button(opt, key=f"sel_{i}"):
            st.session_state.messages.append({"role": "user", "content": f"✅ {opt} 선택"})
            st.session_state.resolved.append(opt)
            st.session_state.queue.pop(0) # 대기열에서 제거
            st.session_state.selecting = False
            st.rerun()
            
    # [추가] 오타 제안이 마음에 안 들 경우 건너뛰기 버튼
    if st.button("❌ 해당 없음 (제외)", type="secondary"):
         st.session_state.messages.append({"role": "assistant", "content": f"❌ '{target}' 제외됨."})
         st.session_state.queue.pop(0)
         st.session_state.selecting = False
         st.rerun()

# --- 5. 메인 로직 (자동 처리 Loop) ---
# 선택 모드가 아닐 때만 실행
if not st.session_state.selecting:
    
    # (A) 대기열 처리 (검색 -> 1개면 자동확정, 여러개면 선택모드)
    if st.session_state.queue:
        curr = st.session_state.queue[0]
        cands = search_products(df, curr)
        
        if len(cands) > 1:
            st.session_state.options = cands
            st.session_state.selecting = True
            st.rerun()
        elif len(cands) == 1:
            # 1개면 사용자에게 묻지 않고 조용히 확정 후 계속 진행
            st.session_state.resolved.append(cands[0])
            st.session_state.queue.pop(0)
            st.rerun()
        else:
            # [수정] 검색 결과가 0개일 때 -> 오타 보정 시도
            suggestion = get_fuzzy_match(curr, all_drug_names)
            
            if suggestion:
                # 오타일 가능성이 높음 -> 선택 모드로 진입시켜 사용자 확인 유도
                st.session_state.options = [suggestion]
                st.session_state.selecting = True
                st.rerun()
            else:
                # 오타 보정으로도 못 찾음 -> 제외
                st.session_state.messages.append({"role": "assistant", "content": f"❌ '{curr}' 정보를 찾을 수 없어 제외합니다."})
                st.session_state.queue.pop(0)
                st.rerun()

    # (B) 대기열이 비었고, 확정된 약물이 있다면 -> 결과 출력
    elif st.session_state.resolved:
        final_drugs = st.session_state.resolved
        
        # 1. 성분 검색 결과
        if st.session_state.mode == "ing":
            for drug in final_drugs:
                ings = get_ingredients(df, drug)
                msg = f"✅ **'{drug}'** 성분: {', '.join(ings)}" if ings else f"ℹ️ '{drug}' 성분 정보 없음"
                st.session_state.messages.append({"role": "assistant", "content": msg})
        
        # 2. 상호작용 분석 결과 (다중 분석 지원)
        elif st.session_state.mode == "int":
            # 면책 조항 문구 정의 및 추가
            disclaimer = "\n\n---\n\n**🔔 본 정보는 약물 상호작용 데이터베이스를 기반으로 합니다. 최종적인 의학적 판단 및 복약 지도는 반드시 전문가(의사, 약사)와 상의하십시오.**"
            if len(final_drugs) < 2:
                st.session_state.messages.append({"role": "assistant", "content": "❌ 비교할 약물이 부족합니다. (최소 2개 입력)"})
            else:
                # [핵심] N:N 분석 로직
                report = []
                found_risk = False
                
                with st.spinner(f"🔄 {len(final_drugs)}개 약물의 모든 조합을 분석 중..."):
                    # combinations를 사용해 모든 짝꿍(2개 조합)을 검사
                    for a, b in combinations(final_drugs, 2):
                        risk, exp = check_interaction(df, a, b)
                        
                        if risk != "안전":
                            report.append(f"**[{a} ↔ {b}]**\n\n{exp}")
                            found_risk = True
                        # 안전한 경우는 리포트에 포함하지 않음 (스크롤 절약)

                if found_risk:
                    final_msg = "### ⚠️ 분석 결과\n\n" + "\n\n---\n\n".join(report)
                else:
                    final_msg = f"✅ 선택하신 {len(final_drugs)}개 약물 간에 발견된 위험 상호작용이 없습니다."

                # 면책 조항 추가
                st.session_state.messages.append({"role": "assistant", "content": final_msg + disclaimer})
        
        st.session_state.resolved = [] # 결과 출력 후 초기화
        st.rerun()

    # (C) 아무 작업 없을 때 입력창 표시
    elif st.session_state.mode:
        placeholder = "약물 이름 입력..." if st.session_state.mode == "ing" else "약물들 입력 (예: A, B, C)"
        if prompt := st.chat_input(placeholder):
            if df is None: st.error("파일 로드 안됨"); st.stop()
            
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"): st.markdown(prompt)
            
            # 쉼표, 공백, 조사 등으로 분리
            parts = re.split(r'[,\s]+|과|와|랑|하고', prompt)
            parts = [p.strip() for p in parts if p.strip()]
            
            if parts:
                st.session_state.queue = parts
                st.session_state.resolved = []
                st.rerun()
            else:
                 st.warning("입력해주세요.")
