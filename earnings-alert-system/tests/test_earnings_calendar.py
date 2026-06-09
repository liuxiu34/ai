from datetime import date

import requests

from config import AppConfig
from src.earnings_calendar import EarningsCalendarService


class _MockResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def test_fetch_earnings_for_date_parses_nasdaq_rows(monkeypatch):
    service = EarningsCalendarService(AppConfig())

    def fake_get(url, params, timeout, **kwargs):
        assert "nasdaq.com/api/calendar/earnings" in url
        assert params["date"] == "2026-06-01"
        assert timeout == service.config.request_timeout
        return _MockResponse(
            {
                "data": {
                    "rows": [
                        {
                            "symbol": "HPE",
                            "name": "Hewlett Packard Enterprise Company",
                            "time": "time-after-hours",
                        }
                    ]
                }
            }
        )

    monkeypatch.setattr(service.primary_session, "get", fake_get)
    if service.primary_session is not service.session:
        monkeypatch.setattr(service.session, "get", fake_get)

    rows = service._fetch_earnings_for_date(date(2026, 6, 1))

    assert rows[0]["symbol"] == "HPE"
    assert service._normalize_earnings_time(rows[0]["time"]) == "盘后"


def test_fetch_earnings_for_date_handles_empty_rows(monkeypatch):
    service = EarningsCalendarService(AppConfig())

    monkeypatch.setattr(
        service.primary_session,
        "get",
        lambda *args, **kwargs: _MockResponse({"data": {"rows": None}}),
    )
    if service.primary_session is not service.session:
        monkeypatch.setattr(
            service.session,
            "get",
            lambda *args, **kwargs: _MockResponse({"data": {"rows": None}}),
        )

    rows = service._fetch_earnings_for_date(date(2026, 6, 1))

    assert rows == []


def test_fetch_earnings_for_date_falls_back_after_ssl_error(monkeypatch):
    service = EarningsCalendarService(AppConfig())

    def raise_ssl_error(*args, **kwargs):
        raise requests.exceptions.SSLError("ssl eof")

    def return_rows(*args, **kwargs):
        return _MockResponse(
            {
                "data": {
                    "rows": [
                        {
                            "symbol": "SAIC",
                            "name": "Science Applications International Corporation",
                            "time": "time-pre-market",
                        }
                    ]
                }
            }
        )

    monkeypatch.setattr(service.primary_session, "get", raise_ssl_error)
    monkeypatch.setattr(service.session, "get", return_rows)

    rows = service._fetch_earnings_for_date(date(2026, 6, 1))

    assert rows[0]["symbol"] == "SAIC"


def test_fetch_earnings_for_date_returns_empty_when_all_requests_fail(monkeypatch):
    service = EarningsCalendarService(AppConfig())

    def raise_ssl_error(*args, **kwargs):
        raise requests.exceptions.SSLError("ssl eof")

    monkeypatch.setattr(service.primary_session, "get", raise_ssl_error)
    monkeypatch.setattr(service.session, "get", raise_ssl_error)

    rows = service._fetch_earnings_for_date(date(2026, 6, 1))

    assert rows == []
