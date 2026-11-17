"""
금오공대 BISKIT 비교과 프로그램 크롤러
- 로그인은 사용자가 직접 수행
- 수집 데이터를 program_navigator DB에 직접 저장
  · program          : 텍스트 + 썸네일 바이너리
  · program_image    : 상세 페이지 이미지 바이너리
  · program_schedule : 회차별 일정
"""

import re
import time
import os
import sys
import json
import requests
import pymysql
from datetime import datetime, date
from urllib.parse import urljoin
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

BASE_URL = "https://biskit.kumoh.ac.kr"
CRAWLED_LOG = "crawled_urls.txt"
JSON_LOG = "crawled_programs.jsonl"

DB_CONFIG = {
    "host":          os.getenv("DB_HOST", "172.30.74.43"),
    "port":          int(os.getenv("DB_PORT", "3306")),
    "user":          os.getenv("DB_USER", "navi"),
    "password":      os.getenv("DB_PASS", "vo8Tm5dnj1em2"),
    "database":      os.getenv("DB_NAME", "program_navigator"),
    "charset":       "utf8mb4",
    "read_timeout":  120,
    "write_timeout": 120,
    **({"ssl": {}} if os.getenv("DB_SSL") == "1" else {}),
}

INSERT_PROGRAM_SQL = """
INSERT INTO program (
    title, summary, description_html, description_text,
    thumbnail_data, thumbnail_mime,
    category, organization, manager_name, manager_contact,
    recruit_start, recruit_end, edu_start, edu_end,
    location, target, capacity, applicant_count, waitlist_count,
    mileage, view_count, raw_data, created_at, updated_at
) VALUES (
    %s, %s, %s, %s,
    %s, %s,
    %s, %s, %s, %s,
    %s, %s, %s, %s,
    %s, %s, %s, %s, %s,
    %s, 0, %s, NOW(), NOW()
)
"""

INSERT_IMAGE_SQL = """
INSERT INTO program_image (program_id, image_type, sort_order, mime_type, image_data)
VALUES (%s, %s, %s, %s, %s)
"""

INSERT_SCHEDULE_SQL = """
INSERT INTO program_schedule (program_id, session_date, start_time, end_time)
VALUES (%s, %s, %s, %s)
"""

INSERT_FILE_SQL = """
INSERT INTO program_file (program_id, file_name, mime_type, file_data, chunk_index, total_chunks)
VALUES (%s, %s, %s, %s, %s, %s)
"""

UPDATE_PROGRAM_SQL = """
UPDATE program SET
    title = COALESCE(%s, title),
    description_html = %s, description_text = %s,
    category = %s, organization = %s, manager_name = %s, manager_contact = %s,
    recruit_start = %s, recruit_end = %s,
    edu_start = COALESCE(%s, edu_start), edu_end = COALESCE(%s, edu_end),
    location = %s, target = %s, capacity = COALESCE(%s, capacity),
    mileage = COALESCE(%s, mileage),
    applicant_count = COALESCE(%s, applicant_count),
    waitlist_count = COALESCE(%s, waitlist_count),
    raw_data = %s, updated_at = NOW()
WHERE program_id = %s
"""

FIELD_MAP = {
    # 제목
    "프로그램명": "title",      "과정명": "title",       "제목": "title",    "강좌명": "title",
    # 카테고리
    "프로그램 분류": "category", "분류": "category",     "카테고리": "category",
    # 조직
    "운영조직": "organization", "주관": "organization", "주관부서": "organization",
    # 담당자 (이름+연락처 같이 파싱)
    "담당자": "_manager",       "담당자명": "_manager",
    # 신청기간
    "신청기간": "_recruit_range", "모집기간": "_recruit_range",
    # 교육/운영기간
    "교육기간": "_edu_range",   "운영기간": "_edu_range",
    # 장소
    "교육장소/강사": "_location_instructor",
    "교육장소": "location",     "장소": "location",     "운영장소": "location",
    # 대상 / 신청조건 / 신청학년 → target에 순서대로 붙임
    "신청대상": "target",       "대상": "target",
    "신청조건": "_grade",       "신청학년": "_grade",
    # 정원/대기
    "정원/대기자": "_capacity_waitlist",
    "모집정원": "capacity",     "정원": "capacity",
    # 마일리지
    "마일리지": "mileage",
    # 본문
    "프로그램 주요내용": "_description",
    # 무시 (raw_data에만 저장)
    "선정방법": "_raw_only",    "취업진로교육": "_raw_only",  "키워드": "_keywords",
    "프로그램 유형": "_raw_only", "진로진출분야": "_raw_only", "첨부파일": "_attachment",
    "수료 인증서": "_raw_only", "운영년도 및 학기": "_raw_only",
    "출석관리": "_raw_only",    "진행속성": "_raw_only",      "과제제출": "_raw_only",
    "핵심역량 비중도": "_raw_only",
}


# ── DB ───────────────────────────────────────────────────────────────

def init_db():
    return pymysql.connect(**DB_CONFIG)


