import streamlit as st
import pandas as pd
from rapidfuzz_file import find_bank_code, find_sql

# find_bank_code 은 company_name 을 정규화한 후, bank_code 갖고오는 함수
# find_sql 은 sql에서 데이터 찾고 유사도 점수까지 확인하는 함수

# 크기 늘리기
st.set_page_config(layout="wide")

# 제목
st.title("금융기관 주소 검사")

# 추가 설명
st.write("엑셀에서 금융기관명, 지점명, 주소를 헤더 없이 복사한 뒤, "
         "붙여넣기 후 확인 버튼을 눌러주세요.")

# 1. 세 열과 빈 행 30개 만들기
initial_df = pd.DataFrame(
    [["","",""]],
    columns = ["금융기관명", "지점명", "주소"]
)

if "table_version" not in st.session_state:
    st.session_state.table_version = 0

def clear_inputs():
    st.session_state.table_version += 1

st.button("전체 입력 지우기", on_click=clear_inputs)

# 2. 사용자가 편집할 수 있는 입력 표
edited_df = st.data_editor(
    initial_df,
    num_rows = "dynamic",
    hide_index = True,
    width = "stretch",
    key = f"input_table_{st.session_state["table_version"]}"
)

# 확인 버튼 누르면 각 행 처리
if st.button("확인"):
    cleaned_df = edited_df.fillna("").astype(str)

    for column in cleaned_df.columns:
        cleaned_df[column] = cleaned_df[column].str.strip()

    count = 0

    st.subheader("주소 검색 결과")
    
    # 입력받은 값을 각 행으로 출력하기
    # records는 표를 딕셔너리 목록으로 바꾸라는 옵션

    for row_number, row in enumerate(
        cleaned_df.to_dict("records"),
        start = 1):

    # 세 칸이 모두 빈 행이면 건너뛰기
        if not any(row.values()):
            st.error("금융기관명, 지점명, 주소 를 입력하세요.")
            continue
        
        count += 1

        company_name, company_code = find_bank_code(row["금융기관명"])
        db_address, score = find_sql(company_name, row["주소"],company_code)
        score = float(score)

        if score < 85:
            st.error(
                f"** 주소 일치 여부 확인요망**  \n"
                f"입력 금융기관명: {row['금융기관명']}  \n"
                f"입력 지점명: {row['지점명']}  \n"
                f"입력 주소: {row['주소']}  \n"
                f"DB 주소: {db_address}  \n"
                f"유사도: {score:.1f}점"
            )

        else:
            with st.container(border=True):
                st.write("입력 금융기관명:", row["금융기관명"])
                st.write("입력 지점명:", row["지점명"])
                st.write("입력 주소:", row["주소"])
                st.write("DB 주소:", db_address)
                st.write(f"유사도: {score:.1f}점")
