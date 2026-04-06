"""
報告產生器 — 將掃描結果輸出為 HTML 視覺報告 + LINE 純文字報告

HTML 報告：含圖表、超連結，可在瀏覽器開啟或 GitHub Pages 瀏覽
LINE 報告：emoji 格式純文字，直接複製貼到社群
"""
import base64
import io
from datetime import datetime

import matplotlib
matplotlib.use("Agg")   # 不需要 GUI，GitHub Actions 也能跑
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from event_classifier import DetectedEvent
from signal_generator import StockSignal


# ── 圖表產生 ─────────────────────────────────────────────────────

def _chart_events_base64(events: list[DetectedEvent]) -> str:
    """產生事件長條圖，回傳 base64 PNG 字串。"""
    if not events:
        return ""

    names   = [e.event_name for e in events]
    counts  = [e.article_count for e in events]
    confs   = [e.confidence for e in events]

    colors = ["#2ecc71" if c >= 1.0 else "#f39c12" for c in confs]

    fig, ax = plt.subplots(figsize=(8, max(3, len(names) * 0.55)))
    bars = ax.barh(names[::-1], counts[::-1], color=colors[::-1], edgecolor="none", height=0.6)

    for bar, cnt in zip(bars, counts[::-1]):
        ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
                f"{cnt} 則", va="center", fontsize=9, color="#444")

    ax.set_xlabel("新聞則數", fontsize=10)
    ax.set_title("今日偵測事件（新聞熱度）", fontsize=12, fontweight="bold", pad=12)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_xlim(0, max(counts) * 1.25)

    high = mpatches.Patch(color="#2ecc71", label="高信心（2則以上）")
    low  = mpatches.Patch(color="#f39c12", label="低信心（1則）")
    ax.legend(handles=[high, low], fontsize=8, loc="lower right")

    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def _chart_signals_base64(signals: list[StockSignal], top_n: int = 15) -> str:
    """產生信號分數圖，回傳 base64 PNG 字串。"""
    top = sorted(signals, key=lambda s: abs(s.score), reverse=True)[:top_n]
    if not top:
        return ""

    labels = [s.stock_code for s in top]
    scores = [s.score for s in top]
    colors = ["#e74c3c" if s > 0 else "#3498db" for s in scores]

    fig, ax = plt.subplots(figsize=(8, max(3, len(labels) * 0.55)))
    bars = ax.barh(labels[::-1], scores[::-1], color=colors[::-1], edgecolor="none", height=0.6)

    for bar, sc in zip(bars, scores[::-1]):
        x = bar.get_width()
        ax.text(x + (0.05 if x >= 0 else -0.05),
                bar.get_y() + bar.get_height() / 2,
                f"{sc:+.1f}", va="center",
                ha="left" if x >= 0 else "right", fontsize=8, color="#444")

    ax.axvline(0, color="#aaa", linewidth=0.8)
    ax.set_xlabel("信號分數", fontsize=10)
    ax.set_title(f"Top {top_n} 信號（紅=買進 / 藍=賣出）", fontsize=12, fontweight="bold", pad=12)
    ax.spines[["top", "right"]].set_visible(False)

    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


# ── HTML 報告 ────────────────────────────────────────────────────

def generate_html_report(
    events: list[DetectedEvent],
    signals: list[StockSignal],
    news_count: int,
    date_str: str | None = None,
) -> str:
    date_str = date_str or datetime.now().strftime("%Y-%m-%d")
    buy_signals  = [s for s in signals if s.direction == "BUY"][:15]
    sell_signals = [s for s in signals if s.direction == "SELL"][:15]

    chart_events  = _chart_events_base64(events)
    chart_signals = _chart_signals_base64(signals)

    # 事件表格 rows
    event_rows = ""
    for ev in events:
        conf_badge = (
            '<span style="color:#27ae60;font-weight:bold">高</span>'
            if ev.confidence >= 1.0 else
            '<span style="color:#e67e22;font-weight:bold">中</span>'
        )
        news_links = ""
        for title, url in zip(ev.source_titles, ev.source_urls):
            if url:
                news_links += f'<li><a href="{url}" target="_blank">{title}</a></li>'
            else:
                news_links += f"<li>{title}</li>"

        event_rows += f"""
        <tr>
          <td><strong>{ev.event_name}</strong></td>
          <td style="text-align:center">{ev.article_count}</td>
          <td style="text-align:center">{conf_badge}</td>
          <td><ul style="margin:0;padding-left:16px">{news_links}</ul></td>
        </tr>"""

    def signal_rows(sigs: list[StockSignal], color: str) -> str:
        rows = ""
        for i, s in enumerate(sigs, 1):
            evts = "、".join(s.events[:2])
            inds = "/".join(s.industries[:2])
            rows += f"""
            <tr>
              <td style="text-align:center">{i}</td>
              <td><strong>{s.stock_code}</strong></td>
              <td style="text-align:center;color:{color};font-weight:bold">{s.score:+.1f}</td>
              <td>{inds}</td>
              <td>{evts}</td>
              <td style="text-align:center">{s.confidence:.0%}</td>
            </tr>"""
        return rows

    buy_rows  = signal_rows(buy_signals,  "#c0392b")
    sell_rows = signal_rows(sell_signals, "#2980b9")

    img_events  = (f'<img src="data:image/png;base64,{chart_events}" style="max-width:100%">'
                   if chart_events else "")
    img_signals = (f'<img src="data:image/png;base64,{chart_signals}" style="max-width:100%">'
                   if chart_signals else "")

    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>事件驅動選股日報 {date_str}</title>