def save_program(conn, data: dict) -> int:
    raw = data.get("raw_data")
    raw_json = json.dumps(raw, ensure_ascii=False) if raw else None

    with conn.cursor() as cur:
        cur.execute(INSERT_PROGRAM_SQL, (
            data.get("title"),
            data.get("summary"),
            data.get("description_html"),
            data.get("description_text"),
            data.get("thumbnail_data"),
            data.get("thumbnail_mime"),
            data.get("category"),
            data.get("organization"),
            data.get("manager_name"),
            data.get("manager_contact"),
            data.get("recruit_start"),
            data.get("recruit_end"),
            data.get("edu_start"),
            data.get("edu_end"),
            data.get("location"),
            data.get("target"),
            data.get("capacity") or 0,
            data.get("applicant_count") or 0,
            data.get("waitlist_count") or 0,
            data.get("mileage") or 0,
            raw_json,
        ))
        last_id = cur.lastrowid
    conn.commit()
    return last_id


def update_program(conn, program_id: int, data: dict):
    raw = data.get("raw_data")
    raw_json = json.dumps(raw, ensure_ascii=False) if raw else None
    with conn.cursor() as cur:
        cur.execute(UPDATE_PROGRAM_SQL, (
            data.get("title"),
            data.get("description_html"),
            data.get("description_text"),
            data.get("category"),
            data.get("organization"),
            data.get("manager_name"),
            data.get("manager_contact"),
            data.get("recruit_start"),
            data.get("recruit_end"),
            data.get("edu_start"),
            data.get("edu_end"),
            data.get("location"),
            data.get("target"),
            data.get("capacity"),
            data.get("mileage"),
            data.get("applicant_count"),
            data.get("waitlist_count"),
            raw_json,
            program_id,
        ))
    conn.commit()


def delete_program(conn, program_id: int):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM program WHERE program_id = %s", (program_id,))
    conn.commit()


def save_tags(conn, program_id: int, keywords: list[str]):
    """키워드를 TAG 테이블에 upsert 후 PROGRAM_TAG 연결"""
    if not keywords:
        return
    with conn.cursor() as cur:
        for keyword in keywords:
            keyword = keyword.strip()
            if not keyword:
                continue
            # TAG 없으면 생성
            cur.execute(
                "INSERT IGNORE INTO tag (name, category) VALUES (%s, %s)",
                (keyword, "키워드")
            )
            # tag_id 조회
            cur.execute("SELECT tag_id FROM tag WHERE name = %s", (keyword,))
            row = cur.fetchone()
            if not row:
                continue
            tag_id = row[0]
            # PROGRAM_TAG 연결 (중복 무시)
            cur.execute(
                "INSERT IGNORE INTO program_tag (program_id, tag_id, confidence, source) "
                "VALUES (%s, %s, NULL, 'manual')",
                (program_id, tag_id)
            )
    conn.commit()


def save_images(conn, program_id: int, images: list[dict]):
    if not images:
        return
    with conn.cursor() as cur:
        for img in images:
            cur.execute(INSERT_IMAGE_SQL, (
                program_id,
                img["image_type"],
                img["sort_order"],
                img["mime_type"],
                img["image_data"],
            ))
    conn.commit()


def save_schedules(conn, program_id: int, schedules: list[dict]):
    if not schedules:
        return
    with conn.cursor() as cur:
        for s in schedules:
            start = s.get("start_time")
            end = s.get("end_time")
            if not start or not end:
                continue
            cur.execute(INSERT_SCHEDULE_SQL, (
                program_id,
                s["session_date"],
                start,
                end,
            ))
    conn.commit()


def save_files(conn, program_id: int, files: list[dict]):
    if not files:
        return
    CHUNK_SIZE = 4 * 1024 * 1024  # 4MB
    for f in files:
        data = f.get("file_data", b"")
        chunks = [data[i:i+CHUNK_SIZE] for i in range(0, max(len(data), 1), CHUNK_SIZE)]
        total = len(chunks)
        for idx, chunk in enumerate(chunks):
            for attempt in range(3):
                try:
                    try:
                        conn.ping(reconnect=True)
                    except Exception:
                        conn = init_db()
                    with conn.cursor() as cur:
                        cur.execute(INSERT_FILE_SQL, (
                            program_id,
                            f["file_name"],
                            f["mime_type"],
                            chunk,
                            idx,
                            total,
                        ))
                    conn.commit()
                    break
                except Exception as e:
                    if attempt == 2:
                        print(f"  파일 저장 실패 (3회 시도): {f.get('file_name')} chunk {idx} — {e}")
                    else:
                        time.sleep(2)


# ── 유틸 ─────────────────────────────────────────────────────────────

