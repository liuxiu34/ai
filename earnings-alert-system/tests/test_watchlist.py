from config import AppConfig
from src.models import EarningsEvent
from src.watchlist import WatchlistBuilder


def test_filter_events_applies_market_cap_and_limit():
    builder = WatchlistBuilder(
        AppConfig(max_scan_symbols=2, min_market_cap_usd=1_000_000_000),
        database=None,
    )
    events = [
        EarningsEvent("AAA", "AAA Inc", "2026-06-01", "盘后", 2, "nasdaq", market_cap=5_000_000_000),
        EarningsEvent("BBB", "BBB Inc", "2026-06-01", "盘后", 2, "nasdaq", market_cap=500_000_000),
        EarningsEvent("CCC", "CCC Inc", "2026-06-01", "盘后", 2, "nasdaq", market_cap=3_000_000_000),
        EarningsEvent("DDD", "DDD Inc", "2026-05-31", "盘前", 1, "nasdaq", market_cap=2_000_000_000),
    ]

    filtered = builder._filter_events(events)

    assert [event.symbol for event in filtered] == ["DDD", "AAA"]
