import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import escape
from io import StringIO

import streamlit as st
import pandas as pd

from rapidfuzz_file import classify_match, find_bank_code, find_branch_match
from openai_test import call_openai

# 1. 화면 설정-문구-디자인

input_columns = ["금융기관명", "주소"]

text = {
    "title": "금융거래조회서 주소 검증 프로그램",
    "label": "EY 한영회계법인 · 금융기관 주소 검증",
    "guide": (
        "금융기관명, 주소를 헤더 없이 붙여넣고 **표에 넣기**를 누르세요. "
        "아래 표에서 내용을 확인하거나 수정한 뒤 **확인**을 눌러주세요."
    ),
    "input_title": "1. 데이터 입력",
    "paste_label": "여러 건 붙여넣기",
    "placeholder": "국민은행 서울특별시 강남구 테헤란로 152",
    "paste_guide": (
        "엑셀의 금융기관명·주소 두 열을 복사하거나, "
        "띄어쓰기로 구분해 한 줄에 한 건씩 입력하세요. "
        "띄어쓰기로 입력할 때는 금융기관명 내부의 공백을 제거해주세요."
    ),
    "clear_button": "전체 입력 지우기",
    "paste_button": "표에 넣기",
    "confirm_button": "확인",
    "empty_paste": "표에 넣을 내용을 붙여넣어 주세요.",
    "empty_input": "확인할 금융기관명과 주소를 입력하세요.",
    "too_many_columns": (
        "{number}행에 열이 너무 많습니다. "
        "금융기관명, 주소 2개 열만 복사하세요."
    ),
    "missing_input": "{number}행의 금융기관명과 주소를 모두 입력하세요.",
    "db_error": (
        "{number}행의 DB 조회 중 오류가 발생했습니다. "
        "DB 설정과 연결 상태를 확인하세요."
    ),
    "result_title": "2. 주소 검색 결과",
    "result_count": "총 {count}건",
    "number_header": "No.",
    "input_header": "입력한 값",
    "db_header": "DB 매핑값",
    "status_header": "결과",
    "ai_title": "AI 검색 결과 · {number}행",
    "ai_waiting": "🤖AI 주소 검색 대기 중...",
    "ai_error": (
        "웹 주소 검색 중 오류가 발생했습니다. "
        "API 설정과 연결 상태를 확인하세요."
    ),
    "ai_notice": (
        "AI로 생성한 결과이므로 참고용으로 사용하시기 바랍니다. "
    ),
}

    # 결과별 배경색과 글씨색 연결
status_style = {
    "일치": ("row-match", "status-match"),
    "주소 검토 필요": ("row-review", "status-review"),
    "불일치": ("row-mismatch", "status-mismatch"),
    "입력 확인 필요": ("row-invalid", "status-invalid"),
    "DB 조회 오류": ("row-invalid", "status-invalid"),
}

    # 결과 표의 열 너비
table_columns = """
<colgroup>
    <col style="width: 5%;">
    <col style="width: 12%;">
    <col style="width: 29%;">
    <col style="width: 12%;">
    <col style="width: 29%;">
    <col style="width: 13%;">
</colgroup>
"""

css = """
<style>
.stApp {
    background-color: #f7f7f8;
    color: #2e2e38;
}

.page-label {
    color: #666672;
    font-size: 14px;
    border-left: 5px solid #ffe600;
    padding-left: 10px;
    margin-bottom: 10px;
}

div.stButton > button {
    border-radius: 6px;
    font-weight: 600;
}

div.stButton > button[kind="primary"] {
    background-color: #ffe600;
    border: 1px solid #ffe600;
    color: #2e2e38;
}

div.stButton > button[kind="primary"]:hover {
    background-color: #f2da00;
    border-color: #f2da00;
    color: #2e2e38;
}

.result-table {
    width: 100%;
    table-layout: fixed;
    border-collapse: collapse;
    font-size: 14px;
    color: #2e2e38;
}

.result-table th,
.result-table td {
    border: 1px solid #dedee3;
    padding: 12px 10px;
    text-align: left;
    vertical-align: top;
    overflow-wrap: anywhere;
}

.result-table th {
    background-color: #e9e9ed;
    font-weight: 600;
}

.result-table .group-title {
    background-color: #2e2e38;
    color: #ffffff;
}

.result-table td {
    background-color: #ffffff;
}

.result-table .row-review td {
    background-color: #fff8d6;
}

.result-table .row-mismatch td {
    background-color: #fde9eb;
}

.result-table .row-invalid td {
    background-color: #f0f0f3;
}

.result-table .row-number {
    text-align: center;
}

.status-match {
    color: #16805d;
    font-weight: 700;
}

.status-review {
    color: #946800;
    font-weight: 700;
}

.status-mismatch {
    color: #b42335;
    font-weight: 700;
}

.status-invalid {
    color: #666672;
    font-weight: 600;
}
</style>
"""