def parse_date(text: str):
    if not text:
        return None
    text = text.strip()
    for fmt in ("%Y.%m.%d", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:10], fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = re.search(r"(\d{4})[년.\-/]\s*(\d{1,2})[월.\-/]\s*(\d{1,2})", text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return None


def parse_range(text: str) -> tuple:
    parts = re.split(r"[~\-–—]", text)
    if len(parts) >= 2:
        return parse_date(parts[0]), parse_date(parts[1])
    return parse_date(text), None


def parse_int(text: str):
    if not text:
        return None
    m = re.search(r"\d+", text.replace(",", ""))
    return int(m.group()) if m else None


def load_crawled_urls() -> set:
    try:
        with open(CRAWLED_LOG, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    except FileNotFoundError:
        return set()


def mark_crawled(url: str):
    with open(CRAWLED_LOG, "a", encoding="utf-8") as f:
        f.write(url + "\n")


def save_to_json(program_id: int, url: str, data: dict):
    SKIP = {"thumbnail_data", "thumbnail_mime", "_attachments", "_keywords", "_schedules"}
    record = {"program_id": program_id, "detail_url": url}
    for k, v in data.items():
        if k not in SKIP and not isinstance(v, (bytes, bytearray)):
            record[k] = v
    with open(JSON_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def make_session(driver):
    session = requests.Session()
    for cookie in driver.get_cookies():
        session.cookies.set(cookie["name"], cookie["value"])
    headers = {"User-Agent": driver.execute_script("return navigator.userAgent")}
    return session, headers


def fetch_image(session, headers, img_url: str) -> tuple[bytes, str] | tuple[None, None]:
    """이미지 바이너리와 mime_type 반환. 실패 시 (None, None)"""
    try:
        resp = session.get(img_url, headers=headers, timeout=10)
        resp.raise_for_status()
        if b"<html" in resp.content[:100].lower():
            return None, None
        mime = resp.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
        return resp.content, mime
    except Exception:
        return None, None


# ── Selenium ─────────────────────────────────────────────────────────

AUTO_MODE = "--auto" in sys.argv
MAX_PAGES = int(os.getenv("MAX_PAGES", "15"))
DEBUG_ONLY = os.getenv("DEBUG_ONLY", "0") == "1"
REFRESH_MODE = "--refresh" in sys.argv  # 신청자 수 갱신 전용 모드


def create_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--window-size=1280,900")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    if AUTO_MODE:
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-popup-blocking")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(30)
    return driver


def login(driver):
    biskit_id = os.getenv("BISKIT_ID", "")
    biskit_pw = os.getenv("BISKIT_PW", "")

    if biskit_id and biskit_pw:
        _auto_login(driver, biskit_id, biskit_pw)
    else:
        driver.get(BASE_URL)
        print("Browser opened. Please log in manually.")
        input("\nPress Enter after login...")


def _auto_login(driver, student_id: str, password: str):
    wait = WebDriverWait(driver, 10)
    print("Auto login...")

    # 1단계: 메인 → 로그인 버튼 클릭
    driver.get(BASE_URL)
    time.sleep(2)
    print(f"  Step 1: current URL = {driver.current_url}")
    wait.until(EC.element_to_be_clickable((By.XPATH,
        "//a[contains(text(),'로그인') or contains(@href,'login') or contains(@class,'login')]"
    ))).click()
    time.sleep(2)

    # 2단계: 포털계정 화면 → 로그인 버튼 클릭
    print(f"  Step 2: current URL = {driver.current_url}, windows = {len(driver.window_handles)}")
    wait = WebDriverWait(driver, 10)

    # 포털계정 로그인 버튼 클릭 (아이콘+텍스트 혼합 버튼이므로 normalize-space 사용)
    btns = driver.find_elements(By.XPATH,
        "//*[self::a or self::button][contains(normalize-space(),'로그인')]"
    )
    print(f"  Step 2: found {len(btns)} login buttons")
    # 파란 로그인 버튼이 여러 개일 수 있으므로 '포털' 탭 안의 버튼 우선
    portal_btn = next(
        (b for b in btns if '포털' not in b.text and b.is_displayed()), None
    ) or (btns[0] if btns else None)
    if portal_btn:
        portal_btn.click()
    time.sleep(2)

    # 3단계: 통합 로그인 → 아이디/비밀번호 입력
    print(f"  Step 3: current URL = {driver.current_url}, windows = {len(driver.window_handles)}")
    wait = WebDriverWait(driver, 15)
    if len(driver.window_handles) > 1:
        driver.switch_to.window(driver.window_handles[-1])
        print(f"  Step 3: switched to new window = {driver.current_url}")

    # 비밀번호 필드가 뜰 때까지 대기 후, 모든 visible input 중 첫 번째를 ID 필드로 사용
    pw_field = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR,
        "input[type='password']"
    )))
    all_inputs = driver.find_elements(By.CSS_SELECTOR,
        "input[type='text'], input[type='email'], input:not([type='password']):not([type='hidden'])"
    )
    id_field = next((el for el in all_inputs if el.is_displayed()), None)
    if id_field is None:
        raise Exception("ID input field not found")
    id_field.clear()
    id_field.send_keys(student_id)
    pw_field.clear()
    pw_field.send_keys(password)
    pw_field.send_keys(Keys.RETURN)
    time.sleep(3)

    # 로그인 완료 대기
    try:
        WebDriverWait(driver, 30).until(
            lambda d: "biskit.kumoh.ac.kr" in d.current_url
                      and "login" not in d.current_url.lower()
                      and "sso" not in d.current_url.lower()
        )
    except Exception:
        print(f"  Login redirect failed. current URL = {driver.current_url}")
        print(f"  Page title = {driver.title}")
        raise
    if len(driver.window_handles) > 1:
        driver.switch_to.window(driver.window_handles[0])
    print("Login successful!")


# ── 공통 헬퍼 ─────────────────────────────────────────────────────────

def _recruit_start_from_card(list_text: str) -> str | None:
    """목록 카드 텍스트에서 신청 시작일 파싱"""
    lines = list_text.splitlines()
    for idx, line in enumerate(lines):
        if "신청기간" in line:
            val = line.split(":", 1)[-1].strip() if ":" in line else ""
            if not val and idx + 1 < len(lines):
                val = lines[idx + 1].strip()
            start, _ = parse_range(val)
            return start
    return None


