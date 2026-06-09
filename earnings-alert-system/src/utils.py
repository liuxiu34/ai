from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path


_LOGGING_CONFIGURED = False


def get_logger(name: str) -> logging.Logger:
    global _LOGGING_CONFIGURED
    if not _LOGGING_CONFIGURED:
        log_dir = Path(__file__).resolve().parents[1] / "data"
        log_dir.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(log_dir / "app.log", encoding="utf-8"),
            ],
        )
        _LOGGING_CONFIGURED = True
    return logging.getLogger(name)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def ensure_parent_dir(file_path: Path) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)


def safe_float(value: object, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def bool_to_int(value: bool) -> int:
    return 1 if value else 0


def normalize_yahoo_symbol(symbol: str) -> str:
    cleaned = (symbol or "").strip().upper()
    return cleaned.replace(".", "-")


def parse_market_cap(value: object, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip().upper()
    if not text or text == "N/A":
        return default

    multiplier = 1.0
    suffix_multipliers = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}
    suffix = text[-1]
    if suffix in suffix_multipliers:
        multiplier = suffix_multipliers[suffix]
        text = text[:-1]

    text = re.sub(r"[^0-9.]", "", text)
    if not text:
        return default
    return safe_float(text, default) * multiplier
