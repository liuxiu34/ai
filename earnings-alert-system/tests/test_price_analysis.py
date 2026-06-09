from datetime import datetime, timezone

import pandas as pd

from src.price_analysis import PriceAnalysisService


def test_extract_series_handles_multiindex_columns():
    frame = pd.DataFrame(
        {
            ("Close", "AAA"): [10.0, 11.5, 12.0],
            ("Volume", "AAA"): [100, 120, 130],
        }
    )

    series = PriceAnalysisService._extract_series(frame, "Close")

    assert list(series) == [10.0, 11.5, 12.0]


def test_get_spy_close_series_uses_cache(monkeypatch):
    service = PriceAnalysisService()
    calls = {"count": 0}

    def fake_download(*args, **kwargs):
        calls["count"] += 1
        return pd.DataFrame({"Close": [100.0, 101.0, 102.0]})

    monkeypatch.setattr("src.price_analysis.yf.download", fake_download)

    start_dt = datetime(2026, 5, 1, tzinfo=timezone.utc)
    end_dt = datetime(2026, 5, 30, tzinfo=timezone.utc)

    first = service._get_spy_close_series("cache-key", start_dt, end_dt)
    second = service._get_spy_close_series("cache-key", start_dt, end_dt)

    assert list(first) == [100.0, 101.0, 102.0]
    assert list(second) == [100.0, 101.0, 102.0]
    assert calls["count"] == 1
