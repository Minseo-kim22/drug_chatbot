import pandas as pd
import re

# 1. 데이터 로드 및 전처리
try:
    df = pd.read_csv(r'C:\Users\NewAdmin\.vscode\drug-interaction-app\druglist_no_combined_use.csv')
    df['상세정보'] = df['상세정보'].fillna('상호작용 정보 없음')
    print("✅ 약물 상호작용 데이터 로드 성공!")
except FileNotFoundError:
    print("❌ 'druglist_no_combined_use' 파일을 찾을 수 없습니다. 파일을 확인해주세요.")
    exit()

try:
    # 절대 경로를 사용하여 파일 로드
    df = pd.read_csv(r'C:\Users\NewAdmin\.vscode\drug-interaction-app\druglist_no_combined_use.csv')
    df['상세정보'] = df['상세정보'].fillna('상호작용 정보 없음')
    print("✅ 약물 상호작용 데이터 로드 성공!")
except FileNotFoundError:
    print(f"❌ '{file_path}. 경로를 다시 확인해주세요.")
    exit()

# 2. 유연한 약물 정보 검색 함수
def find_drug_info(df, query):
    """사용자 쿼리로부터 약물 관련 정보를 유연하게 검색합니다."""
    # 쿼리 전처리: 괄호, 용량 정보 등 불필요한 부분 제거
    cleaned_query = re.sub(r'\(.*?\)|\[.*?\]|\d+m?g?l?|주사제|정제|약|캡슐', '', query).strip()
    if not cleaned_query:
        return pd.DataFrame() # 빈 쿼리 처리

    # 모든 약물 관련 컬럼에서 쿼리 검색
    search_results = df[
        df.apply(lambda row: cleaned_query in str(row['제품명A']) or
                             cleaned_query in str(row['성분명A']) or
                             cleaned_query in str(row['제품명B']) or
                             cleaned_query in str(row['성분명B']), axis=1, result_type='reduce')
    ]
    return search_results

# 3. 약물 상호작용 평가 함수
def check_drug_interaction_flexible(df, drug_A_query, drug_B_query):
    """두 약물 쿼리에 대해 상호작용 위험도를 평가합니다."""
    results_A = find_drug_info(df, drug_A_query)
    results_B = find_drug_info(df, drug_B_query)

    if results_A.empty or results_B.empty:
        return "안전", "두 약물 중 하나 이상의 정보를 찾을 수 없습니다."

    interactions = pd.DataFrame()
    for _, row_A in results_A.iterrows():
        for _, row_B in results_B.iterrows():
            interaction_row = df[((df['제품명A'] == row_A['제품명A']) & (df['제품명B'] == row_B['제품명B'])) |
                                 ((df['제품명A'] == row_B['제품명A']) & (df['제품명B'] == row_A['제품명B']))]
            if not interaction_row.empty:
                interactions = pd.concat([interactions, interaction_row]).drop_duplicates()

    if interactions.empty:
        return "안전", "두 약물 간 상호작용 정보가 없습니다."

    # 위험도 판단 로직
    dangerous_keywords = ["금기", "투여 금지", "독성 증가", "치명적인", "심각한", "유산 산성증", "고칼륨혈증", "심실성 부정맥", "위험성 증가", "위험 증가", "심장 부정맥", "QT간격 연장 위험 증가", "QT연장", "심부정맥", "중대한", "심장 모니터링", "병용금기", "Torsade de pointes 위험 증가", "위험이 증가함", "약물이상반응 발생 위험", "독성", "허혈", "혈관경련", ]
    caution_keywords = ["치료 효과가 제한적", "중증의 위장관계 이상반응", "Alfuzosin 혈중농도 증가", "양쪽 약물 모두 혈장농도 상승 가능", "Amiodarone 혈중농도 증가", "혈중농도 증가", "횡문근융해와 같은 중증의 근육이상 보고",  "혈장 농도 증가", "Finerenone 혈중농도의 현저한 증가가 예상됨"]


    risk_level = "안전"
    reasons = []

    for detail in interactions['상세정보'].unique():
        if any(keyword in str(detail) for keyword in dangerous_keywords):
            risk_level = "위험"
            reasons.append(f"위험: {detail}")
        elif any(keyword in str(detail) for keyword in caution_keywords) and risk_level != "위험":
            risk_level = "주의"
            reasons.append(f"주의: {detail}")

    if not reasons:
        reasons.append("상호작용 정보가 있으나, 심각한 위험은 확인되지 않습니다.")

    return risk_level, "\n".join(reasons)

# 4. 챗봇 인터페이스 (콘솔 기반)
def start_chatbot():
    """콘솔에서 사용자와 상호작용하는 챗봇을 시작합니다."""
    print("안녕하세요! 약물 상호작용 챗봇입니다.")
    print("두 약물을 함께 복용해도 되는지, 혹은 약물의 성분을 알려드릴 수 있습니다.")
    print("예시: (A)약물과 (B)약물을 같이 복용해도 돼? / (A)약물 성분이 뭐야?")
    print("종료하려면 '종료' 또는 'exit'을 입력하세요.")

    while True:
        user_input = input("\n👉 질문을 입력하세요: ")
        if user_input.lower() in ['종료', 'exit']:
            print("챗봇을 종료합니다. 감사합니다!")
            break

        # 질문 유형 분석
        if '성분이 뭐야' in user_input:
            drug_name = user_input.split(' 성분이 뭐야')[0].strip('()').strip()
            if drug_name:
                results = find_drug_info(df, drug_name)
                if not results.empty:
                    # 성분명은 '성분명A'과 '성분명B'에 모두 있을 수 있음
                    components = set()
                    for component in results['성분명A'].tolist() + results['성분명B'].tolist():
                        if pd.notna(component):
                            components.add(component)
                    
                    if components:
                        print(f"✅ '{drug_name}'의 성분은 다음과 같습니다: {', '.join(components)}")
                    else:
                        print(f"ℹ️ '{drug_name}'에 대한 성분 정보가 없습니다.")
                else:
                    print(f"❌ '{drug_name}' 정보를 찾을 수 없습니다.")
            else:
                print("❌ 어떤 약물의 성분을 알고 싶으신가요? 약물 이름을 입력해주세요.")
        
        elif '같이 복용해도 돼' in user_input:
            parts = user_input.split('과 ')
            if len(parts) >= 2:
                drug_A_query = parts[0].strip('()').strip()
                drug_B_query = parts[1].split('를')[0].strip('()').strip()
                
                if drug_A_query and drug_B_query:
                    risk, explanation = check_drug_interaction_flexible(df, drug_A_query, drug_B_query)
                    print(f"**💊 약물 상호작용 위험도: {risk}**")
                    print(f"**💡 상세 정보:**")
                    print(explanation)
                else:
                    print("❌ 두 약물 이름을 정확히 입력해주세요. 예: (A)약물과 (B)약물을 같이 복용해도 돼?")
            else:
                print("❌ 질문 형식을 다시 확인해주세요. 예: (A)약물과 (B)약물을 같이 복용해도 돼?")
        
        else:
            print("🤔 죄송합니다. 질문 형식을 이해하지 못했습니다. 다시 시도해주세요.")

# 챗봇 시작
if __name__ == "__main__":
    start_chatbot()