import steamlit as st

st.title('약물 상호작용 검사기')
drug1 = st.text_input('첫 번째 약물')
drug2 = st.text_input('두 번째 약물')

if st.button('검사하기'):
    # 여기에 상호작용 로직 함수 호출
    result = check_interaction(drug1, drug2)
st.write(result)