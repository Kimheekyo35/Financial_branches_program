# 은행점포 크롤러

Python 3.10 이상에서 실행합니다. Linux 서버에서는 다음과 같이 설치하고 실행합니다.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python bank_crawler.py
```

기본 결과는 스크립트가 있는 디렉터리의 `financial_json_dir/bank_branches.json`에
저장됩니다. 실행 디렉터리와 관계없이 같은 위치를 사용합니다.
다른 위치를 사용하려면 쓰기 가능한 경로를 지정하세요.

```bash
.venv/bin/python bank_crawler.py --output /data/bank_branches.json
```

`BANK_CRAWLER_OUTPUT` 환경변수로도 경로를 설정할 수 있습니다.
`--output`을 함께 지정하면 명령줄 설정이 우선합니다.

- `--max-pages 2000`: 최대 수집 페이지 수
- `--delay 0.5`: 페이지 사이 대기 시간(초)
- `--timeout 30`: 요청 연결 및 읽기 제한 시간(각각 초)

서버는 `https://portal.kfb.or.kr`에 HTTPS로 접근할 수 있어야 합니다.
프록시는 Requests의 `HTTPS_PROXY` 환경변수로 설정할 수 있습니다.
사내 인증서가 필요한 경우 PEM 인증서 번들 경로를 `REQUESTS_CA_BUNDLE`에 지정하세요.
TLS 인증서 검증은 활성화되어 있습니다.

로그는 표준 오류로 즉시 출력됩니다. 정상 완료는 종료 코드 0, 요청·파싱·저장 오류는
1, 사용자 중단은 130을 반환합니다. 일시적인 HTTP 오류는 최대 3회 재시도합니다.
페이지마다 JSON을 임시 파일에 기록한 뒤 교체하므로 중간 종료 시에도 마지막으로
저장한 JSON을 읽을 수 있습니다. 첫 페이지 수집 실패 시 기존 결과를 보존합니다.
수집 도중 실패하면 이번 실행에서 수집한 일부 데이터가 결과 파일에 남습니다.
동일한 출력 파일을 대상으로 여러 프로세스를 동시에 실행하지 마세요.

cron 등에서는 Python과 스크립트의 절대 경로를 사용하세요.

```cron
0 2 * * * /home/azureuser/CoE_ADC_auto/address_check/.venv/bin/python /home/azureuser/CoE_ADC_auto/address_check/bank_crawler.py >> /home/azureuser/CoE_ADC_auto/address_check/bank_crawler.log 2>&1
```

## 금융결제원 크롤러

같은 가상환경에서 Playwright와 Linux용 Chromium을 설치한 뒤 실행합니다.
`install --with-deps`는 시스템 라이브러리 설치 시 관리자 권한이 필요할 수 있습니다.
브라우저 설치와 크롤러 실행은 같은 사용자 계정으로 진행하세요.

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m playwright install --with-deps chromium
.venv/bin/python bank_crawler.py
.venv/bin/python kftc_crawler.py
```

화면이나 Edge 설치 없이 headless Chromium으로 실행합니다. 서버에서
`https://www.kftc.or.kr` 접근이 가능해야 합니다. 기본 결과 위치는 실행 디렉터리에
관계없이 스크립트 옆 `financial_json_dir`입니다. 기존 회사별 JSON 형식을 유지합니다.

```bash
.venv/bin/python kftc_crawler.py --output-dir /data/financial_json_dir --bank-file /data/bank_branches.json
.venv/bin/python kftc_crawler.py --company-code 050 --timeout 60
```

- `--output-dir`: 결과 디렉터리. 환경변수 `KFTC_CRAWLER_OUTPUT_DIR`로도 설정 가능
- `--bank-file`: 은행 중복 제외용 JSON. 환경변수 `KFTC_CRAWLER_BANK_FILE`로도 설정 가능
- `--company-code`: 선택 목록에 있는 코드만 수집. 여러 번 지정 가능
- `--timeout 30`: 브라우저 동작과 페이지 이동 제한 시간(초)
- `--delay 2`: 검색 및 페이지 이동 후 대기 시간(초)
- `--max-pages 2000`: 회사별 최대 페이지 수. 초과하면 실패 처리

명령줄 경로 설정이 환경변수보다 우선합니다. 은행 JSON의 `bank_code`가 있으면 코드로,
현재 은행 크롤러처럼 이름만 있으면 은행명으로도 중복을 제외합니다.
이름 비교 시 공백, 은행 접미어와 일부 브랜드 접두어(BNK, KB, NH 등)를 정리합니다.
은행 JSON에 없는 은행은 제외되지 않으므로 은행연합회 수집을 먼저 완료하세요.
은행 파일이 없거나 비어 있으면 오류로 종료합니다.

회사별 모든 페이지 수집에 성공한 뒤 임시 파일을 교체하므로 실패한 회사의 기존
JSON을 보존합니다. 이전에 완료한 회사 결과는 유지됩니다. 다음 버튼이 없는
단일 페이지도 저장하며, 페이지 반복이나 구조 변경을 감지하면 오류로 종료합니다.
이전에 생성된 결과 파일은 자동 삭제하지 않습니다.
같은 출력 디렉터리에 여러 수집 작업을 동시에 실행하지 마세요.

로그는 표준 오류에 출력합니다. 종료 코드는 정상 완료 0, 오류 1, 사용자 중단 130입니다.
cron에서는 Python과 스크립트의 절대 경로를 사용하세요.

```cron
0 3 * * * /home/azureuser/CoE_ADC_auto/address_check/.venv/bin/python /home/azureuser/CoE_ADC_auto/address_check/kftc_crawler.py >> /home/azureuser/CoE_ADC_auto/address_check/kftc_crawler.log 2>&1
```
