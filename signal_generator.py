"""
信號產生器 — 事件 → 產業 → 股票信號
"""
from collections import defaultdict
from dataclasses import dataclass

from event_kb import EVENT_KB
from event_classifier import DetectedEvent
from industry_stocks import IndustryStockMapper

# lag → 信號強度折扣 (反映訊號不確定性隨時間延遲遞增)
LAG_MULTIPLIER: dict[str, float] = {
    "immediate": 1.00,   # 即時反應（當天~2天）
    "short":     0.85,   # 短期（3~10天）
    "medium":    0.65,   # 中期（2~4週）
    "long":      0.45,   # 長期（1~3個月）
}


@dataclass
class StockSignal:
    stock_code: str
    direction: str        # "BUY" / "SELL" / "NEUTRAL"
    score: float          # 加總後原始分數
    events: list[str]     # 貢獻的事件名稱（去重）
    industries: list[str] # 透過哪些產業連結
    reasons: list[str]    # 可讀原因
    confidence: float     # 貢獻事件的平均信心值

    def __str__(self) -> str:
        events_str = ", ".join(dict.fromkeys(self.events))
        return (f"{self.stock_code:12s} {self.direction:7s} "
                f"score={self.score:+.1f}  [{events_str}]")


class SignalGenerator:
    BUY_THRESHOLD  =  2.0
    SELL_THRESHOLD = -2.0

    def __init__(self, mapper: IndustryStockMapper | None = None):
        self.mapper = mapper or IndustryStockMapper()

    def generate(self, events: list[DetectedEvent]) -> list[StockSignal]:
        """
        從偵測到的事件產生股票信號。
        同一事件對同一股票只取最高強度路徑（避免跨產業重複計分）。
        回傳按 abs(score) 降序排列的 StockSignal 清單。
        """
        # ticker → 累積資料
        accumulator: dict[str, dict] = defaultdict(lambda: {
            "score": 0.0,
            "events": [],
            "industries": [],
            "reasons": [],
            "confidence_sum": 0.0,
            "count": 0,
        })

        for event in events:
            rule = EVENT_KB.get(event.event_id)
            if not rule:
                continue

            # 同一事件對同一股票：先收集所有 (contribution, industry, reason)，
            # 再只取絕對值最大的那條（避免半導體+AI伺服器重複累加）
            ticker_best: dict[str, tuple[float, str, str, str]] = {}
            # key=ticker, value=(contribution, display_industry, reason, strength)

            lag = rule.get("lag", "immediate")
            lag_mult = LAG_MULTIPLIER.get(lag, 1.0)

            for side, sign in [("positive_industries", +1), ("negative_industries", -1)]:
                for entry in rule[side]:
                    kb_industry    = entry["industry"]
                    strength       = entry["strength"]
                    strength_score = entry["strength_score"]
                    tickers        = self.mapper.get_tickers(kb_industry)

                    if not tickers:
                        continue

                    display_industry = self.mapper.get_industry_label(kb_industry)
                    contribution = strength_score * sign * event.confidence * lag_mult
                    reason = self._make_reason(
                        event.event_name, display_industry, sign, strength, event.confidence, lag
                    )

                    for ticker in tickers:
                        prev = ticker_best.get(ticker)
                        if prev is None or abs(contribution) > abs(prev[0]):
                            ticker_best[ticker] = (contribution, display_industry, reason, strength)

            # 將最佳路徑寫入 accumulator
            for ticker, (contribution, display_industry, reason, _) in ticker_best.items():
                acc = accumulator[ticker]
                acc["score"] += contribution
                acc["events"].append(event.event_name)
                acc["industries"].append(display_industry)
                acc["reasons"].append(reason)
                acc["confidence_sum"] += event.confidence
                acc["count"] += 1

        # 組裝 StockSignal
        signals: list[StockSignal] = []
        for ticker, acc in accumulator.items():
            score = acc["score"]
            if score >= self.BUY_THRESHOLD:
                direction = "BUY"
            elif score <= self.SELL_THRESHOLD:
                direction = "SELL"
            else:
                direction = "NEUTRAL"

            avg_conf = acc["confidence_sum"] / acc["count"] if acc["count"] else 0.0

            # 去重（保留順序）
            events_dedup = list(dict.fromkeys(acc["events"]))
            ind_dedup    = list(dict.fromkeys(acc["industries"]))
            reasons_dedup = list(dict.fromkeys(acc["reasons"]))

            signals.append(StockSignal(
                stock_code=ticker,
                direction=direction,
                score=round(score, 2),
                events=events_dedup,
                industries=ind_dedup,
                reasons=reasons_dedup,
                confidence=round(avg_conf, 2),
            ))

        signals.sort(key=lambda x: abs(x.score), reverse=True)
        return signals

    @staticmethod
    def _make_reason(event_name: str, industry: str, sign: int,
                     strength: str, confidence: float, lag: str = "immediate") -> str:
        direction = "利多" if sign > 0 else "利空"
        lag_label = {"immediate": "即時", "short": "短期", "medium": "中期", "long": "長期"}.get(lag, lag)
        return f"{event_name} → {industry}（{strength}強度{direction}, 信心{confidence:.0%}, {lag_label}）"
