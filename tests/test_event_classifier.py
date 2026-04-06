"""
測試：EventClassifier — 關鍵字分類與互斥事件抑制
"""
import pytest
from datetime import datetime, timezone

from news_fetcher import NewsItem
from event_classifier import EventClassifier


def _make_item(title: str, summary: str = "") -> NewsItem:
    return NewsItem(
        source="test", url="",
        title=title, summary=summary,
        published=datetime.now(timezone.utc),
    )


class TestEventClassifier:
    def setup_method(self):
        self.clf = EventClassifier()

    # ── 基本命中 ────────────────────────────────────────────────

    def test_detects_rate_hike(self):
        items = [_make_item("聯準會宣布升息2碼")]
        events = self.clf.classify_batch(items)
        ids = [e.event_id for e in events]
        assert "rate_hike" in ids

    def test_detects_ai_boom(self):
        items = [_make_item("AI boom drives GPU demand to record high", "generative AI infrastructure spending surges")]
        events = self.clf.classify_batch(items)
        ids = [e.event_id for e in events]
        assert "ai_boom" in ids

    def test_detects_war(self):
        items = [_make_item("中東戰事升溫 地緣政治風險加劇")]
        events = self.clf.classify_batch(items)
        ids = [e.event_id for e in events]
        assert "war" in ids

    def test_detects_english_keyword(self):
        items = [_make_item("Fed hikes rates by 50 basis points")]
        events = self.clf.classify_batch(items)
        ids = [e.event_id for e in events]
        assert "rate_hike" in ids

    # ── 互斥事件抑制 ────────────────────────────────────────────

    def test_mutually_exclusive_rate(self):
        """升息新聞多於降息 → 應只保留 rate_hike"""
        items = [
            _make_item("Fed升息"),
            _make_item("Fed升息兩碼"),
            _make_item("降息預期"),
        ]
        events = self.clf.classify_batch(items)
        ids = [e.event_id for e in events]
        assert "rate_hike" in ids
        assert "rate_cut" not in ids

    def test_mutually_exclusive_oil(self):
        """油價漲多於跌 → 只保留 oil_up"""
        items = [
            _make_item("油價上漲創今年新高"),
            _make_item("布蘭特原油上漲"),
            _make_item("油價下跌"),
        ]
        events = self.clf.classify_batch(items)
        ids = [e.event_id for e in events]
        assert "oil_up" in ids
        assert "oil_down" not in ids

    # ── 信心值 ──────────────────────────────────────────────────

    def test_confidence_single_article(self):
        items = [_make_item("Fed升息")]
        events = self.clf.classify_batch(items)
        hike = next(e for e in events if e.event_id == "rate_hike")
        assert hike.confidence == pytest.approx(0.7)

    def test_confidence_multiple_articles(self):
        items = [_make_item("Fed升息"), _make_item("聯準會升息2碼")]
        events = self.clf.classify_batch(items)
        hike = next(e for e in events if e.event_id == "rate_hike")
        assert hike.confidence == pytest.approx(1.0)

    # ── 邊界條件 ────────────────────────────────────────────────

    def test_no_news(self):
        assert self.clf.classify_batch([]) == []

    def test_irrelevant_news(self):
        items = [_make_item("今天天氣晴朗"), _make_item("software update released")]
        events = self.clf.classify_batch(items)
        # software 不應命中 war（避免 word-boundary 誤判）
        ids = [e.event_id for e in events]
        assert "war" not in ids

    def test_results_sorted_by_article_count(self):
        items = [
            _make_item("AI熱潮 GPU需求"),
            _make_item("AI伺服器訂單"),
            _make_item("升息"),
        ]
        events = self.clf.classify_batch(items)
        counts = [e.article_count for e in events]
        assert counts == sorted(counts, reverse=True)
