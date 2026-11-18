import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from html import escape
from io import StringIO

import streamlit as st
import pandas as pd

from rapidfuzz_file import classify_match, find_bank_code, find_branch_match
from openai_test import call_openai

# 1. 화면 설정·문구·디자인

input_columns = ["금융기관명", "주소"]
text = {
    "title": "금융거래조회서 주소 검증",
    "label": "EY 한영회계법인 · 금융기관 주소 검증",
    "english_title": "Financial Institution Address Verification",
    "guide": (
        "금융기관명, 주소를 붙여넣고 **표에 넣기**. "
        "표에서 내용 확인 및 수정 후 **확인**."
    ),
    "input_title": "데이터 입력",
    "paste_label": "여러 건 붙여넣기",
    "editor_label": "입력 내용 (수정 가능)",
    "placeholder": (
        "국민은행 서울특별시 강남구 테헤란로 152\n"
        "신한은행 서울특별시 중구 세종대로 9"
    ),
    "paste_guide": (
        "엑셀의 금융기관명·주소 두 열을 복사하거나, "
        "금융기관명 내부 공백을 제거해주세요."
    ),
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
    "result_title": "주소 검색 결과",
    "result_count": "총 {count}건",
    "number_header": "No.",
    "input_header": "입력한 값",
    "db_header": "DB 매핑값",
    "status_header": "결과",
    "ai_title": "AI 검색 결과 · {number}행",
    "ai_waiting": "AI 주소 검색 대기 중...",
    "ai_error": (
        "웹 주소 검색 중 오류가 발생했습니다. "
        "API 설정과 연결 상태를 확인하세요."
    ),
    "ai_notice": "AI로 생성한 결과입니다. 참고용으로 사용하시기 바랍니다.",
}

status_style = {
    "일치": ("row-match", "status-match", "✓"),
    "주소 검토 필요": ("row-review", "status-review", "!"),
    "불일치": ("row-mismatch", "status-mismatch", "×"),
    "입력 확인 필요": ("row-invalid", "status-invalid", "!"),
    "DB 조회 오류": ("row-invalid", "status-invalid", "!"),
}

# No. / 입력 금융기관명 / 입력 주소 / DB 금융기관명 / DB 주소 / 결과
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
# 왼쪽 입력값 영역/ 오른쪽 DB 매핑값·결과 영역
ai_column_widths = [46, 54]

