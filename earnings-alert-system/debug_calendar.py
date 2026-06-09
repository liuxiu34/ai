from pathlib import Path

from config import load_config
from src.earnings_calendar import EarningsCalendarService


service = EarningsCalendarService(load_config())
results = []
for day in ["2026-05-30", "2026-06-01", "2026-06-02"]:
    response = service.session.get(
        "https://api.nasdaq.com/api/calendar/earnings",
        params={"date": day},
        timeout=service.config.request_timeout,
    )
    try:
        payload = response.json()
        rows = (payload.get("data") or {}).get("rows")
        row_count = len(rows) if isinstance(rows, list) else -1
    except Exception as exc:
        payload = {"error": repr(exc)}
        row_count = -999
    results.append(
        {
            "date": day,
            "status": response.status_code,
            "row_count": row_count,
            "payload": payload,
        }
    )

items = service.get_upcoming_earnings(days=14)
Path("debug_calendar_out.txt").write_text(
    repr(
        {
            "events_count": len(items),
            "sample": [repr(item) for item in items[:5]],
            "requests": results,
        }
    ),
    encoding="utf-8",
)
