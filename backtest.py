"""
事件驅動選股 — 回測模組

用法：
    python backtest.py                          # 用內建範例事件回測
    python backtest.py --start 2024-01-01       # 指定開始日期
    python backtest.py --end   2024-12-31       # 指定結束日期
    python backtest.py --hold  10               # 持有天數（預設依 lag 自動判斷）
    python backtest.py --threshold 2.0          # 進場分數門檻（預設 2.0）

回測邏輯：
  1. 從 SAMPLE_NEWS 產生信號（BUY/SELL）
  2. 以信號日當天收盤價進場
  3. 持有 N 天後出場（N 由事件 lag 決定）
  4. 統計勝率、平均報酬、Sharpe ratio
"""
import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta

import yfinance as yf
import pandas as pd

from news_fetcher import SAMPLE_NEWS
from event_classifier import EventClassifier
from signal_generator import SignalGenerator, StockSignal, LAG_MULTIPLIER
from industry_stocks import IndustryStockMapper
from event_kb import EVENT_KB

# lag → 建議持有天數（交易日）
LAG_HOLD_DAYS: dict[str, int] = {
    "immediate": 3,
    "short":     10,
    "medium":    20,
    "long":      45,
}


@dataclass
class TradeRecord:
    stock_code: str
    direction: str       # BUY / SELL
    score: float
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    return_pct: float    # 含方向（BUY 正 = 獲利）
    events: list[str]
    hold_days: int


@dataclass
class BacktestResult:
    total_trades: int
    win_trades: int
    win_rate: float
    avg_return: float
    max_return: float
    min_return: float
    sharpe: float
    records: list[TradeRecord]

    def print_summary(self) -> None:
        print("\n" + "=" * 60)
        print("  回測結果")
        print("=" * 60)
        print(f"  交易筆數  : {self.total_trades}")
        print(f"  勝率      : {self.win_rate:.1%}")
        print(f"  平均報酬  : {self.avg_return:+.2f}%")
        print(f"  最大報酬  : {self.max_return:+.2f}%")
        print(f"  最大虧損  : {self.min_return:+.2f}%")
        print(f"  Sharpe    : {self.sharpe:.2f}")
        print("=" * 60)

        if not self.records:
            return
        print(f"\n  {'代號':<14} {'方向':<6} {'評分':>5}  {'進場':>10}  {'出場':>10}  {'報酬':>7}  事件")
        print("  " + "─" * 72)
        for r in self.records:
            events_str = "、".join(r.events[:2])
            print(f"  {r.stock_code:<14} {r.direction:<6} {r.score:>+5.1f}  "
                  f"{r.entry_date}  {r.exit_date}  {r.return_pct:>+6.2f}%  {events_str}")


