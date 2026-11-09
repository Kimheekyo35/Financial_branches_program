from pathlib import Path
import json
rows = []

with open(Path(__file__).parent/"financial_json_dir"/"all_jsonfile.json","r",encoding='utf-8') as line:
    json_to_dict = json.load(line)
    
    for data in json_to_dict:

        print(type(data))
        break