from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict

from config import AppConfig
from src.analyst_data import AnalystDataService
from src.database import DatabaseManager
from src.earnings_calendar import EarningsCalendarService
from src.llm_analyzer import LLMAnalyzer
from src.models import AnalystSnapshot, EarningsEvent, PriceMetrics, WatchlistItem
from src.news_collector import NewsCollector
from src.outcome_evaluator import OutcomeEvaluator
from src.price_analysis import PriceAnalysisService
from src.scoring import calculate_score
from src.utils import get_logger, today_iso


logger = get_logger(__name__)

_MAX_WORKERS = 8


class WatchlistBuilder:
    def __init__(self, config: AppConfig, database: DatabaseManager) -> None:
        self.config = config
        self.database = database
        self.earnings_service = EarningsCalendarService(config)
        self.price_service = PriceAnalysisService()
        self.news_collector = NewsCollector(config.finnhub_api_key, request_timeout=config.request_timeout)
        self.llm_analyzer = LLMAnalyzer(config)
        self.analyst_service = AnalystDataService(config)

    def run_daily_scan(self, days: int | None = None) -> list[dict]:
        OutcomeEvaluator(self.database).evaluate_pending()

        raw_events = self.earnings_service.get_upcoming_earnings(days=days)
        events = self._filter_events(raw_events)
        self.database.upsert_earnings_events(events)

        run_date = today_iso()
        results = []

        workers = min(_MAX_WORKERS, len(events)) if events else 1
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(self._fetch_symbol_data, event, run_date): event for event in events}
            for future in as_completed(futures):
                event = futures[future]
                try:
                    results.append(future.result())
                except Exception as exc:
                    logger.warning("Symbol processing failed for %s: %s", event.symbol, exc)

        watchlist: list[WatchlistItem] = []
        for price_metrics, analyst_snapshot, analyzed_news, scorecard, watchlist_item in results:
            self.database.upsert_price_metrics(price_metrics)
            self.database.upsert_analyst_snapshot(analyst_snapshot)
            if analyzed_news:
                self.database.insert_news_items(analyzed_news)
            self.database.upsert_scorecard(scorecard)
            watchlist.append(watchlist_item)

        self.database.replace_watchlist(run_date, watchlist)
        self.database.insert_prediction_stubs(run_date, watchlist)
        return [asdict(item) for item in watchlist]

    def _fetch_symbol_data(self, event: EarningsEvent, run_date: str) -> tuple:
        price_metrics = PriceMetrics(symbol=event.symbol, date=run_date)
        analyst_snapshot = AnalystSnapshot(symbol=event.symbol, date=run_date, source="unavailable")
        raw_news: list[dict] = []
        analyzed_news = []

        try:
            price_metrics = self.price_service.get_metrics(event.symbol)
        except Exception as exc:
            logger.warning("Price analysis failed for %s: %s", event.symbol, exc)

        try:
            current_price = price_metrics.latest_close or None
            analyst_snapshot = self.analyst_service.fetch_snapshot(event.symbol, current_price=current_price)
        except Exception as exc:
            logger.warning("Analyst data collection failed for %s: %s", event.symbol, exc)

        try:
            raw_news = self.news_collector.fetch_recent_news(event.symbol, days=self.config.news_window_days)
            analyzed_news = [
                self.llm_analyzer.analyze_news_item(event.symbol, item)
                for item in raw_news[: self.config.max_news_items]
            ]
        except Exception as exc:
            logger.warning("News collection failed for %s: %s", event.symbol, exc)
            analyzed_news = []

        scorecard = calculate_score(
            earnings_event=event,
            price_metrics=price_metrics,
            news_items=analyzed_news,
            analyst_snapshot=analyst_snapshot,
            has_news_data=bool(raw_news),
            has_analyst_data=analyst_snapshot.source != "unavailable",
        )

        watchlist_item = WatchlistItem(
            symbol=event.symbol,
            company_name=event.company_name,
            earnings_date=event.earnings_date,
            earnings_time=event.earnings_time,
            total_score=scorecard.total_score,
            priority=scorecard.priority,
            reasons=scorecard.reasons,
            risks=scorecard.risks,
        )

        return price_metrics, analyst_snapshot, analyzed_news, scorecard, watchlist_item

    def _filter_events(self, events: list) -> list:
        filtered = [
            event
            for event in events
            if event.market_cap <= 0 or event.market_cap >= self.config.min_market_cap_usd
        ]
        filtered.sort(key=lambda event: (event.days_until_earnings, -event.market_cap, event.symbol))
        if self.config.max_scan_symbols > 0:
            filtered = filtered[: self.config.max_scan_symbols]

        logger.info(
            "Prepared scan universe: %s raw events -> %s filtered events (min_market_cap=%s, max_scan_symbols=%s)",
            len(events),
            len(filtered),
            int(self.config.min_market_cap_usd),
            self.config.max_scan_symbols,
        )
        return filtered
