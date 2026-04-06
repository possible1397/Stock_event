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


# ── 測試用假新聞（含模擬 URL，用於 --dry-run）──────────────────
SAMPLE_NEWS: list[NewsItem] = [
    # AI 熱潮（多則，讓圖表有差異）
    NewsItem(
        source="cnyes", url="https://news.cnyes.com/news/id/5800001",
        title="Nvidia GPU需求爆發 輝達市值再創新高",
        summary="生成式AI基礎建設需求持續，Nvidia GPU訂單強勁，AI伺服器廠商廣達、英業達受惠。",
        published=datetime.now(timezone.utc),
    ),
    NewsItem(
        source="cnyes", url="https://news.cnyes.com/news/id/5800002",
        title="台積電CoWoS產能滿載 AI晶片需求不墜",
        summary="台積電AI相關封裝產能全滿，聯發科、AMD AI晶片需求強勁。",
        published=datetime.now(timezone.utc),
    ),
    NewsItem(
        source="moneydj", url="https://www.moneydj.com/KLINE/news/001",
        title="AI伺服器帶動散熱需求 奇鋐雙鴻業績亮眼",
        summary="AI伺服器熱設計功耗提升，散熱模組廠奇鋐、雙鴻、建準訂單能見度高。",
        published=datetime.now(timezone.utc),
    ),
    # 關稅貿易戰（多則）
    NewsItem(
        source="cnyes", url="https://news.cnyes.com/news/id/5800003",
        title="美國加徵關稅 台灣轉單效應受矚目",
        summary="美中貿易摩擦升溫，台灣電子零組件廠鴻海、仁寶可望受惠轉單。",
        published=datetime.now(timezone.utc),
    ),
    NewsItem(
        source="udn", url="https://money.udn.com/money/story/001",
        title="川普關稅升級 供應鏈重組加速 台廠搶單",
        summary="美國對中國加徵高額關稅，台灣半導體、電子廠受惠供應鏈脫鉤趨勢。",
        published=datetime.now(timezone.utc),
    ),
    # 升息
    NewsItem(
        source="reuters", url="https://www.reuters.com/markets/rates-bonds/001",
        title="Fed宣布升息2碼 市場震盪 成長股承壓",
        summary="聯準會FOMC會議決定升息2碼，抑制通膨，成長股折現率上升。",
        published=datetime.now(timezone.utc),
    ),
    # 戰爭/地緣
    NewsItem(
        source="cnbc", url="https://www.cnbc.com/2026/04/06/oil-prices.html",
        title="中東戰事升溫 布蘭特原油突破90美元",
        summary="地緣政治風險加劇，油價上漲，航空股跌，軍工需求升溫。",
        published=datetime.now(timezone.utc),
    ),
    # 記憶體
    NewsItem(
        source="moneydj", url="https://www.moneydj.com/KLINE/news/002",
        title="DRAM報價連續上漲 南亞科華邦電獲利看俏",
        summary="記憶體供不應求，HBM需求強勁，DRAM現貨價走揚，南亞科、群聯受惠。",
        published=datetime.now(timezone.utc),
    ),
    # 台積電額外提及
    NewsItem(
        source="ctee", url="https://ctee.com.tw/news/tech/001",
        title="台積電3奈米良率提升 法人上調目標價",
        summary="台積電先進製程良率改善，聯發科、Nvidia等客戶受惠，法人持續看好。",
        published=datetime.now(timezone.utc),
    ),
]
