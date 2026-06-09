from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import requests
import yfinance as yf

from src.utils import get_logger, normalize_yahoo_symbol


logger = get_logger(__name__)


class NewsCollector:
    def __init__(self, finnhub_api_key: str, request_timeout: int = 20) -> None:
        self.finnhub_api_key = finnhub_api_key
        self.request_timeout = request_timeout

    def fetch_recent_news(self, symbol: str, days: int = 30) -> list[dict]:
        items = self._fetch_finnhub_news(symbol, days)
        if items:
            return items
        return self._fetch_yfinance_news(symbol)

    def _fetch_finnhub_news(self, symbol: str, days: int) -> list[dict]:
        if not self.finnhub_api_key:
            return []

        today = date.today()
        from_date = today - timedelta(days=days)
        response = requests.get(
            "https://finnhub.io/api/v1/company-news",
            params={
                "symbol": symbol,
                "from": from_date.isoformat(),
                "to": today.isoformat(),
                "token": self.finnhub_api_key,
            },
            timeout=self.request_timeout,
        )
        if not response.ok:
            return []

        records = response.json()
        normalized: list[dict] = []
        for item in records[:20]:
            normalized.append(
                {
                    "title": (item.get("headline") or "").strip(),
                    "url": item.get("url") or "",
                    "source": item.get("source") or "finnhub",
                    "published_at": self._from_unix_timestamp(item.get("datetime")),
                    "raw_content": (item.get("summary") or "").strip(),
                }
            )
        return [item for item in normalized if item["title"]]

    @staticmethod
    def _fetch_yfinance_news(symbol: str) -> list[dict]:
        yf_symbol = normalize_yahoo_symbol(symbol)
        try:
            ticker = yf.Ticker(yf_symbol)
            records = getattr(ticker, "news", []) or []
        except Exception as exc:
            logger.warning("Failed to fetch yfinance news for %s (%s): %s", symbol, yf_symbol, exc)
            return []

        normalized: list[dict] = []
        for item in records[:20]:
            content = item.get("content") or {}
            canonical_url = content.get("canonicalUrl") or {}
            normalized.append(
                {
                    "title": (content.get("title") or item.get("title") or "").strip(),
                    "url": canonical_url.get("url") or item.get("link") or "",
                    "source": content.get("provider", {}).get("displayName") or "yfinance",
                    "published_at": NewsCollector._from_unix_timestamp(content.get("pubDate")),
                    "raw_content": (content.get("summary") or item.get("summary") or "").strip(),
                }
            )
        return [item for item in normalized if item["title"]]

    @staticmethod
    def _from_unix_timestamp(value: object) -> str:
        if value is None:
            return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        try:
            if isinstance(value, str) and "T" in value:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
            return datetime.fromtimestamp(int(value), tz=timezone.utc).replace(microsecond=0).isoformat()
        except (TypeError, ValueError, OSError):
            return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
