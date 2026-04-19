"""
事件驅動選股掃描器 — 主程式

用法：
    python event_scanner.py              # 抓即時新聞，關鍵字分類
    python event_scanner.py --llm        # 改用 Claude LLM 分類（需 ANTHROPIC_API_KEY）
    python event_scanner.py --hours 48   # 回顧 48 小時新聞（預設 24）
    python event_scanner.py --top 20     # 顯示前 20 名（預設 15）
    python event_scanner.py --dry-run    # 用範例新聞，不連網
    python event_scanner.py --output result.csv  # 同時輸出 CSV
"""
import argparse
import csv
import sys
from datetime import datetime

from news_fetcher import NewsFetcher, SAMPLE_NEWS
from event_classifier import EventClassifier, DetectedEvent
from signal_generator import SignalGenerator, StockSignal
from industry_stocks import IndustryStockMapper


# ── 輸出格式 ────────────────────────────────────────────────────

def print_events(events: list[DetectedEvent]) -> None:
    print("\n┌─ 偵測到的事件 " + "─" * 50)
    if not events:
        print("│  （無符合事件）")
    for ev in events:
        kws = "、".join(ev.matched_keywords[:4])
        print(f"│  [{ev.event_name}]  {ev.article_count} 則新聞  信心 {ev.confidence:.0%}")
        print(f"│    關鍵字: {kws}")
        for title in ev.source_titles[:2]:
            print(f"│    → {title}")
    print("└" + "─" * 64)


def print_signals(signals: list[StockSignal], top_n: int = 15) -> None:
    buy_signals  = [s for s in signals if s.direction == "BUY"][:top_n]
    sell_signals = [s for s in signals if s.direction == "SELL"][:top_n]

    def _print_group(title: str, items: list[StockSignal], sign_char: str) -> None:
        print(f"\n{'▲' if sign_char=='+' else '▼'} {title}")
        print(f"  {'排名':<4} {'代號':<14} {'評分':>6}  {'產業':<18} {'事件來源'}")
        print("  " + "─" * 70)
        for i, s in enumerate(items, 1):
            industries = "/".join(s.industries[:2])
            events     = "、".join(s.events[:3])
            print(f"  {i:<4} {s.stock_code:<14} {s.score:>+6.1f}  {industries:<18} {events}")

    if buy_signals:
        _print_group("買進信號 (BUY)", buy_signals, "+")
    else:
        print("\n▲ 買進信號：無")

    if sell_signals:
        _print_group("賣出信號 (SELL)", sell_signals, "-")
    else:
        print("\n▼ 賣出信號：無")

    neutral_count = sum(1 for s in signals if s.direction == "NEUTRAL")
    if neutral_count:
        print(f"\n  中性信號 (NEUTRAL)：{neutral_count} 檔（未顯示）")


def save_csv(signals: list[StockSignal], path: str) -> None:
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
    print(f"\n[輸出] 結果已存至: {path}")


# ── 主流程 ────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="事件驅動選股掃描器")
    parser.add_argument("--hours",   type=int,  default=24,
                        help="回顧幾小時的新聞（預設 24）")
    parser.add_argument("--top",     type=int,  default=15,
                        help="顯示前 N 名（預設 15）")
    parser.add_argument("--dry-run", action="store_true",
                        help="使用範例新聞，不連網")
    parser.add_argument("--output",  type=str,  default="",
                        help="輸出 CSV 路徑（選填）")
    parser.add_argument("--report",    type=str,  default="",
                        help="輸出報告目錄（選填），會產生 .html 和 .txt 兩個檔案")
    parser.add_argument("--community", type=str,  default="",
                        help="輸出社群版報告目錄（選填），產生 community_YYYYMMDD.html/.txt")
    parser.add_argument("--llm",     action="store_true",
                        help="使用 Claude LLM 分類（需設定 ANTHROPIC_API_KEY）")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    print(f"\n{'='*60}")
    print(f"  事件驅動選股信號  {now_str}")
    print(f"{'='*60}")

    # ① 抓新聞
    if args.dry_run:
        news_items = SAMPLE_NEWS
        print(f"\n[模式] dry-run — 使用 {len(news_items)} 則範例新聞")
    else:
        print(f"\n[抓取] 最近 {args.hours} 小時新聞...")
        fetcher = NewsFetcher(max_age_hours=args.hours)
        news_items = fetcher.fetch_all()
        print(f"[抓取] 取得 {len(news_items)} 則新聞（去重後）")

    if not news_items:
        print("[警告] 未取得任何新聞，請確認網路連線或改用 --dry-run")
        sys.exit(1)

    # ② 偵測事件
    if args.llm:
        import os
        if not os.environ.get("GEMINI_API_KEY") and not os.environ.get("ANTHROPIC_API_KEY"):
            print("[錯誤] --llm 需要設定 GEMINI_API_KEY 或 ANTHROPIC_API_KEY 環境變數")
            sys.exit(1)
        from llm_classifier import LLMClassifier
        classifier = LLMClassifier()
    else:
        classifier = EventClassifier()
        print("[分類] 使用關鍵字分類器")
    events = classifier.classify_batch(news_items)
    print_events(events)

    if not events:
        print("\n[結果] 未偵測到任何已知事件，無法產生信號")
        sys.exit(0)

    # ③ 產生信號
    mapper    = IndustryStockMapper()
    generator = SignalGenerator(mapper)
    signals   = generator.generate(events)

    print(f"\n[信號] 共計 {len(signals)} 檔有信號")
    print_signals(signals, top_n=args.top)

    # ③-2 產生 AI 總結
    ai_summary = ""
    if getattr(args, "llm", False) and events:
        try:
            ai_summary = classifier.generate_daily_summary(events)
        except Exception as e:
            print(f"[警告] 產生 AI 總結失敗: {e}")

    # ④ 儲存 CSV（選填）
    if args.output:
        save_csv(signals, args.output)

    # ⑤ 產生社群版報告（選填）
    if args.community:
        import os
        from stock_mention_counter import count_stock_mentions
        from community_report import generate_community_html, generate_community_text
        os.makedirs(args.community, exist_ok=True)
        date_str  = datetime.now().strftime("%Y%m%d")
        html_path = os.path.join(args.community, f"community_{date_str}.html")
        txt_path  = os.path.join(args.community, f"community_{date_str}.txt")

        mentions = count_stock_mentions(news_items)
        html = generate_community_html(events, mentions, news_items, ai_summary=ai_summary)
        txt  = generate_community_text(events, mentions, news_items, ai_summary=ai_summary)

        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(txt)

        print(f"\n[社群報告] HTML → {html_path}")
        print(f"[社群報告] 文字 → {txt_path}")

    # ⑥ 產生報告（選填）
    if args.report:
        import os
        from report_generator import generate_html_report, generate_text_report
        os.makedirs(args.report, exist_ok=True)
        date_str = datetime.now().strftime("%Y%m%d")
        html_path = os.path.join(args.report, f"report_{date_str}.html")
        txt_path  = os.path.join(args.report, f"report_{date_str}.txt")

        html = generate_html_report(events, signals, len(news_items), ai_summary=ai_summary)
        txt  = generate_text_report(events, signals, len(news_items), ai_summary=ai_summary)

        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(txt)

        print(f"\n[報告] HTML → {html_path}")
        print(f"[報告] 文字 → {txt_path}")

    print(f"\n{'='*60}\n")

    # 印出供應鏈資料來源
    print(f"[資料來源] 供應鏈: {mapper.source}")


if __name__ == "__main__":
    main()