def _advance_page(driver, page: int) -> int | None:
    """다음 페이지로 이동. 성공 시 다음 페이지 번호, 없으면 None."""
    next_page = page + 1
    if driver.execute_script(
        "return typeof global !== 'undefined' && typeof global.page === 'function';"
    ):
        has_next = driver.execute_script(f"""
            var links = document.querySelectorAll('.pageList a, .paging a, .pagination a');
            for (var i = 0; i < links.length; i++) {{
                if (links[i].textContent.trim() === '{next_page}') return true;
            }}
            var nextBtn = document.querySelector('a[onclick*="page({next_page})"]');
            return nextBtn !== null;
        """)
        if not has_next:
            return None
        driver.execute_script(f"global.page({next_page});")
        time.sleep(1.5)
        return next_page
    else:
        try:
            next_btn = driver.find_element(By.XPATH,
                "//a[contains(@class,'next') or text()='다음' or @title='다음']"
            )
            cls = next_btn.get_attribute("class") or ""
            if "disabled" in cls or "off" in cls:
                return None
            next_btn.click()
            time.sleep(1.5)
            return next_page
        except Exception:
            return None


def _save_list_preview(conn, item: dict, session, headers) -> int:
    """목록 카드를 미리보기로 DB 저장. item에 card 파싱 결과를 업데이트하고 program_id 반환."""
    title = extract_title_from_list(item["list_text"])
    summary = extract_summary_from_list(item["list_text"])
    card = parse_list_card(item["list_text"])
    item.update(card)
    thumb_data, thumb_mime = None, None
    thumb_src = item.get("thumbnail_src")
    if thumb_src and is_program_image(thumb_src):
        thumb_data, thumb_mime = fetch_image(session, headers, thumb_src)
    return save_program(conn, {
        "title": title, "summary": summary,
        "thumbnail_data": thumb_data, "thumbnail_mime": thumb_mime,
        "capacity": card.get("capacity", 0),
        "applicant_count": card.get("applicant_count", 0),
        "waitlist_count": card.get("waitlist_count", 0),
        "mileage": card.get("mileage", 0),
        "edu_start": card.get("edu_start"),
        "edu_end": card.get("edu_end"),
    })


def _process_detail(driver, conn, item: dict) -> bool:
    """상세 페이지 크롤링 + DB 저장. 성공 시 True, 필터/오류 시 False."""
    url = item["detail_url"]
    data = extract_detail(driver, item)

    recruit_start = data.get("recruit_start")
    if not recruit_start or recruit_start < "2026-09-01":
        preview_id = item.get("program_id")
        if preview_id:
            delete_program(conn, preview_id)
            print(f"    -> recruit_start={recruit_start or 'None'} - deleted preview (id={preview_id})")
        else:
            print(f"    -> recruit_start={recruit_start or 'None'} - skip")
        return False

    schedules = data.pop("_schedules", []) or extract_schedules(driver)
    images = collect_images(driver, item)
    session, headers = make_session(driver)
    attach_files = collect_attachments(session, headers, data.get("_attachments", []))

    op_method = item.get("operation_method")
    if op_method:
        if isinstance(data.get("raw_data"), dict):
            data["raw_data"]["운영방법"] = op_method
        else:
            data["raw_data"] = {"운영방법": op_method}

    program_id = item.get("program_id")
    if program_id:
        data["applicant_count"] = item.get("applicant_count")
        data["waitlist_count"] = item.get("waitlist_count")
        update_program(conn, program_id, data)
    else:
        thumb = next((img for img in images if img["image_type"] == "thumbnail"), None)
        data["thumbnail_data"] = thumb["image_data"] if thumb else None
        data["thumbnail_mime"] = thumb["mime_type"] if thumb else None
        program_id = save_program(conn, data)

    save_schedules(conn, program_id, schedules)
    save_images(conn, program_id, images)
    save_files(conn, program_id, attach_files)
    save_tags(conn, program_id, data.get("_keywords", []))

    mark_crawled(url)
    save_to_json(program_id, url, data)
    print(f"    -> 저장: '{data.get('title', '')}' "
          f"(id={program_id}, images={len(images)}, files={len(attach_files)})")
    return True


# ── 목록 수집 ─────────────────────────────────────────────────────────

def collect_items(driver, list_url: str, conn=None) -> list[dict]:
    driver.get(list_url)
    time.sleep(2)
    items = []
    page = 1
    session, headers = make_session(driver)

    while True:
        print(f"  Collecting page {page}...")
        rows = driver.find_elements(By.CSS_SELECTOR,
            "table tbody tr, .list-item, .card-item, li.program-item"
        )
        rows = [r for r in rows if r.text.strip()]

        for row in rows:
            item = {}
            try:
                btn = row.find_element(By.CSS_SELECTOR, "a.detailBtn")
                params = json.loads(btn.get_attribute("data-params") or "{}")
                enc_seq = params.get("encSddpbSeq", "")
                page_no = params.get("paginationInfo.currentPageNo", "1")
                if enc_seq:
                    item["detail_url"] = (
                        f"{BASE_URL}/ptfol/imng/icmpNsbjtPgm/findIcmpNsbjtPgmInfo.do"
                        f"?encSddpbSeq={enc_seq}&paginationInfo.currentPageNo={page_no}"
                    )
            except Exception:
                pass
            try:
                img = row.find_element(By.TAG_NAME, "img")
                src = img.get_attribute("src") or ""
                if src and not src.startswith("data:"):
                    item["thumbnail_src"] = urljoin(list_url, src)
            except Exception:
                pass
            item["list_text"] = row.text.strip()
            if not (item.get("detail_url") or item.get("thumbnail_src")):
                continue

            recruit_start = _recruit_start_from_card(item["list_text"])
            if recruit_start and recruit_start < "2026-09-01":
                continue

            if conn and item.get("detail_url"):
                item["program_id"] = _save_list_preview(conn, item, session, headers)
                print(f"    -> saved preview: {item['list_text'][:50]} (id={item['program_id']})")
            items.append(item)

        print(f"    -> {len(rows)} rows processed (total {len(items)})")

        if MAX_PAGES and page >= MAX_PAGES:
            print(f"  Reached MAX_PAGES={MAX_PAGES}, stopping.")
            break

        next_p = _advance_page(driver, page)
        if next_p is None:
            break
        page = next_p

    return items


