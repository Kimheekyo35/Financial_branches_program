import streamlit as st
import pandas as pd

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
    for row_number, row in enumerate(
        cleaned_df.to_dict("records"),
        start = 1
    ):

    # 세 칸이 모두 빈 행이면 건너뛰기
        if not any(row.values()):
            continue
        
        count += 1

        with st.container(border=True):
            st.write("입력 금융기관명: ",row["금융기관명"])
            st.write("입력 지점명: ",row["지점명"])
            st.write("입력 주소: ",row["주소"])
