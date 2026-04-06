"""
事件驅動選股 — 自動排程器

用法：
    python scheduler.py                   # 每天 08:30 執行，結果存 output/
    python scheduler.py --time 09:00      # 自訂執行時間
    python scheduler.py --now             # 立即執行一次後開始排程
    python scheduler.py --once            # 只執行一次，不排程

輸出：
    output/signal_YYYYMMDD.csv            # 每日信號 CSV
    output/backtest_YYYYMMDD.csv          # 每日回測摘要（可選）
"""
import argparse
import csv
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import schedule
import time

from news_fetcher import NewsFetcher
from event_classifier import EventClassifier
from signal_generator import SignalGenerator
from industry_stocks import IndustryStockMapper

OUTPUT_DIR = Path(__file__).parent / "output"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def run_scan(hours: int = 24, top_n: int = 30, use_llm: bool = False) -> None:
    """執行一次完整掃描並存 CSV。"""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    date_str = datetime.now().strftime("%Y%m%d")
    log.info(f"開始掃描 [{now_str}]")

    # ① 抓新聞
    fetcher = NewsFetcher(max_age_hours=hours)
    news_items = fetcher.fetch_all()
    log.info(f"取得 {len(news_items)} 則新聞")

    if not news_items:
        log.warning("未取得任何新聞，略過本次掃描")
        return

    # ② 分類事件
    if use_llm and os.environ.get("ANTHROPIC_API_KEY"):
        from llm_classifier import LLMClassifier
        classifier = LLMClassifier()
        log.info("使用 LLM 分類器")
    else:
        classifier = EventClassifier()
        log.info("使用關鍵字分類器")

    events = classifier.classify_batch(news_items)
    log.info(f"偵測到 {len(events)} 個事件: {[e.event_name for e in events]}")

    if not events:
        log.info("無事件，略過信號產生")
        return

    # ③ 產生信號
    mapper    = IndustryStockMapper()
    generator = SignalGenerator(mapper)
    signals   = generator.generate(events)
    log.info(f"共 {len(signals)} 個信號 "
             f"(BUY={sum(1 for s in signals if s.direction=='BUY')}, "
             f"SELL={sum(1 for s in signals if s.direction=='SELL')})")

    # ④ 儲存 CSV
    OUTPUT_DIR.mkdir(exist_ok=True)
    csv_path = OUTPUT_DIR / f"signal_{date_str}.csv"
    _save_csv(signals[:top_n], str(csv_path))
    log.info(f"結果已存至: {csv_path}")


def _save_csv(signals, path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "stock_code", "direction", "score",
                         "events", "industries", "confidence", "reasons"])
        today = datetime.now().strftime("%Y-%m-%d")
        for s in signals:
            writer.writerow([
                today,
                s.stock_code,
                s.direction,
                s.score,
                " | ".join(s.events),
                " | ".join(s.industries),
                s.confidence,
                " / ".join(s.reasons),
            ])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="事件驅動選股排程器")
    parser.add_argument("--time",  type=str,  default="08:30",
                        help="每日執行時間 HH:MM（預設 08:30）")
    parser.add_argument("--hours", type=int,  default=24,
                        help="回顧幾小時新聞（預設 24）")
    parser.add_argument("--top",   type=int,  default=30,
                        help="儲存前 N 名信號（預設 30）")
    parser.add_argument("--llm",   action="store_true",
                        help="使用 Claude LLM 分類（需 ANTHROPIC_API_KEY）")
    parser.add_argument("--now",   action="store_true",
                        help="啟動時立即執行一次")
    parser.add_argument("--once",  action="store_true",
                        help="只執行一次後退出，不排程")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    job = lambda: run_scan(hours=args.hours, top_n=args.top, use_llm=args.llm)

    if args.once:
        job()
        return

    if args.now:
        job()

    schedule.every().day.at(args.time).do(job)
    log.info(f"排程已啟動，每天 {args.time} 執行。按 Ctrl+C 停止。")

    try:
        while True:
            schedule.run_pending()
            time.sleep(30)
    except KeyboardInterrupt:
        log.info("排程器已停止")
        sys.exit(0)


if __name__ == "__main__":
    main()
