"""
은행연합회에서는 은행별 고유 코드를 주지 않기 때문에 금결원에서 가져온 금융기관 별 고유 코드와 연결해야함.
그 과정에서 필요한 코드
"""

import json, re, unicodedata
from pathlib import Path

BASE = Path(__file__).parent/"financial_json_dir"

with open(BASE / "company_unique_value.json", encoding="utf-8") as f:
    unique = json.load(f)

with open(BASE / "company_alias.json", encoding="utf-8") as f:
    alias = json.load(f)

with open(BASE / "bank_branches.json", encoding="utf-8") as f:
    bank = json.load(f)

def norm(s):
    s = unicodedata.normalize("NFKC", str(s)).lower()
    return re.sub(r"[\s.\-·ㆍ/&()]", "", s)

name_to_code = {}
for code, v in alias.items():
    for a in [v["name"], *v["aliases"]]:
        name_to_code.setdefault(norm(a), set()).add(code)


def map_kfb(records):
    out, unmatched = [], set()
    for r in records:
        r = dict(r)
        codes = name_to_code.get(norm(r["bank_name"]), set())
        code = next(iter(codes)) if len(codes) == 1 else None
        r["bank_code"] = code
        if code is None:
            unmatched.add(r["bank_name"])
        out.append(r)

    return out
bank_result = map_kfb(bank)
with open(BASE/"bank_branches.json",'w',encoding='utf-8') as f:
    json.dump(bank_result,f,ensure_ascii=False,indent=4)