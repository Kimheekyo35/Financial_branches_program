import argparse
import json
import logging
import os
from pathlib import Path
import tempfile
import time

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://portal.kfb.or.kr/minwon/branch.php"

OUTPUT_DIR = Path(__file__).resolve().parent / "financial_json_dir"
OUTPUT_FILE = OUTPUT_DIR / "bank_branches.json"
LOGGER = logging.getLogger(__name__)

REQUEST_DELAY = 0.5
MAX_PAGE = 2000

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/141.0.0.0 Safari/537.36"
    )
}


# ============================================================
# 한 페이지 수집 함수
# ============================================================

def crawl_page(session, page_number, timeout=30):
    """
    주어진 페이지 번호의 은행 점포 데이터를 수집한다.

    반환값:
        branches:
            해당 페이지의 점포 데이터 목록

        page_signature:
            이전 페이지와 중복 여부를 확인하기 위한 값
    """

    params = {
        "idx": "",
        "col": "",
        "sw": "",
        "pg": page_number,
        "gubun": "",
        "orderby": "",
        "code": "",
        "data_year": "",
        "s_que1": "",
        "s_que2": "",
        "s_que3": "",
    }

    response = session.get(
        BASE_URL,
        params=params,
        headers=HEADERS,
        timeout=timeout,
    )

    response.raise_for_status()
    response.encoding = "cp949"

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    target_table = None
    for table in soup.find_all("table"):
        table_text = table.get_text(
            " ",
            strip=True,
        )

        required_headers = [
            "은행",
            "지점",
            "주소",
            "전화번호",
        ]

        if all(
            keyword in table_text
            for keyword in required_headers
        ):
            target_table = table
            break

    # 차단 페이지나 사이트 구조 변경을 정상적인 수집 완료로 처리하지 않는다.
    if target_table is None:
        raise ValueError("은행점포 결과 테이블을 찾을 수 없습니다.")

    branches = []

    for row in target_table.find_all("tr"):
        cells = row.find_all("td")

        # 데이터 행은 총 4개 컬럼
        if len(cells) != 4:
            continue

        values = [
            cell.get_text(
                " ",
                strip=True,
            )
            for cell in cells
        ]

        bank_name = values[0]
        branch_name = values[1]
        address = values[2]
        phone = values[3]

        # 헤더가 td로 되어 있는 경우 제외
        if (
            bank_name == "은행"
            and branch_name == "지점"
            and address == "주소"
        ):
            continue

        # 은행명 또는 지점명이 없는 빈 행 제외
        if not bank_name or not branch_name:
            continue

        branches.append({
            "source_page": page_number,
            "bank_name": bank_name,
            "branch_name": branch_name,
            "address": address,
            "phone": phone,
        })

    # 이전 페이지와 같은 내용인지 비교하기 위한 값
    page_signature = tuple(
        (
            branch["bank_name"],
            branch["branch_name"],
            branch["address"],
            branch["phone"],
        )
        for branch in branches
    )

    return branches, page_signature


def save_json(branches, output_file=OUTPUT_FILE):
    """같은 디렉터리의 임시 파일에 쓴 뒤 교체하여 불완전한 JSON을 방지한다."""
    output_file = Path(output_file).expanduser().resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=output_file.parent,
            prefix=f".{output_file.name}.", suffix=".tmp", delete=False,
        ) as json_file:
            temporary_path = Path(json_file.name)
            json.dump(branches, json_file, ensure_ascii=False, indent=2)
            json_file.write("\n")
        os.replace(temporary_path, output_file)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def create_session():
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    session.mount("https://", HTTPAdapter(max_retries=retries))
    return session


def positive_int(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("1 이상의 정수를 입력하세요.")
    return number


def nonnegative_float(value):
    number = float(value)
    if not 0 <= number < float("inf"):
        raise argparse.ArgumentTypeError("0 이상의 유한한 숫자를 입력하세요.")
    return number


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="전국은행연합회 은행점포 수집")
    parser.add_argument(
        "--output", type=Path,
        default=os.environ.get("BANK_CRAWLER_OUTPUT", str(OUTPUT_FILE)),
        help="저장할 JSON 경로 (환경변수: BANK_CRAWLER_OUTPUT)",
    )
    parser.add_argument("--max-pages", type=positive_int, default=MAX_PAGE)
    parser.add_argument("--delay", type=nonnegative_float, default=REQUEST_DELAY)
    parser.add_argument("--timeout", type=positive_int, default=30)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    output_file = args.output.expanduser().resolve()
    all_branches = []
    previous_signature = None
    total_pages = 0
    saved_count = 0
    LOGGER.info("은행점포 수집 시작 | 저장 위치: %s", output_file)

    try:
        with create_session() as session:
            for page_number in range(1, args.max_pages + 1):
                branches, current_signature = crawl_page(
                    session, page_number, timeout=args.timeout,
                )
                if not branches:
                    if not all_branches:
                        raise ValueError("첫 페이지에 은행점포 데이터가 없습니다.")
                    LOGGER.info("%s페이지에 데이터가 없어 수집 종료", page_number)
                    break
                if current_signature == previous_signature:
                    LOGGER.info("%s페이지가 이전 페이지와 동일하여 수집 종료", page_number)
                    break
                all_branches.extend(branches)
                save_json(all_branches, output_file)
                total_pages = page_number
                saved_count = len(all_branches)
                LOGGER.info(
                    "%s페이지 완료 | 현재 %s건 | 누적 %s건",
                    page_number, len(branches), len(all_branches),
                )
                previous_signature = current_signature
                if page_number < args.max_pages:
                    time.sleep(args.delay)
    except (requests.exceptions.RequestException, ValueError, OSError) as error:
        LOGGER.error("수집 실패: %s | 이번 실행에서 저장한 데이터: %s건", error, saved_count)
        return 1
    except KeyboardInterrupt:
        LOGGER.warning("수집 중단 | 마지막 저장 페이지: %s", total_pages)
        return 130

    LOGGER.info("수집 완료 | %s페이지 | %s건 | %s", total_pages, len(all_branches), output_file)
    if total_pages >= args.max_pages:
        LOGGER.warning("페이지 제한(%s)에 도달했습니다. 결과가 일부일 수 있습니다.", args.max_pages)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