st.set_page_config(
    page_title=text["title"],
    layout="wide",
)

st.markdown(css, unsafe_allow_html=True)

# 2. 입력 데이터 처리

def parse_pasted_rows(text_value, columns=None):
    if columns is None:
        columns = input_columns
    rows = []
    reader = csv.reader(StringIO(text_value), delimiter="\t")
    for values in reader:
        if not any(value.strip() for value in values):
            continue
        if len(values) == 1:
            # 주소 앞의 항목만 나눠서 주소 내부의 공백을 보존한다.
            values = values[0].split(maxsplit=len(columns) - 1)
        if len(values) > len(columns):
            raise ValueError(
                text["too_many_columns"].format(
                    number=reader.line_num
                )
            )
        values = [value.strip() for value in values]
        rows.append(values + [""] * (len(columns) - len(values)))
    return pd.DataFrame(rows, columns=columns)

  # 입력값 내, 빈 표를 보여주는 용도
initial_df = pd.DataFrame(
    [[""] * len(input_columns)],
    columns=input_columns,
)
if "table_version" not in st.session_state:
    st.session_state.table_version = 0
if "input_data" not in st.session_state:
    st.session_state.input_data = initial_df.copy()
if "pasted_text" not in st.session_state:
    st.session_state.pasted_text = ""
def clear_inputs():
    st.session_state.table_version += 1
    st.session_state.input_data = initial_df.copy()
    st.session_state.pasted_text = ""

# 3. 입력 화면 구성

st.markdown(
    f'<div class="page-label">{escape(text["label"])}</div>',
    unsafe_allow_html=True,
)
st.title(text["title"])
st.write(text["guide"])
st.subheader(text["input_title"])
st.button(
    text["clear_button"],
    on_click=clear_inputs,
)
paste_text = st.text_area(
    text["paste_label"],
    key="pasted_text",
    height=120,
    placeholder=text["placeholder"],
)
st.caption(text["paste_guide"])
if st.button(text["paste_button"], type="primary"):
    try:
        pasted_df = parse_pasted_rows(
            paste_text,
            input_columns,
        )
        if pasted_df.empty:
            st.warning(text["empty_paste"])
        else:
            st.session_state.input_data = pasted_df
            st.session_state.table_version += 1
    except (ValueError, csv.Error) as error:
        st.warning(str(error))

  # 사용자가 편집할 수 있는 입력 표
edited_df = st.data_editor(
    st.session_state.input_data,
    num_rows="dynamic",
    hide_index=True,
    width="stretch",
    key=f"input_table_{st.session_state['table_version']}",
)

confirmed = st.button(
    text["confirm_button"],
    type="primary",
)

# 4. 결과 표·AI 결과 출력

def show_result_table(content):
    # HTML 앞의 들여쓰기를 제거해 코드 블록으로 표시되지 않게 한다.
    table_html = f"""
    <table class="result-table">
        {table_columns}
        {content}
    </table>
    """
    table_html = "\n".join(
        line.strip() for line in table_html.splitlines()
    )
    st.markdown(
        table_html,
        unsafe_allow_html=True,
    )
def show_result_header():
    show_result_table(
        f"""
        <thead>
            <tr>
                <th rowspan="2" class="group-title">
                    {text["number_header"]}
                </th>
                <th colspan="2" class="group-title">
                    {text["input_header"]}
                </th>
                <th colspan="2" class="group-title">
                    {text["db_header"]}
                </th>
                <th rowspan="2" class="group-title">
                    {text["status_header"]}
                </th>
            </tr>
            <tr>
                <th>{input_columns[0]}</th>
                <th>{input_columns[1]}</th>
                <th>{input_columns[0]}</th>
                <th>{input_columns[1]}</th>
            </tr>
        </thead>
        """
    )
