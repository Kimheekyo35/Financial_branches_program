import pandas as pd
from rapidfuzz import fuzz
from pathlib import Path
import unicodedata
import re
import json
import psycopg2
from dotenv import load_dotenv
import os

load_dotenv(Path(__file__).parent/".env")

# sql 코드
conn = psycopg2.connect(
    dbname = os.environ["DB_NAME"],
    user = os.environ["DB_USER"],
    password = os.environ["DB_PASSWORD"],
    host = os.environ["DB_HOST"],
    port = os.environ["DB_PORT"]
)

"""
입력값 : 금융기관명, 지점명, 주소
"""

# 주소 Alias 설정
REGION_ALIAS_GROUPS = {
    "서울": ["서울특별시", "서울시", "서울"],
    "부산": ["부산광역시", "부산시", "부산","부산직할시"],
    "대구": ["대구광역시", "대구시", "대구"],
    "인천": ["인천광역시", "인천시", "인천"],
    "광주": ["광주광역시", "광주"],
    "대전": ["대전광역시", "대전시", "대전"],
    "울산": ["울산광역시", "울산시", "울산"],
    "세종": ["세종특별자치시", "세종시", "세종"],
    "경기": ["경기도", "경기"],
    "강원": ["강원특별자치도", "강원도", "강원"],
    "충북": ["충청북도", "충북도", "충북"],
    "충남": ["충청남도", "충남도", "충남"],
    "전북": ["전북특별자치도", "전라북도", "전북도", "전북"],
    "전남": ["전라남도", "전남도", "전남"],
    "경북": ["경상북도", "경북도", "경북"],
    "경남": ["경상남도", "경남도", "경남"],
    "제주": ["제주특별자치도", "제주도", "제주"],
    "전남광주": ["전남광주통합특별시", "전남광주"],
}

# 주소 정규화 함수
def normalize_address(address):
    address = str(address).strip()

    for standard, aliases in REGION_ALIAS_GROUPS.items():
        for alias in sorted(aliases,key=len, reverse=True):
            address = re.sub(
            rf"^{re.escape(alias)}(?=\s|$)",
            standard,
            address
            )

    address = re.sub(r"\s+", " ", address)

    return address
    
#json 담아둔 폴더명
json_folder = Path(__file__).parent/"financial_json_dir"

def find_bank_code(company_name):
    with open(json_folder/"company_alias.json","r",encoding='utf-8') as file:
        company_alias = json.load(file)

    company_name = str(company_name).strip()

    for bank_name, company_info in company_alias.items():
        bank_name = company_info["name"]

        for alias in sorted(company_info["aliases"], key=len, reverse=True):
            company_name = re.sub(
                rf"^{re.escape(alias)}(?=\s|$)",
                bank_name,
                company_name
            )

    company_name = re.sub(r"\s+", " ", company_name)

    code = next(
        (key for key, value in company_alias.items() if value["name"] == company_name),
        None,
    )

    return company_name, code

# 예: (엘에스증권,265)
# company_name, code = find_bank_code(input_company)
# print(company_name, code)
# if code == None:
    # 입력된 company_name 과 일치하는 별칭 찾기
    address = normalize_address(input_address)

    # OPENAI API 호출

def normalize_branch_name(name):
    if pd.isna(name):
        return ""

    name = unicodedata.normalize("NFKC", str(name)).strip()
    name = re.sub(r"[\s\-_/().]", "", name)

    if name.endswith("지점"):
        return name[:-2]
    if name.endswith("점"):
        return name[:-1]
    return name


def classify_match(branch_score, address_score):
    if address_score >= 90 and branch_score >= 90:
        return "자동 일치"
    elif address_score >= 85 and branch_score >= 85:
        return "일치 후보"
    elif address_score >= 85:
        return "지점명 검토 필요"
    elif branch_score >= 85:
        return "주소 검토 필요"
    else:
        return "불일치"


def find_branch_match(branch_name, address, code):
    if not code or not str(address).strip():
        return None

    with conn:
        with conn.cursor() as cur:
            cur.execute("""
            SELECT bank_name, branch_name, address
            FROM FINANCIAL_BRANCHES
            WHERE bank_code = %s
            """,
            (code,),
            )
            # 조회한 데이터를 branches 라는 변수에 저장하는 것
            branches = cur.fetchall()
    # 입력받은 주소 정규화
    normalized_input = normalize_address(address)
    normalized_branch = normalize_branch_name(branch_name)
    best_match = None

    if normalized_input:
        for db_bank_name, db_branch_name, db_address in branches:
            if not db_address:
                continue
            normalized_db = normalize_address(db_address)

            if not normalized_db:
                continue
            
            address_score = fuzz.ratio(normalized_input, normalized_db)
            normalized_db_branch = normalize_branch_name(db_branch_name)
            branch_score = 0.0
            if normalized_branch and normalized_db_branch:
                branch_score = fuzz.ratio(normalized_branch, normalized_db_branch)

            # 주소 점수가 가장 높은 행을 선택하고, 동점일 때 지점명으로 비교한다.
            if best_match is None or (address_score, branch_score) > (
                best_match["address_score"], best_match["branch_score"]
            ):
                best_match = {
                    "bank_name": db_bank_name,
                    "branch_name": db_branch_name,
                    "address": db_address,
                    "branch_score": branch_score,
                    "address_score": address_score,
                }

    return best_match


def find_sql(company_name, address, code):
    match = find_branch_match("", address, code)
    if match is None:
        return None
    return match["address"], f"{match['address_score']:.1f}"
