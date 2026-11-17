import pymysql, sys, os
from dotenv import load_dotenv
load_dotenv()
sys.stdout.reconfigure(encoding='utf-8')

ssl_opts = {} if os.getenv("DB_SSL") == "1" else None
conn = pymysql.connect(
    host=os.getenv("DB_HOST", "172.30.74.43"),
    port=int(os.getenv("DB_PORT", "3306")),
    user=os.getenv("DB_USER", "navi"),
    password=os.getenv("DB_PASS", "vo8Tm5dnj1em2"),
    database=os.getenv("DB_NAME", "program_navigator"),
    charset='utf8mb4',
    **({'ssl': ssl_opts} if ssl_opts is not None else {}),
)
lines = []

with conn.cursor() as cur:
    # ── 요약 ──────────────────────────────────────────────
    cur.execute('SELECT COUNT(*) FROM program')
    total = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM program WHERE recruit_start IS NOT NULL')
    full = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM program WHERE recruit_start IS NULL')
    preview_only = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM program_schedule')
    sched_total = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM program_image')
    img_total = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM tag')
    tag_total = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM program_tag')
    ptag_total = cur.fetchone()[0]

    lines.append('=' * 110)
    lines.append('  DB 저장 현황 요약')
    lines.append('=' * 110)
    lines.append(f'  전체 program      : {total}개')
    lines.append(f'  완전한 데이터      : {full}개  (recruit_start 있음)')
    lines.append(f'  preview only      : {preview_only}개  (목록만 저장, 상세 미수집)')
    lines.append(f'  program_schedule  : {sched_total}행')
    lines.append(f'  program_image     : {img_total}행')
    lines.append(f'  tag               : {tag_total}개')
    lines.append(f'  program_tag       : {ptag_total}행')
    lines.append('')

    # ── 완전한 데이터 목록 ────────────────────────────────
    lines.append('=' * 110)
    lines.append('  완전한 데이터 (recruit_start >= 2026-09-01)')
    lines.append('=' * 110)

    cur.execute('''
        SELECT p.program_id, p.title, p.summary, p.category, p.organization,
               p.recruit_start, p.recruit_end, p.edu_start, p.edu_end,
               p.capacity, p.applicant_count, p.waitlist_count, p.mileage,
               CASE WHEN p.thumbnail_data IS NOT NULL THEN 'O' ELSE 'X' END,
               CASE WHEN p.description_html IS NOT NULL THEN 'O' ELSE 'X' END,
               (SELECT COUNT(*) FROM program_schedule ps WHERE ps.program_id = p.program_id),
               (SELECT COUNT(*) FROM program_image pi WHERE pi.program_id = p.program_id),
               (SELECT GROUP_CONCAT(t.name ORDER BY t.name SEPARATOR ', ')
                FROM program_tag pt JOIN tag t ON pt.tag_id = t.tag_id
                WHERE pt.program_id = p.program_id)
        FROM program p
        WHERE p.recruit_start IS NOT NULL
        ORDER BY p.recruit_start, p.program_id
    ''')
    for r in cur.fetchall():
        pid, title, summary, cat, org, rs, re, es, ee, cap, app, wait, mile, thumb, desc_, sched, imgs, tags = r
        recruit = f"{str(rs)} ~ {str(re)}" if rs else '-'
        edu     = f"{str(es)} ~ {str(ee)}" if es else '-'
        lines.append(f"{str(pid):<6} {str(title):<40} {str(cat or ''):<16} {str(org or ''):<22}")
        lines.append(f"       요약: {str(summary or '')[:80]}")
        lines.append(f"       신청: {recruit:<24}  교육: {edu}")
        lines.append(f"       정원:{str(cap):>4} 신청:{str(app):>4} 대기:{str(wait):>4} 마일:{str(mile):>4}  썸네일:{thumb} 설명:{desc_} 이미지:{str(imgs):>2}")
        lines.append(f"       태그: {str(tags or '')[:80]}")
        lines.append("")

    lines.append('')

    # ── preview only 목록 ─────────────────────────────────
    lines.append('=' * 110)
    lines.append('  Preview only (상세 미수집 — 날짜 필터에서 제외된 항목)')
    lines.append('=' * 110)
    cur.execute('''
        SELECT program_id, title,
               CASE WHEN thumbnail_data IS NOT NULL THEN 'O' ELSE 'X' END,
               applicant_count, capacity, waitlist_count
        FROM program
        WHERE recruit_start IS NULL
        ORDER BY program_id
    ''')
    for r in cur.fetchall():
        pid, title, thumb, app, cap, wait = r
        lines.append(f"{str(pid):<6} {str(title):<50} {thumb:>3} {str(app):>5} {str(cap):>5} {str(wait):>5}")

    lines.append('')

    # ── 태그 목록 ─────────────────────────────────────────
    lines.append('=' * 110)
    lines.append('  태그 목록')
    lines.append('=' * 110)
    cur.execute('SELECT tag_id, name, category FROM tag ORDER BY tag_id')
    for r in cur.fetchall():
        lines.append(f"  id={r[0]:<4} {r[1]}  (category: {r[2]})")

conn.close()

with open('db_check.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))

print(f'저장 완료: db_check.txt ({len(lines)}줄)')
