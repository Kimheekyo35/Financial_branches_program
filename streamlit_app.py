import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from html import escape
from io import StringIO

import logging
import streamlit as st
import pandas as pd

from rapidfuzz_file import classify_match, find_bank_code, find_branch_match
from openai_test import call_openai
from chatbot import openai_chatbot

import os
import hmac
from dotenv import load_dotenv

load_dotenv()

APP_PASSWORD = os.getenv("APP_PASSWORD")

# 페이지 이름 (복붙했을 때 나오는 이름)
st.set_page_config(
    page_title="금융거래조회서 주소 검증",
    layout="wide"
)

# 로그인 과정
if not APP_PASSWORD:
    st.error("APP_PASSWORD가 설정되어 있지 않습니다. ")
    st.stop()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("로그인")

    with st.form("login_form"):
        password = st.text_input("비밀번호", type="password")
        submitted = st.form_submit_button("입력")

    if submitted:
        if hmac.compare_digest(password, APP_PASSWORD):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("비밀번호가 올바르지 않습니다.")
    
    st.stop()


# 1. 화면 설정·문구·디자인
input_columns = ["금융기관명", "주소"]
text = {
    "title": "금융거래조회서 주소 검증",
    "guide": (
        "금융기관명, 주소를 붙여넣고 <strong>표에 넣기</strong>. "
        "표에서 내용 검토 후 <strong>확인</strong>."
    ),
    "input_title": "데이터 입력",
    "paste_label": "식별 주소 붙여넣기",
    "editor_label": "입력 내용",
    "placeholder": (
        "국민은행 서울특별시 강남구 테헤란로 152\n"
        "신한은행 서울특별시 중구 세종대로 9"
    ),
    "paste_guide": (
        "엑셀의 금융기관명·주소 두 열을 복사해주세요. "
        "금융기관명이 올바른지 확인해주세요."
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
    "input_header": "회사 제시 주소",
    "db_header": "주소 확인 결과",
    "status_header": "검증 결과",
    "ai_title": "AI 검색 결과",
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
    background-color: #eeeeee;
    color: #2e2e38;
}
.block-container {
    width: 100%;
    max-width: none;
    padding: 3rem 24px 2rem;
}
/* 2. 상단 배너 */
.brand-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 15px;
    background: linear-gradient(
        125deg,
        #202024 0%,
        #303038 72%,
        #ffe600 72%,
        #ffe600 78%,
        #202024 78%
    );
    color: #ffffff;
    padding: 30px 32px;
    border-radius: 1px;
    margin-bottom: 24px;
}
.brand-left {
    display: flex;
    align-items: center;
    gap: 20px;
}
.brand-ey {
    color: #ffffff;
    font-size: 20px;
    font-weight: 800;
    line-height: 1;
    border-top: 5px solid #ffe600;
    padding-top: 9px;
}
.brand-name {
    font-size: 15px;
    font-weight: 600;
}

