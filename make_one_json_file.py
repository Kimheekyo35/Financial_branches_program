import json
from pathlib import Path

code_list = []
BASE = Path(__file__).parent/"financial_json_dir"

# all_jsonfile.json을 한번 더 읽어서 데이터가 중복으로 쌓임
PASS_JSON = {"company_alias.json", "company_unique_value.json", "저축은행_050.json","savings_code.json", "savings_codes.backup.json","all_jsonfile.json"}

json_list = []
for json_file in BASE.glob("*.json"):
    if json_file.name in PASS_JSON:
        pass
    else:
        with open(json_file, encoding="utf-8") as f:
            new_dict = json.load(f)
            for data in new_dict:
                json_list.append(data)

with open(BASE/"all_jsonfile.json", 'w', encoding='utf-8') as f:
    json.dump(json_list, f, ensure_ascii=False, indent=4)