def collect_items_by_click(driver, list_url: str) -> list[dict]:
    driver.get(list_url)
    time.sleep(2)
    items = []
    seen_urls = set()
    page = 1

    while True:
        print(f"  Collecting page {page} (click method)...")
        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        rows = [r for r in rows if r.text.strip()]

        for i in range(len(rows)):
            try:
                rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
                rows = [r for r in rows if r.text.strip()]
                row = rows[i]
                thumbnail_src = None
                try:
                    img = row.find_element(By.TAG_NAME, "img")
                    src = img.get_attribute("src") or ""
                    if src and not src.startswith("data:"):
                        thumbnail_src = urljoin(list_url, src)
                except Exception:
                    pass
                list_text = row.text.strip()
                row.click()
                time.sleep(1.2)
                url = driver.current_url
                if url not in seen_urls and url != list_url:
                    seen_urls.add(url)
                    items.append({"detail_url": url, "thumbnail_src": thumbnail_src, "list_text": list_text})
                driver.back()
                time.sleep(1.2)
            except Exception:
                continue

        try:
            next_btn = driver.find_element(By.XPATH,
                "//a[contains(@class,'next') or text()='다음' or @title='다음']"
            )
            cls = next_btn.get_attribute("class") or ""
            if "disabled" in cls or "off" in cls:
                break
            if MAX_PAGES and page >= MAX_PAGES:
                print(f"  Reached MAX_PAGES={MAX_PAGES}, stopping.")
                break
            next_btn.click()
            page += 1
            time.sleep(1.5)
        except Exception:
            break

    return items


# ── 필드별 특수 파서 ──────────────────────────────────────────────────

def parse_manager(val: str) -> tuple[str, str]:
    """'김도영(0544787965)' or '김도영 ( 054-478-7965 )' → (이름, 연락처)"""
    m = re.match(r"(.+?)\s*[\(（]\s*([0-9\-.\s]+)\s*[\)）]", val)
    if m:
        return m.group(1).strip(), re.sub(r"[\s]", "", m.group(2))
    return val.strip(), ""


def parse_capacity_waitlist(val: str) -> tuple[int | None, int | None]:
    """'정원 10명 / 대기자 10명' → (10, 10)"""
    cap = re.search(r"정원\s*(\d+)", val)
    wait = re.search(r"대기자\s*(\d+)", val)
    return (int(cap.group(1)) if cap else None,
            int(wait.group(1)) if wait else None)


def parse_location_instructor(val: str) -> str:
    """'비대면/학과별 강사님 매칭' → '비대면'"""
    return val.split("/")[0].strip()


def parse_list_card(list_text: str) -> dict:
    """목록 카드에서 신청자수/정원/대기자수/마일리지/운영방법/교육기간 파싱
    실제 포맷: '신청자10명', '모집정원10명', '대기자3명', '마일리지33Point', '운영방법 : 온라인'
    교육기간 포맷: '교육기간 :\n2026.11.16 00:00 ~ 2026.12.15 00:00'
    """
    result = {}
    m = re.search(r"신청자(\d+)명", list_text)
    if m:
        result["applicant_count"] = int(m.group(1))
    m = re.search(r"모집정원(\d+)명", list_text)
    if m:
        result["capacity"] = int(m.group(1))
    m = re.search(r"대기자(\d+)명", list_text)
    if m:
        result["waitlist_count"] = int(m.group(1))
    m = re.search(r"마일리지(\d+)Point", list_text)
    if m:
        result["mileage"] = int(m.group(1))
    m = re.search(r"운영방법\s*:\s*(\S+)", list_text)
    if m:
        result["operation_method"] = m.group(1).strip()
    # 교육기간: "교육기간 :\n날짜범위" 형식
    lines = list_text.splitlines()
    for idx, line in enumerate(lines):
        if "교육기간" in line and idx + 1 < len(lines):
            val = line.split(":", 1)[-1].strip() if ":" in line else ""
            if not val:
                val = lines[idx + 1].strip()
            edu_start, edu_end = parse_range(val)
            if edu_start:
                result["edu_start"] = edu_start
            if edu_end:
                result["edu_end"] = edu_end
            break
    return result


def extract_title_from_list(list_text: str) -> str:
    """목록 카드에서 프로그램 제목 추출.
    구조: 조직명 → 역량들 → 운영방법 → [제목] → 요약 → 필드들
    """
    skip_keywords = ['역량', '운영방법', '신청대상', '신청조건', '신청기간', '신청학년',
                     '교육기간', '담당자', '신청자', '모집정원', '대기자', '마일리지',
                     '모집중', '마감', '신청종료']
    lines = [l.strip() for l in list_text.splitlines() if l.strip()]
    for i, line in enumerate(lines):
        if i == 0:  # 첫 줄은 조직명
            continue
        if any(kw in line for kw in skip_keywords):
            continue
        if len(line) < 5:
            continue
        return line[:200]
    return lines[0][:200] if lines else ""


