import csv
from io import StringIO

import streamlit as st
import pandas as pd
from rapidfuzz_file import classify_match, find_bank_code, find_branch_match

# find_bank_code 은 company_name 을 정규화한 후, bank_code 갖고오는 함수
# find_branch_match는 같은 DB 행의 지점명과 주소 점수를 반환한다.


def parse_pasted_rows(text, columns=None):
    if columns is None:
        columns = ["금융기관명", "지점명", "주소"]
    rows = []
    reader = csv.reader(StringIO(text), delimiter="\t")
    for values in reader:
        if not any(value.strip() for value in values):
            continue
        if len(values) == 1:
            # 주소 앞의 항목만 나눠서 주소 내부의 공백을 보존한다.
            values = values[0].split(maxsplit=len(columns) - 1)
        if len(values) > len(columns):
            raise ValueError(
                f"{reader.line_num}행에 열이 너무 많습니다. {', '.join(columns)} {len(columns)}개 열만 복사하세요."
            )
        values = [value.strip() for value in values]
        rows.append(values + [""] * (len(columns) - len(values)))
    return pd.DataFrame(rows, columns=columns)

# 글씨 크기 수정
st.markdown(
    """
    <style>
    .st-key-search_mode p {
        font-size: 18px !important;
    }
    </style>
    """,
    unsafe_allow_html=True)

# 크기 늘리기
st.set_page_config(layout="wide")

search_mode = st.radio(
    "검색 방식",
    ["지점명 + 주소 비교", "주소만 검색"],
    horizontal=True,
    key = "search_mode"
)
# 제목
st.title("금융기관 주소 검사")

address_only = search_mode == "주소만 검색"
input_columns = ["금융기관명", "주소"] if address_only else ["금융기관명", "지점명", "주소"]

# 추가 설명
st.write(f"{', '.join(input_columns)}를 헤더 없이 붙여넣고 **표에 넣기**를 누르세요. "
         "아래 표에서 내용을 확인하거나 수정한 뒤 ‘확인’을 눌러주세요.")

# 1. 세 열과 빈 행 30개 만들기
initial_df = pd.DataFrame(
    [[""] * len(input_columns)],
    columns=input_columns,
)

if "table_version" not in st.session_state:
    st.session_state.table_version = 0
if "input_data" not in st.session_state:
    st.session_state.input_data = initial_df.copy()
if st.session_state.get("previous_search_mode") != search_mode:
    st.session_state.input_data = st.session_state.get(
        f"saved_input_{search_mode}", initial_df
    ).copy()
    st.session_state.pasted_text = st.session_state.get(f"saved_paste_{search_mode}", "")
    st.session_state.table_version += 1
    st.session_state.previous_search_mode = search_mode

def clear_inputs():
    st.session_state.table_version += 1
    st.session_state.input_data = initial_df.copy()
    st.session_state.pasted_text = ""

st.button("전체 입력 지우기", on_click=clear_inputs)

paste_text = st.text_area(
    "여러 건 붙여넣기",
    key="pasted_text",
    height=120,
    placeholder=(
        "국민은행 서울특별시 강남구 테헤란로 152"
        if address_only else "국민은행 강남중앙지점 서울특별시 강남구 테헤란로 152"
    ),
)
st.caption(
    f"{'·'.join(input_columns)}는 반드시 띄어쓰기로 구분하고, 한 줄에 한 건씩 입력하세요. "
    f"{'이나 '.join(input_columns[:-1])}에 공백이 있으면 **공란을 제거한 후** 작성해주세요."
)
if st.button("표에 넣기"):
    try:
        pasted_df = parse_pasted_rows(paste_text, input_columns)
        if pasted_df.empty:
            st.warning("표에 넣을 내용을 붙여넣어 주세요.")
        else:
            st.session_state.input_data = pasted_df
            st.session_state.table_version += 1
    except (ValueError, csv.Error) as error:
        st.warning(str(error))

# 2. 사용자가 편집할 수 있는 입력 표
edited_df = st.data_editor(
    st.session_state.input_data,
    num_rows = "dynamic",
    hide_index = True,
    width = "stretch",
    key = f"input_table_{st.session_state["table_version"]}"
)
st.session_state[f"saved_input_{search_mode}"] = edited_df.copy()
st.session_state[f"saved_paste_{search_mode}"] = paste_text

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
                st.warning(f"{row_number}행의 {', '.join(input_columns)}를 모두 입력하세요.")
                comparison = pd.DataFrame([row], index=["입력값"])
                st.table(comparison)
            continue

        company_name, company_code = find_bank_code(row["금융기관명"])
        match = find_branch_match(row.get("지점명", ""), row["주소"], company_code)

        if match is None:
            with st.container(border=True):
                st.warning(f"{row_number}행의 비교할 DB 데이터를 찾지 못했습니다. 금융기관명을 확인하세요.")
                comparison = pd.DataFrame([row], index=["입력값"])
                st.table(comparison)
            continue
        if address_only:
            if match["address_score"] >= 90:
                status = "주소 일치"
            elif match["address_score"] >= 85:
                status = "주소 일치 후보"
            else:
                status = "주소 검토 필요"
        else:
            status = classify_match(match["branch_score"], match["address_score"])
        status_display = {
            "자동 일치": st.success,
            "일치 후보": st.info,
            "지점명 검토 필요": st.warning,
            "주소 검토 필요": st.warning,
            "불일치": st.error,
            "주소 일치": st.success,
            "주소 일치 후보": st.info,
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
                columns=["금융기관명", "지점명", "주소"],
            ).fillna("")
            st.table(comparison)
            if address_only:
                st.caption(f"주소 유사도 {match['address_score']:.2f}점")