css = """
<style>
/* 1. 전체 화면 */
.stApp {
    background-color: #f5f6f8;
    color: #2e2e38;
}
.block-container {
    width: 100%;
    max-width: none;
    padding: 1rem 24px 2rem;
}
/* 2. 상단 배너 */
.brand-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 24px;
    background: linear-gradient(
        125deg,
        #202024 0%,
        #303038 72%,
        #ffe600 72%,
        #ffe600 78%,
        #202024 78%
    );
    color: #ffffff;
    padding: 22px 28px;
    border-radius: 4px;
    margin-bottom: 24px;
}
.brand-left {
    display: flex;
    align-items: center;
    gap: 20px;
}
.brand-ey {
    color: #ffffff;
    font-size: 38px;
    font-weight: 800;
    line-height: 1;
    border-top: 5px solid #ffe600;
    padding-top: 7px;
}
.brand-name {
    font-size: 15px;
    font-weight: 600;
}
.brand-right {
    font-size: 13px;
    text-align: right;
}
.page-label {
    color: #666672;
    font-size: 14px;
    border-left: 4px solid #ffe600;
    padding-left: 10px;
    margin-bottom: 8px;
}

.page-english {
    color: #666672;
    font-size: 13px;
    margin-bottom: 6px;
}
/* 3. 입력·결과 영역 */
[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 10px;
}
.section-heading {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 0 16px;
}
.step-number {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    flex-shrink: 0;
    border-radius: 50%;
    background-color: #202024;
    color: #ffe600;
    font-size: 17px;
    font-weight: 700;
}
.section-title {
    font-size: 22px;
    font-weight: 700;
    color: #202024;
}
.count-badge {
    background-color: #ffffff;
    border: 1px solid #e2e3e8;
    border-radius: 20px;
    padding: 4px 12px;
    color: #555563;
    font-size: 14px;
}
/* 4. 버튼 */
div.stButton > button {
    border-radius: 6px;
    font-weight: 700;
    min-height: 42px;
    padding: 8px 22px;
}
div.stButton > button[kind="primary"] {
    background-color: #ffe600;
    border: 1px solid #ffe600;
    color: #202024;
}
div.stButton > button[kind="primary"]:hover {
    background-color: #f2da00;
    border-color: #f2da00;
    color: #202024;
}
/* 5. 결과 표 */
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
    padding: 11px 10px;
    text-align: left;
    vertical-align: middle;
    overflow-wrap: anywhere;
}
.result-table th {
    font-weight: 700;
}
.result-table td {
    background-color: #ffffff;
}
.result-table .row-number {
    text-align: center;
}
/* 6. 표 상단 제목*/
.result-table th.header-number,
.result-table th.header-input {
    background-color: #202024;
    color: #ffffff;
    border-color: #45454d;
}
.result-table th.header-db {
    background-color: #ffe600;
    color: #202024;
    border-color: #e0ca00;
}
.result-table th.header-status {
    background-color: #202024;
    color: #ffe600;
    border-color: #45454d;
}
/* 7. 금융기관명·주소 열 제목 */
.result-table th.sub-input,
.result-table th.sub-db {
    background-color: #eceef2;
    color: #2e2e38;
}
/* 8. 결과별 행 배경 */
.result-table .row-review td {
    background-color: #fff8d6;
}
.result-table .row-mismatch td {
    background-color: #fde9eb;
}
.result-table .row-invalid td {
    background-color: #f0f0f3;
}
/* 9. 결과 글씨·아이콘 */
.status-label {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-weight: 700;
}
.status-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
    flex-shrink: 0;
    border-radius: 50%;
    color: #ffffff;
    font-size: 14px;
    line-height: 1;
}
.status-match {
    color: #16805d;
}
.status-match .status-icon {
    background-color: #16805d;
}
.status-review {
    color: #946800;
}
.status-review .status-icon {
    background-color: #d99a00;
}
.status-mismatch {
    color: #b42335;
}
.status-mismatch .status-icon {
    background-color: #c92a3c;
}
.status-invalid {
    color: #666672;

.status-invalid .status-icon {
    background-color: #777783;
}
/* 10. 불일치인 DB 값의 차이 강조 */
.result-table .db-difference {
    font-weight: 800;
    color: #922033;
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
            # 주소 내부의 공백은 유지한다.
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

# 처음 화면에 보여지는 빈 표
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

# 3. 입력 화면 구성
st.markdown(
    """
    <div class="brand-banner">
        <div class="brand-left">
            <div class="brand-ey">EY</div>
            <div class="brand-name">한영회계법인</div>
        </div>
        <div class="brand-right">
            금융기관 주소 검증 프로그램
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    f'<div class="page-label">{escape(text["label"])}</div>'
    f'<div class="page-english">{escape(text["english_title"])}</div>',
    unsafe_allow_html=True,
)
st.title(text["title"])
st.write(text["guide"])
with st.container(border=True):
    st.markdown(
        f"""
        <div class="section-heading">
            <span class="step-number">1</span>
            <span class="section-title">
                {escape(text["input_title"])}
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    paste_column, editor_column = st.columns(
        [1, 1.1],
        gap="medium",
    )
    # 왼쪽입력값: 붙여넣기값
    with paste_column:
        paste_text = st.text_area(
            text["paste_label"],
            key="pasted_text",
            height=150,
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

    # 오른쪽: 입력 표
    with editor_column:
        st.markdown(f"**{text['editor_label']}**")
        edited_df = st.data_editor(
            st.session_state.input_data,
            num_rows="dynamic",
            hide_index=True,
            width="stretch",
            height=240,
            column_config={
                "금융기관명": st.column_config.TextColumn(
                    "금융기관명",
                    width="small",
                ),
                "주소": st.column_config.TextColumn(
                    "주소",
                    width="large",
                ),
            },
            key=f"input_table_{st.session_state['table_version']}",
        )
        # 확인 버튼
        _, confirm_column = st.columns([3, 1])

        with confirm_column:
            confirmed = st.button(
                text["confirm_button"],
                type="primary",
                use_container_width=True,
            )


# 4. 결과 표·차이 강조·AI 결과 출력

def show_result_table(content):
    table_html = f"""
    <table class="result-table">
        {table_columns}
        {content}
    </table>
    """
    # HTML 들여쓰기 제거
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
                <th rowspan="2" class="header-number">
                    {text["number_header"]}
                </th>
                <th colspan="2" class="header-input">
                    {text["input_header"]}
                </th>
                <th colspan="2" class="header-db">
                    {text["db_header"]}
                </th>
                <th rowspan="2" class="header-status">
                    {text["status_header"]}
                </th>
            </tr>
            <tr>
                <th class="sub-input">{input_columns[0]}</th>
                <th class="sub-input">{input_columns[1]}</th>
                <th class="sub-db">{input_columns[0]}</th>
                <th class="sub-db">{input_columns[1]}</th>
            </tr>
        </thead>
        """
    )