<style>
  body {{ font-family: -apple-system, "Segoe UI", sans-serif; max-width: 900px;
          margin: 0 auto; padding: 20px; background: #f8f9fa; color: #333; }}
  h1   {{ font-size: 1.5rem; color: #2c3e50; border-bottom: 3px solid #3498db;
          padding-bottom: 8px; }}
  h2   {{ font-size: 1.1rem; color: #2c3e50; margin-top: 28px; }}
  .stat-bar {{ display: flex; gap: 16px; margin: 12px 0; flex-wrap: wrap; }}
  .stat {{ background: #fff; border-radius: 8px; padding: 12px 20px;
           box-shadow: 0 1px 4px rgba(0,0,0,.08); text-align: center; }}
  .stat strong {{ display: block; font-size: 1.6rem; color: #3498db; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff;
           border-radius: 8px; overflow: hidden;
           box-shadow: 0 1px 4px rgba(0,0,0,.08); margin-top: 8px; }}
  th {{ background: #2c3e50; color: #fff; padding: 10px 12px;
        font-size: .85rem; text-align: left; }}
  td {{ padding: 9px 12px; border-bottom: 1px solid #f0f0f0; font-size: .88rem; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: #f8f9fa; }}
  a  {{ color: #2980b9; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .chart {{ background: #fff; border-radius: 8px; padding: 16px;
            box-shadow: 0 1px 4px rgba(0,0,0,.08); margin-top: 8px; text-align: center; }}
  footer {{ margin-top: 32px; font-size: .8rem; color: #999; text-align: center; }}
</style>
</head>
<body>

<h1>📊 事件驅動選股日報</h1>
<p style="color:#666">{date_str} &nbsp;|&nbsp; 自動掃描報告</p>

<div class="stat-bar">
  <div class="stat"><strong>{news_count}</strong>則新聞</div>
  <div class="stat"><strong>{len(events)}</strong>個事件</div>
  <div class="stat"><strong style="color:#c0392b">{len(buy_signals)}</strong>買進信號</div>
  <div class="stat"><strong style="color:#2980b9">{len(sell_signals)}</strong>賣出信號</div>
</div>

<h2>🔍 偵測到的事件 &amp; 新聞來源</h2>
<table>
  <tr>
    <th>事件</th><th style="text-align:center">則數</th>
    <th style="text-align:center">信心</th><th>相關新聞（點擊查看原文）</th>
  </tr>
  {event_rows}
</table>

<h2>📈 事件熱度圖</h2>
<div class="chart">{img_events}</div>

<h2>▲ 買進信號 TOP {len(buy_signals)}</h2>
<table>
  <tr><th>#</th><th>代號</th><th style="text-align:center">評分</th>
      <th>產業</th><th>事件來源</th><th style="text-align:center">信心</th></tr>
  {buy_rows}
</table>

<h2>▼ 賣出信號 TOP {len(sell_signals)}</h2>
<table>
  <tr><th>#</th><th>代號</th><th style="text-align:center">評分</th>
      <th>產業</th><th>事件來源</th><th style="text-align:center">信心</th></tr>
  {sell_rows}
</table>

<h2>📉 信號強度分布</h2>
<div class="chart">{img_signals}</div>

<footer>由事件驅動選股系統自動產生 · {date_str}</footer>
</body>
</html>"""


# ── LINE / 社群純文字報告 ─────────────────────────────────────────

def generate_text_report(
    events: list[DetectedEvent],
    signals: list[StockSignal],
    news_count: int,
    date_str: str | None = None,
    top_n: int = 10,
) -> str:
    date_str = date_str or datetime.now().strftime("%Y-%m-%d")
    buy_signals  = [s for s in signals if s.direction == "BUY"][:top_n]
    sell_signals = [s for s in signals if s.direction == "SELL"][:top_n]

    lines = [
        f"📊 事件驅動選股日報 {date_str}",
        "═" * 30,
        f"掃描 {news_count} 則新聞  |  偵測 {len(events)} 個事件",
        "",
        "🔍 今日事件 & 新聞",
        "─" * 30,
    ]

    for ev in events:
        conf_label = "🟢高" if ev.confidence >= 1.0 else "🟡中"
        lines.append(f"【{ev.event_name}】{ev.article_count} 則 {conf_label}")
        for title, url in zip(ev.source_titles[:3], ev.source_urls[:3]):
            if url:
                lines.append(f"  → {title}")
                lines.append(f"     {url}")
            else:
                lines.append(f"  → {title}")
        lines.append("")

    if buy_signals:
        lines += ["▲ 買進信號", "─" * 30]
        for i, s in enumerate(buy_signals, 1):
            inds = "/".join(s.industries[:2])
            evts = "、".join(s.events[:2])
            lines.append(f"{i:2}. {s.stock_code:<12} {s.score:+.1f}  {inds}｜{evts}")
        lines.append("")

    if sell_signals:
        lines += ["▼ 賣出信號", "─" * 30]
        for i, s in enumerate(sell_signals, 1):
            inds = "/".join(s.industries[:2])
            evts = "、".join(s.events[:2])
            lines.append(f"{i:2}. {s.stock_code:<12} {s.score:+.1f}  {inds}｜{evts}")
        lines.append("")

    lines += [
        "─" * 30,
        "⚠️ 本報告為自動掃描，僅供參考，不構成投資建議",
    ]

    return "\n".join(lines)
