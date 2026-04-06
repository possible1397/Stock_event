"""
新聞抓取模組 — 從台灣財經 RSS 拉取近期新聞
"""
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

import certifi
import feedparser
import requests

# 台灣財經 RSS 來源
RSS_FEEDS_TW: dict[str, str] = {
    "cnyes_tw":    "https://www.cnyes.com/rss/cat/tw_stock",
    "cnyes_macro": "https://www.cnyes.com/rss/cat/wd_stock",
    "moneydj":     "https://www.moneydj.com/rss/news.xml",
    "ctee":        "https://ctee.com.tw/feed",
    "udn_money":   "https://money.udn.com/rssfeed/news/1001/5591/USD",
    "yahoo_tw":    "https://tw.stock.yahoo.com/rss",
}

# 國際財經 RSS 來源（英文）
RSS_FEEDS_INTL: dict[str, str] = {
    "reuters_biz":    "https://feeds.reuters.com/reuters/businessNews",
    "reuters_finance": "https://feeds.reuters.com/reuters/financialNewsAndInvestment",
    "marketwatch":    "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    "cnbc_top":       "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
    "cnbc_economy":   "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258",
    "yahoo_finance":  "https://finance.yahoo.com/news/rssindex",
    "seeking_alpha":  "https://seekingalpha.com/market_currents.xml",
    "investing_com":  "https://www.investing.com/rss/news.rss",
}

# 合併（預設全開）
RSS_FEEDS: dict[str, str] = {**RSS_FEEDS_TW, **RSS_FEEDS_INTL}

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


@dataclass
class NewsItem:
    source: str
    title: str
    summary: str
    url: str
    published: datetime
    full_text: str = field(init=False)

    def __post_init__(self):
        self.full_text = (self.title + " " + self.summary).strip()

    @property
    def dedup_key(self) -> str:
        return hashlib.md5(self.title[:40].encode("utf-8", errors="ignore")).hexdigest()


class NewsFetcher:
    def __init__(self, max_age_hours: int = 24, timeout: int = 10):
        self.max_age_hours = max_age_hours
        self.timeout = timeout

    def fetch_all(self) -> list[NewsItem]:
        """並行抓取所有 RSS，去重後回傳。"""
        all_items: list[NewsItem] = []
        with ThreadPoolExecutor(max_workers=len(RSS_FEEDS)) as ex:
            futures = {
                ex.submit(self._fetch_feed, name, url): name
                for name, url in RSS_FEEDS.items()
            }
            for fut in as_completed(futures):
                name = futures[fut]
                try:
                    items = fut.result()
                    all_items.extend(items)
                except Exception as e:
                    print(f"[Warning] {name} 抓取失敗: {e}")

        return self._dedup(all_items)

    def _fetch_feed(self, source: str, url: str) -> list[NewsItem]:
        """抓單一 RSS feed。"""
        raw_content = self._get(url)
        if not raw_content:
            return []

        parsed = feedparser.parse(raw_content)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.max_age_hours)
        items: list[NewsItem] = []

        for entry in parsed.entries:
            pub_dt = self._parse_published(entry)
            if pub_dt and pub_dt < cutoff:
                continue

            title   = getattr(entry, "title",   "") or ""
            summary = getattr(entry, "summary", "") or ""
            url_link = getattr(entry, "link",   "") or ""

            # 去除 HTML tag
            summary = self._strip_html(summary)

            if not title:
                continue

            items.append(NewsItem(
                source=source,
                title=title.strip(),
                summary=summary.strip(),
                url=url_link,
                published=pub_dt or datetime.now(timezone.utc),
            ))

        return items

    def _get(self, url: str) -> bytes | None:
        """HTTP GET with SSL fallback (同 Stock 專案慣例)。"""
        try:
            resp = requests.get(
                url, headers=_HEADERS,
                timeout=self.timeout, verify=certifi.where()
            )
            resp.raise_for_status()
            return resp.content
        except Exception:
            try:
                resp = requests.get(
                    url, headers=_HEADERS,
                    timeout=self.timeout, verify=False
                )
                resp.raise_for_status()
                return resp.content
            except Exception:
                return None

    @staticmethod
    def _parse_published(entry) -> datetime | None:
        import time as _time
        pt = getattr(entry, "published_parsed", None)
        if pt:
            return datetime.fromtimestamp(_time.mktime(pt), tz=timezone.utc)
        # fallback: updated_parsed
        pt = getattr(entry, "updated_parsed", None)
        if pt:
            return datetime.fromtimestamp(_time.mktime(pt), tz=timezone.utc)
        return None

    @staticmethod
    def _strip_html(text: str) -> str:
        import re
        return re.sub(r"<[^>]+>", "", text)

    @staticmethod
    def _dedup(items: list[NewsItem]) -> list[NewsItem]:
        seen: set[str] = set()
        result: list[NewsItem] = []
        for item in items:
            key = item.dedup_key
            if key not in seen:
                seen.add(key)
                result.append(item)
        return result


# ── 測試用假新聞 ──────────────────────────────────────────────
SAMPLE_NEWS: list[NewsItem] = [
    NewsItem(
        source="sample", url="",
        title="Fed宣布升息2碼 市場震盪",
        summary="聯準會FOMC會議決定升息2碼，抑制通膨，成長股承壓。",
        published=datetime.now(timezone.utc),
    ),
    NewsItem(
        source="sample", url="",
        title="AI熱潮持續 GPU需求創新高 台積電訂單滿載",
        summary="生成式AI基礎建設需求爆發，AI伺服器、散熱模組廠商受惠。",
        published=datetime.now(timezone.utc),
    ),
    NewsItem(
        source="sample", url="",
        title="中東戰事升溫 油價突破90美元",
        summary="地緣政治風險加劇，布蘭特原油上漲，航空股跌幅明顯。",
        published=datetime.now(timezone.utc),
    ),
    NewsItem(
        source="sample", url="",
        title="美國加徵關稅 台灣轉單效應受矚目",
        summary="美中貿易摩擦升溫，台灣電子零組件廠可望受惠轉單。",
        published=datetime.now(timezone.utc),
    ),
    NewsItem(
        source="sample", url="",
        title="DRAM報價連續上漲 記憶體廠商獲利看俏",
        summary="記憶體供不應求，HBM需求強勁，DRAM現貨價走揚。",
        published=datetime.now(timezone.utc),
    ),
]
