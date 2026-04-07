"""
LLM 事件分類器 — 支援 Google Gemini（免費）或 Claude（付費）

優先使用 GEMINI_API_KEY，fallback 到 ANTHROPIC_API_KEY。

用法：
    classifier = LLMClassifier()
    events = classifier.classify_batch(news_items)

與 EventClassifier 介面相同，可直接替換。
"""
import json
import os
import time
from collections import defaultdict

from event_kb import EVENT_KB
from event_classifier import DetectedEvent, MUTUALLY_EXCLUSIVE_PAIRS
from news_fetcher import NewsItem

# 給 LLM 看的事件清單
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
3. 回傳格式：JSON 物件，key 為新聞編號（字串），value 為事件陣列
4. 每個事件包含 event_id 和 matched_reason（一句話說明原因）
5. 範例：{{"0": [{{"event_id": "rate_hike", "matched_reason": "Fed raised rates"}}], "1": []}}
6. 只回傳 JSON，不要其他文字
"""


def _strip_code_block(raw: str) -> str:
    """去除 markdown code block 包裹。"""
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1]) if lines[-1] == "```" else "\n".join(lines[1:])
    return raw.strip()


class GeminiBackend:
    """Google Gemini API，內建 429 retry。"""

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        from google import genai
        self.client = genai.Client(api_key=api_key)
        self.model  = model

    def call(self, user_msg: str, max_retries: int = 3) -> str:
        from google.genai import types
        import re

        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=user_msg,
                    config=types.GenerateContentConfig(
                        system_instruction=_SYSTEM_PROMPT,
                    ),
                )
                return response.text

            except Exception as e:
                err_str = str(e)

                # 偵測 429，解析建議等待秒數
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    # 嘗試從錯誤訊息中取得 retryDelay
                    match = re.search(r"retryDelay.*?(\d+)s", err_str)
                    wait_sec = int(match.group(1)) + 5 if match else 60

                    if attempt < max_retries - 1:
                        print(f"[LLM] 429 配額限制，等待 {wait_sec} 秒後重試"
                              f"（第 {attempt + 1}/{max_retries} 次）...")
                        time.sleep(wait_sec)
                        continue
                    else:
                        print(f"[LLM] 已達最大重試次數，略過此批次")
                        raise

                # 其他錯誤直接拋出
                raise

        raise RuntimeError("Gemini API 重試失敗")


class AnthropicBackend:
    """Claude API（付費備用）。"""

    def __init__(self, api_key: str, model: str = "claude-haiku-4-5-20251001"):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model  = model

    def call(self, user_msg: str, max_retries: int = 3) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        return response.content[0].text


class LLMClassifier:
    def __init__(self, batch_size: int = 10):  # 從 20 改為 10，減少 token 消耗
        gemini_key    = os.environ.get("GEMINI_API_KEY", "")
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")

        if gemini_key:
            self.backend = GeminiBackend(gemini_key)
            self._backend_name = "Gemini"
        elif anthropic_key:
            self.backend = AnthropicBackend(anthropic_key)
            self._backend_name = "Claude"
        else:
            raise EnvironmentError(
                "請設定 GEMINI_API_KEY 或 ANTHROPIC_API_KEY 環境變數"
            )

        self.batch_size = batch_size
        print(f"[LLM] 使用 {self._backend_name} 分類器")

    def classify_batch(self, items: list[NewsItem]) -> list[DetectedEvent]:
        aggregated: dict[str, dict] = defaultdict(lambda: {
            "titles": [], "urls": [], "reasons": [], "count": 0
        })

        total_batches = (len(items) + self.batch_size - 1) // self.batch_size

        for batch_idx, i in enumerate(range(0, len(items), self.batch_size)):
            batch = items[i: i + self.batch_size]
            print(f"[LLM] 處理批次 {batch_idx + 1}/{total_batches}（{len(batch)} 則）...")

            results = self._call_llm(batch)

            for item_idx, event_list in results.items():
                for ev in event_list:
                    eid    = ev.get("event_id", "")
                    reason = ev.get("matched_reason", "")
                    if eid in EVENT_KB:
                        agg = aggregated[eid]
                        agg["titles"].append(batch[item_idx].title[:60])
                        agg["urls"].append(batch[item_idx].url)
                        agg["reasons"].append(reason)
                        agg["count"] += 1

            # 批次之間稍作等待，避免觸發 RPM 限制
            if batch_idx < total_batches - 1:
                time.sleep(6)  # 每分鐘最多 10 次請求，間隔 6 秒

        # 互斥事件抑制
        for ev_a, ev_b in MUTUALLY_EXCLUSIVE_PAIRS:
            count_a = aggregated[ev_a]["count"] if ev_a in aggregated else 0
            count_b = aggregated[ev_b]["count"] if ev_b in aggregated else 0
            if count_a > 0 and count_b > 0:
                if count_a >= count_b:
                    del aggregated[ev_b]
                else:
                    del aggregated[ev_a]

        result: list[DetectedEvent] = []
        for eid, agg in aggregated.items():
            count = agg["count"]
            result.append(DetectedEvent(
                event_id=eid,
                event_name=EVENT_KB[eid]["event_name"],
                matched_keywords=agg["reasons"][:3],
                confidence=1.0 if count >= 2 else 0.7,
                article_count=count,
                source_titles=agg["titles"][:5],
                source_urls=agg["urls"][:5],
            ))

        result.sort(key=lambda x: x.article_count, reverse=True)
        return result

    def _call_llm(self, batch: list[NewsItem]) -> dict[int, list[dict]]:
        news_text = "\n".join(
            f"[{i}] {item.title}"
            for i, item in enumerate(batch)
        )
        user_msg = (
            f"請分析以下 {len(batch)} 則新聞標題，回傳每則對應的事件。\n\n"
            f"新聞：\n{news_text}\n\n只回傳 JSON，不要其他文字。"
        )
        try:
            raw    = self.backend.call(user_msg)
            raw    = _strip_code_block(raw)
            parsed = json.loads(raw)
            return {int(k): v for k, v in parsed.items()}
        except Exception as e:
            print(f"[LLM Warning] {e}")
            return {}
