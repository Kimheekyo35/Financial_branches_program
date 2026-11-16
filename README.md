# 금융거래조회서 주소 확인 프로그램

## 셸 종료 후에도 실행하기 (systemd)

Docker 없이 기존 Python 가상환경을 사용하는 Linux 서비스 설정은
`deploy/address-check.service`에 있습니다. 현재 서버의 사용자(`azureuser`)와
프로젝트 경로를 기준으로 작성했습니다. 다른 서버로 옮길 때는 `User`,
`WorkingDirectory`, `ExecStart`를 수정하세요.

프로젝트의 `.venv`, `.env`, `financial_json_dir` 및 기존 PostgreSQL을 그대로
사용합니다. 이 설정은 DB를 설치하거나 관리하지 않으므로 서버 재부팅 시
PostgreSQL도 자동으로 시작되도록 구성되어 있어야 합니다.

현재 수동으로 실행 중인 Streamlit이 있다면 해당 터미널에서 `Ctrl+C`로
종료하고 아래 명령을 프로젝트 디렉터리에서 실행하세요. 두 프로세스가
동시에 8501 포트를 사용할 수 없습니다.

```bash
sudo install -m 644 deploy/address-check.service /etc/systemd/system/address-check.service
sudo systemctl daemon-reload
sudo systemctl enable --now address-check.service
```

서비스는 셸이나 SSH 연결을 종료해도 실행됩니다. 프로세스가 종료되면
5초 후 재시작하고, 서버 재부팅 후에도 자동으로 시작합니다.
`systemctl stop`으로 직접 중지하면 즉시 재시작하지 않습니다.

```bash
# 실행 상태와 최근 로그
sudo systemctl status address-check.service --no-pager
sudo journalctl -u address-check.service -n 100 --no-pager

# 웹서버 응답 확인 (DB 조회 기능은 별도 확인 필요)
curl --fail http://127.0.0.1:8501/_stcore/health

# 코드 수정 후 재시작
sudo systemctl restart address-check.service

# 중지 / 부팅 시 자동 실행도 해제
sudo systemctl stop address-check.service
sudo systemctl disable address-check.service
```

접속 주소와 방화벽 설정은 기존과 동일합니다. 서비스 등록은 외부 접속
장애를 해결하는 설정과는 별개입니다.

