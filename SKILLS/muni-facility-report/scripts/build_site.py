#!/usr/bin/env python3
"""SITE/ の公開ページ一式を DATA/ のCSVから生成するテンプレート。
豊橋#1の build_site.py から一般化したもの。

このファイルはテンプレートであり、市ごとに CONFIG と「柱の数字」
（ヒーロー数字・お金のギャップ図の内訳）をその市の総合管理計画の
数字に書き換える必要がある。書き換え箇所には全て「# ★市ごとに書き換え」
と付けてある。

配色・マーク仕様は dataviz skill の references/palette.md に準拠。
新しい市でも validate_palette.js を必ず実行してから使うこと
（palette.md の3色スロットはCVD検証済みだが、別の色を選ぶ場合は要再検証）。

生成物:
- SITE/index.html    表紙 + 中核図表(お金のギャップ・築年代分布) + 出典
- SITE/kouku.html    地域単位別サマリー表
- SITE/shisetsu.html 全施設一覧表(テキスト絞り込み付き)
"""
import csv
import html as H
from pathlib import Path

ROOT = Path(__file__).parent
SITE = ROOT / "SITE"

# ==== ★市ごとに書き換え: 基本設定 ====
CITY_NAME = "〇〇市"
AUTHOR_NAME = "【実名をここに】"
DISTRICT_COL = "小学校区"  # analyze_shisetsu.py の DISTRICT_COL と一致させる
DISTRICT_LABEL = "校区"    # 表の見出しに使う短い呼び名
PUBLISH_DATE = "20XX年X月X日（X）"
GITHUB_REPO_URL = "https://github.com/USER/REPO/tree/main/CITY_DIR"

# 30年収支試算（総合管理計画から。単位: 億円）— ★市ごとに書き換え
HERO_NUMBERS = {
    "need_total": 4392,          # 必要な費用の合計
    "need_breakdown": [           # (ラベル, 億円) の内訳。合計がneed_totalと一致すること
        ("更新等（建て替え）", 1551),
        ("改修（大規模修繕）", 2000),
        ("維持管理・修繕", 841),
    ],
    "available_total": 3268,      # 用意できる費用
    "annual_actual": 108.9,       # 現在の年間実績支出（億円/年）
    "shortfall": 1124,            # 不足額
    "shortfall_pct": 26,          # 不足率(%)
    "reduction_target_pct": 20,   # 市が掲げる延床削減目標(%、「程度」等の言葉は本文で補う)
    "source_plan_name": "〇〇市公共施設等総合管理計画20XX-20XX",
    "source_page_gap": "52-53",   # ギャップ試算のページ
    "source_page_annual": "34",   # 現在の年間実績支出のページ
    "source_page_target": "53",   # 削減目標のページ
    "test_range_note": "試算対象は建物系施設（インフラ系施設・上下水道・市民病院等を除く）",  # 対象範囲の注記。市の計画の記載に合わせる
}
# ======================================

