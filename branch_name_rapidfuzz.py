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


df["rapidfuzz_score"] = df.apply(lambda row:fuzz.ratio(normalize_branch_name(row["input_branch_name"]), row["reference_branch_name"]), axis=1)
# df["norm_bank_nm"] = df.apply(lambda row: norm_company(row["input_bank_name"]), axis=1)

# df.to_csv(BASE/ "rapidfuzz_test_result.csv", index=False, encoding="utf-8-sig")

result_csv = pd.read_csv(BASE / "rapidfuzz_test_result.csv", encoding="utf-8-sig")
# # result_head = result_csv.head()

# Precision, Recall, F1 Score 계산
print(result_csv.describe())

for threshold in range(70,100,5):
    pred = (result_csv["rapidfuzz_score"] >= threshold).astype(int)

    print(f"Threshold: {threshold}")
    print(f"Precision: {precision_score(result_csv['branch_actual_match'], pred)}")
    print(f"Recall: {recall_score(result_csv['branch_actual_match'], pred)}")
    print(f"F1 Score: {f1_score(result_csv['branch_actual_match'], pred)}")
    print()

# df_csv = result_csv[["bank_name","input_branch_name","reference_branch_name","rapidfuzz_score"]]
# print(df_csv.head())