/* 3. 입력·결과 영역 */
[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 20px;
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
    font-size: 20px;
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
/* 6. 결과표 상단 제목 */
.result-table th.header-number,
.result-table th.header-input,
.result-table th.header-db,
.result-table th.header-status {
    background-color: #f0f1f3;
    color: #2e2e38;
    border-color: #000000;
    border-top: 3px solid #C4C5C7;
    text-align: center;
    font-size: 14px;
    font-weight: 700;
    padding: 12px 10px;
}
.result-table th.header-input {
    border-top-color: #202024;
}
.result-table th.header-db {
    border-top-color: #ffe600;
}

/* 7. 금융기관명·주소 열 제목 */
.result-table th.sub-input,
.result-table th.sub-db {
    background-color: #fafafb;
    color: #666672;
    border-color: #000000;
    text-align: center;
    font-size: 13px;
    font-weight: 600;
    padding: 9px 10px;
}

/* 표 내용: 번호·금융기관명·결과는 가운데 정렬 */
.result-table td:nth-child(1),
.result-table td:nth-child(2),
.result-table td:nth-child(4),
.result-table td:nth-child(6) {
    text-align: center;
}

/* 긴 주소는 왼쪽 정렬 */
.result-table td:nth-child(3),
.result-table td:nth-child(5) {
    text-align: left;
}

/* 결과 아이콘과 문구 정렬 */
.result-table .status-label {
    justify-content: center;
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
}
.status-invalid .status-icon {
    background-color: #777783;
}
/* 10. 불일치인 DB 값의 차이 강조 */
.result-table .db-difference {
    font-weight: 800;
    color: #922033;
}
/* 11. input박스 전체: 배경 + 테두리 두께 */
.st-key-input_box {
    background-color: #ffffff !important;
    border: 2px solid #8a8a96 !important;
    border-radius: 10px !important;
}
/* 12. result박스 전체: 배경 + 테두리 두께 */
.st-key-result_box {
    background-color: #ffffff !important;
    border: 2px solid #8a8a96 !important;
    border-radius: 10px !important;
}
/* 13. 배너 안 제목·안내문 */
.brand-content {
    display: flex;
    flex-direction: column;
    gap: 16px;
    max-width: 68%;   /* 오른쪽 노란 줄무늬와 안 겹치게 */
}
.brand-title {
    font-size: 30px;
    font-weight: 800;
    line-height: 1.2;
    border-left: 8px solid #ffe600;
    padding-left: 14px;
}
.brand-guide {
    font-size: 15px;
    color: #e6e6ea;
}
.brand-guide strong {
    color: #ffe600;
}
/* 14. AI 검색 결과 영역 */
div[class*="st-key-ai_result_"] {
    background-color: #FFFFF7;
    border: 1px solid #FA8072;
    border-radius: 8px;
    padding: 16px 20px;
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
    f"""
    <div class="brand-banner">
        <div class="brand-content">
            <div class="brand-left">
                <div class="brand-ey">EY</div>
                <div class="brand-name">한영회계법인 CoE_ADC</div>
            </div>
            <div class="brand-title">{escape(text["title"])}</div>
            <div class="brand-guide">{text["guide"]}</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.container(border=True, key="input_box"):
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
        with st.container(border=False, key=f"ai_result_{row_number}"):
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
        with st.container(border=True, key="result_box"):
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


@st.dialog("💬 주소 검증 챗봇", width="medium")
def show_chatbot():
    st.caption("궁금한 주소에 대해 질문해 주세요.")
    if "chatbot_messages" not in st.session_state:
        st.session_state.chatbot_messages = []
    
    if st.button("대화 지우기", key="clear_chatbot"):
        st.session_state.chatbot_messages = []

    with st.container(height=250):
        for message in st.session_state.chatbot_messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
    
    prompt = st.chat_input("질문을 입력하세요.",key="chatbot_input")
    if prompt:
        user_message = {"role":"user", "content":prompt}
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            try:
                with st.spinner("답변을 작성하고 있습니다.."):
                    answer = openai_chatbot(
                        st.session_state.chatbot_messages + [user_message]
                    )

            except Exception:
                logging.getLogger(__name__).exception("주소 검증 챗봇 응담 생성 실패")
                st.error("답변을 가져오지 못했습니다. 잠시 후 다시 질문해 주세요.")
            
            else:
                st.markdown(answer)
                st.session_state.chatbot_messages.extend([
                    user_message,
                    {"role":"assistant","content":answer}
                ])

st.markdown(
    """
    <style>
    .st-key-chatbot_launcher {
        position: fixed;
        right: 24px;
        bottom: 24px;
        width: auto;
        z-index: 1000;
    }
    .st-key-chatbot_launcher button {
        border-radius: 50%;
        width: 56px;
        height: 56px;
        font-size: 24px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.18);
    }
    </style>
    """,
    unsafe_allow_html=True,
)
with st.container(key="chatbot_launcher"):
    if st.button("💬", key="open_chatbot", help="주소 검증 챗봇 열기"):
        show_chatbot()
