import sqlite3
import time
from main import run_scan

start = time.perf_counter()
df = run_scan(7)
elapsed = time.perf_counter() - start

conn = sqlite3.connect('data/app.db')
watchlist_rows = conn.execute('select count(*) from watchlist').fetchone()[0]
scores_rows = conn.execute('select count(*) from scores').fetchone()[0]
earnings_rows = conn.execute('select count(*) from earnings_calendar').fetchone()[0]

with open('timing_result.txt', 'w', encoding='utf-8') as f:
    f.write(f'elapsed_seconds={elapsed:.2f}\n')
    f.write(f'rows={len(df)}\n')
    f.write(f'watchlist_rows={watchlist_rows}\n')
    f.write(f'scores_rows={scores_rows}\n')
    f.write(f'earnings_rows={earnings_rows}\n')
