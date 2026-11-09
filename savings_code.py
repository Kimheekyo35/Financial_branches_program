"""
저축회사는 구분이 제대로 되어있지 않아서, branch_name 에서 회사 이름 갖고오고
회사 이름을 bank_name에 붙여야 함.
"""


import json, os
from collections import defaultdict
from pathlib import Path
import shutil
import unicodedata

BASE = Path(__file__).parent
CODES = BASE /"financial_json_dir"/"savings_code.json"              # {"하나저축은행": "050_033", ...}
SRC = BASE /"financial_json_dir"/"저축은행_050.json"
OUT = BASE / "financial_json_dir"/"저축은행_050_converted.json"
EXTRA_TOKENS = {"상상인플러스"}  # 상상인플러스에는 공백이 없어서 미리 토큰 넣어줌
UNIQUE_VALUES = BASE / "financial_json_dir"/"company_unique_value.json"

# 1) 기존 번호 읽기
if CODES.exists():
    shutil.copy(CODES, CODES.with_name("savings_codes.backup.json"))
    with open(CODES, encoding='utf-8') as f:
        codes = json.load(f)

else:
    codes = {}

code_map = {name:code for code, name in codes.items()}
last_no = max((int(c.split("_")[1]) for c in codes), default=0)

# 2) 원본 읽기
with open(SRC, encoding='utf-8') as f:
    records = json.load(f)

# 3) 변환
converted, unresolved = [], []
tokens = set(EXTRA_TOKENS)  # set은 같은 값을 한 번만 보관하는 목록

for r in records:
    r = dict(r)
    name = unicodedata.normalize("NFKC",str(r["branch_name"])).strip()
    if " " in name:
        tokens.add(name.split(" ")[0])

    hits = [t for t in tokens if name.startswith(t) and len(name) > len(t)]

    if not hits:
        unresolved.append(r)
        continue

    first =max(hits, key=len)  # ["상상인", "상상인플러스"]  이렇다면 제일 긴 거 선택, 내가 상상인플러스 필요하니까
    rest = name[len(first):].strip()   # 상상인플러스대전(지) 일 떄, 상상인플러스 | 대전(지) 이렇게 나눠짐

    new_name = first + r["bank_name"]
    r["branch_name"] = rest

    # 저축은행 고유 번호 만들기
    if new_name not in code_map:
        last_no += 1
        code = f"050_{last_no:03d}"
        code_map[new_name] = code
        codes[code] = new_name

    r["orig_bank_name"] = r["bank_name"]
    r["orig_branch_name"] = r["branch_name"]
    r["bank_name"] = new_name
    r["branch_name"] = rest
    r["bank_code"] = code_map[new_name]
    converted.append(r)


# 4) 저장하기
with open(OUT,"w",encoding="utf-8") as f:
    json.dump(converted,f,ensure_ascii=False,indent=4)
with open(CODES,"w",encoding="utf-8") as f:
    json.dump(codes,f,ensure_ascii=False,indent=2)

combined_list = []
# company_unique_value_combined.json 파일 만들기
with open(UNIQUE_VALUES,encoding="utf-8") as f:
    values = json.load(f)
    values.update(codes)   # dict 추가하는 건 update

# value랑 codes 합쳐서 바로 json에 저장하기 -> 해당 json 파일은 나중에 sql이 읽도록
with open(UNIQUE_VALUES,'w',encoding='utf-8') as f:
    json.dump(values,f,ensure_ascii=False, indent=4)
