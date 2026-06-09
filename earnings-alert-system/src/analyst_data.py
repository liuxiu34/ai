from __future__ import annotations

from datetime import date, timedelta

import requests
import yfinance as yf

from config import AppConfig
from src.models import AnalystSnapshot
from src.utils import get_logger, normalize_yahoo_symbol, safe_float


logger = get_logger(__name__)


class AnalystDataService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def fetch_snapshot(self, symbol: str, current_price: float | None = None) -> AnalystSnapshot:
        today = date.today().isoformat()

        if self.config.finnhub_api_key:
            snapshot = self._fetch_from_finnhub(symbol=symbol, current_price=current_price)
            if snapshot.average_target_price or snapshot.rating_upgrades or snapshot.rating_downgrades:
                return snapshot

        # Skip yfinance analyst fetch when no API key is configured — yf.Ticker.info
        # is very slow (5-10s/call) and provides limited value without a primary data source.
        if not self.config.finnhub_api_key:
            return AnalystSnapshot(symbol=symbol, date=today, source="unavailable")

        return self._fetch_from_yfinance(symbol=symbol, current_price=current_price)

    def _fetch_from_finnhub(self, symbol: str, current_price: float | None) -> AnalystSnapshot:
        today = date.today()
        start_date = today - timedelta(days=30)
        target_response = requests.get(
            "https://finnhub.io/api/v1/stock/price-target",
            params={"symbol": symbol, "token": self.config.finnhub_api_key},
            timeout=self.config.request_timeout,
        )
        rating_response = requests.get(
            "https://finnhub.io/api/v1/stock/upgrade-downgrade",
            params={
                "symbol": symbol,
                "from": start_date.isoformat(),
                "to": today.isoformat(),
                "token": self.config.finnhub_api_key,
            },
            timeout=self.config.request_timeout,
        )

        average_target_price = 0.0
        if target_response.ok:
            payload = target_response.json()
            average_target_price = safe_float(payload.get("targetMean"))

        rating_upgrades = 0
        rating_downgrades = 0
        target_price_upgrades = 0
        target_price_downgrades = 0
        if rating_response.ok:
            for item in rating_response.json():
                action = str(item.get("action") or "").lower()
                if "upgrade" in action:
                    rating_upgrades += 1
                if "downgrade" in action:
                    rating_downgrades += 1
                if "target price raised" in action or "price target raised" in action:
                    target_price_upgrades += 1
                if "target price lowered" in action or "price target lowered" in action:
                    target_price_downgrades += 1

        upside_to_target = 0.0
        if current_price and average_target_price:
            upside_to_target = ((average_target_price - current_price) / current_price) * 100

        return AnalystSnapshot(
            symbol=symbol,
            date=today.isoformat(),
            target_price_upgrades=target_price_upgrades,
            target_price_downgrades=target_price_downgrades,
            rating_upgrades=rating_upgrades,
            rating_downgrades=rating_downgrades,
            average_target_price=average_target_price,
            upside_to_target=upside_to_target,
            source="finnhub",
        )

    @staticmethod
    def _fetch_from_yfinance(symbol: str, current_price: float | None) -> AnalystSnapshot:
        today = date.today().isoformat()
        average_target_price = 0.0
        yf_symbol = normalize_yahoo_symbol(symbol)
        try:
            info = yf.Ticker(yf_symbol).info
            average_target_price = safe_float(info.get("targetMeanPrice"))
            live_price = current_price or safe_float(info.get("currentPrice"))
        except Exception as exc:
            logger.warning("Failed to fetch yfinance analyst data for %s (%s): %s", symbol, yf_symbol, exc)
            live_price = current_price or 0.0

        upside_to_target = 0.0
        if live_price and average_target_price:
            upside_to_target = ((average_target_price - live_price) / live_price) * 100

        return AnalystSnapshot(
            symbol=symbol,
            date=today,
            average_target_price=average_target_price,
            upside_to_target=upside_to_target,
            source="yfinance",
        )
