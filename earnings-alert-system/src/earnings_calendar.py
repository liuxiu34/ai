from __future__ import annotations

from datetime import date, timedelta

import requests

try:
    from curl_cffi import requests as curl_requests
except ImportError:  # pragma: no cover
    curl_requests = None

from config import AppConfig
from src.models import EarningsEvent
from src.utils import parse_market_cap


class EarningsCalendarService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.session = requests.Session()
        self.browser_session = curl_requests.Session() if curl_requests else None
        self.primary_session = self.browser_session or self.session
        self._default_headers = {
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://www.nasdaq.com",
            "Referer": "https://www.nasdaq.com/",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/136.0.0.0 Safari/537.36"
            ),
        }
        self.session.headers.update(self._default_headers)
        if self.browser_session is not None:
            self.browser_session.headers.update(self._default_headers)

    def get_upcoming_earnings(self, days: int | None = None) -> list[EarningsEvent]:
        window = days or self.config.scan_window_days
        start_date = date.today()
        events: list[EarningsEvent] = []

        for offset in range(window + 1):
            earnings_date = start_date + timedelta(days=offset)
            records = self._fetch_earnings_for_date(earnings_date)
            for item in records:
                symbol = (item.get("symbol") or "").strip().upper()
                if not symbol:
                    continue
                events.append(
                    EarningsEvent(
                        symbol=symbol,
                        company_name=(item.get("name") or symbol).strip(),
                        earnings_date=earnings_date.isoformat(),
                        earnings_time=self._normalize_earnings_time(item.get("time")),
                        days_until_earnings=offset,
                        source="nasdaq",
                        market_cap=parse_market_cap(item.get("marketCap")),
                    )
                )

        return sorted(events, key=lambda event: (event.earnings_date, event.symbol))

    def _fetch_earnings_for_date(self, earnings_date: date) -> list[dict]:
        sessions_to_try = [self.primary_session]
        if self.primary_session is not self.session:
            sessions_to_try.append(self.session)

        for session in sessions_to_try:
            try:
                rows = self._request_rows(session, earnings_date)
                if rows:
                    return rows
            except Exception:
                continue

        return []

    def _request_rows(self, session: requests.Session, earnings_date: date) -> list[dict]:
        request_kwargs = {
            "params": {"date": earnings_date.isoformat()},
            "timeout": self.config.request_timeout,
        }
        if curl_requests and session is self.browser_session:
            request_kwargs["impersonate"] = "chrome"

        response = session.get(
            "https://api.nasdaq.com/api/calendar/earnings",
            **request_kwargs,
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data") or {}
        rows = data.get("rows")
        if not isinstance(rows, list):
            return []
        return rows

    @staticmethod
    def _normalize_earnings_time(raw_value: str | None) -> str:
        mapping = {
            "time-pre-market": "盘前",
            "time-after-hours": "盘后",
            "time-not-supplied": "未知",
        }
        if not raw_value:
            return "未知"
        return mapping.get(raw_value.lower(), raw_value)