CSS = """
  :root { color-scheme: light; }
  body {
    --surface-1:#fcfcfb; --page:#f9f9f7; --ink-1:#0b0b0b; --ink-2:#52514e;
    --ink-muted:#898781; --grid:#e1e0d9; --baseline:#c3c2b7;
    --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a; --ctx:#c3c2b7;
    --border:rgba(11,11,11,0.10);
    font-family: system-ui,-apple-system,"Segoe UI",sans-serif;
    background:var(--page); color:var(--ink-1);
    margin:0 auto; max-width:860px; padding:24px 16px 48px; line-height:1.75;
  }
  @media (prefers-color-scheme: dark) {
    :root:where(:not([data-theme="light"])) body {
      color-scheme:dark;
      --surface-1:#1a1a19; --page:#0d0d0d; --ink-1:#fff; --ink-2:#c3c2b7;
      --grid:#2c2c2a; --baseline:#383835;
      --s1:#3987e5; --s2:#d95926; --s3:#199e70; --ctx:#52514e;
      --border:rgba(255,255,255,0.10);
    }
  }
  h1 { font-size:1.45rem; margin:0 0 4px; line-height:1.4; }
  h2 { font-size:1.1rem; margin:32px 0 8px; }
  .sub { color:var(--ink-2); font-size:.9rem; margin:0 0 20px; }
  .card { background:var(--surface-1); border:1px solid var(--border);
          border-radius:10px; padding:20px; margin-bottom:20px; }
  .hero-label { font-size:.85rem; color:var(--ink-2); margin:0; }
  .hero { font-size:52px; font-weight:700; line-height:1.15; margin:2px 0 0; }
  .hero small { font-size:22px; font-weight:600; }
  .hero-note { font-size:.85rem; color:var(--ink-2); margin:6px 0 0; }
  .chart-title { font-size:1rem; font-weight:600; margin:0 0 2px; }
  .chart-sub { font-size:.82rem; color:var(--ink-2); margin:0 0 14px; }
  .legend { display:flex; gap:16px; flex-wrap:wrap; font-size:.8rem;
            color:var(--ink-2); margin:10px 0 0; }
  .legend span::before { content:""; display:inline-block; width:10px; height:10px;
    border-radius:2px; margin-right:6px; vertical-align:-1px; background:var(--sw); }
  svg { display:block; width:100%; height:auto; }
  svg text { font-family:inherit; }
  .axis-t { fill:var(--ink-muted); font-size:11px; }
  .lab-t { fill:var(--ink-2); font-size:12px; }
  .val-t { fill:var(--ink-1); font-size:12px; font-weight:600; }
  .seg-t { fill:#fff; font-size:11.5px; font-weight:600; }
  .bar-seg:hover, .col:hover { opacity:.85; }
  .tip { position:fixed; pointer-events:none; z-index:10; display:none;
    background:var(--surface-1); color:var(--ink-1); border:1px solid var(--border);
    border-radius:6px; padding:6px 10px; font-size:.8rem;
    box-shadow:0 2px 8px rgba(0,0,0,.18); }
  details { margin-top:12px; font-size:.85rem; }
  details summary { cursor:pointer; color:var(--ink-2); }
  .tblwrap { overflow-x:auto; }
  table { border-collapse:collapse; margin-top:8px;
          font-variant-numeric:tabular-nums; width:100%; }
  th,td { border-bottom:1px solid var(--grid); padding:5px 12px 5px 0;
          text-align:right; font-size:.82rem; white-space:nowrap; }
  th:first-child, td:first-child { text-align:left; white-space:normal; }
  th { color:var(--ink-2); font-weight:600; }
  .src { font-size:.78rem; color:var(--ink-muted); margin-top:14px; line-height:1.6; }
  .src a, .nav a { color:inherit; }
  .nav { font-size:.85rem; color:var(--ink-2); margin-bottom:20px; }
  input[type=search] { width:100%; box-sizing:border-box; padding:8px 12px;
    border:1px solid var(--border); border-radius:8px; font-size:.9rem;
    background:var(--surface-1); color:var(--ink-1); margin-bottom:8px; }
"""

TIP_JS = """
<script>
  const tip = document.getElementById("tip");
  if (tip) document.querySelectorAll("[data-tip]").forEach(el => {
    el.addEventListener("mousemove", e => {
      tip.textContent = el.dataset.tip; tip.style.display = "block";
      tip.style.left = Math.min(e.clientX + 12, window.innerWidth - 240) + "px";
      tip.style.top = (e.clientY + 14) + "px";
    });
    el.addEventListener("mouseleave", () => tip.style.display = "none");
  });
</script>
"""


def page(title, body, desc=""):
    return f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{H.escape(desc)}">
