"""
LLM 事件分類器 — 用 Claude API 取代靜態關鍵字

優點：任何寫法的新聞都能理解，不需要手動維護關鍵字清單
用法：
    classifier = LLMClassifier()          # 需設定 ANTHROPIC_API_KEY
    events = classifier.classify_batch(news_items)

與 EventClassifier 介面相同，可直接替換。
"""
import json
import os
from collections import defaultdict
from dataclasses import dataclass, field

import anthropic

from event_kb import EVENT_KB
from event_classifier import DetectedEvent, MUTUALLY_EXCLUSIVE_PAIRS
from news_fetcher import NewsItem

# 給 LLM 看的事件清單（event_id + 中文說明）
_EVENT_DESCRIPTIONS = "\n".join(
    f"- {eid}: {rule['event_name']}（{', '.join(rule['factors'])}）"
    for eid, rule in EVENT_KB.items()
)

_SYSTEM_PROMPT = f"""你是一個財經新聞事件分類器。
你的任務是判斷每則新聞標題是否對應以下任一事件，並只回傳 JSON。

事件清單：
{_EVENT_DESCRIPTIONS}

規則：
1. 一則新聞可對應多個事件，也可以完全不對應（回傳空陣列）
2. 只在確定相關時才標記，不確定就不標記
3. 回傳格式：JSON 陣列，每項包含 event_id 和 matched_reason（一句話說明原因）
4. 範例回傳：[{{"event_id": "rate_hike", "matched_reason": "Fed announced 25bp rate increase"}}]
5. 若無相關事件回傳：[]
"""


class LLMClassifier:
    def __init__(self, model: str = "claude-haiku-4-5-20251001", batch_size: int = 20):
        """
        model: 用 Haiku（快速便宜），分類任務不需要 Sonnet
        batch_size: 每次送幾則新聞給 LLM（避免 token 過多）
        """
        self.client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self.model = model
        self.batch_size = batch_size

    def classify_batch(self, items: list[NewsItem]) -> list[DetectedEvent]:
        """
        批次分類，介面與 EventClassifier.classify_batch 相同。
        """
        # 彙總：event_id → {titles, reasons, count}
        aggregated: dict[str, dict] = defaultdict(lambda: {
            "titles": [], "reasons": [], "count": 0
        })

        # 分批送 LLM
        for i in range(0, len(items), self.batch_size):
            batch = items[i: i + self.batch_size]
            results = self._call_llm(batch)
            for item_idx, event_list in results.items():
                title = batch[item_idx].title[:50]
                for ev in event_list:
                    eid = ev.get("event_id", "")
                    reason = ev.get("matched_reason", "")
                    if eid in EVENT_KB:
                        agg = aggregated[eid]
                        agg["titles"].append(title)
                        agg["reasons"].append(reason)
                        agg["count"] += 1

        # 互斥事件抑制（與 EventClassifier 相同邏輯）
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
        for eid, agg in aggregated.items():
            count = agg["count"]
            result.append(DetectedEvent(
                event_id=eid,
                event_name=EVENT_KB[eid]["event_name"],
                matched_keywords=agg["reasons"][:3],   # 重用欄位存 LLM 理由
                confidence=1.0 if count >= 2 else 0.7,
                article_count=count,
                source_titles=agg["titles"][:3],
            ))

        result.sort(key=lambda x: x.article_count, reverse=True)
        return result

    def _call_llm(self, batch: list[NewsItem]) -> dict[int, list[dict]]:
        """送一批新聞給 LLM，回傳 {index: [event_list]}。"""
        # 組成新聞列表文字
        news_text = "\n".join(
            f"[{i}] {item.title}"
            for i, item in enumerate(batch)
        )

        user_msg = f"""請分析以下 {len(batch)} 則新聞標題，回傳每則對應的事件。
格式：JSON 物件，key 為新聞編號（字串），value 為事件陣列。

新聞：
{news_text}

回傳範例（只回傳 JSON，不要其他文字）：
{{"0": [{{"event_id": "rate_hike", "matched_reason": "Fed raised rates"}}], "1": [], "2": [{{"event_id": "ai_boom", "matched_reason": "GPU demand surge"}}]}}"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
            )
            raw = response.content[0].text.strip()
            # 清理 markdown code block
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            parsed = json.loads(raw)
            return {int(k): v for k, v in parsed.items()}
        except Exception as e:
            print(f"[LLM Warning] {e}")
            return {}
