from __future__ import annotations

import json
import re
from typing import Any

from config import AppConfig
from src.models import NewsAnalysis

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None


EVENT_KEYWORDS = {
    "AI": ["ai", "artificial intelligence", "gpu", "inference", "llm"],
    "major_order": ["order", "purchase", "backlog", "contract win", "award"],
    "government_contract": ["government", "department", "military", "defense", "federal"],
    "new_product": ["launch", "released", "introduces", "unveils", "product"],
    "merger_acquisition": ["acquire", "acquisition", "merge", "merger"],
    "share_buyback": ["buyback", "repurchase"],
    "guidance_raise": ["raise guidance", "guidance increased", "outlook raised"],
    "customer_deal": ["partnership", "customer", "strategic agreement"],
    "regulatory_approval": ["approved", "clearance", "authorization"],
    "executive_change": ["ceo", "cfo", "executive", "chairman", "leadership"],
    "financial_warning": ["warning", "miss", "cuts forecast", "weak demand"],
    "litigation": ["lawsuit", "probe", "investigation", "subpoena"],
}

POSITIVE_KEYWORDS = [
    "beat",
    "raises guidance",
    "partnership",
    "contract",
    "approval",
    "buyback",
    "record",
    "growth",
    "strong demand",
]

NEGATIVE_KEYWORDS = [
    "miss",
    "cuts guidance",
    "lawsuit",
    "investigation",
    "probe",
    "delay",
    "warning",
    "layoff",
]


class LLMAnalyzer:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.client = OpenAI(api_key=config.openai_api_key) if config.openai_api_key and OpenAI else None

    def analyze_news_item(self, symbol: str, item: dict[str, Any]) -> NewsAnalysis:
        title = item.get("title", "").strip()
        raw_content = item.get("raw_content", "").strip()
        if self.client:
            try:
                llm_result = self._analyze_with_openai(title=title, raw_content=raw_content)
                return NewsAnalysis(
                    symbol=symbol,
                    title=title,
                    url=item.get("url", ""),
                    source=item.get("source", ""),
                    published_at=item.get("published_at", ""),
                    raw_content=raw_content,
                    sentiment=llm_result["sentiment"],
                    event_types=llm_result["event_types"],
                    impact_score=int(llm_result["impact_score"]),
                    llm_summary=llm_result["summary"],
                )
            except Exception:
                pass
        fallback = self._keyword_fallback(title=title, raw_content=raw_content)
        return NewsAnalysis(
            symbol=symbol,
            title=title,
            url=item.get("url", ""),
            source=item.get("source", ""),
            published_at=item.get("published_at", ""),
            raw_content=raw_content,
            sentiment=fallback["sentiment"],
            event_types=fallback["event_types"],
            impact_score=fallback["impact_score"],
            llm_summary=fallback["summary"],
        )

    def _analyze_with_openai(self, title: str, raw_content: str) -> dict[str, Any]:
        prompt = f"""
        你是金融新闻分析器。请只输出 JSON，不要输出额外解释。
        字段要求：
        - sentiment: positive | negative | neutral
        - event_types: 字符串数组
        - summary: 简短中文总结，不超过 50 字
        - impact_score: -30 到 30 的整数

        标题：{title}
        内容：{raw_content}
        """
        response = self.client.chat.completions.create(
            model=self.config.openai_model,
            messages=[
                {"role": "system", "content": "你只返回严格 JSON。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
        )
        content = response.choices[0].message.content or "{}"
        parsed = json.loads(self._extract_json(content))
        return {
            "sentiment": parsed.get("sentiment", "neutral"),
            "event_types": parsed.get("event_types", []),
            "summary": parsed.get("summary", "LLM 未返回有效摘要"),
            "impact_score": int(parsed.get("impact_score", 0)),
        }

    @staticmethod
    def _extract_json(content: str) -> str:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        return match.group(0) if match else "{}"

    def _keyword_fallback(self, title: str, raw_content: str) -> dict[str, Any]:
        text = f"{title} {raw_content}".lower()
        event_types = [event for event, words in EVENT_KEYWORDS.items() if any(word in text for word in words)]

        score = 0
        if any(word in text for word in POSITIVE_KEYWORDS):
            score += 12
        if any(word in text for word in NEGATIVE_KEYWORDS):
            score -= 15
        if "ai" in text:
            score += 8
        if "guidance" in text and "raise" in text:
            score += 10
        if "investigation" in text or "lawsuit" in text:
            score -= 10

        sentiment = "neutral"
        if score > 3:
            sentiment = "positive"
        elif score < -3:
            sentiment = "negative"

        return {
            "sentiment": sentiment,
            "event_types": event_types,
            "impact_score": max(-30, min(30, score)),
            "summary": self._build_summary(title, event_types, sentiment),
        }

    @staticmethod
    def _build_summary(title: str, event_types: list[str], sentiment: str) -> str:
        if event_types:
            return f"{sentiment}，涉及 {', '.join(event_types[:3])}：{title[:28]}"
        return f"{sentiment}，新闻摘要：{title[:32]}"