<title>{H.escape(title)}</title>
<style>{CSS}</style></head>
<body>
{body}
<div class="tip" id="tip"></div>
{TIP_JS}
</body></html>"""


def read_csv(name):
    with (ROOT / "DATA" / name).open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def fmt(n, unit=""):
    if n in ("", None):
        return "－"
    try:
        return f"{float(n):,.0f}{unit}"
    except ValueError:
        return H.escape(str(n))


# ---------------- 中核図表(index) ----------------

def core_figure_svg():
    """お金のギャップの横バー。HERO_NUMBERSから座標を自動計算する。"""
    h = HERO_NUMBERS
    x0, x1 = 140, 780
    axis_max = round(h["need_total"] * 1.05, -2) or 100  # 必要額の少し上まで
    px = (x1 - x0) / axis_max
    colors = ["var(--s1)", "var(--s2)", "var(--s3)"]
    parts, x = [], x0
    for i, (label, v) in enumerate(h["need_breakdown"]):
        color = colors[i % len(colors)]
        w = v * px - (2 if i < len(h["need_breakdown"]) - 1 else 0)
        rx = ' rx="4"' if i == len(h["need_breakdown"]) - 1 else ""
        parts.append(f'<rect class="bar-seg" data-tip="{label}: 約{v:,}億円" '
                     f'x="{x:.1f}" y="48" width="{w:.1f}" height="28" fill="{color}"{rx}/>')
        parts.append(f'<text class="seg-t" x="{x + v*px/2:.0f}" y="66" '
                     f'text-anchor="middle">{v:,}</text>')
        x += v * px
    need_end = x0 + h["need_total"] * px
    avail_end = x0 + h["available_total"] * px
    step = round(axis_max / 4, -2) or axis_max / 4
    gridx = [(x0 + v * px, f"{v:,.0f}" + ("億円" if i == 4 else ""))
             for i, v in enumerate([step * k for k in range(5)])]
    grid = "".join(f'<line x1="{gx:.0f}" y1="30" x2="{gx:.0f}" y2="168"/>'
                   for gx, _ in gridx[1:])
    ticks = "".join(f'<text x="{gx:.0f}" y="182" text-anchor="middle">{t}</text>'
                    for gx, t in gridx)
    legend = "".join(
        f'<span style="--sw: {colors[i % len(colors)]}">{label}</span>'
        for i, (label, _) in enumerate(h["need_breakdown"]))
    legend += '<span style="--sw: var(--ctx)">用意できる費用</span>'
    svg = f"""<svg viewBox="0 0 800 190" role="img"
  aria-label="必要{h['need_total']:,}億円に対し用意できるのは{h['available_total']:,}億円で{h['shortfall']:,}億円不足">
  <g class="axis-t">{ticks}</g>
  <g stroke="var(--grid)" stroke-width="1">{grid}</g>
  <line x1="{x0}" y1="30" x2="{x0}" y2="168" stroke="var(--baseline)" stroke-width="1"/>
  <text class="lab-t" x="{x0-8}" y="66" text-anchor="end">必要な費用</text>
  {''.join(parts)}
  <text class="val-t" x="{need_end+8:.0f}" y="66">{h['need_total']:,}</text>
  <text class="lab-t" x="{x0-8}" y="128" text-anchor="end">用意できる</text>
  <rect class="bar-seg" data-tip="約{h['annual_actual']}億円/年 × 30年 → 約{h['available_total']:,}億円（計画の試算値）"
    x="{x0}" y="110" width="{avail_end-x0:.1f}" height="28" fill="var(--ctx)" rx="4"/>
  <text class="val-t" x="{avail_end+8:.0f}" y="128">{h['available_total']:,}</text>
  <g stroke="var(--ink-2)" fill="none" stroke-width="1.2">
    <line x1="{avail_end:.1f}" y1="88" x2="{avail_end:.1f}" y2="98"/>
    <line x1="{need_end:.1f}" y1="88" x2="{need_end:.1f}" y2="98"/>
    <line x1="{avail_end:.1f}" y1="93" x2="{need_end:.1f}" y2="93"/>
  </g>
  <text class="lab-t" x="{(avail_end+need_end)/2:.0f}" y="106" text-anchor="middle"
    style="font-weight:600">不足 約{h['shortfall']:,}億円</text>
  <line x1="{avail_end:.1f}" y1="30" x2="{avail_end:.1f}" y2="168"
    stroke="var(--ink-2)" stroke-width="1" stroke-dasharray="3 3"/>
