from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class EarningsEvent:
    symbol: str
    company_name: str
    earnings_date: str
    earnings_time: str
    days_until_earnings: int
    source: str
    market_cap: float = 0.0


@dataclass(slots=True)
class PriceMetrics:
    symbol: str
    date: str
    latest_close: float = 0.0
    return_7d: float = 0.0
    return_30d: float = 0.0
    spy_relative_7d: float = 0.0
    spy_relative_30d: float = 0.0
    is_20d_high: bool = False
    is_60d_high: bool = False
    volume_ratio: float = 0.0
    above_ma20: bool = False
    above_ma50: bool = False


@dataclass(slots=True)
class NewsAnalysis:
    symbol: str
    title: str
    url: str
    source: str
    published_at: str
    raw_content: str
    sentiment: str = "neutral"
    event_types: list[str] = field(default_factory=list)
    impact_score: int = 0
    llm_summary: str = ""


@dataclass(slots=True)
class AnalystSnapshot:
    symbol: str
    date: str
    target_price_upgrades: int = 0
    target_price_downgrades: int = 0
    rating_upgrades: int = 0
    rating_downgrades: int = 0
    average_target_price: float = 0.0
    upside_to_target: float = 0.0
    source: str = "unavailable"


@dataclass(slots=True)
class ScoreCard:
    symbol: str
    date: str
    total_score: int
    priority: str
    reasons: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PredictionOutcome:
    symbol: str
    prediction_date: str
    earnings_date: str
    predicted_priority: str
    actual_return_pct: float = 0.0
    was_correct: bool = False
    evaluated_at: str = ""


@dataclass(slots=True)
class WatchlistItem:
    symbol: str
    company_name: str
    earnings_date: str
    earnings_time: str
    total_score: int
    priority: str
    reasons: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
