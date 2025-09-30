import pandas as pd
import re
from itertools import combinations

# --- 1. 데이터 로드 및 전처리 ---
try:
    # CSV 파일 경로를 확인해주세요.
    # 예: 'C:/Users/MyUser/Desktop/druglist.csv'
    # 코드 파일과 CSV 파일이 같은 폴더에 있다면 파일명만 적어도 됩니다.
    CSV_FILE_PATH = 'druglist.csv' 
    df = pd.read_csv(CSV_FILE_PATH)
    
    # 상세정보와 비고 컬럼의 빈 값을 채워줍니다.
    df['상세정보'] = df['상세정보'].fillna('상호작용 정보 없음')
    df['비고'] = df['비고'].fillna('') # 비고는 내용이 없을 수 있으므로 빈 문자열로 처리
    print("✅ 약물 상호작용 데이터 로드 성공!")

except FileNotFoundError:
    print(f"❌ '{CSV_FILE_PATH}' 파일을 찾을 수 없습니다. 파일 경로를 다시 확인해주세요.")
    exit()


# --- 2. 유연한 약물 정보 검색 및 사용자 확인 기능 ---

def find_potential_drugs(df, query):
    """
    사용자 쿼리(일부만 입력해도)와 일치하는 후보 약물 제품명 목록을 반환합니다.
    """
    # 쿼리 전처리: 괄호, 용량, 제형 등 불필요한 정보 제거
    cleaned_query = re.sub(r'\(.*?\)|\[.*?\]|\d+m?g?l?|주사제|정제|약|캡슐', '', query).strip()
    if not cleaned_query:
        return []

    # '제품명' 컬럼에서 부분 일치하는 모든 데이터 검색
    mask = (df['제품명A'].str.contains(cleaned_query, na=False)) | \
           (df['제품명B'].str.contains(cleaned_query, na=False))
    
    results = df[mask]
    if results.empty:
        return []

    # 검색된 결과에서 해당 쿼리가 포함된 제품명을 모두 수집 (중복 제거)
    potential_products = set()
    for _, row in results.iterrows():
        if cleaned_query in str(row['제품명A']):
            potential_products.add(row['제품명A'])
        if cleaned_query in str(row['제품명B']):
            potential_products.add(row['제품명B'])
            
    return sorted(list(potential_products)) # 가나다순으로 정렬하여 반환

def confirm_drug_from_list(query, potential_drugs):
    """
    후보 약물 목록을 사용자에게 제시하고 선택을 받아 확정된 약물명을 반환합니다.
    """
    if not potential_drugs:
        print(f"❌ '{query}'에 대한 약물 정보를 찾을 수 없습니다.")
        return None
    
    if len(potential_drugs) == 1:
        # 후보가 하나일 경우, 바로 확인 질문
        confirmed_drug = potential_drugs[0]
        while True:
            user_confirm = input(f"👉 입력하신 '{query}'(이)란 '{confirmed_drug}'이(가) 맞나요? (y/n): ").lower()
            if user_confirm == 'y':
                return confirmed_drug
            elif user_confirm == 'n':
                print("ℹ️ 다른 약물 이름을 입력해주세요.")
                return None
            else:
                print("❌ y 또는 n으로만 입력해주세요.")
    else:
        # 후보가 여러 개일 경우, 목록을 보여주고 선택하게 함
        print(f"'❓{query}'에 해당하는 약물이 여러 개 있습니다. 어떤 약물을 찾으시나요?")
        for i, drug_name in enumerate(potential_drugs, 1):
            print(f"  {i}. {drug_name}")
        
        while True:
            try:
                choice = int(input("👉 번호를 선택하세요: "))
                if 1 <= choice <= len(potential_drugs):
                    return potential_drugs[choice - 1]
                else:
                    print("❌ 목록에 있는 번호를 입력해주세요.")
            except ValueError:
                print("❌ 숫자로 번호를 입력해주세요.")


# --- 3. 약물 상호작용 평가 함수 (개선된 버전) ---

