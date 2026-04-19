"""
報告產生器 — HTML（Chart.js 圖表 + 新聞超連結）+ LINE 純文字

HTML 報告：用 Chart.js（CDN），無中文亂碼問題，直接瀏覽器開啟
LINE 報告：emoji 格式純文字，直接複製貼到社群
"""
from datetime import datetime

from event_classifier import DetectedEvent
from signal_generator import StockSignal


# ── HTML 報告 ────────────────────────────────────────────────────

def generate_html_report(
    events: list[DetectedEvent],
    signals: list[StockSignal],
    news_count: int,
    date_str: str | None = None,
    ai_summary: str = "",
) -> str:
    date_str = date_str or datetime.now().strftime("%Y-%m-%d")
    buy_signals  = [s for s in signals if s.direction == "BUY"][:15]
    sell_signals = [s for s in signals if s.direction == "SELL"][:15]

    # ── Chart.js 資料 ──────────────────────────────────────────
    event_labels  = [e.event_name   for e in events]
    event_counts  = [e.article_count for e in events]
    event_colors  = ["rgba(46,204,113,0.8)" if e.confidence >= 1.0
                     else "rgba(243,156,18,0.8)" for e in events]

    top_signals = sorted(signals, key=lambda s: abs(s.score), reverse=True)[:15]
    sig_labels  = [s.stock_code for s in top_signals]
    sig_scores  = [s.score      for s in top_signals]
    sig_colors  = ["rgba(231,76,60,0.8)" if s > 0
                   else "rgba(52,152,219,0.8)" for s in sig_scores]

    def js_array(lst) -> str:
        return "[" + ", ".join(
            f'"{v}"' if isinstance(v, str) else str(v) for v in lst
        ) + "]"

    if ai_summary:
        # replace newline with <br> for HTML rendering
        fmt_summary = ai_summary.replace('\n', '<br>')
        ai_summary_html = f'<div class="ai-summary-box"><h2>💡 AI 今日盤勢與焦點速報</h2><p>{fmt_summary}</p></div>'
    else:
        ai_summary_html = ""

    # ── 事件表格 rows ──────────────────────────────────────────
    event_rows = ""
    for ev in events:
        conf_badge = (
            '<span class="badge green">高信心</span>'
            if ev.confidence >= 1.0 else
            '<span class="badge orange">單篇</span>'
        )
        news_items_html = ""
        for title, url in zip(ev.source_titles, ev.source_urls):
            title = title or "(無標題)"
            if url:
                news_items_html += (
                    f'<li>'
                    f'<a href="{url}" target="_blank" rel="noopener">{title}</a>'
                    f'<br><span class="url-text">{url}</span>'
                    f'</li>'
                )
            else:
                news_items_html += f"<li>{title}</li>"

        if not news_items_html:
            news_items_html = "<li>（無新聞連結）</li>"

        event_rows += f"""
        <tr>
          <td><strong>{ev.event_name}</strong></td>
          <td class="center">{ev.article_count}</td>
          <td class="center">{conf_badge}</td>
          <td><ul class="news-list">{news_items_html}</ul></td>
        </tr>"""

    # ── 信號表格 rows ──────────────────────────────────────────
    def _signal_rows(sigs: list[StockSignal], color_class: str) -> str:
        rows = ""
        for i, s in enumerate(sigs, 1):
            inds = "/".join(s.industries[:2])
            evts = "、".join(s.events[:2])
            rows += f"""
            <tr>
              <td class="center">{i}</td>
              <td><strong>{s.stock_code}</strong></td>
              <td class="center {color_class}">{s.score:+.1f}</td>
              <td>{inds}</td>
              <td>{evts}</td>
              <td class="center">{s.confidence:.0%}</td>
            </tr>"""
        return rows

    buy_rows  = _signal_rows(buy_signals,  "red")
    sell_rows = _signal_rows(sell_signals, "blue")

    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>事件驅動選股日報 {date_str}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: -apple-system, "Microsoft JhengHei", "Noto Sans TC", sans-serif;
  background: #f5f6fa; color: #2c3e50; padding: 20px;
}}
.container {{ max-width: 960px; margin: 0 auto; }}
h1 {{ font-size: 1.5rem; border-bottom: 3px solid #3498db; padding-bottom: 10px; margin-bottom: 6px; }}
h2 {{ font-size: 1.05rem; margin: 28px 0 8px; color: #34495e; }}
.meta {{ color: #888; font-size: .85rem; margin-bottom: 16px; }}
.stat-bar {{
  display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 20px;
}}
.stat {{
  background: #fff; border-radius: 10px; padding: 14px 22px;
  box-shadow: 0 1px 4px rgba(0,0,0,.08); text-align: center; flex: 1; min-width: 100px;
}}
.stat strong {{ display: block; font-size: 2rem; color: #3498db; line-height: 1.1; }}
.stat.red  strong {{ color: #e74c3c; }}
.stat.blue strong {{ color: #2980b9; }}
table {{
  width: 100%; border-collapse: collapse; background: #fff;
  border-radius: 10px; overflow: hidden;
  box-shadow: 0 1px 4px rgba(0,0,0,.08);
}}
th {{
  background: #2c3e50; color: #fff; padding: 10px 12px;
  font-size: .82rem; text-align: left;
}}
td {{ padding: 10px 12px; border-bottom: 1px solid #f0f0f0; font-size: .87rem; vertical-align: top; }}
tr:last-child td {{ border-bottom: none; }}
tr:hover td {{ background: #fafbfc; }}
.center {{ text-align: center; }}
.red  {{ color: #c0392b; font-weight: bold; }}
.blue {{ color: #2980b9; font-weight: bold; }}
.badge {{
  display: inline-block; padding: 2px 8px; border-radius: 4px;
  font-size: .75rem; font-weight: bold;
}}
.badge.green  {{ background: #d5f5e3; color: #1e8449; }}
.badge.orange {{ background: #fdebd0; color: #d35400; }}
.news-list {{
  list-style: none; padding: 0; margin: 0;
  display: flex; flex-direction: column; gap: 6px;
}}
.news-list li {{ line-height: 1.4; }}
.news-list a {{
  color: #2980b9; text-decoration: none; font-weight: 500;
}}
.news-list a:hover {{ text-decoration: underline; }}
.url-text {{
  font-size: .72rem; color: #aaa; word-break: break-all;
}}
.chart-box {{
  background: #fff; border-radius: 10px; padding: 20px;
  box-shadow: 0 1px 4px rgba(0,0,0,.08); margin-top: 8px;
}}
.ai-summary-box {{
  background: #eaf2f8; border-left: 5px solid #2980b9; 
  border-radius: 8px; padding: 16px 20px; margin-bottom: 20px;
  font-size: .95rem; line-height: 1.6;
}}
.ai-summary-box h2 {{
  margin-top: 0;
  margin-bottom: 12px;
}}
footer {{
  margin-top: 40px; font-size: .78rem; color: #bbb; text-align: center; padding: 10px;
}}
</style>
</head>
<body>
<div class="container">

<h1>📊 事件驅動選股日報</h1>
<p class="meta">{date_str} &nbsp;·&nbsp; 自動掃描</p>

<div class="stat-bar">
  <div class="stat"><strong>{news_count}</strong>則新聞</div>
  <div class="stat"><strong>{len(events)}</strong>個事件</div>
  <div class="stat red"><strong>{len(buy_signals)}</strong>買進信號</div>
  <div class="stat blue"><strong>{len(sell_signals)}</strong>賣出信號</div>
</div>

{ai_summary_html}

<!-- 事件表格 -->
<h2>🔍 偵測到的事件 &amp; 新聞來源</h2>
<table>
  <tr>
    <th>事件</th>
    <th style="text-align:center;width:60px">則數</th>
    <th style="text-align:center;width:80px">信心</th>
    <th>相關新聞（點標題可看原文）</th>
  </tr>
  {event_rows}
</table>

<!-- 事件熱度圖 -->
<h2>📈 事件熱度圖</h2>
<div class="chart-box" style="height:320px">
  <canvas id="chartEvents"></canvas>
</div>

<!-- 買進信號 -->
<h2>▲ 買進信號 TOP {len(buy_signals)}</h2>
<table>
  <tr>
    <th style="width:36px">#</th>
    <th>代號</th>
    <th style="text-align:center;width:70px">評分</th>
    <th>產業</th>
    <th>事件來源</th>
    <th style="text-align:center;width:60px">信心</th>
  </tr>
  {buy_rows if buy_rows else '<tr><td colspan="6" style="text-align:center;color:#aaa">無買進信號</td></tr>'}
</table>

<!-- 賣出信號 -->
<h2>▼ 賣出信號 TOP {len(sell_signals)}</h2>
<table>
  <tr>
    <th style="width:36px">#</th>
    <th>代號</th>
    <th style="text-align:center;width:70px">評分</th>
    <th>產業</th>
    <th>事件來源</th>
    <th style="text-align:center;width:60px">信心</th>
  </tr>
  {sell_rows if sell_rows else '<tr><td colspan="6" style="text-align:center;color:#aaa">無賣出信號</td></tr>'}
</table>

<!-- 信號強度圖 -->
<h2>📉 信號強度分布</h2>
<div class="chart-box" style="height:420px">
  <canvas id="chartSignals"></canvas>
</div>

<footer>由事件驅動選股系統自動產生 &nbsp;·&nbsp; {date_str}<br>本報告僅供參考，不構成投資建議</footer>

</div><!-- /container -->

<script>
// 事件熱度圖
(function() {{
  const ctx = document.getElementById('chartEvents').getContext('2d');
  new Chart(ctx, {{
    type: 'bar',
    data: {{
      labels: {js_array(event_labels[::-1])},
      datasets: [{{
        label: '新聞則數',
        data:   {js_array(event_counts[::-1])},
        backgroundColor: {js_array(event_colors[::-1])},
        borderRadius: 4,
      }}]
    }},
    options: {{
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{ callbacks: {{
          label: ctx => ctx.parsed.x + ' 則新聞'
        }}}}
      }},
      scales: {{
        x: {{ beginAtZero: true, ticks: {{ stepSize: 1 }} }},
        y: {{ ticks: {{ font: {{ size: 13 }} }} }}
      }}
    }}
  }});
}})();

// 信號強度圖
(function() {{
  const ctx = document.getElementById('chartSignals').getContext('2d');
  new Chart(ctx, {{
    type: 'bar',
    data: {{
      labels: {js_array(sig_labels[::-1])},
      datasets: [{{
        label: '信號分數',
        data:   {js_array(sig_scores[::-1])},
        backgroundColor: {js_array(sig_colors[::-1])},
        borderRadius: 4,
      }}]
    }},
    options: {{
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{ callbacks: {{
          label: ctx => (ctx.parsed.x > 0 ? '買進 ' : '賣出 ') + ctx.parsed.x.toFixed(1)
        }}}}
      }},
      scales: {{
        x: {{ ticks: {{ callback: v => (v > 0 ? '+' : '') + v }} }},
        y: {{ ticks: {{ font: {{ size: 12 }} }} }}
      }}
    }}
  }});
}})();
</script>
</body>
</html>"""


# ── LINE / 社群純文字報告 ─────────────────────────────────────────

def generate_text_report(
    events: list[DetectedEvent],
    signals: list[StockSignal],
    news_count: int,
    date_str: str | None = None,
    top_n: int = 10,
    ai_summary: str = "",
) -> str:
    date_str = date_str or datetime.now().strftime("%Y-%m-%d")
    buy_signals  = [s for s in signals if s.direction == "BUY"][:top_n]
    sell_signals = [s for s in signals if s.direction == "SELL"][:top_n]

    lines = [
        f"📊 事件驅動選股日報 {date_str}",
        "═" * 32,
        f"掃描 {news_count} 則新聞  |  偵測 {len(events)} 個事件",
        "",
    ]
    
    if ai_summary:
        lines += [
            "💡 AI 今日盤勢與焦點速報",
            "─" * 32,
            ai_summary,
            "",
        ]

    lines += [
        "🔍 今日事件 & 新聞",
        "─" * 32,
    ]

    for ev in events:
        conf_label = "🟢高信心" if ev.confidence >= 1.0 else "🟡單篇"
        lines.append(f"【{ev.event_name}】{ev.article_count} 則  {conf_label}")
        for title, url in zip(ev.source_titles[:3], ev.source_urls[:3]):
            title = title or "(無標題)"
            lines.append(f"  ▸ {title}")
            if url:
                lines.append(f"    {url}")
        lines.append("")

    if buy_signals:
        lines += ["▲ 買進信號", "─" * 32]
        for i, s in enumerate(buy_signals, 1):
            inds = "/".join(s.industries[:2])
            evts = "、".join(s.events[:2])
            lines.append(f"{i:2}. {s.stock_code:<12} {s.score:+.1f}  {inds}｜{evts}")
        lines.append("")

    if sell_signals:
        lines += ["▼ 賣出信號", "─" * 32]
        for i, s in enumerate(sell_signals, 1):
            inds = "/".join(s.industries[:2])
            evts = "、".join(s.events[:2])
            lines.append(f"{i:2}. {s.stock_code:<12} {s.score:+.1f}  {inds}｜{evts}")
        lines.append("")

    lines += [
        "─" * 32,
        "⚠️ 本報告為自動掃描，僅供參考，不構成投資建議",
    ]

    return "\n".join(lines)
