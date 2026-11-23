"""DB 데이터 품질 점검 스크립트"""
import pymysql, os, sys, re
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
sys.stdout.reconfigure(encoding='utf-8')

conn = pymysql.connect(
    host=os.getenv('DB_HOST'),
    port=int(os.getenv('DB_PORT', '3306')),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASS'),
    database=os.getenv('DB_NAME'),
    charset='utf8mb4',
    ssl={},
)

out = []
issues = []

def p(s=''):  out.append(s)
def issue(tag, pid, title, msg):
    s = f"  [{tag}] #{pid} {title[:35]:<35} → {msg}"
    issues.append(s)
    out.append(s)

# ─────────────────────────────────────────────────────────────
p('=' * 100)
p('  DB 데이터 품질 점검')
p('=' * 100)

with conn.cursor() as cur:

    # 1. 전체 카운트
    cur.execute('SELECT COUNT(*) FROM program')
    total = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM program WHERE recruit_start IS NOT NULL')
    full_cnt = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM program WHERE recruit_start IS NULL')
    preview_cnt = cur.fetchone()[0]
    p(f'\n총 {total}개 (완전:{full_cnt} / 목록만:{preview_cnt})\n')

    # 2. 날짜/시간 필드 점검
    p('─' * 100)
    p('  [1] 날짜/시간 필드 점검')
    p('─' * 100)

    cur.execute('''
        SELECT program_id, title,
               recruit_start, recruit_end,
               edu_start, edu_end
        FROM program
        WHERE recruit_start IS NOT NULL
        ORDER BY program_id
    ''')
    rows = cur.fetchall()

    date_only_pat = re.compile(r'^\d{4}-\d{2}-\d{2}$')  # 시간 없는 DATE 형식
    for pid, title, rs, re_, es, ee in rows:
        t = str(title or '')[:35]
        # datetime 객체인 경우 00:00:00이면 시간 미수집 의심
        for label, val in [('recruit_start', rs), ('recruit_end', re_),
                           ('edu_start', es), ('edu_end', ee)]:
            if val is None:
                if label in ('edu_start', 'edu_end'):
                    pass  # 교육 날짜는 없어도 허용
                else:
                    issue('날짜NULL', pid, title, f'{label} 없음')
            elif isinstance(val, datetime):
                if val.hour == 0 and val.minute == 0 and val.second == 0:
                    issue('시간=00:00', pid, title, f'{label} = {val}  ← 시간 미수집 의심')
            else:
                s = str(val)
                if date_only_pat.match(s):
                    issue('DATE형식', pid, title, f'{label} = {s}  ← datetime 아님')

    # 3. 날짜 역전 (start > end)
    p('\n─' * 50)
    p('  [2] 날짜 역전 (start > end)')
    p('─' * 50)
    cur.execute('''
        SELECT program_id, title, recruit_start, recruit_end, edu_start, edu_end
        FROM program
        WHERE (recruit_start IS NOT NULL AND recruit_end IS NOT NULL AND recruit_start > recruit_end)
           OR (edu_start IS NOT NULL AND edu_end IS NOT NULL AND edu_start > edu_end)
    ''')
    rows = cur.fetchall()
    if not rows:
        p('  이상 없음')
    for pid, title, rs, re_, es, ee in rows:
        if rs and re_ and rs > re_:
            issue('날짜역전', pid, title, f'recruit {rs} > {re_}')
        if es and ee and es > ee:
            issue('날짜역전', pid, title, f'edu {es} > {ee}')

    # 4. title / summary 잘림 점검
    p('\n─' * 50)
    p('  [3] title 길이 분포 & 잘림 의심')
    p('─' * 50)
    cur.execute('SELECT program_id, title FROM program ORDER BY program_id')
    rows = cur.fetchall()
    for pid, title in rows:
        t = str(title or '')
        if len(t) == 0:
            issue('제목없음', pid, '(empty)', '제목 없음')
        elif len(t) >= 490:
            issue('제목500자', pid, title, f'제목 {len(t)}자 → 잘림 의심: ...{t[-20:]}')
        # 중간에 이상한 문자로 잘렸을 가능성 (줄바꿈 포함)
        if '\n' in t or '\r' in t:
            issue('제목개행', pid, title, f'제목에 개행문자 포함')

    cur.execute('SELECT program_id, title, summary FROM program WHERE summary IS NOT NULL ORDER BY program_id')
    rows = cur.fetchall()
    p(f'  summary 있는 항목: {len(rows)}개')
    for pid, title, summary in rows:
        s = str(summary or '')
        if len(s) >= 490:
            issue('요약500자', pid, title, f'요약 {len(s)}자 → 잘림 의심: ...{s[-20:]}')
        if '\n' in s or '\r' in s:
            issue('요약개행', pid, title, f'요약에 개행문자 포함: {repr(s[:60])}')

    # 5. location 점검
    p('\n─' * 50)
    p('  [4] location 점검')
    p('─' * 50)
    cur.execute('''
        SELECT program_id, title, location
        FROM program
        WHERE recruit_start IS NOT NULL
        ORDER BY program_id
    ''')
    rows = cur.fetchall()
    for pid, title, loc in rows:
        l = str(loc or '')
        if not l or l == 'None':
            issue('장소없음', pid, title, 'location 없음')
        elif len(l) >= 490:
            issue('장소500자', pid, title, f'장소 {len(l)}자 잘림: ...{l[-30:]}')
        elif '\n' in l or '\r' in l:
            issue('장소개행', pid, title, f'장소에 개행 포함: {repr(l[:60])}')

    # 6. 정원/신청자 수 이상치
    p('\n─' * 50)
    p('  [5] 정원 / 신청자 수 이상')
    p('─' * 50)
    cur.execute('''
        SELECT program_id, title, capacity, applicant_count, waitlist_count
        FROM program
        WHERE recruit_start IS NOT NULL
        ORDER BY program_id
    ''')
    rows = cur.fetchall()
    for pid, title, cap, app, wait in rows:
        if cap is None:
            issue('정원없음', pid, title, 'capacity NULL')
        elif cap == 0:
            issue('정원0', pid, title, 'capacity=0')
        if app is not None and cap is not None and app > cap * 3:
            issue('신청과다', pid, title, f'신청자{app} > 정원{cap}×3')

    # 7. mileage 이상치
    p('\n─' * 50)
    p('  [6] 마일리지 이상')
    p('─' * 50)
    cur.execute('''
        SELECT program_id, title, mileage
        FROM program
        WHERE mileage IS NOT NULL AND (mileage < 0 OR mileage > 100)
        ORDER BY program_id
    ''')
    rows = cur.fetchall()
    if not rows:
        p('  이상 없음 (0~100 범위 초과 없음)')
    for pid, title, mile in rows:
        issue('마일리지', pid, title, f'mileage={mile}')

    # 8. description 잘림 / 없는 항목
    p('\n─' * 50)
    p('  [7] 설명(description_html) 없는 완전 항목')
    p('─' * 50)
    cur.execute('''
        SELECT program_id, title
        FROM program
        WHERE recruit_start IS NOT NULL
          AND (description_html IS NULL OR description_html = '')
        ORDER BY program_id
    ''')
    rows = cur.fetchall()
    if not rows:
        p('  모두 설명 있음')
    for pid, title in rows:
        issue('설명없음', pid, title, 'description_html 없음')

    # 9. program_schedule 점검
    p('\n─' * 50)
    p('  [8] program_schedule 점검 (시간 NULL)')
    p('─' * 50)
    cur.execute('''
        SELECT ps.schedule_id, p.program_id, p.title,
               ps.session_date, ps.start_time, ps.end_time
        FROM program_schedule ps
        JOIN program p ON p.program_id = ps.program_id
        WHERE ps.start_time IS NULL OR ps.end_time IS NULL OR ps.session_date IS NULL
        LIMIT 20
    ''')
    rows = cur.fetchall()
    if not rows:
        p('  이상 없음')
    for sid, pid, title, sd, st, et in rows:
        issue('일정NULL', pid, title, f'schedule_id={sid} date={sd} start={st} end={et}')

    # 10. 전체 데이터 샘플 출력
    p('\n' + '=' * 100)
    p('  전체 항목 목록 (ID | 제목 | 신청기간 | 교육기간 | 장소 | 정원/신청)')
    p('=' * 100)
    cur.execute('''
        SELECT program_id, title,
               recruit_start, recruit_end,
               edu_start, edu_end,
               location, capacity, applicant_count, mileage, category
        FROM program
        WHERE recruit_start IS NOT NULL
        ORDER BY edu_start, program_id
    ''')
    rows = cur.fetchall()
    for pid, title, rs, re_, es, ee, loc, cap, app, mile, cat in rows:
        p(f'  #{pid:<4} {str(title or "")[:45]:<45}')
        p(f'         신청: {str(rs)[:19] if rs else "없음":<20} ~ {str(re_)[:19] if re_ else "없음":<20}')
        p(f'         교육: {str(es)[:19] if es else "없음":<20} ~ {str(ee)[:19] if ee else "없음":<20}')
        p(f'         장소: {str(loc or "없음")[:50]}')
        p(f'         정원:{str(cap):>4} 신청:{str(app):>4} 마일:{str(mile):>4}  카테고리: {str(cat or "없음")}')
        p('')

conn.close()

p('\n' + '=' * 100)
p(f'  이슈 요약: 총 {len(issues)}건')
p('=' * 100)
for s in issues:
    p(s)

result = '\n'.join(out)
with open('quality_check.txt', 'w', encoding='utf-8') as f:
    f.write(result)

print(f'완료: quality_check.txt ({len(out)}줄, 이슈 {len(issues)}건)')
