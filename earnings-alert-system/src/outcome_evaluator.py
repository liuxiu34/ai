from __future__ import annotations

from datetime import date, timedelta, timezone, datetime

import yfinance as yf

from src.database import DatabaseManager
from src.models import PredictionOutcome
from src.utils import get_logger, normalize_yahoo_symbol


logger = get_logger(__name__)


class OutcomeEvaluator:
    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    def evaluate_pending(self) -> int:
        pending = self.database.get_unevaluated_predictions()
        count = 0
        for row in pending:
            symbol = row["symbol"]
            earnings_date = row["earnings_date"]
            prediction_date = row["prediction_date"]
            predicted_priority = row["predicted_priority"]

            actual_return = self._fetch_post_earnings_return(symbol, earnings_date)
            if actual_return is None:
                continue

            outcome = PredictionOutcome(
                symbol=symbol,
                prediction_date=prediction_date,
                earnings_date=earnings_date,
                predicted_priority=predicted_priority,
                actual_return_pct=round(actual_return, 4),
                was_correct=actual_return > 0,
                evaluated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            )
            self.database.update_prediction_outcome(outcome)
            count += 1
            logger.info(
                "Evaluated %s (earnings %s): return=%.2f%%, correct=%s",
                symbol, earnings_date, actual_return, outcome.was_correct,
            )

        if count:
            logger.info("Evaluated %d past predictions.", count)
        return count

    @staticmethod
    def _fetch_post_earnings_return(symbol: str, earnings_date_str: str) -> float | None:
        yf_symbol = normalize_yahoo_symbol(symbol)
        try:
            earnings_dt = date.fromisoformat(earnings_date_str)
            start = earnings_dt - timedelta(days=7)
            end = earnings_dt + timedelta(days=10)
            history = yf.download(
                yf_symbol,
                start=start,
                end=end,
                progress=False,
                auto_adjust=True,
                threads=False,
            )
        except Exception as exc:
            logger.warning("Failed to fetch price history for %s around %s: %s", symbol, earnings_date_str, exc)
            return None

        if history.empty or len(history) < 2:
            return None

        close = history["Close"]
        if hasattr(close, "iloc") and close.ndim > 1:
            close = close.iloc[:, 0]
        close = close.dropna()
        if len(close) < 2:
            return None

        dates = [d.date() for d in close.index]
        earnings_dt = date.fromisoformat(earnings_date_str)

        # Find last trading day before earnings and first trading day on/after
        pre_idx = None
        post_idx = None
        for i, d in enumerate(dates):
            if d < earnings_dt:
                pre_idx = i
            elif post_idx is None:
                post_idx = i

        if pre_idx is None or post_idx is None:
            return None

        # Use 2 trading days after earnings for a settled post-earnings price
        post_idx = min(post_idx + 1, len(dates) - 1)

        pre_price = float(close.iloc[pre_idx])
        post_price = float(close.iloc[post_idx])
        if not pre_price:
            return None

        return ((post_price - pre_price) / pre_price) * 100
