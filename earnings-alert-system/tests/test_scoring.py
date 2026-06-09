from src.models import AnalystSnapshot, EarningsEvent, NewsAnalysis, PriceMetrics
from src.scoring import calculate_score


def test_calculate_score_promotes_strong_setup():
    event = EarningsEvent(
        symbol="DELL",
        company_name="Dell Technologies",
        earnings_date="2026-06-05",
        earnings_time="盘后",
        days_until_earnings=7,
        source="test",
    )
    metrics = PriceMetrics(
        symbol="DELL",
        date="2026-05-30",
        return_7d=8,
        return_30d=22,
        spy_relative_7d=4,
        spy_relative_30d=14,
        is_20d_high=True,
        is_60d_high=True,
        volume_ratio=2.2,
        above_ma20=True,
        above_ma50=True,
    )
    news = [
        NewsAnalysis(
            symbol="DELL",
            title="Dell wins AI server order",
            url="",
            source="test",
            published_at="2026-05-25T00:00:00+00:00",
            raw_content="Major AI order and guidance raise",
            sentiment="positive",
            event_types=["AI", "major_order", "guidance_raise"],
            impact_score=28,
            llm_summary="利好",
        )
    ]
    analyst = AnalystSnapshot(
        symbol="DELL",
        date="2026-05-30",
        target_price_upgrades=2,
        rating_upgrades=2,
        average_target_price=180,
        upside_to_target=18,
        source="test",
    )

    scorecard = calculate_score(event, metrics, news, analyst)

    assert scorecard.total_score == 100
    assert scorecard.priority == "高"
    assert "存在 AI 相关重大新闻" in scorecard.reasons


def test_calculate_score_penalizes_negative_news():
    event = EarningsEvent(
        symbol="XYZ",
        company_name="XYZ Corp",
        earnings_date="2026-06-10",
        earnings_time="盘前",
        days_until_earnings=5,
        source="test",
    )
    metrics = PriceMetrics(symbol="XYZ", date="2026-05-30")
    news = [
        NewsAnalysis(
            symbol="XYZ",
            title="XYZ faces investigation",
            url="",
            source="test",
            published_at="2026-05-25T00:00:00+00:00",
            raw_content="Lawsuit and probe",
            sentiment="negative",
            event_types=["litigation"],
            impact_score=-25,
            llm_summary="利空",
        )
    ]
    analyst = AnalystSnapshot(symbol="XYZ", date="2026-05-30", source="test")

    scorecard = calculate_score(event, metrics, news, analyst)

    assert scorecard.total_score < 20
    assert "存在明确利空新闻" in scorecard.risks
