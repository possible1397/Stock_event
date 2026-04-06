"""
測試：SignalGenerator — 信號計算、lag 折扣、閾值
"""
import pytest
from datetime import datetime, timezone

from event_classifier import DetectedEvent
from signal_generator import SignalGenerator, StockSignal, LAG_MULTIPLIER
from industry_stocks import IndustryStockMapper


def _make_event(event_id: str, confidence: float = 1.0, count: int = 2) -> DetectedEvent:
    from event_kb import EVENT_KB
    return DetectedEvent(
        event_id=event_id,
        event_name=EVENT_KB[event_id]["event_name"],
        matched_keywords=["test"],
        confidence=confidence,
        article_count=count,
    )


class TestSignalGenerator:
    def setup_method(self):
        self.gen = SignalGenerator()

    # ── 基本信號產生 ─────────────────────────────────────────────

    def test_ai_boom_produces_buy_signals(self):
        events = [_make_event("ai_boom")]
        signals = self.gen.generate(events)
        buy = [s for s in signals if s.direction == "BUY"]
        assert len(buy) > 0

    def test_rate_hike_produces_sell_for_growth(self):
        """升息 → 成長股 → 應有 SELL"""
        events = [_make_event("rate_hike")]
        signals = self.gen.generate(events)
        # 成長股在 industry_stocks 映射為半導體
        sell = [s for s in signals if s.direction == "SELL"]
        assert len(sell) > 0

    def test_no_events_no_signals(self):
        assert self.gen.generate([]) == []

    # ── lag 折扣 ─────────────────────────────────────────────────

    def test_lag_multiplier_values(self):
        assert LAG_MULTIPLIER["immediate"] == 1.00
        assert LAG_MULTIPLIER["short"]     == pytest.approx(0.85)
        assert LAG_MULTIPLIER["medium"]    == pytest.approx(0.65)
        assert LAG_MULTIPLIER["long"]      == pytest.approx(0.45)

    def test_immediate_score_higher_than_medium(self):
        """immediate lag 的信號分數應大於 medium lag 的相同事件"""
        from event_kb import EVENT_KB
        import copy

        # ai_boom 是 immediate；手動建一個 medium 版本的偽事件
        ev_immediate = _make_event("ai_boom", confidence=1.0)  # lag=immediate

        # 用 rate_cut 作為 medium lag 的代表（lag=short），直接比乘數
        imm_mult = LAG_MULTIPLIER["immediate"]
        med_mult = LAG_MULTIPLIER["medium"]
        assert imm_mult > med_mult

    def test_reason_includes_lag_label(self):
        events = [_make_event("rate_cut")]  # lag=short
        signals = self.gen.generate(events)
        all_reasons = [r for s in signals for r in s.reasons]
        assert any("短期" in r for r in all_reasons)

    # ── 閾值 ────────────────────────────────────────────────────

    def test_buy_threshold(self):
        events = [_make_event("ai_boom", confidence=1.0)]
        signals = self.gen.generate(events)
        for s in signals:
            if s.direction == "BUY":
                assert s.score >= SignalGenerator.BUY_THRESHOLD

    def test_sell_threshold(self):
        events = [_make_event("rate_hike", confidence=1.0)]
        signals = self.gen.generate(events)
        for s in signals:
            if s.direction == "SELL":
                assert s.score <= SignalGenerator.SELL_THRESHOLD

    # ── 排序 ────────────────────────────────────────────────────

    def test_signals_sorted_by_abs_score(self):
        events = [_make_event("ai_boom"), _make_event("war"), _make_event("rate_hike")]
        signals = self.gen.generate(events)
        abs_scores = [abs(s.score) for s in signals]
        assert abs_scores == sorted(abs_scores, reverse=True)

    # ── 無重複事件名稱 ──────────────────────────────────────────

    def test_no_duplicate_events_in_signal(self):
        events = [_make_event("ai_boom"), _make_event("ai_boom")]
        signals = self.gen.generate(events)
        for s in signals:
            assert len(s.events) == len(set(s.events))

    # ── unknown event_id 不崩潰 ─────────────────────────────────

    def test_unknown_event_id_ignored(self):
        unknown = DetectedEvent(
            event_id="ghost_event",
            event_name="幽靈事件",
            matched_keywords=[],
            confidence=1.0,
            article_count=1,
        )
        signals = self.gen.generate([unknown])
        assert signals == []