def extract_summary_from_list(list_text: str) -> str:
    """목록 카드 텍스트에서 짧은 소개 추출 (제목 다음 줄)"""
    skip_keywords = ['역량', '운영방법', '신청대상', '신청조건', '신청기간', '신청학년',
                     '교육기간', '담당자', '신청자', '모집정원', '대기자', '마일리지',
                     '모집중', '마감', '신청종료']
    lines = [l.strip() for l in list_text.splitlines() if l.strip()]
    title_found = False
    for i, line in enumerate(lines):
        if i == 0:
            continue
        if any(kw in line for kw in skip_keywords):
            continue
        if len(line) < 5:
            continue
        if not title_found:
            title_found = True  # 이 줄이 제목
            continue
        # 제목 다음 줄 중 메타데이터가 아닌 첫 번째 줄 = 요약
        # "신청기간 :" 처럼 줄 끝에 : 가 오는 경우만 메타데이터로 판단
        if not line.rstrip().endswith(":"):
            return line[:500]
    return ""



# ── 상세 파싱 ─────────────────────────────────────────────────────────

def extract_detail(driver, item: dict) -> dict:
    url = item["detail_url"]
    try:
        driver.get(url)
    except Exception:
        pass  # 페이지 로드 타임아웃 — 로딩된 내용으로 파싱 시도
    time.sleep(1.5)

    data = {}
    raw_data = {}
    schedules_from_detail = []

    for row in driver.find_elements(By.CSS_SELECTOR, "table tr"):
        ths = row.find_elements(By.TAG_NAME, "th")
        tds = row.find_elements(By.TAG_NAME, "td")
        for th, td in zip(ths, tds):
            key = th.text.strip()
            val = td.text.strip()
            if not key:
                continue

            raw_data[key] = val
            col = FIELD_MAP.get(key)

            if col == "_keywords":
                # td 안의 span/li/a 개별 텍스트로 분리
                spans = td.find_elements(By.CSS_SELECTOR, "span, li, a, em")
                if spans:
                    keywords = [s.text.strip() for s in spans if s.text.strip()]
                else:
                    # 자식 요소 없으면 텍스트를 공백/쉼표로 분리 시도
                    keywords = [k.strip() for k in re.split(r"[,\s]+", val) if k.strip()]
                data["_keywords"] = keywords
                raw_data[key] = keywords
                continue

            if col is None:
                # N회차 패턴 → schedule
                if re.match(r"^\d+회차$", key):
                    m = re.search(
                        r"(\d{4}\.\d{2}\.\d{2}).+?~\s*(\d{4}\.\d{2}\.\d{2})", val
                    )
                    if m:
                        schedules_from_detail.append({
                            "session_date": parse_date(m.group(1)),
                            "start_time": None,
                            "end_time": None,
                        })
                continue

            if col == "_raw_only":
                continue
            elif col == "_attachment":
                att_list = []
                for a in td.find_elements(By.TAG_NAME, "a"):
                    href = a.get_attribute("href") or ""
                    if href and "javascript" not in href:
                        att_list.append({"url": urljoin(BASE_URL, href), "name": a.text.strip()})
                if att_list:
                    data["_attachments"] = att_list
                    raw_data[key] = [att["name"] for att in att_list]
                else:
                    raw_data[key] = val
                continue
            elif col == "_recruit_range":
                data["recruit_start"], data["recruit_end"] = parse_range(val)
            elif col == "_edu_range":
                data["edu_start"], data["edu_end"] = parse_range(val)
            elif col == "_manager":
                data["manager_name"], data["manager_contact"] = parse_manager(val)
            elif col == "_capacity_waitlist":
                data["capacity"], data["waitlist_count"] = parse_capacity_waitlist(val)
            elif col == "_location_instructor":
                data["location"] = parse_location_instructor(val)
            elif col == "_description":
                data["description_text"] = val
                data["description_html"] = td.get_attribute("innerHTML").strip()
            elif col == "_grade":
                # 신청학년은 target에 덧붙임
                existing = data.get("target", "")
                data["target"] = (existing + " / " + val).strip(" /") if existing else val
            elif col == "mileage":
                data["mileage"] = parse_int(val)
            elif col == "capacity":
                data["capacity"] = parse_int(val)
            elif col:
                data[col] = val

    data["summary"] = extract_summary_from_list(item.get("list_text", ""))

    # title 없으면 목록 카드에서 추출
    if not data.get("title"):
        data["title"] = extract_title_from_list(item.get("list_text", ""))

    data["raw_data"] = raw_data
    data["_schedules"] = schedules_from_detail
    return data


def extract_schedules(driver) -> list[dict]:
    schedules = []
    for row in driver.find_elements(By.CSS_SELECTOR, "table tr"):
        cells = row.find_elements(By.TAG_NAME, "td")
        if len(cells) >= 2:
            date = parse_date(cells[0].text)
            if date:
                times = cells[1].text.strip() if len(cells) > 1 else ""
                start, end = None, None
                m = re.search(r"(\d{1,2}:\d{2})\s*[~\-]\s*(\d{1,2}:\d{2})", times)
                if m:
                    start, end = m.group(1) + ":00", m.group(2) + ":00"
                schedules.append({"session_date": date, "start_time": start, "end_time": end})
    return schedules


