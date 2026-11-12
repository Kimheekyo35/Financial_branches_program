"""
지점명의 threshold와 주소의 threshold를
찾기 위한 코드 파일

지점명 : threshold = 85
주소 : threshold = 85
로 예정이지만 지점명에 가중치와 주소에 가중치를 조절해서
정답 확인할 예정
"""


import pandas as pd
from rapidfuzz import fuzz
from pathlib import Path
import unicodedata
import re
import json
from sklearn.metrics import precision_score, recall_score, f1_score


BASE = Path(__file__).parent/"financial_json_dir"

# 금융기관 지점 json 불러오기
with open(BASE/"all_jsonfile.json",encoding="utf-8") as f:
    company_info= json.load(f)

df = pd.read_csv(BASE/ "branch_name_similarity_dataset.csv", encoding="utf-8",)

# 지점 정규화 진행
def normalize_branch_name(name):
    if not name:
        return ""

    name = str(name).strip()

    # 공백과 일부 특수문자만 제거
    name = re.sub(r"[\s\-_/().]", "", name)

    # 반드시 긴 단어인 '지점'을 먼저 확인
    if name.endswith("지점"):
        name = name[:-2]
    elif name.endswith("점"):
        name = name[:-1]

    return name

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

df["branch_score"] = df.apply(lambda row:fuzz.ratio(normalize_branch_name(row["input_branch_name"]), row["reference_branch_name"]), axis=1)
df["address_score"] = df.apply(lambda row:fuzz.ratio(normalize_address(row["input_address"]),row["reference_address"]), axis=1)
df["combined_score"] = df.apply(lambda row: (row["branch_score"])*0.4 + (row["address_score"])*0.6,axis=1)

df.to_csv(BASE/ "rapidfuzz_test_result.csv", index=False, encoding="utf-8-sig")

result_csv = pd.read_csv(BASE / "rapidfuzz_test_result.csv", encoding="utf-8-sig")
# result_head = result_csv.head()

# Precision, Recall, F1 Score 계산
print(result_csv.describe())

for threshold in range(70,96):
    pred = (result_csv["combined_score"] >= threshold).astype(int)

    print(f"Threshold: {threshold}")
    print(f"Precision: {precision_score(result_csv['actual_match'], pred)}")
    print(f"Recall: {recall_score(result_csv['actual_match'], pred)}")
    print(f"F1 Score: {f1_score(result_csv['actual_match'], pred)}")
    print()

# df_csv = result_csv[["bank_name","input_branch_name","reference_branch_name","rapidfuzz_score"]]
# print(df_csv.head())