</svg>"""
    return svg, legend


def nendai_svg(nendai):
    """建築年代別延床の縦棒。DATA/derived_nendai_bunpu.csv から自動計算する。"""
    top, bottom = 26, 209
    ymax = max(float(r["延床面積合計_m2"]) for r in nendai) * 1.06
    h = bottom - top
    cols, labels, peak = [], [], max(nendai, key=lambda r: float(r["延床面積合計_m2"]))
    for i, r in enumerate(nendai):
        m2 = float(r["延床面積合計_m2"])
        bh = m2 / ymax * h
        x = 74 + i * (700 / max(len(nendai), 1))
        rx = 4 if bh > 4 else 1
        cols.append(f'<rect class="col" data-tip="{r["建築年代"]}: {r["施設数"]}施設 / '
                    f'{m2/10000:.1f}万㎡" x="{x:.0f}" y="{bottom-bh:.1f}" width="44" '
                    f'height="{bh:.1f}" rx="{rx}"/>')
        dec = r["建築年代"].replace("年代", "")
        lab = "1930s" if dec == "1930" else ("2000s" if dec == "2000" else dec[-2:] + "s")
        labels.append(f'<text x="{x+22:.0f}" y="226" text-anchor="middle">{lab}</text>')
        if r is peak:
            peak_x, peak_y = x + 22, bottom - bh - 7
    gtick = ymax / 3
    return f"""<svg viewBox="0 0 800 240" role="img"
  aria-label="建築年代別延床面積。{peak['建築年代']}が最大">
  <g stroke="var(--grid)" stroke-width="1">
    <line x1="60" y1="26" x2="780" y2="26"/><line x1="60" y1="87" x2="780" y2="87"/>
    <line x1="60" y1="148" x2="780" y2="148"/>
  </g>
  <g class="axis-t">
    <text x="54" y="30" text-anchor="end">{gtick*3/10000:.0f}万㎡</text>
    <text x="54" y="91" text-anchor="end">{gtick*2/10000:.0f}万㎡</text>
    <text x="54" y="152" text-anchor="end">{gtick/10000:.0f}万㎡</text>
  </g>
  <line x1="60" y1="209" x2="780" y2="209" stroke="var(--baseline)" stroke-width="1"/>
  <g fill="var(--s1)">{''.join(cols)}</g>
  <text class="val-t" x="{peak_x:.0f}" y="{peak_y:.0f}" text-anchor="middle">
    {float(peak['延床面積合計_m2'])/10000:.1f}万㎡</text>
  <g class="axis-t">{''.join(labels)}</g>
</svg>"""


def build_index():
    h = HERO_NUMBERS
    nendai = read_csv("derived_nendai_bunpu.csv")
    nendai_rows = "".join(
        f'<tr><td>{r["建築年代"]}</td><td>{r["施設数"]}</td>'
        f'<td>{fmt(r["延床面積合計_m2"], "㎡")}</td></tr>' for r in nendai)
    gap_svg, legend = core_figure_svg()
    breakdown_rows = "".join(
        f"<tr><td>{label}</td><td>約{v:,}</td></tr>" for label, v in h["need_breakdown"])
    body = f"""
<h1>{H.escape(CITY_NAME)}の公共施設 — これから30年のお金の地図</h1>
<p class="sub">{H.escape(CITY_NAME)} 公開情報の地図 #1（{PUBLISH_DATE}公開）</p>

