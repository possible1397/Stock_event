"""
事件分類器 — 從新聞標題/摘要偵測事件

修正：
1. 英文關鍵字使用單詞邊界匹配，避免 software/hardware/forward 誤判
2. 互斥事件對（升息↔降息、油價漲↔跌、美元強↔弱）保留命中數較多的那個
"""
import re
from collections import defaultdict
from dataclasses import dataclass, field

from event_kb import EVENT_KEYWORDS, EVENT_KB
from news_fetcher import NewsItem

# 互斥事件對：(event_a, event_b)，命中數少的那個會被抑制
MUTUALLY_EXCLUSIVE_PAIRS: list[tuple[str, str]] = [
    ("rate_hike",  "rate_cut"),
    ("oil_up",     "oil_down"),
    ("usd_strong", "usd_weak"),
    ("inflation_up", "inflation_down"),
]

# 預先編譯每個關鍵字的 pattern：
#   中文 (無空格語言)：直接 substring
#   英文 (有空格語言)：加 \b 單詞邊界
def _is_english(kw: str) -> bool:
    return bool(re.search(r"[a-zA-Z]", kw))

_KW_PATTERNS: dict[str, list[re.Pattern]] = {}
for _eid, _kws in EVENT_KEYWORDS.items():
    patterns = []
    for kw in _kws:
        if _is_english(kw):
            patterns.append(re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE))
        else:
            patterns.append(re.compile(re.escape(kw)))
    _KW_PATTERNS[_eid] = patterns


def _match_keywords(text: str, event_id: str) -> str | None:
    """回傳第一個命中的關鍵字，否則 None。"""
    for pat in _KW_PATTERNS[event_id]:
        if pat.search(text):
            return pat.pattern.strip(r"\b").replace(r"\ ", " ")
    return None


@dataclass
class DetectedEvent:
    event_id: str
    event_name: str
    matched_keywords: list[str]
    confidence: float        # 0.7 = 1篇命中, 1.0 = 2篇以上
    article_count: int
    source_titles: list[str] = field(default_factory=list)


class EventClassifier:
    def classify_batch(self, items: list[NewsItem]) -> list[DetectedEvent]:
        """
        批次分析新聞，回傳去重、互斥抑制後的 DetectedEvent 清單。
        """
        aggregated: dict[str, dict] = defaultdict(lambda: {
            "matched_kws": set(),
            "titles": [],
            "count": 0,
        })

        for item in items:
            text = item.full_text
            for event_id in EVENT_KEYWORDS:
                kw = _match_keywords(text, event_id)
                if kw:
                    agg = aggregated[event_id]
                    agg["matched_kws"].add(kw)
                    agg["titles"].append(item.title[:50])
                    agg["count"] += 1

        # 互斥事件抑制：保留 count 較多的，移除 count 較少的
        for ev_a, ev_b in MUTUALLY_EXCLUSIVE_PAIRS:
            count_a = aggregated[ev_a]["count"] if ev_a in aggregated else 0
            count_b = aggregated[ev_b]["count"] if ev_b in aggregated else 0
            if count_a > 0 and count_b > 0:
                if count_a >= count_b:
                    del aggregated[ev_b]
                else:
                    del aggregated[ev_a]

        # 組裝 DetectedEvent
        result: list[DetectedEvent] = []
        for event_id, agg in aggregated.items():
            count = agg["count"]
            confidence = 1.0 if count >= 2 else 0.7
            event_name = EVENT_KB.get(event_id, {}).get("event_name", event_id)
            result.append(DetectedEvent(
                event_id=event_id,
                event_name=event_name,
                matched_keywords=sorted(agg["matched_kws"]),
                confidence=confidence,
                article_count=count,
                source_titles=agg["titles"][:3],
            ))

        result.sort(key=lambda x: x.article_count, reverse=True)
        return result
