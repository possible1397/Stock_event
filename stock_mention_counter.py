"""
股票提及次數統計器 — 掃描所有新聞標題，統計哪些股票/公司被提及最多次。

不走事件推導，直接從新聞文字中找公司名稱，更直觀。
"""
import re
from dataclasses import dataclass, field

from news_fetcher import NewsItem

# ── 股票名稱對照表 ────────────────────────────────────────────────
# 格式：名稱關鍵字 → (股票代號, 顯示名稱)
# 同一家公司列多個別名，計數時會合併

_RAW: list[tuple[str, str, str]] = [
    # ── 半導體 ──────────────────────────────────────────────────
    ("台積電",   "2330.TW", "台積電"),
    ("TSMC",     "2330.TW", "台積電"),
    ("聯發科",   "2454.TW", "聯發科"),
    ("MediaTek", "2454.TW", "聯發科"),
    ("聯電",     "2303.TW", "聯電"),
    ("日月光",   "3711.TW", "日月光"),
    ("矽力",     "6415.TW", "矽力-KY"),
    ("穩懋",     "3105.TW", "穩懋"),
    ("世界先進", "5347.TW", "世界先進"),
    ("力積電",   "6770.TW", "力積電"),

    # ── AI 伺服器 / 散熱 ────────────────────────────────────────
    ("廣達",     "2382.TW", "廣達"),
    ("英業達",   "2356.TW", "英業達"),
    ("緯穎",     "6669.TWO","緯穎"),
    ("緯創",     "3231.TW", "緯創"),
    ("仁寶",     "2324.TW", "仁寶"),
    ("技嘉",     "2376.TW", "技嘉"),
    ("微星",     "2377.TW", "微星"),
    ("超微",     "2492.TW", "超微"),
    ("雙鴻",     "3324.TW", "雙鴻"),
    ("奇鋐",     "3017.TW", "奇鋐"),
    ("建準",     "2421.TW", "建準"),

    # ── 記憶體 ──────────────────────────────────────────────────
    ("南亞科",   "2408.TW", "南亞科"),
    ("華邦電",   "2344.TW", "華邦電"),
    ("旺宏",     "2337.TW", "旺宏"),
    ("群聯",     "8299.TW", "群聯"),

    # ── 電子代工 / 組件 ─────────────────────────────────────────
    ("鴻海",     "2317.TW", "鴻海"),
    ("Foxconn",  "2317.TW", "鴻海"),
    ("台達電",   "2308.TW", "台達電"),
    ("光寶科",   "2301.TW", "光寶科"),
    ("研華",     "2395.TW", "研華"),
    ("和碩",     "4938.TW", "和碩"),
    ("台光電",   "2383.TW", "台光電"),
    ("台灣大電",  "2383.TW", "台光電"),
    ("正崴",     "2392.TW", "正崴"),

    # ── 金融 ────────────────────────────────────────────────────
    ("富邦金",   "2881.TW", "富邦金"),
    ("富邦",     "2881.TW", "富邦金"),
    ("國泰金",   "2882.TW", "國泰金"),
    ("國泰",     "2882.TW", "國泰金"),
    ("中信金",   "2891.TW", "中信金"),
    ("玉山金",   "2884.TW", "玉山金"),
    ("兆豐金",   "2886.TW", "兆豐金"),
    ("第一金",   "2892.TW", "第一金"),
    ("合庫金",   "5880.TW", "合庫金"),
    ("元大金",   "2885.TW", "元大金"),

    # ── 航運 ────────────────────────────────────────────────────
    ("長榮海",   "2603.TW", "長榮"),
    ("陽明",     "2609.TW", "陽明"),
    ("萬海",     "2615.TW", "萬海"),
    ("長榮航",   "2618.TW", "長榮航"),
    ("華航",     "2610.TW", "華航"),
    ("立榮",     "2611.TW", "立榮"),

    # ── 石化 / 能源 ─────────────────────────────────────────────
    ("台塑化",   "6505.TW", "台塑化"),
    ("台塑",     "1301.TW", "台塑"),
    ("南亞",     "1303.TW", "南亞"),
    ("台化",     "1326.TW", "台化"),
    ("中鋼",     "2002.TW", "中鋼"),

    # ── 通訊 ────────────────────────────────────────────────────
    ("中華電",   "2412.TW", "中華電"),
    ("台灣大",   "3045.TW", "台灣大"),
    ("遠傳",     "4904.TW", "遠傳"),

    # ── 建設 ────────────────────────────────────────────────────
    ("興富發",   "2542.TW", "興富發"),
    ("長虹",     "5534.TW", "長虹"),
    ("冠德",     "2520.TW", "冠德"),

    # ── 消費 ────────────────────────────────────────────────────
    ("統一超",   "2912.TW", "統一超"),
    ("統一",     "1216.TW", "統一"),
    ("全家",     "5903.TW", "全家"),

    # ── 國際科技（常見於台灣財經新聞）────────────────────────────
    ("Nvidia",   "NVDA",   "Nvidia"),
    ("輝達",     "NVDA",   "Nvidia"),
    ("英偉達",   "NVDA",   "Nvidia"),
    ("AMD",      "AMD",    "AMD"),
    ("Intel",    "INTC",   "Intel"),
    ("英特爾",   "INTC",   "Intel"),
    ("蘋果",     "AAPL",   "Apple"),
    ("Apple",    "AAPL",   "Apple"),
    ("特斯拉",   "TSLA",   "Tesla"),
    ("Tesla",    "TSLA",   "Tesla"),
    ("微軟",     "MSFT",   "Microsoft"),
    ("Microsoft","MSFT",   "Microsoft"),
    ("Google",   "GOOGL",  "Google"),
    ("谷歌",     "GOOGL",  "Google"),
    ("Meta",     "META",   "Meta"),
    ("亞馬遜",   "AMZN",   "Amazon"),
    ("Amazon",   "AMZN",   "Amazon"),
    ("三星",     "005930.KS","Samsung"),
    ("Samsung",  "005930.KS","Samsung"),
    ("SK海力士", "000660.KS","SK Hynix"),
    ("海力士",   "000660.KS","SK Hynix"),
]