class Backtester:
    def __init__(
        self,
        signal_date: str | None = None,
        score_threshold: float = 2.0,
        fixed_hold_days: int | None = None,
    ):
        """
        signal_date     : 信號產生日（預設今天）
        score_threshold : abs(score) 低於此值的信號略過
        fixed_hold_days : 強制固定持有天數（None = 依 lag 自動）
        """
        self.signal_date = signal_date or datetime.now().strftime("%Y-%m-%d")
        self.score_threshold = score_threshold
        self.fixed_hold_days = fixed_hold_days

    def run(self, signals: list[StockSignal]) -> BacktestResult:
        """執行回測，回傳結果。"""
        filtered = [s for s in signals if abs(s.score) >= self.score_threshold
                    and s.direction in ("BUY", "SELL")]

        records: list[TradeRecord] = []
        for sig in filtered:
            hold = self._hold_days_for(sig)
            record = self._simulate_trade(sig, hold)
            if record:
                records.append(record)

        return self._compute_result(records)

    # ── 內部方法 ────────────────────────────────────────────────

    def _hold_days_for(self, sig: StockSignal) -> int:
        if self.fixed_hold_days is not None:
            return self.fixed_hold_days
        # 取信號所有貢獻事件中 lag 最短的那個（保守原則）
        best_hold = LAG_HOLD_DAYS["long"]
        for event_name in sig.events:
            for eid, rule in EVENT_KB.items():
                if rule["event_name"] == event_name:
                    lag = rule.get("lag", "immediate")
                    best_hold = min(best_hold, LAG_HOLD_DAYS.get(lag, 3))
        return best_hold

    def _simulate_trade(self, sig: StockSignal, hold_days: int) -> TradeRecord | None:
        """下載 yfinance 資料，模擬一筆交易。"""
        entry_dt = datetime.strptime(self.signal_date, "%Y-%m-%d")
        exit_dt  = entry_dt + timedelta(days=hold_days + 5)  # 多抓幾天防假日

        try:
            df: pd.DataFrame = yf.download(
                sig.stock_code,
                start=self.signal_date,
                end=exit_dt.strftime("%Y-%m-%d"),
                progress=False,
                auto_adjust=True,
            )
        except Exception:
            return None

        if df is None or len(df) < 2:
            return None

        close = df["Close"].dropna()
        if len(close) < 2:
            return None

        # 進場：第 0 根 K 棒收盤
        entry_price = float(close.iloc[0])
        # 出場：第 hold_days 根 K 棒（或最後一根）
        exit_idx    = min(hold_days, len(close) - 1)
        exit_price  = float(close.iloc[exit_idx])

        raw_return = (exit_price - entry_price) / entry_price * 100
        # SELL 信號反向
        pnl = raw_return if sig.direction == "BUY" else -raw_return

        entry_date = str(close.index[0].date())
        exit_date  = str(close.index[exit_idx].date())

        return TradeRecord(
            stock_code=sig.stock_code,
            direction=sig.direction,
            score=sig.score,
            entry_date=entry_date,
            exit_date=exit_date,
            entry_price=round(entry_price, 2),
            exit_price=round(exit_price, 2),
            return_pct=round(pnl, 2),
            events=sig.events,
            hold_days=exit_idx,
        )

    @staticmethod
    def _compute_result(records: list[TradeRecord]) -> BacktestResult:
        if not records:
            return BacktestResult(0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, [])

        returns = [r.return_pct for r in records]
        wins    = [r for r in records if r.return_pct > 0]

        avg = sum(returns) / len(returns)
        std = pd.Series(returns).std()
        sharpe = (avg / std * (252 ** 0.5)) if std and std > 0 else 0.0

        return BacktestResult(
            total_trades=len(records),
            win_trades=len(wins),
            win_rate=len(wins) / len(records),
            avg_return=avg,
            max_return=max(returns),
            min_return=min(returns),
            sharpe=round(sharpe, 2),
            records=records,
        )


# ── CLI ─────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="事件驅動選股回測")
    parser.add_argument("--date",      type=str,   default=None,
                        help="信號日期 YYYY-MM-DD（預設今天）")
    parser.add_argument("--hold",      type=int,   default=None,
                        help="固定持有天數（預設依 lag 自動）")
    parser.add_argument("--threshold", type=float, default=2.0,
                        help="進場分數門檻（預設 2.0）")
    parser.add_argument("--top",       type=int,   default=20,
                        help="最多回測幾檔（預設 20）")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # ① 產生信號（用範例新聞）
    classifier = EventClassifier()
    events     = classifier.classify_batch(SAMPLE_NEWS)
    mapper     = IndustryStockMapper()
    generator  = SignalGenerator(mapper)
    signals    = generator.generate(events)[: args.top]

    print(f"\n[回測] 信號日: {args.date or '今天'}  門檻: {args.threshold}  "
          f"持有: {'auto' if args.hold is None else args.hold + '天'}")
    print(f"[回測] 共 {len(signals)} 個信號，開始下載價格資料...")

    # ② 執行回測
    backtester = Backtester(
        signal_date=args.date,
        score_threshold=args.threshold,
        fixed_hold_days=args.hold,
    )
    result = backtester.run(signals)
    result.print_summary()


if __name__ == "__main__":
    main()