def show_result_row(row_number, row, match, status):
    row_class, status_class = status_style[status]

    db_bank = match.get("bank_name", "") if match else ""
    db_address = match.get("address", "") if match else ""

    # 입력값과 DB 값이 HTML 코드로 해석되지 않도록 처리한다.
    input_bank = escape(str(row["금융기관명"]))
    input_address = escape(str(row["주소"]))
    db_bank = escape(str(db_bank or ""))
    db_address = escape(str(db_address or ""))
    show_result_table(
        f"""
        <tbody>
            <tr class="{row_class}">
                <td class="row-number">{row_number}</td>
                <td>{input_bank}</td>
                <td>{input_address}</td>
                <td>{db_bank}</td>
                <td>{db_address}</td>
                <td>
                    <span class="{status_class}">
                        {status}
                    </span>
                </td>
            </tr>
        </tbody>
        """
    )

def show_ai_result(placeholder, row_number, state, result=None):
    with placeholder.container():
        with st.container(border=True):
            st.markdown(
                f"**{text['ai_title'].format(number=row_number)}**"
            )

            if state == "waiting":
                st.info(text["ai_waiting"])

            elif state == "error":
                st.warning(text["ai_error"])

            else:
                st.markdown(result)
                st.caption(text["ai_notice"])


# 5. 확인·DB 매칭·판정

ai_jobs = []

if confirmed:
    cleaned_df = edited_df.fillna("").astype(str)

    for column in input_columns:
        cleaned_df[column] = cleaned_df[column].str.strip()

    # 완전히 빈 행은 제외한다.
    cleaned_df = cleaned_df.loc[
        cleaned_df[input_columns].ne("").any(axis=1)
    ]

    if cleaned_df.empty:
        st.warning(text["empty_input"])

    else:
        st.subheader(text["result_title"])
        st.caption(
            text["result_count"].format(count=len(cleaned_df))
        )

        show_result_header()

        # 입력 표를 딕셔너리 목록으로 바꿔 각 행을 처리한다.
        for row_number, row in enumerate(
            cleaned_df.to_dict("records"),
            start=1,
        ):
            # 금융기관명과 주소 입력 여부 확인
            if not all(row[column] for column in input_columns):
                show_result_row(
                    row_number,
                    row,
                    None,
                    "입력 확인 필요",
                )

                st.caption(
                    text["missing_input"].format(number=row_number)
                )
                continue

            # 금융기관명을 정규화하고 금융기관 코드를 조회한다.
            # 같은 금융기관의 DB에서 가장 유사한 주소를 찾는다.
            try:
                company_name, company_code = find_bank_code(
                    row["금융기관명"]
                )

                match = find_branch_match(
                    "",
                    row["주소"],
                    company_code,
                )

            except Exception:
                show_result_row(
                    row_number,
                    row,
                    None,
                    "DB 조회 오류",
                )

                st.warning(
                    text["db_error"].format(number=row_number)
                )
                continue

      
            if match is None:
                status = "불일치"

            else:
                status = classify_match(match["address_score"])

            # 불일치인 경우에도 DB 매핑값을 함께 표시한다.
            show_result_row(
                row_number,
                row,
                match,
                status,
            )

            # 불일치 행 바로 아래에 AI 결과 공간을 만든다.
            if status == "불일치":
                result_placeholder = st.empty()

                show_ai_result(
                    result_placeholder,
                    row_number,
                    state="waiting",
                )

                ai_jobs.append(
                    (row_number, row, result_placeholder)
                )


# 6. AI 검색


if ai_jobs:
    # API 요청만 작업 스레드에서 실행한다.
    # 화면은 메인 스레드에서 갱신한다.
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(
                call_openai,
                bank_name=row["금융기관명"],
                address=row["주소"],
            ): (row_number, placeholder)
            for row_number, row, placeholder in ai_jobs
        }

        for future in as_completed(futures):
            row_number, placeholder = futures[future]

            try:
                result = future.result()

            except Exception:
                show_ai_result(
                    placeholder,
                    row_number,
                    state="error",
                )

            else:
                show_ai_result(
                    placeholder,
                    row_number,
                    state="success",
                    result=result,
                )