# 建立 pattern → (ticker, display_name)
_PATTERNS: list[tuple[re.Pattern, str, str]] = []
for keyword, ticker, display in _RAW:
    if re.search(r"[a-zA-Z]", keyword):
        pat = re.compile(r"\b" + re.escape(keyword) + r"\b", re.IGNORECASE)
    else:
        pat = re.compile(re.escape(keyword))
    _PATTERNS.append((pat, ticker, display))


@dataclass
class StockMention:
    ticker: str
    name: str
    count: int
    sample_titles: list[str] = field(default_factory=list)
    sample_urls: list[str]   = field(default_factory=list)


def count_stock_mentions(
    news_items: list[NewsItem],
    top_n: int = 20,
) -> list[StockMention]:
    """
    掃描所有新聞，統計每個股票被提及幾次。
    回傳依 count 降序排列的 StockMention 清單。
    """
    data: dict[str, dict] = {}   # ticker → {name, count, titles, urls}

    for item in news_items:
        text = item.full_text
        matched_tickers: set[str] = set()

        for pat, ticker, display in _PATTERNS:
            if ticker in matched_tickers:
                continue   # 同一則新聞同一股票只算一次
            if pat.search(text):
                matched_tickers.add(ticker)
                if ticker not in data:
                    data[ticker] = {
                        "name": display,
                        "count": 0,
                        "titles": [],
                        "urls": [],
                    }
                d = data[ticker]
                d["count"] += 1
                if len(d["titles"]) < 3:
                    d["titles"].append(item.title[:60])
                    d["urls"].append(item.url or "")

    result = [
        StockMention(
            ticker=ticker,
            name=d["name"],
            count=d["count"],
            sample_titles=d["titles"],
            sample_urls=d["urls"],
        )
        for ticker, d in data.items()
    ]
    result.sort(key=lambda x: x.count, reverse=True)
    return result[:top_n]