def check_interactions(df, drug_list):
    """
    확정된 약물 목록 내 모든 조합에 대해 상호작용 위험도를 평가합니다.
    """
    if len(drug_list) < 2:
        return # 약물이 2개 미만이면 검사할 필요 없음

    all_interactions = []
    
    # 약물 목록에서 가능한 모든 2개 조합 생성
    for drug_A, drug_B in combinations(drug_list, 2):
        # 데이터프레임에서 두 약물 조합 검색 (A-B, B-A 순서 모두 고려)
        interaction_rows = df[
            ((df['제품명A'] == drug_A) & (df['제품명B'] == drug_B)) |
            ((df['제품명A'] == drug_B) & (df['제품명B'] == drug_A))
        ]
        
        if not interaction_rows.empty:
            all_interactions.append({
                "pair": (drug_A, drug_B),
                "details": interaction_rows
            })

    if not all_interactions:
        print("\n**✅ 분석 결과: 입력하신 약물들 간에 고시된 병용금기/주의 정보가 없습니다.**")
        return

    print("\n**⚠️ 약물 상호작용 분석 결과:**")
    
    # 키워드 기반 위험도 판단 로직
    dangerous_keywords = ["금기", "독성", "치명적", "심각한", "증가", "상승", "연장"]
    caution_keywords = ["주의", "모니터링", "감소", "저하", "제한적"]

    for interaction in all_interactions:
        pair = interaction['pair']
        details_df = interaction['details']
        
        # 상세정보와 비고를 합쳐서 분석
        full_info = details_df['상세정보'].iloc[0] + " " + details_df['비고'].iloc[0]
        
        risk_level = "정보 확인" # 기본 등급
        if any(keyword in full_info for keyword in dangerous_keywords):
            risk_level = "🚨 위험"
        elif any(keyword in full_info for keyword in caution_keywords):
            risk_level = "🟡 주의"

        print(f"\n--- {pair[0]} ↔️ {pair[1]} ---")
        print(f"**등급: {risk_level}**")
        print(f"**상세 정보:** {details_df['상세정보'].iloc[0]}")
        if pd.notna(details_df['비고'].iloc[0]) and details_df['비고'].iloc[0]:
             print(f"**참고 사항(조건):** {details_df['비고'].iloc[0]}")


# --- 4. 챗봇 인터페이스 (개선된 버전) ---

def start_chatbot():
    """콘솔에서 사용자와 상호작용하는 챗봇을 시작합니다."""
    print("\n안녕하세요! 약물 상호작용 챗봇입니다. 💊")
    print("궁금한 약물들을 쉼표(,)로 구분하여 입력해주세요.")
    print("예시: 아스피린, 이부프로펜 같이 복용해도 돼?")
    print("종료하려면 '종료' 또는 'exit'을 입력하세요.")

    while True:
        user_input = input("\n👉 질문을 입력하세요: ")
        if user_input.lower() in ['종료', 'exit']:
            print("챗봇을 종료합니다. 감사합니다! 🧑‍⚕️")
            break

        # '같이 복용해도 돼' 와 같은 키워드로 상호작용 질문 분석
        if '같이' in user_input and ('복용' in user_input or '먹어' in user_input):
            # 약물 이름만 추출
            raw_drugs = re.sub(r'같이.*', '', user_input).strip()
            drug_queries = [drug.strip() for drug in raw_drugs.split(',')]
            
            if len(drug_queries) < 2:
                print("❌ 상호작용을 보려면 약물을 2개 이상 입력해주세요. (쉼표로 구분)")
                continue

            # 각 약물명 확정 프로세스
            confirmed_drugs = []
            for query in drug_queries:
                potential_drugs = find_potential_drugs(df, query)
                confirmed_drug = confirm_drug_from_list(query, potential_drugs)
                if confirmed_drug:
                    confirmed_drugs.append(confirmed_drug)
                else:
                    # 하나라도 약물 확정이 안되면 상호작용 검사를 중단
                    break
            
            # 모든 약물이 성공적으로 확정되었는지 확인
            if len(confirmed_drugs) == len(drug_queries):
                # 중복 제거 후 상호작용 검사
                check_interactions(df, list(set(confirmed_drugs)))

        else:
            print("🤔 죄송합니다. 질문 형식을 이해하지 못했습니다.")
            print("예시: '약물A, 약물B, 약물C 같이 먹어도 돼?' 와 같이 질문해주세요.")

# --- 챗봇 시작 ---
if __name__ == "__main__":
    start_chatbot()