def highlight_difference(input_str, db_str):
    input_str = str(input_str or "")
    db_str = str(db_str or "")

    matcher = SequenceMatcher(
        None,
        input_str,
        db_str,
        autojunk=False,
    )
    highlighted_db = ""
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        db_part = escape(db_str[j1:j2])

        if tag == "equal":
            highlighted_db += db_part

        elif tag in ("replace", "insert"):
            highlighted_db += (
                f'<span class="db-difference">{db_part}</span>'
            )
    return highlighted_db

def show_result_row(row_number, row, match, status):
    row_class, status_class, status_icon = status_style[status]

    db_bank = match.get("bank_name", "") if match else ""
    db_address = match.get("address", "") if match else ""

    input_bank = escape(str(row["금융기관명"]))
    input_address = escape(str(row["주소"]))

    # 불일치인 경우 DB 값의 차이 강조
    if status == "불일치":
        db_bank = highlight_difference(
            row["금융기관명"],
            db_bank,
        )
        db_address = highlight_difference(
            row["주소"],
            db_address,
        )
    else:
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
                    <span class="status-label {status_class}">
                        <span class="status-icon">{status_icon}</span>
                        <span>{status}</span>
                    </span>
                </td>
            </tr>
        </tbody>
        """
    )

def create_ai_placeholder(row_number):
    #  AI 결과 표시
    _, ai_column = st.columns(
        ai_column_widths,
        gap=None,
    )
    with ai_column:
        with st.container(border=True):
            st.markdown(
                f"**{text['ai_title'].format(number=row_number)}**"
            )
            placeholder = st.empty()
    return placeholder

def show_ai_result(placeholder, state, result=None):
    # AI 제목과 바깥 영역은 유지하고 내용만 갱신한다.
    with placeholder.container():
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
        with st.container(border=True):
            st.markdown(
                f"""
                <div class="section-heading">
                    <span class="step-number">2</span>
                    <span class="section-title">
                        {escape(text["result_title"])}
                    </span>
                    <span class="count-badge">
                        {text["result_count"].format(count=len(cleaned_df))}
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            show_result_header()
            for row_number, row in enumerate(
                cleaned_df.to_dict("records"),
                start=1,
            ):
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
                try:
                    _, company_code = find_bank_code(
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
                show_result_row(
                    row_number,
                    row,
                    match,
                    status,
                )
                # 불일치 행 아래 AI 검색 영역
                if status == "불일치":
                    result_placeholder = create_ai_placeholder(
                        row_number
                    )

                    show_ai_result(
                        result_placeholder,
                        state="waiting",
                    )

                    ai_jobs.append(
                        (row, result_placeholder)
                    )

# 6. AI 검색

if ai_jobs:
    # API 요청은 작업 스레드에서 실행한다.
    # 화면은 메인 스레드에서 갱신한다.
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(
                call_openai,
                bank_name=row["금융기관명"],
                address=row["주소"],
            ): placeholder
            for row, placeholder in ai_jobs
        }
        for future in as_completed(futures):
            placeholder = futures[future]
            try:
                result = future.result()
            except Exception:
                show_ai_result(
                    placeholder,
                    state="error",
                )
            else:
                show_ai_result(
                    placeholder,
                    state="success",
                    result=result,
                )