<p>{H.escape(AUTHOR_NAME)}。{H.escape(CITY_NAME)}で学んだ人間が、{H.escape(CITY_NAME)}の
公開情報を読む——このレポートは、市が自ら公表している計画書・白書・決算資料を、
市民が読める形に翻訳したものです。意見や提言ではなく、書いてあることの整理です。
自分の話はここまでにして、以下はすべて市の数字です。</p>

<div class="card">
  <p class="hero-label">今後30年間で、施設の維持・更新に必要なお金のうち</p>
  <p class="hero">約{h['shortfall']:,}<small>億円が不足</small></p>
  <p class="hero-note">必要額 約{h['need_total']:,}億円に対し、用意できる見込みは約
  {h['available_total']:,}億円（約{h['shortfall_pct']}%不足）。市の結論は「施設の延べ床面積を
  30年間で{h['reduction_target_pct']}%程度削減する」。
  ——{h['source_plan_name']} p.{h['source_page_gap']}</p>
</div>

<div class="card">
  <p class="chart-title">必要なお金と、用意できるお金（30年間の累計・建物系施設）</p>
  <p class="chart-sub">上段: 維持・更新に必要な費用の内訳 ／
  下段: 現在の支出ペース（実績 約{h['annual_actual']}億円/年）を30年続けた場合</p>
  {gap_svg}
  <div class="legend">{legend}</div>
  <details><summary>データ表を開く</summary>
    <div class="tblwrap"><table>
      <tr><th>項目</th><th>金額（億円）</th></tr>
      {breakdown_rows}
      <tr><td><b>必要な費用 計</b></td><td><b>約{h['need_total']:,}</b></td></tr>
      <tr><td>用意できる費用（{h['annual_actual']}億円/年×30年、計画の試算値）</td><td>約{h['available_total']:,}</td></tr>
      <tr><td><b>不足</b></td><td><b>約{h['shortfall']:,}（約{h['shortfall_pct']}%）</b></td></tr>
    </table></div>
  </details>
</div>

<div class="card">
  <p class="chart-title">その建物たちは、いつ建てられたか（建築年代別の延べ床面積）</p>
  <p class="chart-sub">建築年度が公表されている施設を集計</p>
  {nendai_svg(nendai)}
  <details><summary>データ表を開く</summary>
    <div class="tblwrap"><table>
      <tr><th>建築年代</th><th>施設数</th><th>延べ床面積</th></tr>
      {nendai_rows}
    </table></div>
  </details>
</div>

<h2>裏付け表</h2>
<ul>
  <li><a href="kouku.html">{DISTRICT_LABEL}別に見る</a></li>
  <li><a href="shisetsu.html">全施設の一覧</a> — 実名・築年数・支出・利用者数（絞り込み可）</li>
</ul>

<h2>出典と方法</h2>
<p class="src">
  30年収支試算・費用内訳・削減目標 —
  {h['source_plan_name']} p.{h['source_page_gap']}。{h['test_range_note']}。
  現在の年間実績支出（約{h['annual_actual']}億円）は同計画 p.{h['source_page_annual']}。
  削減目標 p.{h['source_page_target']}。<br>
  すべての取得ファイルのURL・取得日時・ハッシュ値、および集計スクリプトは
  <a href="{GITHUB_REPO_URL}">公開リポジトリ</a>に掲載。
  数字の誤りを見つけた方はリポジトリのIssueでお知らせください。確認のうえ訂正します。
