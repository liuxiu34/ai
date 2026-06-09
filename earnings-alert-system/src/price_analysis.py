from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone

import pandas as pd
import yfinance as yf

from src.models import PriceMetrics
from src.utils import get_logger, normalize_yahoo_symbol


logger = get_logger(__name__)


class PriceAnalysisService:
    def __init__(self) -> None:
        self._spy_cache: dict[str, pd.Series] = {}
        self._spy_lock = threading.Lock()

    def get_metrics(self, symbol: str) -> PriceMetrics:
        end_dt = datetime.now(timezone.utc)
        start_dt = end_dt - timedelta(days=120)
        cache_key = f"{start_dt.date()}_{(end_dt + timedelta(days=1)).date()}"
        yf_symbol = normalize_yahoo_symbol(symbol)
        if yf_symbol != symbol:
            logger.info("Normalized yfinance symbol %s -> %s", symbol, yf_symbol)

        try:
            stock_history = yf.download(
                yf_symbol,
                start=start_dt.date(),
                end=(end_dt + timedelta(days=1)).date(),
                progress=False,
                auto_adjust=False,
                threads=False,
            )
        except Exception as exc:
            logger.warning("Failed to download price history for %s (%s): %s", symbol, yf_symbol, exc)
            return PriceMetrics(symbol=symbol, date=end_dt.date().isoformat())
        spy_close_series = self._get_spy_close_series(cache_key, start_dt, end_dt)

        if stock_history.empty:
            logger.info("No stock history returned for %s (%s)", symbol, yf_symbol)
            return PriceMetrics(symbol=symbol, date=end_dt.date().isoformat())

        close_series = self._extract_series(stock_history, "Close")
        volume_series = self._extract_series(stock_history, "Volume")

        if close_series.empty or volume_series.empty:
            return PriceMetrics(symbol=symbol, date=end_dt.date().isoformat())

        latest_close = float(close_series.iloc[-1])
        latest_volume = float(volume_series.iloc[-1])
        ma20 = float(close_series.tail(20).mean()) if len(close_series) >= 20 else latest_close
        ma50 = float(close_series.tail(50).mean()) if len(close_series) >= 50 else latest_close
        avg_volume_20 = float(volume_series.tail(20).mean()) if len(volume_series) >= 20 else latest_volume

        stock_return_7d = self._period_return(close_series, 7)
        stock_return_30d = self._period_return(close_series, 30)
        spy_return_7d = self._period_return(spy_close_series, 7) if not spy_close_series.empty else 0.0
        spy_return_30d = self._period_return(spy_close_series, 30) if not spy_close_series.empty else 0.0

        return PriceMetrics(
            symbol=symbol,
            date=end_dt.date().isoformat(),
            latest_close=latest_close,
            return_7d=stock_return_7d,
            return_30d=stock_return_30d,
            spy_relative_7d=stock_return_7d - spy_return_7d,
            spy_relative_30d=stock_return_30d - spy_return_30d,
            is_20d_high=latest_close >= float(close_series.tail(20).max()) if len(close_series) >= 20 else False,
            is_60d_high=latest_close >= float(close_series.tail(60).max()) if len(close_series) >= 60 else False,
            volume_ratio=(latest_volume / avg_volume_20) if avg_volume_20 else 0.0,
            above_ma20=latest_close > ma20,
            above_ma50=latest_close > ma50,
        )

    def _get_spy_close_series(self, cache_key: str, start_dt: datetime, end_dt: datetime) -> pd.Series:
        with self._spy_lock:
            if cache_key in self._spy_cache:
                return self._spy_cache[cache_key]

        try:
            spy_history = yf.download(
                "SPY",
                start=start_dt.date(),
                end=(end_dt + timedelta(days=1)).date(),
                progress=False,
                auto_adjust=False,
                threads=False,
            )
        except Exception as exc:
            logger.warning("Failed to download SPY benchmark history: %s", exc)
            spy_history = pd.DataFrame()
        spy_close_series = self._extract_series(spy_history, "Close") if not spy_history.empty else pd.Series(dtype=float)

        with self._spy_lock:
            self._spy_cache[cache_key] = spy_close_series
        return spy_close_series

    @staticmethod
    def _extract_series(frame: pd.DataFrame, column_name: str) -> pd.Series:
        values = frame[column_name]
        if isinstance(values, pd.DataFrame):
            values = values.iloc[:, 0]
        return values.dropna()

    @staticmethod
    def _period_return(close_series: pd.Series, periods: int) -> float:
        if len(close_series) <= periods:
            return 0.0
        start_price = float(close_series.iloc[-periods - 1])
        end_price = float(close_series.iloc[-1])
        if not start_price:
            return 0.0
        return ((end_price - start_price) / start_price) * 100