# 실제 프로그램 이미지가 아닌 URL 패턴 (필터링 대상)
SKIP_IMG_PATTERNS = [
    "userPhoto.do",   # 담당자 프로필 사진
    "cmnFile/download.do",  # 첨부파일 다운로드 (HWP 등)
    "/common/images/",      # 공통 UI 이미지
    "/css/images/",         # CSS 아이콘
]


def is_program_image(url: str) -> bool:
    return not any(p in url for p in SKIP_IMG_PATTERNS)


def collect_images(driver, item: dict) -> list[dict]:
    """썸네일 + 상세 페이지 이미지 바이너리 수집"""
    session, headers = make_session(driver)
    images = []

    # 목록 썸네일
    thumb_src = item.get("thumbnail_src")
    if thumb_src and is_program_image(thumb_src):
        data, mime = fetch_image(session, headers, thumb_src)
        if data:
            images.append({"image_type": "thumbnail", "sort_order": 0,
                           "mime_type": mime, "image_data": data})

    # 상세 페이지 이미지 (프로그램 관련만)
    order = 1
    for img in driver.find_elements(By.TAG_NAME, "img"):
        src = img.get_attribute("src") or ""
        if not src or src.startswith("data:"):
            continue
        img_url = urljoin(driver.current_url, src)
        if img_url == thumb_src or not is_program_image(img_url):
            continue
        data, mime = fetch_image(session, headers, img_url)
        if data:
            images.append({"image_type": "detail", "sort_order": order,
                           "mime_type": mime, "image_data": data})
            order += 1

    return images


def collect_attachments(session, headers, attachments: list[dict]) -> list[dict]:
    """첨부파일 바이너리 수집 (HWP, PDF 등)"""
    files = []
    for att in attachments:
        url = att.get("url")
        if not url:
            continue
        try:
            resp = session.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
            cd = resp.headers.get("Content-Disposition", "")
            fname = att.get("name", "")
            if not fname:
                m = re.search(r'filename[*]?=["\']?([^"\';\r\n]+)', cd)
                if m:
                    fname = m.group(1).strip()
            mime = resp.headers.get("Content-Type", "application/octet-stream").split(";")[0].strip()
            files.append({
                "file_name": fname[:255] if fname else None,
                "mime_type": mime,
                "file_data": resp.content,
            })
        except Exception:
            continue
    return files


# ── 일일 갱신 ─────────────────────────────────────────────────────────

def daily_refresh(driver, conn, list_url: str):
    """매일 갱신용
    - 새 프로그램: 상세 페이지까지 풀 크롤링
    - 기존 프로그램(신청기간 유효): applicant_count / waitlist_count만 UPDATE
    """
    # 1. 기존 크롤링 기록에서 crawled encSddpbSeq 추출
    crawled_seqs = set()
    for u in load_crawled_urls():
        m = re.search(r"encSddpbSeq=([^&]+)", u)
        if m:
            crawled_seqs.add(m.group(1))

    # 2. DB에서 신청기간 유효한 program_id → encSddpbSeq 매핑
    today = date.today().strftime("%Y-%m-%d")
    with conn.cursor() as cur:
        cur.execute(
            "SELECT program_id FROM program WHERE recruit_end >= %s OR recruit_end IS NULL",
            (today,)
        )
        active_ids = {row[0] for row in cur.fetchall()}

    seq_to_id = {}
    try:
        with open(JSON_LOG, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    record = json.loads(line)
                except Exception:
                    continue
                pid = record.get("program_id")
                url = record.get("detail_url", "")
                m = re.search(r"encSddpbSeq=([^&]+)", url)
                if pid in active_ids and m:
                    seq_to_id[m.group(1)] = pid
    except FileNotFoundError:
        pass

    refresh_target_seqs = set(seq_to_id.keys())
    print(f"신청자 수 갱신 대상: {len(refresh_target_seqs)}개")

    # 3. 목록 페이지 순회
    session, headers = make_session(driver)
    new_items = []
    driver.get(list_url)
    time.sleep(2)
    page = 1
    count_updated = 0

    while True:
        rows = driver.find_elements(By.CSS_SELECTOR,
            "table tbody tr, .list-item, .card-item, li.program-item"
        )
        rows = [r for r in rows if r.text.strip()]

        for row in rows:
            item = {}
            enc_seq = ""
            try:
                btn = row.find_element(By.CSS_SELECTOR, "a.detailBtn")
                params = json.loads(btn.get_attribute("data-params") or "{}")
                enc_seq = params.get("encSddpbSeq", "")
                page_no = params.get("paginationInfo.currentPageNo", "1")
                if enc_seq:
                    item["detail_url"] = (
                        f"{BASE_URL}/ptfol/imng/icmpNsbjtPgm/findIcmpNsbjtPgmInfo.do"
                        f"?encSddpbSeq={enc_seq}&paginationInfo.currentPageNo={page_no}"
                    )
            except Exception:
                continue

            if not enc_seq:
                continue

            if enc_seq in crawled_seqs:
                # 기존 프로그램 — 신청기간 유효한 것만 신청자 수 갱신
                if enc_seq in refresh_target_seqs:
                    program_id = seq_to_id[enc_seq]
                    card = parse_list_card(row.text.strip())
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE program SET "
                            "applicant_count = COALESCE(%s, applicant_count), "
                            "waitlist_count = COALESCE(%s, waitlist_count), "
                            "updated_at = NOW() "
                            "WHERE program_id = %s",
                            (card.get("applicant_count"), card.get("waitlist_count"), program_id)
                        )
                    conn.commit()
                    refresh_target_seqs.discard(enc_seq)
                    count_updated += 1
                    print(f"  [갱신] id={program_id}, "
                          f"신청자={card.get('applicant_count')}, 대기={card.get('waitlist_count')}")
            else:
                # 새 프로그램 — 목록 카드 수집 후 상세 크롤링 큐에 추가
                try:
                    img = row.find_element(By.TAG_NAME, "img")
                    src = img.get_attribute("src") or ""
                    if src and not src.startswith("data:"):
                        item["thumbnail_src"] = urljoin(list_url, src)
                except Exception:
                    pass
                item["list_text"] = row.text.strip()

                recruit_start = _recruit_start_from_card(item["list_text"])
                if recruit_start and recruit_start < "2026-09-01":
                    continue

                item["program_id"] = _save_list_preview(conn, item, session, headers)
                new_items.append(item)
                print(f"  [신규] 발견: {item['list_text'][:50]} (id={item['program_id']})")

        if MAX_PAGES and page >= MAX_PAGES:
            print(f"  MAX_PAGES={MAX_PAGES} 도달, 중단")
            break

        next_p = _advance_page(driver, page)
        if next_p is None:
            break
        page = next_p

    print(f"\n목록 순회 완료 — 신청자 수 갱신 {count_updated}개, 신규 발견 {len(new_items)}개")

    # 4. 새 프로그램 상세 크롤링
    if not new_items:
        return

    print("\n[신규 프로그램 상세 크롤링...]")
    success = 0
    for i, item in enumerate(new_items, 1):
        if not item.get("detail_url"):
            continue
        print(f"  ({i}/{len(new_items)}) {item['detail_url']}")
        try:
            try:
                conn.ping(reconnect=True)
            except Exception:
                conn = init_db()
            if _process_detail(driver, conn, item):
                success += 1
        except Exception as e:
            print(f"    -> error: {e}")
    print(f"신규 프로그램 저장 완료: {success}/{len(new_items)}개")