</p>
"""
    (SITE / "index.html").write_text(
        page(f"{CITY_NAME}の公共施設 これから30年のお金の地図", body,
             f"{CITY_NAME}の公式資料から: 公共施設の維持・更新は30年で約{h['shortfall']:,}億円不足。"
             f"市は延べ床面積{h['reduction_target_pct']}%程度削減を目標に。"),
        encoding="utf-8")
    print("wrote index.html")


def build_kouku():
    rows = read_csv("derived_kouku_summary.csv")
    old_n_col = next(c for c in rows[0] if c.endswith("_施設数") and c != "施設数")
    old_m2_col = next(c for c in rows[0] if c.endswith("_延床m2"))
    old_pct_col = next(c for c in rows[0] if c.endswith("_%"))
    tr = "".join(
        f'<tr><td>{H.escape(r[DISTRICT_COL])}</td><td>{r["施設数"]}</td>'
        f'<td>{fmt(r["延床面積合計_m2"], "㎡")}</td>'
        f'<td>{r[old_n_col]}</td><td>{fmt(r[old_m2_col], "㎡")}</td>'
        f'<td>{r[old_pct_col] or "－"}%</td></tr>'
        for r in rows)
    body = f"""
<p class="nav"><a href="index.html">← お金の地図（トップ）</a></p>
<h1>{DISTRICT_LABEL}別に見る {H.escape(CITY_NAME)}の公共施設</h1>
<p class="sub">延べ床面積の大きい順。複合施設・全市共通施設も所在地の{DISTRICT_LABEL}に計上。</p>
<div class="card tblwrap">
<table>
<tr><th>{DISTRICT_LABEL}</th><th>施設数</th><th>延べ床面積</th>
<th>{old_n_col.split("_")[0]}以上</th><th>同 延べ床面積</th><th>同 面積比</th></tr>
{tr}
</table>
</div>
"""
    (SITE / "kouku.html").write_text(
        page(f"{DISTRICT_LABEL}別に見る {CITY_NAME}の公共施設", body), encoding="utf-8")
    print("wrote kouku.html")


def build_shisetsu():
    rows = read_csv("shisetsu_list.csv")
    spend_col = next((c for c in rows[0] if c.startswith("支出")), None)
    users_col = next((c for c in rows[0] if c.startswith("利用者数")), None)
    percap_col = next((c for c in rows[0] if c.startswith("市民1人")), None)
    tr = "".join(
        f'<tr><td>{H.escape(r["施設名"])}</td>'
        f'<td>{H.escape(r["施設分類_大分類"])}</td>'
        f'<td>{H.escape(r[DISTRICT_COL])}</td>'
        f'<td>{r["建築年度_最古棟"] or "－"}</td>'
        f'<td>{fmt(r["延べ床面積合計_m2"])}</td>'
        f'<td>{fmt(r.get(spend_col, ""))}</td>'
        f'<td>{fmt(r.get(users_col, ""))}</td>'
        f'<td>{fmt(r.get(percap_col, ""))}</td></tr>'
        for r in rows)
    body = f"""
<p class="nav"><a href="index.html">← お金の地図（トップ）</a></p>
<h1>{H.escape(CITY_NAME)}の公共施設 全{len(rows)}施設</h1>
<input type="search" id="q" placeholder="施設名・分類・{DISTRICT_LABEL}で絞り込み">
<div class="card tblwrap">
<table id="t">
<tr><th>施設名</th><th>分類</th><th>{DISTRICT_LABEL}</th><th>建築年度</th>
<th>延べ床面積(㎡)</th><th>支出(円)</th><th>利用者数(人)</th><th>市民1人あたり(円)</th></tr>
{tr}
</table>
</div>
<p class="src">詳細と出典ページは<a href="{GITHUB_REPO_URL}">リポジトリのCSV</a>を参照。</p>
<script>
  const q = document.getElementById("q"), rows = document.querySelectorAll("#t tr");
  q.addEventListener("input", () => {{
    const v = q.value.trim();
    rows.forEach((tr, i) => {{ if (i) tr.style.display = tr.textContent.includes(v) ? "" : "none"; }});
  }});
</script>
"""
    (SITE / "shisetsu.html").write_text(
        page(f"{CITY_NAME}の公共施設 全施設一覧", body), encoding="utf-8")
    print("wrote shisetsu.html")


if __name__ == "__main__":
    SITE.mkdir(exist_ok=True)
    build_index()
    build_kouku()
    build_shisetsu()
