from __future__ import annotations

from src.models import AnalystSnapshot, EarningsEvent, NewsAnalysis, PriceMetrics, ScoreCard


def calculate_score(
    earnings_event: EarningsEvent,
    price_metrics: PriceMetrics,
    news_items: list[NewsAnalysis],
    analyst_snapshot: AnalystSnapshot,
    has_news_data: bool = True,
    has_analyst_data: bool = True,
) -> ScoreCard:
    score = 0
    reasons: list[str] = []
    risks: list[str] = []

    if 1 <= earnings_event.days_until_earnings <= 7:
        score += 10
        reasons.append("财报将在 1-7 天内公布")
    elif 8 <= earnings_event.days_until_earnings <= 14:
        score += 5
        reasons.append("财报将在 8-14 天内公布")

    if price_metrics.return_7d > 5:
        score += 10
        reasons.append("近 7 天涨幅超过 5%")
    if price_metrics.return_30d > 15:
        score += 15
        reasons.append("近 30 天涨幅超过 15%")
    if price_metrics.spy_relative_30d > 10:
        score += 15
        reasons.append("近 30 天显著跑赢 SPY")
    if price_metrics.is_20d_high:
        score += 10
        reasons.append("股价创 20 日新高")
    if price_metrics.is_60d_high:
        score += 15
        reasons.append("股价创 60 日新高")
    if price_metrics.volume_ratio > 1.8:
        score += 10
        reasons.append("成交量明显放大")
    if price_metrics.above_ma20 and price_metrics.above_ma50:
        score += 5
        reasons.append("价格位于 20/50 日均线之上")

    if analyst_snapshot.target_price_upgrades > 0:
        score += 20
        reasons.append("分析师近期上调目标价")
    if analyst_snapshot.rating_upgrades > 0:
        score += 20
        reasons.append("分析师近期上调评级")
    if analyst_snapshot.rating_upgrades >= 2 or analyst_snapshot.target_price_upgrades >= 2:
        score += 25
        reasons.append("多家分析师连续上调")
    if analyst_snapshot.rating_downgrades > 0:
        score -= 20
        risks.append("存在分析师下调评级")
    if analyst_snapshot.target_price_downgrades > 0:
        score -= 15
        risks.append("存在目标价下调")
    if analyst_snapshot.upside_to_target > 15:
        score += 10
        reasons.append("当前价格距离平均目标价仍有空间")

    total_news_impact = sum(item.impact_score for item in news_items)
    event_types = {event for item in news_items for event in item.event_types}
    if any(item.sentiment == "positive" for item in news_items):
        score += 20
        reasons.append("存在明确利好新闻")
    if "AI" in event_types:
        score += 20
        reasons.append("存在 AI 相关重大新闻")
    if "major_order" in event_types:
        score += 20
        reasons.append("存在重大订单新闻")
    if "government_contract" in event_types:
        score += 20
        reasons.append("存在政府合同新闻")
    if "guidance_raise" in event_types:
        score += 25
        reasons.append("公司上调业绩指引")
    if "share_buyback" in event_types:
        score += 10
        reasons.append("公司存在股票回购动作")
    if "merger_acquisition" in event_types:
        score += 10
        reasons.append("公司存在并购相关催化")
    if any(item.sentiment == "negative" for item in news_items):
        score -= 30
        risks.append("存在明确利空新闻")
    if total_news_impact < -10:
        risks.append("近期新闻整体情绪偏弱")

    if price_metrics.return_30d > 25 and total_news_impact <= 0 and analyst_snapshot.rating_upgrades == 0:
        score -= 10
        risks.append("财报前涨幅较大但基本面催化不足")

    if not has_news_data:
        risks.append("新闻模块缺少可用数据，结论可能不完整")
    if not has_analyst_data:
        risks.append("分析师模块缺少可用数据，结论可能不完整")

    total_score = max(0, min(100, score))
    priority = get_priority(total_score)
    return ScoreCard(
        symbol=earnings_event.symbol,
        date=price_metrics.date,
        total_score=total_score,
        priority=priority,
        reasons=_dedupe(reasons),
        risks=_dedupe(risks),
    )


def get_priority(score: int) -> str:
    if score >= 80:
        return "高"
    if score >= 60:
        return "中"
    return "低"


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            output.append(item)
    return output
