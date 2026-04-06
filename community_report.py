"""
社群版日報產生器

輸出兩個檔案：
  community_YYYYMMDD.html  ← 瀏覽器開啟，有圖表 + 可點擊連結
  community_YYYYMMDD.txt   ← 直接複製貼到 LINE / Discord

重點：
  1. 熱門話題排行（新聞則數）
  2. 熱門股票排行（被提及次數）
  3. 每個話題列出 3 則原文連結
"""
from datetime import datetime

from event_classifier import DetectedEvent
from news_fetcher import NewsItem
from stock_mention_counter import StockMention


# ── 輔助：全部新聞列表 HTML ──────────────────────────────────────

def _all_news_html(news_items: list[NewsItem]) -> str:
    rows = ""
    for i, item in enumerate(news_items, 1):
        title = item.title or "(無標題)"
        source = item.source or ""
        if item.url:
            title_cell = f'<a href="{item.url}" target="_blank" rel="noopener">{title}</a>'
        else:
            title_cell = title
        rows += f"""
        <tr>
          <td class="center" style="color:#bbb;width:36px">{i}</td>
          <td class="src-badge">{source}</td>
          <td>{title_cell}</td>
        </tr>"""
    return f"""
    <table>
      <tr>
        <th style="width:36px">#</th>
        <th style="width:90px">來源</th>
        <th>標題（點擊看原文）</th>
      </tr>
      {rows}
    </table>"""


# ── HTML 社群報告 ────────────────────────────────────────────────

def generate_community_html(
    events: list[DetectedEvent],
    mentions: list[StockMention],
    news_items: list[NewsItem],
    date_str: str | None = None,
) -> str:
    news_count = len(news_items)
    date_str = date_str or datetime.now().strftime("%Y-%m-%d")

    # Chart.js 資料：事件熱度
    ev_labels = [e.event_name    for e in events]
    ev_counts = [e.article_count for e in events]
    ev_colors = [
        "rgba(52,152,219,0.85)" if e.confidence >= 1.0
        else "rgba(149,165,166,0.7)"
        for e in events
    ]

    # Chart.js 資料：股票提及
    top_mentions = mentions[:15]
    mn_labels = [f"{m.name}({m.ticker})" for m in top_mentions]
    mn_counts = [m.count for m in top_mentions]

    def js_str_array(lst: list[str]) -> str:
        escaped = [v.replace('"', '\\"') for v in lst]
        return "[" + ", ".join(f'"{v}"' for v in escaped) + "]"

    def js_num_array(lst: list) -> str:
        return "[" + ", ".join(str(v) for v in lst) + "]"

    # 事件 → 新聞列表 HTML
    event_sections = ""
    for ev in events:
        conf_cls   = "high" if ev.confidence >= 1.0 else "mid"
        conf_label = "高信心" if ev.confidence >= 1.0 else "單篇"
        news_html  = ""
        has_links  = False

        for title, url in zip(ev.source_titles, ev.source_urls):
            title = title or "(無標題)"
            if url:
                has_links = True
                news_html += (
                    f'<li>'
                    f'<a href="{url}" target="_blank" rel="noopener">{title}</a>'
                    f'</li>'
                )
            else:
                news_html += f'<li><span class="no-link">{title}</span></li>'

        if not news_html:
            news_html = '<li class="no-link">（本次無抓到新聞連結）</li>'

        event_sections += f"""
        <div class="ev-card">
          <div class="ev-header">
            <span class="ev-name">{ev.event_name}</span>
            <span class="ev-count">{ev.article_count} 則</span>
            <span class="badge {conf_cls}">{conf_label}</span>
          </div>
          <ul class="news-list">{news_html}</ul>
        </div>"""

    # 股票提及表格 HTML
    mention_rows = ""
    for i, m in enumerate(top_mentions, 1):
        bar_w = int(m.count / max(mn_counts) * 120) if mn_counts else 0
        mention_rows += f"""
        <tr>
          <td class="center rank">{i}</td>
          <td><strong>{m.name}</strong><br><span class="ticker">{m.ticker}</span></td>
          <td class="center count">{m.count}</td>
          <td>
            <div class="bar-wrap">
              <div class="bar-fill" style="width:{bar_w}px"></div>
            </div>
          </td>
          <td class="sample-news">{'<br>'.join(
              f'<a href="{u}" target="_blank" rel="noopener">{t}</a>'
              if u else t
              for t, u in zip(m.sample_titles[:2], m.sample_urls[:2])
          )}</td>
        </tr>"""

    if not mention_rows:
        mention_rows = '<tr><td colspan="5" class="center" style="color:#aaa">（未偵測到已知股票名稱）</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>財經熱點日報 {date_str}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,"Microsoft JhengHei","Noto Sans TC",sans-serif;
      background:#f0f2f5;color:#2c3e50;padding:16px}}
