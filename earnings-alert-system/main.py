from __future__ import annotations

import argparse
import json

import pandas as pd

from config import load_config
from src.database import DatabaseManager
from src.utils import today_iso
from src.watchlist import WatchlistBuilder


def run_scan(days: int | None = None) -> pd.DataFrame:
    config = load_config()
    database = DatabaseManager(config)
    database.init_db()
    builder = WatchlistBuilder(config, database)
    builder.run_daily_scan(days=days)
    return database.fetch_watchlist(run_date=today_iso())


def main() -> None:
    parser = argparse.ArgumentParser(description="美股财报异动预警系统")
    parser.add_argument("--days", type=int, default=None, help="扫描未来多少天的财报")
    parser.add_argument("--json", action="store_true", help="输出 JSON 结果")
    args = parser.parse_args()

    frame = run_scan(days=args.days)
    if args.json:
        print(frame.to_json(orient="records", force_ascii=False))
        return

    if frame.empty:
        print("未获取到可展示的 watchlist 结果。请重试扫描，或检查当前筛选条件和网络请求日志。")
        return

    display = frame[["symbol", "company_name", "earnings_date", "earnings_time", "total_score", "priority"]]
    print(display.to_string(index=False))

    sample = frame.head(3).to_dict(orient="records")
    print("\n示例详情:")
    print(json.dumps(sample, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