# ── 메인 ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Connecting to MySQL...")
    conn = init_db()
    print("DB connected!")

    driver = create_driver()
    try:
        login(driver)

        list_url = os.getenv("BISKIT_LIST_URL", "").strip()
        if not list_url:
            print("\nPlease navigate to the program list page in the browser.")
            list_url = input("Paste list page URL: ").strip()

        if REFRESH_MODE:
            print("\n[Refresh mode] 일일 갱신 시작...")
            daily_refresh(driver, conn, list_url)
            conn.close()
            if not AUTO_MODE:
                input("\nPress Enter to close browser...")
            driver.quit()
            exit(0)

        if DEBUG_ONLY:
            import json as _json
            driver.get(list_url)
            time.sleep(2)
            btn = driver.find_element(By.CSS_SELECTOR, "a.detailBtn")
            params = _json.loads(btn.get_attribute("data-params"))
            enc_seq = params.get("encSddpbSeq", "")
            print(f"DEBUG: encSddpbSeq = {enc_seq}")
            # JS로 클릭 후 URL/내용 변화 확인
            driver.execute_script("arguments[0].click();", btn)
            time.sleep(2)
            print(f"DEBUG: after JS click URL = {driver.current_url}")
            # POST 시도
            session, headers = make_session(driver)
            for suffix in ["findIcmpNsbjtPgmDtl.do", "findIcmpNsbjtPgmWrite.do", "write.do"]:
                url = f"{BASE_URL}/ptfol/imng/icmpNsbjtPgm/{suffix}"
                resp = session.post(url, data={"encSddpbSeq": enc_seq}, headers=headers, timeout=10)
                print(f"DEBUG: POST {suffix} -> {resp.status_code}, text[:100]={resp.text[:100]}")
            conn.close()
            driver.quit()
            exit(0)

        print("\n[Step 1] Collecting list items + saving previews...")
        items = collect_items(driver, list_url, conn)
        if not any(isinstance(i.get("detail_url"), str) for i in items):
            print("  No href links found -> retrying with click method...")
            items = collect_items_by_click(driver, list_url)

        print(f"\nFound {len(items)} programs")

        crawled_urls = load_crawled_urls()
        if crawled_urls:
            print(f"  {len(crawled_urls)} URLs already crawled - will skip")

        print("\n[Step 2] Fetching details + saving to DB...")
        success = 0
        for i, item in enumerate(items, 1):
            if not isinstance(item.get("detail_url"), str):
                continue
            if item["detail_url"] in crawled_urls:
                print(f"  ({i}/{len(items)}) Already crawled - skip")
                continue
            print(f"  ({i}/{len(items)}) {item['detail_url']}")
            try:
                try:
                    conn.ping(reconnect=True)
                except Exception:
                    conn = init_db()
                if _process_detail(driver, conn, item):
                    success += 1
            except Exception as e:
                print(f"    -> error: {e}")

        print(f"\nDone! {success}/{len(items)} programs saved to DB")
    finally:
        conn.close()
        if not AUTO_MODE:
            input("\nPress Enter to close browser...")
        driver.quit()
