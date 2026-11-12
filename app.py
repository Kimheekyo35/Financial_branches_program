import streamlit as st
import pandas as pd
from rapidfuzz_file import classify_match, find_bank_code, find_branch_match

# find_bank_code 은 company_name 을 정규화한 후, bank_code 갖고오는 함수
# find_branch_match는 같은 DB 행의 지점명과 주소 점수를 반환한다.

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

    st.subheader("주소 검색 결과")
    
    # 입력받은 값을 각 행으로 출력하기
    # records는 표를 딕셔너리 목록으로 바꾸라는 옵션

    for row_number, row in enumerate(
        cleaned_df.to_dict("records"),
        start = 1):

        if not row["금융기관명"]:
            with st.container(border=True):
                st.warning(f"{row_number} 행의 금융기관명을 입력하세요. ")
                st.table(pd.DataFrame([row], index=["입력값"]))
            continue

        if not all(row.values()):
            with st.container(border=True):
                st.warning(f"{row_number}행의 금융기관명, 지점명, 주소를 모두 입력하세요.")
                comparison = pd.DataFrame([row], index=["입력값"])
                st.table(comparison)
            continue

        company_name, company_code = find_bank_code(row["금융기관명"])
        match = find_branch_match(row["지점명"], row["주소"], company_code)

        if match is None:
            with st.container(border=True):
                st.warning(f"{row_number}행의 비교할 DB 데이터를 찾지 못했습니다. 금융기관명을 확인하세요.")
                comparison = pd.DataFrame([row], index=["입력값"])
                st.table(comparison)
            continue
        status = classify_match(match["branch_score"], match["address_score"])
        status_display = {
            "자동 일치": st.success,
            "일치 후보": st.info,
            "지점명 검토 필요": st.warning,
            "주소 검토 필요": st.warning,
            "불일치": st.error,
        }
        with st.container(border=True):
            status_display[status](f"**{status}**")
            comparison = pd.DataFrame(
                [
                    row,
                    {
                        "금융기관명": match["bank_name"],
                        "지점명": match["branch_name"],
                        "주소": match["address"],
                    },
                ],
                index=["입력값", "저장값"],
            )
            st.table(comparison)
