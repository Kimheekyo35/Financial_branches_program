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

# code가 있는 경우 sql에서 bank_code와 code가 일치하는 것 찾고, address와 input_address 비교해야함
def find_sql(company_name, address, code):
    with conn:
        with conn.cursor() as cur:
            cur.execute(f"""
            SELECT branch_name, address
            FROM FINANCIAL_BRANCHES
            WHERE bank_code = '{code}'
            """
            )
            # 조회한 데이터를 branches 라는 변수에 저장하는 것
            branches = cur.fetchall()
    # 입력받은 주소 정규화
    normalized_input = normalize_address(address)
    best_match = None
    threshold = 85

    if normalized_input:
        for branch_name, db_address in branches:
            normalized_db = normalize_address(db_address)

            if not normalized_db:
                continue
            
            score = fuzz.ratio(normalized_input,normalized_db)

            if best_match is None or score > best_match["score"]:
                best_match = {
                    "address": db_address,
                    "score": score
                }

    if best_match is None:
        print("비교할 주소가 없습니다.")
    elif best_match["score"] > threshold:
        print("주소 유사도 기준을 통과했습니다.")
        print("회사명: ",company_name)
        print("입력 주소:", address)
        print("가장 유사한 DB 주소:", best_match["address"])
        print(f"주소 유사도: {best_match['score']:.1f}")
    else:
        print("주소 유사도 기준 미만입니다.")
        print("가장 유사한 DB 주소: ", best_match['address'])
        print(f"주소 유사도: {best_match['score']:.1f}")


test_rows = [
    {
        "company_name": "KB국민은행",
        "branch_name": "K-2(점)",
        "address": "대구광역시 동구 54 아양로 352",
    },
    {
        "company_name": "신한은행",
        "branch_name": "ASE코리아(출)",
        "address": "제주특별자치도 서귀포시 테스트로 999",
    },
    {
        "company_name": "우리은행",
        "branch_name": "BIFC금융센터",
        "address": "부산 남구 문현동 문현금융로 40",
    },
    {
        "company_name": "하나은행",
        "branch_name": "63빌딩",
        "address": "강원특별자치도 춘천시 테스트길 888",
    },
    {
        "company_name": "IBK기업은행",
        "branch_name": "MBC",
        "address": "서울특별시 마포구 상암동 성암로 267 1603",
    },
    {
        "company_name": "NH농협은행",
        "branch_name": "JDC첨단지점",
        "address": "인천광역시 강화군 테스트로 777",
    },
    {
        "company_name": "BNK부산은행",
        "branch_name": "W스퀘어",
        "address": "부산광역시 남구 (용호동) 566, 신선로",
    },
    {
        "company_name": "iM뱅크(구 대구은행)",
        "branch_name": "3공단영업부",
        "address": "전라남도 목포시 테스트길 666",
    },
    {
        "company_name": "엘에스증권",
        "branch_name": "SC제일CYBER",
        "address": "서울특별시 영등포구 여의나루로 60, 포스트타워 25층",
    },
    {
        "company_name": "케이뱅크",
        "branch_name": "Operation팀",
        "address": "충청북도 충주시 테스트로 555",
    },
]

for row in test_rows:
    company_name, code = find_bank_code(row["company_name"])
    print(company_name,code)
    find_sql(company_name,row["address"],code)