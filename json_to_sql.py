import psycopg2
import json
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv(Path(__file__).parent/".env")


conn = psycopg2.connect(
    dbname = os.environ["DB_NAME"],
    user = os.environ["DB_USER"],
    password = os.environ["DB_PASSWORD"],
    host = os.environ["DB_HOST"],
    port= os.environ["DB_PORT"]
    )

rows = []

with open(Path(__file__).parent/"financial_json_dir"/"all_jsonfile.json","r",encoding='utf-8') as line:
    json_to_dict = json.load(line)
    
    for data in json_to_dict:
        row = (
            data["bank_name"],
            data["branch_name"],
            data["address"],
            data["bank_code"]
        )

        rows.append(row)

with conn:
    with conn.cursor() as cur:
        # 테이블 없으면 생성
        cur.execute("""
            CREATE TABLE IF NOT EXISTS FINANCIAL_BRANCHES (
            ID BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            BANK_NAME TEXT NOT NULL,
            BRANCH_NAME TEXT NOT NULL,
            ADDRESS TEXT NOT NULL,
            BANK_CODE TEXT
            )
            """)

        # 임시 테이블 생성
        cur.execute("""
            CREATE TEMP TABLE BRANCH_STAGING
            ON COMMIT DROP
            AS 
            SELECT BANK_NAME, BRANCH_NAME, ADDRESS, BANK_CODE
            FROM FINANCIAL_BRANCHES
            WITH NO DATA     
            """)

        # 새 데이터를 임시 테이블에 먼저 저장
        cur.executemany(
            """
            INSERT INTO BRANCH_STAGING
            (BANK_NAME, BRANCH_NAME, ADDRESS, BANK_CODE)
            VALUES (%s, %s, %s, %s)
            """,
            rows
        )
 
        # ID를 1부터 다시 시작
        cur.execute("TRUNCATE TABLE FINANCIAL_BRANCHES RESTART IDENTITY")

        # 새 데이터로 교체
        cur.execute("""
            INSERT INTO FINANCIAL_BRANCHES
            (BANK_NAME, BRANCH_NAME, ADDRESS, BANK_CODE)
            SELECT *
            FROM  BRANCH_STAGING
        """)

        conn.commit()

print(f"{len(rows)}개 행 저장 완료")
conn.close()