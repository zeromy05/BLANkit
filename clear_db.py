import pymysql, os

conn = pymysql.connect(
    host=os.environ['DB_HOST'],
    port=int(os.environ['DB_PORT']),
    user=os.environ['DB_USER'],
    password=os.environ['DB_PASS'],
    database=os.environ['DB_NAME'],
    charset='utf8mb4',
    ssl={},
)
with conn.cursor() as cur:
    cur.execute('DELETE FROM program')
    print('deleted:', cur.rowcount)
conn.commit()
conn.close()
