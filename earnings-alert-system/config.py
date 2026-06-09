from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"


@dataclass(slots=True)
class AppConfig:
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    finnhub_api_key: str = ""
    alpha_vantage_api_key: str = ""
    polygon_api_key: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = ""
    database_url: str = "sqlite:///data/app.db"
    scan_window_days: int = 7
    max_scan_symbols: int = 20
    min_market_cap_usd: float = 1_000_000_000.0
    news_window_days: int = 30
    max_news_items: int = 3
    request_timeout: int = 20

    @property
    def database_path(self) -> Path:
        if self.database_url.startswith("sqlite:///"):
            raw_path = self.database_url.replace("sqlite:///", "", 1)
            db_path = Path(raw_path)
            if not db_path.is_absolute():
                db_path = BASE_DIR / raw_path
            return db_path
        raise ValueError("Only sqlite DATABASE_URL is supported in the MVP.")


def load_config() -> AppConfig:
    load_dotenv()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return AppConfig(
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip(),
        finnhub_api_key=os.getenv("FINNHUB_API_KEY", "").strip(),
        alpha_vantage_api_key=os.getenv("ALPHA_VANTAGE_API_KEY", "").strip(),
        polygon_api_key=os.getenv("POLYGON_API_KEY", "").strip(),
        reddit_client_id=os.getenv("REDDIT_CLIENT_ID", "").strip(),
        reddit_client_secret=os.getenv("REDDIT_CLIENT_SECRET", "").strip(),
        reddit_user_agent=os.getenv("REDDIT_USER_AGENT", "").strip(),
        database_url=os.getenv("DATABASE_URL", "sqlite:///data/app.db").strip(),
        scan_window_days=int(os.getenv("SCAN_WINDOW_DAYS", "7")),
        max_scan_symbols=int(os.getenv("MAX_SCAN_SYMBOLS", "20")),
        min_market_cap_usd=float(os.getenv("MIN_MARKET_CAP_USD", "1000000000")),
        news_window_days=int(os.getenv("NEWS_WINDOW_DAYS", "30")),
        max_news_items=int(os.getenv("MAX_NEWS_ITEMS", "3")),
        request_timeout=int(os.getenv("REQUEST_TIMEOUT", "20")),
    )