.wrap{{max-width:880px;margin:0 auto}}
h1{{font-size:1.4rem;border-left:5px solid #3498db;padding-left:12px;margin-bottom:4px}}
.meta{{color:#999;font-size:.82rem;margin-bottom:18px;padding-left:17px}}
h2{{font-size:1rem;margin:24px 0 10px;color:#34495e;
    display:flex;align-items:center;gap:8px}}
/* stat bar */
.stat-bar{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:20px}}
.stat{{background:#fff;border-radius:10px;padding:12px 20px;
       box-shadow:0 1px 4px rgba(0,0,0,.08);flex:1;min-width:90px;text-align:center}}
.stat strong{{display:block;font-size:1.8rem;color:#3498db;line-height:1.1}}
/* chart */
.chart-box{{background:#fff;border-radius:10px;padding:16px;
            box-shadow:0 1px 4px rgba(0,0,0,.08);margin-bottom:20px}}
/* event cards */
.ev-card{{background:#fff;border-radius:10px;padding:14px 16px;
          margin-bottom:10px;box-shadow:0 1px 4px rgba(0,0,0,.07)}}
.ev-header{{display:flex;align-items:center;gap:10px;margin-bottom:8px}}
.ev-name{{font-weight:700;font-size:1rem}}
.ev-count{{color:#666;font-size:.85rem}}
.badge{{padding:2px 8px;border-radius:4px;font-size:.72rem;font-weight:600}}
.badge.high{{background:#d5f5e3;color:#1e8449}}
.badge.mid{{background:#fdebd0;color:#d35400}}
.news-list{{list-style:none;display:flex;flex-direction:column;gap:5px;padding-left:4px}}
.news-list li{{font-size:.87rem;line-height:1.45}}
.news-list a{{color:#2980b9;text-decoration:none}}
.news-list a:hover{{text-decoration:underline}}
.no-link{{color:#aaa;font-style:italic}}
/* mention table */
table{{width:100%;border-collapse:collapse;background:#fff;
       border-radius:10px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
th{{background:#2c3e50;color:#fff;padding:9px 12px;font-size:.82rem;text-align:left}}
td{{padding:9px 12px;border-bottom:1px solid #f0f0f0;font-size:.85rem;vertical-align:middle}}
tr:last-child td{{border-bottom:none}}
tr:hover td{{background:#fafbfc}}
.center{{text-align:center}}
.rank{{font-weight:700;color:#7f8c8d;font-size:1.1rem}}
.count{{font-weight:700;color:#2980b9;font-size:1.1rem}}
.ticker{{color:#aaa;font-size:.75rem}}
.bar-wrap{{width:130px;height:14px;background:#ecf0f1;border-radius:7px;overflow:hidden}}
.bar-fill{{height:100%;background:linear-gradient(90deg,#3498db,#2ecc71);border-radius:7px}}
.sample-news{{font-size:.8rem;max-width:260px}}
.sample-news a{{color:#2980b9;text-decoration:none}}
.sample-news a:hover{{text-decoration:underline}}
footer{{margin-top:30px;font-size:.75rem;color:#bbb;text-align:center;padding:8px}}
.src-badge{{font-size:.75rem;color:#888;white-space:nowrap}}
</style>
</head>
<body>
<div class="wrap">

<h1>📰 財經熱點日報</h1>
<p class="meta">{date_str} &nbsp;·&nbsp; 掃描 {news_count} 則新聞自動產生</p>

<div class="stat-bar">
  <div class="stat"><strong>{news_count}</strong>則新聞</div>
  <div class="stat"><strong>{len(events)}</strong>個熱門話題</div>
  <div class="stat"><strong>{len(top_mentions)}</strong>檔股票被提及</div>
</div>

<!-- 話題熱度圖 -->
<h2>🔥 話題熱度（新聞則數）</h2>
<div class="chart-box" style="height:{max(200, len(ev_labels)*48)}px">
  <canvas id="chartEvents"></canvas>
</div>

<!-- 話題 + 新聞列表 -->
<h2>📋 各話題精選新聞（點標題看原文）</h2>
{event_sections}

<!-- 股票提及圖 -->
<h2>📊 熱門股票提及排行</h2>
<div class="chart-box" style="height:{max(200, len(mn_labels)*40)}px">
  <canvas id="chartMentions"></canvas>
</div>

<!-- 股票提及表格 -->
<h2>🏭 詳細排行</h2>
<table>
  <tr>
    <th style="width:40px">#</th>
    <th>股票</th>
    <th style="width:60px;text-align:center">提及</th>
    <th style="width:140px">熱度</th>
    <th>相關新聞</th>
  </tr>
  {mention_rows}
</table>

<footer>由事件驅動選股系統自動產生 · {date_str}<br>本報告為自動掃描，僅供參考，不構成投資建議</footer>
</div>
<div id="all-news-wrap" class="wrap" style="margin-top:0">
<h2 style="margin-top:8px">📑 今日全部新聞（{news_count} 則）</h2>
<p style="font-size:.8rem;color:#999;margin-bottom:10px">
  以下為本次掃描的所有新聞標題，點標題可開原文。
</p>
{_all_news_html(news_items)}
<div style="height:24px"></div>
</div>

<script>
// 話題熱度圖
new Chart(document.getElementById('chartEvents'), {{
  type: 'bar',
  data: {{
    labels: {js_str_array(ev_labels[::-1])},
    datasets: [{{
      label: '新聞則數',
      data: {js_num_array(ev_counts[::-1])},
      backgroundColor: {js_str_array(ev_colors[::-1])},
      borderRadius: 5,
    }}]
  }},
  options: {{
    indexAxis: 'y', responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ beginAtZero: true, ticks: {{ stepSize: 1 }} }},
      y: {{ ticks: {{ font: {{ size: 13 }} }} }}
    }}
  }}
}});

// 股票提及圖
new Chart(document.getElementById('chartMentions'), {{
  type: 'bar',
  data: {{
    labels: {js_str_array(mn_labels[::-1])},
    datasets: [{{
      label: '提及次數',
      data: {js_num_array(mn_counts[::-1])},
      backgroundColor: 'rgba(52,152,219,0.75)',
      borderRadius: 5,
    }}]
  }},
  options: {{
    indexAxis: 'y', responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ beginAtZero: true, ticks: {{ stepSize: 1 }} }},
      y: {{ ticks: {{ font: {{ size: 12 }} }} }}
    }}
  }}
}});
</script>
</body>
</html>"""


# ── LINE 純文字報告 ──────────────────────────────────────────────

def generate_community_text(
    events: list[DetectedEvent],
    mentions: list[StockMention],
    news_items: list[NewsItem],
    date_str: str | None = None,
    top_events: int = 8,
    top_stocks: int = 10,
) -> str:
    date_str  = date_str or datetime.now().strftime("%Y-%m-%d")
    news_count = len(news_items)
    lines = [
        f"📰 財經熱點日報 {date_str}",
        "═" * 32,
        f"共掃描 {news_count} 則新聞",
        "",
        "🔥 熱門話題（依新聞則數）",
        "─" * 32,
    ]

    for i, ev in enumerate(events[:top_events], 1):
        bar = "█" * min(ev.article_count, 10)
        conf = "🟢" if ev.confidence >= 1.0 else "🟡"
        lines.append(f"{i:2}. {conf} {ev.event_name}  {bar} {ev.article_count}則")

    lines += ["", "📋 精選新聞（附連結）", "─" * 32]

    for ev in events[:top_events]:
        lines.append(f"【{ev.event_name}】")
        paired = list(zip(ev.source_titles, ev.source_urls))
        if not paired:
            lines.append("  （無新聞資料）")
        else:
            for title, url in paired[:3]:
                title = title or "(無標題)"
                lines.append(f"  ▸ {title}")
                if url:
                    lines.append(f"    {url}")
        lines.append("")

    lines += ["🏭 熱門股票（被新聞提及次數）", "─" * 32]

    for i, m in enumerate(mentions[:top_stocks], 1):
        bar = "▪" * min(m.count, 8)
        lines.append(f"{i:2}. {m.name:<8} ({m.ticker})  {bar} {m.count}次")
        for title, url in zip(m.sample_titles[:1], m.sample_urls[:1]):
            if url:
                lines.append(f"     → {title}")
                lines.append(f"       {url}")

    lines += ["", "📑 今日全部新聞", "─" * 32]
    for i, item in enumerate(news_items, 1):
        title = item.title or "(無標題)"
        lines.append(f"{i:3}. [{item.source}] {title}")
        if item.url:
            lines.append(f"      {item.url}")

    lines += [
        "",
        "─" * 32,
        "⚠️ 本報告為自動掃描，僅供參考，不構成投資建議",
    ]

    return "\n".join(lines)
