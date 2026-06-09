from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd

from config import AppConfig
from src.models import AnalystSnapshot, EarningsEvent, NewsAnalysis, PredictionOutcome, PriceMetrics, ScoreCard, WatchlistItem
from src.utils import bool_to_int, ensure_parent_dir, utc_now_iso


class DatabaseManager:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.db_path = config.database_path
        ensure_parent_dir(self.db_path)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS earnings_calendar (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    company_name TEXT,
                    earnings_date TEXT NOT NULL,
                    earnings_time TEXT,
                    days_until_earnings INTEGER,
                    source TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(symbol, earnings_date)
                );

                CREATE TABLE IF NOT EXISTS price_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    date TEXT NOT NULL,
                    return_7d REAL,
                    return_30d REAL,
                    spy_relative_7d REAL,
                    spy_relative_30d REAL,
                    is_20d_high INTEGER,
                    is_60d_high INTEGER,
                    volume_ratio REAL,
                    above_ma20 INTEGER,
                    above_ma50 INTEGER,
                    created_at TEXT NOT NULL,
                    UNIQUE(symbol, date)
                );

                CREATE TABLE IF NOT EXISTS news_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT,
                    source TEXT,
                    published_at TEXT,
                    raw_content TEXT,
                    sentiment TEXT,
                    event_types TEXT,
                    impact_score INTEGER,
                    llm_summary TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(symbol, title, published_at)
                );

                CREATE TABLE IF NOT EXISTS analyst_changes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    date TEXT NOT NULL,
                    target_price_upgrades INTEGER,
                    target_price_downgrades INTEGER,
                    rating_upgrades INTEGER,
                    rating_downgrades INTEGER,
                    average_target_price REAL,
                    upside_to_target REAL,
                    source TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(symbol, date)
                );

                CREATE TABLE IF NOT EXISTS scores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    date TEXT NOT NULL,
                    total_score INTEGER,
                    priority TEXT,
                    reasons TEXT,
                    risks TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(symbol, date)
                );

                CREATE TABLE IF NOT EXISTS prediction_outcomes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    prediction_date TEXT NOT NULL,
                    earnings_date TEXT NOT NULL,
                    predicted_priority TEXT NOT NULL,
                    actual_return_pct REAL,
                    was_correct INTEGER,
                    evaluated_at TEXT,
                    UNIQUE(symbol, prediction_date)
                );

                CREATE TABLE IF NOT EXISTS watchlist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    company_name TEXT,
                    earnings_date TEXT,
                    earnings_time TEXT,
                    total_score INTEGER,
                    priority TEXT,
                    reasons TEXT,
                    risks TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(date, symbol)
                );
                """
            )

    def upsert_earnings_events(self, events: list[EarningsEvent]) -> None:
        now = utc_now_iso()
        rows = [
            (
                event.symbol,
                event.company_name,
                event.earnings_date,
                event.earnings_time,
                event.days_until_earnings,
                event.source,
                now,
                now,
            )
            for event in events
        ]
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO earnings_calendar (
                    symbol, company_name, earnings_date, earnings_time,
                    days_until_earnings, source, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, earnings_date) DO UPDATE SET
                    company_name = excluded.company_name,
                    earnings_time = excluded.earnings_time,
                    days_until_earnings = excluded.days_until_earnings,
                    source = excluded.source,
                    updated_at = excluded.updated_at
                """,
                rows,
            )

    def upsert_price_metrics(self, metrics: PriceMetrics) -> None:
        now = utc_now_iso()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO price_metrics (
                    symbol, date, return_7d, return_30d, spy_relative_7d,
                    spy_relative_30d, is_20d_high, is_60d_high, volume_ratio,
                    above_ma20, above_ma50, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, date) DO UPDATE SET
                    return_7d = excluded.return_7d,
                    return_30d = excluded.return_30d,
                    spy_relative_7d = excluded.spy_relative_7d,
                    spy_relative_30d = excluded.spy_relative_30d,
                    is_20d_high = excluded.is_20d_high,
                    is_60d_high = excluded.is_60d_high,
                    volume_ratio = excluded.volume_ratio,
                    above_ma20 = excluded.above_ma20,
                    above_ma50 = excluded.above_ma50
                """,
                (
                    metrics.symbol,
                    metrics.date,
                    metrics.return_7d,
                    metrics.return_30d,
                    metrics.spy_relative_7d,
                    metrics.spy_relative_30d,
                    bool_to_int(metrics.is_20d_high),
                    bool_to_int(metrics.is_60d_high),
                    metrics.volume_ratio,
                    bool_to_int(metrics.above_ma20),
                    bool_to_int(metrics.above_ma50),
                    now,
                ),
            )

    def insert_news_items(self, items: list[NewsAnalysis]) -> None:
        now = utc_now_iso()
        rows = [
            (
                item.symbol,
                item.title,
                item.url,
                item.source,
                item.published_at,
                item.raw_content,
                item.sentiment,
                json.dumps(item.event_types, ensure_ascii=False),
                item.impact_score,
                item.llm_summary,
                now,
            )
            for item in items
        ]
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO news_items (
                    symbol, title, url, source, published_at, raw_content,
                    sentiment, event_types, impact_score, llm_summary, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def upsert_analyst_snapshot(self, snapshot: AnalystSnapshot) -> None:
        now = utc_now_iso()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO analyst_changes (
                    symbol, date, target_price_upgrades, target_price_downgrades,
                    rating_upgrades, rating_downgrades, average_target_price,
                    upside_to_target, source, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, date) DO UPDATE SET
                    target_price_upgrades = excluded.target_price_upgrades,
                    target_price_downgrades = excluded.target_price_downgrades,
                    rating_upgrades = excluded.rating_upgrades,
                    rating_downgrades = excluded.rating_downgrades,
                    average_target_price = excluded.average_target_price,
                    upside_to_target = excluded.upside_to_target,
                    source = excluded.source
                """,
                (
                    snapshot.symbol,
                    snapshot.date,
                    snapshot.target_price_upgrades,
                    snapshot.target_price_downgrades,
                    snapshot.rating_upgrades,
                    snapshot.rating_downgrades,
                    snapshot.average_target_price,
                    snapshot.upside_to_target,
                    snapshot.source,
                    now,
                ),
            )

    def upsert_scorecard(self, scorecard: ScoreCard) -> None:
        now = utc_now_iso()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO scores (
                    symbol, date, total_score, priority, reasons, risks, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, date) DO UPDATE SET
                    total_score = excluded.total_score,
                    priority = excluded.priority,
                    reasons = excluded.reasons,
                    risks = excluded.risks
                """,
                (
                    scorecard.symbol,
                    scorecard.date,
                    scorecard.total_score,
                    scorecard.priority,
                    json.dumps(scorecard.reasons, ensure_ascii=False),
                    json.dumps(scorecard.risks, ensure_ascii=False),
                    now,
                ),
            )

    def replace_watchlist(self, run_date: str, items: list[WatchlistItem]) -> None:
        now = utc_now_iso()
        rows = [
            (
                run_date,
                item.symbol,
                item.company_name,
                item.earnings_date,
                item.earnings_time,
                item.total_score,
                item.priority,
                json.dumps(item.reasons, ensure_ascii=False),
                json.dumps(item.risks, ensure_ascii=False),
                now,
            )
            for item in items
        ]
        with self.connect() as conn:
            conn.execute("DELETE FROM watchlist WHERE date = ?", (run_date,))
            conn.executemany(
                """
                INSERT INTO watchlist (
                    date, symbol, company_name, earnings_date, earnings_time,
                    total_score, priority, reasons, risks, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def insert_prediction_stubs(self, run_date: str, items: list[WatchlistItem]) -> None:
        rows = [
            (item.symbol, run_date, item.earnings_date, item.priority)
            for item in items
        ]
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT OR IGNORE INTO prediction_outcomes
                    (symbol, prediction_date, earnings_date, predicted_priority)
                VALUES (?, ?, ?, ?)
                """,
                rows,
            )

    def get_unevaluated_predictions(self, min_days_after: int = 3) -> list[dict]:
        cutoff = (
            __import__("datetime").date.today()
            - __import__("datetime").timedelta(days=min_days_after)
        ).isoformat()
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT symbol, prediction_date, earnings_date, predicted_priority
                FROM prediction_outcomes
                WHERE was_correct IS NULL AND earnings_date <= ?
                """,
                (cutoff,),
            ).fetchall()
        return [dict(row) for row in rows]

    def update_prediction_outcome(self, outcome: PredictionOutcome) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE prediction_outcomes
                SET actual_return_pct = ?, was_correct = ?, evaluated_at = ?
                WHERE symbol = ? AND prediction_date = ?
                """,
                (
                    outcome.actual_return_pct,
                    1 if outcome.was_correct else 0,
                    outcome.evaluated_at,
                    outcome.symbol,
                    outcome.prediction_date,
                ),
            )

    def get_symbol_accuracies(self) -> dict[str, dict]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT symbol,
                       COUNT(*) AS total,
                       SUM(was_correct) AS correct
                FROM prediction_outcomes
                WHERE was_correct IS NOT NULL
                GROUP BY symbol
                """,
            ).fetchall()
        result = {}
        for row in rows:
            total = row["total"]
            correct = row["correct"] or 0
            result[row["symbol"]] = {
                "total": total,
                "correct": correct,
                "accuracy_pct": round(correct / total * 100, 1) if total else 0.0,
            }
        return result

    def fetch_watchlist(self, run_date: str | None = None, priority: str | None = None) -> pd.DataFrame:
        query = "SELECT * FROM watchlist WHERE 1=1"
        params: list[str] = []
        if run_date:
            query += " AND date = ?"
            params.append(run_date)
        if priority:
            query += " AND priority = ?"
            params.append(priority)
        query += " ORDER BY total_score DESC, earnings_date ASC, symbol ASC"
        with self.connect() as conn:
            frame = pd.read_sql_query(query, conn, params=params)
        return frame

    def available_watchlist_dates(self) -> list[str]:
        with self.connect() as conn:
            rows = conn.execute("SELECT DISTINCT date FROM watchlist ORDER BY date DESC").fetchall()
        return [row["date"] for row in rows]
