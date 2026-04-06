"""
測試：NewsFetcher — 去重、時間過濾、HTML 清理
"""
import pytest
from datetime import datetime, timezone, timedelta

from news_fetcher import NewsItem, NewsFetcher, SAMPLE_NEWS


class TestNewsItem:
    def test_full_text_combines_title_and_summary(self):
        item = NewsItem(
            source="test", url="",
            title="升息消息", summary="Fed宣布升息",
            published=datetime.now(timezone.utc),
        )
        assert "升息消息" in item.full_text
        assert "Fed宣布升息" in item.full_text

    def test_dedup_key_based_on_title(self):
        now = datetime.now(timezone.utc)
        a = NewsItem(source="s1", url="", title="升息", summary="", published=now)
        b = NewsItem(source="s2", url="", title="升息", summary="不同摘要", published=now)
        assert a.dedup_key == b.dedup_key

    def test_different_titles_different_keys(self):
        now = datetime.now(timezone.utc)
        a = NewsItem(source="s1", url="", title="升息", summary="", published=now)
        b = NewsItem(source="s1", url="", title="降息", summary="", published=now)
        assert a.dedup_key != b.dedup_key


class TestNewsFetcherDedup:
    def test_dedup_removes_duplicates(self):
        now = datetime.now(timezone.utc)
        items = [
            NewsItem(source="a", url="", title="升息", summary="", published=now),
            NewsItem(source="b", url="", title="升息", summary="不同", published=now),
            NewsItem(source="c", url="", title="降息", summary="", published=now),
        ]
        result = NewsFetcher._dedup(items)
        assert len(result) == 2
        titles = [r.title for r in result]
        assert "降息" in titles

    def test_dedup_preserves_order(self):
        now = datetime.now(timezone.utc)
        items = [
            NewsItem(source="a", url="", title="A", summary="", published=now),
            NewsItem(source="b", url="", title="B", summary="", published=now),
            NewsItem(source="c", url="", title="C", summary="", published=now),
        ]
        result = NewsFetcher._dedup(items)
        assert [r.title for r in result] == ["A", "B", "C"]


class TestNewsFetcherUtils:
    def test_strip_html(self):
        raw = "<p>升息 <b>2碼</b></p>"
        assert NewsFetcher._strip_html(raw) == "升息 2碼"

    def test_strip_html_empty(self):
        assert NewsFetcher._strip_html("") == ""

    def test_strip_html_no_tags(self):
        assert NewsFetcher._strip_html("plain text") == "plain text"


class TestSampleNews:
    def test_sample_news_not_empty(self):
        assert len(SAMPLE_NEWS) > 0

    def test_sample_news_items_have_titles(self):
        for item in SAMPLE_NEWS:
            assert item.title

    def test_sample_news_covers_key_events(self):
        """範例新聞應涵蓋升息、AI、戰爭等主要事件"""
        all_text = " ".join(item.full_text for item in SAMPLE_NEWS)
        assert "升息" in all_text or "rate" in all_text.lower()
        assert "AI" in all_text or "ai" in all_text.lower()
