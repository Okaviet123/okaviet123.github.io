#!/usr/bin/env python3
"""SITE/ の公開ページ一式を DATA/ のCSVから生成する。

生成物:
- SITE/index.html    表紙 + 中核図表(30年収支ギャップ・築年代分布) + 出典
- SITE/kouku.html    校区別サマリー表(52校区)
- SITE/shisetsu.html 全416施設の一覧表(テキスト絞り込み付き)
"""
import csv
import html as H
from pathlib import Path

ROOT = Path(__file__).parent
SITE = ROOT / "SITE"

AUTHOR_NAME = "【実名をここに】"  # 公開前に必ず差し替えること
REVIEWER_NAME = "かなこ"  # 事実確認をお願いする相手
INCLUDE_VERIFY_BANNER = True  # 8/10の本公開直前にFalseにして、確認バナーなしの版を作る

# 確認用の原本PDF一覧: (資料名, 使うページ, 直接URL)
# ダウンロード元がすべて豊橋市の公式サイトそのものであること(こちらで加工した
# 抜粋ではないこと)が、quality_bar.mdの原則(検証される側が検証材料を作らない)。
VERIFY_MATERIALS = [
    ("豊橋市公共施設等総合管理計画2026-2055（令和8年3月）", "p.52-53（主要な数字）／p.34（108.9億円）",
     "https://www.city.toyohashi.lg.jp/secure/122819/koukyousisetutousougoukannrikeikaku2026-2055.pdf"),
    ("公共施設白書2025 個別票「行政系施設」", "p.1-2（市役所）",
     "https://www.city.toyohashi.lg.jp/secure/117134/kobetuhyougyouseikeisisetu.pdf"),
    ("公共施設白書2025 個別票「スポーツ系施設」", "p.1-2（総合体育館）",
     "https://www.city.toyohashi.lg.jp/secure/117134/kobetuhyousupo-tusisetu.pdf"),
    ("公共施設白書2025 個別票「その他施設」", "p.1-2（競輪場）",
     "https://www.city.toyohashi.lg.jp/secure/117134/kobetuhyousonotasisetu.pdf"),
    ("公共施設白書2025 個別票「文化・社会教育系施設」", "p.149-150／159-160／167-168（アイプラザ・図書館・動植物公園）",
     "https://www.city.toyohashi.lg.jp/secure/117134/kobetuhyoubunnkashakaikyouikukeisisetu.pdf"),
    ("公共施設白書2025 個別票「子育て系施設」", "p.47-48（こども未来館）",
     "https://www.city.toyohashi.lg.jp/secure/117134/kobetuhyoukosodatesisetu.pdf"),
]

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

  /* ---- 確認依頼バナー(かなこさん向け・公開前レビュー用。公開時はremove_verify_banner()で除去) ---- */
  .verify-banner { background:var(--surface-1); border:1.5px solid var(--s2);
    border-radius:12px; padding:22px 24px; margin-bottom:8px; }
  .vb-eyebrow { font-size:.78rem; font-weight:700; letter-spacing:.03em; color:var(--s2);
    text-transform:uppercase; margin:0 0 6px; }
  .vb-title { font-size:1.2rem; margin:0 0 10px; }
  .vb-lead { font-size:.9rem; color:var(--ink-2); margin:0 0 14px; }
  .vb-steps { margin:0 0 12px; padding-left:1.3em; font-size:.88rem; }
  .vb-steps li { margin-bottom:6px; }
  .vb-note { font-size:.82rem; color:var(--ink-muted); margin:0 0 18px; }
  .vb-materials-title { font-size:.85rem; font-weight:600; margin:0 0 8px; }
  .verify-banner table { font-size:.82rem; }
  .verify-banner th:last-child, .verify-banner td:last-child { text-align:right; white-space:nowrap; }
  .vb-dl { display:inline-block; background:var(--s2); color:#fff; text-decoration:none;
    padding:5px 12px; border-radius:6px; font-size:.78rem; font-weight:600; }
  .vb-dl:hover { opacity:.88; }
  .vb-divider { text-align:center; font-size:.8rem; color:var(--ink-muted);
    margin:22px 0 28px; position:relative; }
  .vb-divider::before, .vb-divider::after { content:""; display:block; height:1px;
    background:var(--grid); margin:10px 0; }
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
    """30年収支ギャップの横バー。値→座標はここで計算する。"""
    x0, x1 = 140, 780  # 0〜4600億円
    px = (x1 - x0) / 4600.0
    segs = [("更新等（建て替え）", 1551, "var(--s1)"),
            ("改修（大規模修繕）", 2000, "var(--s2)"),
            ("維持管理・修繕", 841, "var(--s3)")]
    parts, x = [], x0
    for i, (label, v, color) in enumerate(segs):
        w = v * px - (2 if i < len(segs) - 1 else 0)
        rx = ' rx="4"' if i == len(segs) - 1 else ""
        parts.append(f'<rect class="bar-seg" data-tip="{label}: 約{v:,}億円" '
                     f'x="{x:.1f}" y="48" width="{w:.1f}" height="28" fill="{color}"{rx}/>')
        parts.append(f'<text class="seg-t" x="{x + v*px/2:.0f}" y="66" '
                     f'text-anchor="middle">{v:,}</text>')
        x += v * px
    need_end = x0 + 4392 * px
    avail_end = x0 + 3268 * px
    gridx = [(x0 + v * px, f"{v:,}" + ("億円" if v == 4000 else ""))
             for v in (0, 1000, 2000, 3000, 4000)]
    grid = "".join(f'<line x1="{gx:.0f}" y1="30" x2="{gx:.0f}" y2="168"/>'
                   for gx, _ in gridx[1:])
    ticks = "".join(f'<text x="{gx:.0f}" y="182" text-anchor="middle">{t}</text>'
                    for gx, t in gridx)
    return f"""<svg viewBox="0 0 800 190" role="img"
  aria-label="必要4392億円に対し用意できるのは3268億円で1124億円不足">
  <g class="axis-t">{ticks}</g>
  <g stroke="var(--grid)" stroke-width="1">{grid}</g>
  <line x1="{x0}" y1="30" x2="{x0}" y2="168" stroke="var(--baseline)" stroke-width="1"/>
  <text class="lab-t" x="{x0-8}" y="66" text-anchor="end">必要な費用</text>
  {''.join(parts)}
  <text class="val-t" x="{need_end+8:.0f}" y="66">4,392</text>
  <text class="lab-t" x="{x0-8}" y="128" text-anchor="end">用意できる</text>
  <rect class="bar-seg" data-tip="2024年度実績 約108.9億円/年 × 30年 → 約3,268億円（計画の試算値）"
    x="{x0}" y="110" width="{avail_end-x0:.1f}" height="28" fill="var(--ctx)" rx="4"/>
  <text class="val-t" x="{avail_end+8:.0f}" y="128">3,268</text>
  <g stroke="var(--ink-2)" fill="none" stroke-width="1.2">
    <line x1="{avail_end:.1f}" y1="88" x2="{avail_end:.1f}" y2="98"/>
    <line x1="{need_end:.1f}" y1="88" x2="{need_end:.1f}" y2="98"/>
    <line x1="{avail_end:.1f}" y1="93" x2="{need_end:.1f}" y2="93"/>
  </g>
  <text class="lab-t" x="{(avail_end+need_end)/2:.0f}" y="106" text-anchor="middle"
    style="font-weight:600">不足 約1,124億円</text>
  <line x1="{avail_end:.1f}" y1="30" x2="{avail_end:.1f}" y2="168"
    stroke="var(--ink-2)" stroke-width="1" stroke-dasharray="3 3"/>
</svg>"""


def nendai_svg(nendai):
    """建築年代別延床の縦棒。DATA/derived_nendai_bunpu.csv から生成。"""
    top, bottom, ymax = 26, 209, 450000.0
    h = bottom - top
    cols, labels, peak = [], [], max(nendai, key=lambda r: float(r["延床面積合計_m2"]))
    for i, r in enumerate(nendai):
        m2 = float(r["延床面積合計_m2"])
        bh = m2 / ymax * h
        x = 74 + i * 72
        rx = 4 if bh > 4 else 1
        cols.append(f'<rect class="col" data-tip="{r["建築年代"]}: {r["施設数"]}施設 / '
                    f'{m2/10000:.1f}万㎡" x="{x}" y="{bottom-bh:.1f}" width="44" '
                    f'height="{bh:.1f}" rx="{rx}"/>')
        dec = r["建築年代"].replace("年代", "")
        lab = "1930s" if dec == "1930" else ("2000s" if dec == "2000" else dec[-2:] + "s")
        labels.append(f'<text x="{x+22}" y="226" text-anchor="middle">{lab}</text>')
        if r is peak:
            peak_tag = (f'<text class="val-t" x="{x+22}" y="{bottom-bh-7:.0f}" '
                        f'text-anchor="middle">{m2/10000:.1f}万㎡</text>')
    return f"""<svg viewBox="0 0 800 240" role="img"
  aria-label="建築年代別延床面積。1970年代が最大">
  <g stroke="var(--grid)" stroke-width="1">
    <line x1="60" y1="26" x2="780" y2="26"/><line x1="60" y1="87" x2="780" y2="87"/>
    <line x1="60" y1="148" x2="780" y2="148"/>
  </g>
  <g class="axis-t">
    <text x="54" y="30" text-anchor="end">45万㎡</text>
    <text x="54" y="91" text-anchor="end">30万㎡</text>
    <text x="54" y="152" text-anchor="end">15万㎡</text>
  </g>
  <line x1="60" y1="209" x2="780" y2="209" stroke="var(--baseline)" stroke-width="1"/>
  <g fill="var(--s1)">{''.join(cols)}</g>
  {peak_tag}
  <g class="axis-t">{''.join(labels)}</g>
</svg>"""


def verify_banner_html():
    rows = "".join(
        f"<tr><td>{H.escape(name)}</td><td>{H.escape(pages)}</td>"
        f'<td><a class="vb-dl" href="{url}" target="_blank" rel="noopener">PDFを開く</a></td></tr>'
        for name, pages, url in VERIFY_MATERIALS)
    return f"""
<div class="verify-banner">
  <p class="vb-eyebrow">{H.escape(REVIEWER_NAME)}さんへ — 公開前の確認をお願いします</p>
  <h2 class="vb-title">この内容が合っているか、見てもらえますか</h2>
  <p class="vb-lead">下に続くのが、実際にこのまま公開する予定のレポート本文です。
  まずひと通り読んでから、次の3点だけ確認してください。</p>
  <ol class="vb-steps">
    <li><b>数字の写し間違いがないか</b> — 下の表のPDFを開いて、レポート中の
    「約1,124億円」「66%」などの数字と見比べてください。</li>
    <li><b>実感と合うか</b> — 知っている施設の情報（市役所・総合体育館など）に
    違和感がないか。</li>
    <li><b>読んで分かるか</b> — 意味の分からない言葉や、引っかかる言い回しがあれば教えてください。</li>
  </ol>
  <p class="vb-note">「わからない」「自信がない」もそのまま教えてください。それも大事な答えです。</p>
  <p class="vb-materials-title">確認用の原本PDF（豊橋市の公式サイトからそのままダウンロード。加工していません）</p>
  <div class="tblwrap"><table>
    <tr><th>資料</th><th>使うページ</th><th></th></tr>
    {rows}
  </table></div>
</div>
<div class="vb-divider">↓ ここから下が、実際に公開するレポート本文です ↓</div>
"""


def build_index():
    nendai = read_csv("derived_nendai_bunpu.csv")
    nendai_rows = "".join(
        f'<tr><td>{r["建築年代"]}</td><td>{r["施設数"]}</td>'
        f'<td>{fmt(r["延床面積合計_m2"], "㎡")}</td></tr>' for r in nendai)
    verify_banner = verify_banner_html() if INCLUDE_VERIFY_BANNER else ""
    body = f"""
{verify_banner}
<h1>豊橋市の公共施設 — これから30年のお金の地図</h1>
<p class="sub">豊橋市 公開情報の地図 #1（2026年8月10日公開）</p>

<p>{H.escape(AUTHOR_NAME)}。豊橋で学んだ人間が、豊橋の公開情報を読む——
このレポートは、市が自ら公表している計画書・白書・決算資料を、
市民が読める形に翻訳したものです。意見や提言ではなく、
書いてあることの整理です。自分の話はここまでにして、以下はすべて市の数字です。</p>

<div class="card">
  <p class="hero-label">今後30年間で、施設の維持・更新に必要なお金のうち</p>
  <p class="hero">約1,124<small>億円が不足</small></p>
  <p class="hero-note">必要額 約4,392億円に対し、用意できる見込みは約3,268億円（約26%不足）。
  市の結論は「施設の延べ床面積を30年間で20%程度削減する」。
  ——豊橋市公共施設等総合管理計画2026-2055（令和8年3月）p.52-53</p>
</div>

<div class="card">
  <p class="chart-title">あなたの校区は、この416施設の中でどうなっているか</p>
  <p class="chart-sub">「20%削減」の対象になりうるのは、抽象的な数字ではなく、実在する416施設です。
  校区ごとに事情はまるで違います——延べ床面積のうち築40年以上が占める割合は、
  八町校区で96.4%、吉田方校区で8.9%です。</p>
  <p style="margin:0 0 4px">市役所（八町校区・1978年築）も、総合体育館（吉田方校区・1988年築）も、
  この416施設のうちの2つです。</p>
  <p style="margin:0">
    <a href="kouku.html">→ 校区別の一覧を見る</a>
    <a href="shisetsu.html">→ 全416施設から検索する</a>
  </p>
</div>

<div class="card">
  <p class="chart-title">必要なお金と、用意できるお金（30年間の累計・建物系施設）</p>
  <p class="chart-sub">上段: 維持・更新に必要な費用の内訳 ／
  下段: 現在の支出ペース（2024年度実績 約108.9億円/年）を30年続けた場合</p>
  {core_figure_svg()}
  <div class="legend">
    <span style="--sw: var(--s1)">更新等（建て替え）</span>
    <span style="--sw: var(--s2)">改修（大規模修繕）</span>
    <span style="--sw: var(--s3)">維持管理・修繕</span>
    <span style="--sw: var(--ctx)">用意できる費用</span>
  </div>
  <details><summary>データ表を開く</summary>
    <div class="tblwrap"><table>
      <tr><th>項目</th><th>金額（億円）</th></tr>
      <tr><td>更新等（建て替え）</td><td>約1,551</td></tr>
      <tr><td>改修（大規模修繕）</td><td>約2,000</td></tr>
      <tr><td>維持管理・修繕</td><td>約841</td></tr>
      <tr><td><b>必要な費用 計</b></td><td><b>約4,392</b></td></tr>
      <tr><td>用意できる費用（108.9億円/年×30年、計画の試算値）</td><td>約3,268</td></tr>
      <tr><td><b>不足</b></td><td><b>約1,124（約26%）</b></td></tr>
    </table></div>
  </details>
</div>

<div class="card">
  <p class="chart-title">その建物たちは、いつ建てられたか（建築年代別の延べ床面積）</p>
  <p class="chart-sub">全416施設のうち建築年度が公表されている390施設。
  1960〜70年代築（築47年以上）が全体の延べ床面積の半分を占める</p>
  {nendai_svg(nendai)}
  <details><summary>データ表を開く</summary>
    <div class="tblwrap"><table>
      <tr><th>建築年代</th><th>施設数</th><th>延べ床面積</th></tr>
      {nendai_rows}
    </table></div>
  </details>
</div>

<h2>裏付け表</h2>
<p class="sub">「延べ床面積20%削減」の対象になりうるのは、この416施設です。</p>
<ul>
  <li><a href="kouku.html">校区別に見る</a> — あなたの校区の施設は何棟、そのうち築40年以上は何%か</li>
  <li><a href="shisetsu.html">全416施設の一覧</a> — 実名・築年数・2024年度の支出・利用者数（絞り込み可）</li>
</ul>

<h2>出典と方法</h2>
<p class="src">
  30年収支試算・費用内訳・延べ床面積20%削減目標 —
  <a href="https://www.city.toyohashi.lg.jp/64295.htm">豊橋市公共施設等総合管理計画2026-2055</a>（令和8年3月）p.52-53。
  試算対象は建物系施設（インフラ系施設、上下水道局、市民病院を除く）。
  2024年度維持・更新費実績（約108.9億円）は同計画p.34。<br>
  施設別データ（延べ床面積・建築年度・収支・利用者数）—
  <a href="https://www.city.toyohashi.lg.jp/34019.htm">豊橋市公共施設白書2025</a> 個別票。
  白書の対象は公称417施設（軟式庭球場①・②が1枚の個別票にまとめられているため、
  個別票は416票。本サイトの「416施設」は個別票の数）。<br>
  すべての取得ファイルのURL・取得日時・ハッシュ値、および集計スクリプトは
  <a href="https://github.com/Okaviet123/okaviet123.github.io/tree/main/TOYOHASHI">公開リポジトリ</a>に掲載。
  数字の誤りを見つけた方はリポジトリのIssueでお知らせください。確認のうえ訂正します。
</p>
"""
    (SITE / "index.html").write_text(
        page("豊橋市の公共施設 これから30年のお金の地図", body,
             "豊橋市の公式資料から: 公共施設の維持・更新は30年で約1,124億円不足。"
             "市は延べ床面積20%程度削減を目標に。全416施設の実名データ付き。"),
        encoding="utf-8")
    print("wrote index.html")


def build_kouku():
    rows = read_csv("derived_kouku_summary.csv")
    tr = "".join(
        f'<tr><td>{H.escape(r["小学校区"])}</td><td>{r["施設数"]}</td>'
        f'<td>{fmt(r["延床面積合計_m2"], "㎡")}</td>'
        f'<td>{r["築40年以上_施設数"]}</td>'
        f'<td>{fmt(r["築40年以上_延床m2"], "㎡")}</td>'
        f'<td>{r["築40年以上_延床比率_%"] or "－"}%</td></tr>'
        for r in rows)
    body = f"""
<p class="nav"><a href="index.html">← お金の地図（トップ）</a></p>
<h1>校区別に見る 豊橋市の公共施設</h1>
<p class="sub">出典: 豊橋市公共施設白書2025 個別票（建築年度公表の390施設を、個別票記載の小学校区で集計）。
延べ床面積の大きい順。市営住宅・市役所など全市共通の施設も所在校区に計上している。</p>
<div class="card tblwrap">
<table>
<tr><th>小学校区</th><th>施設数</th><th>延べ床面積</th>
<th>築40年以上</th><th>同 延べ床面積</th><th>同 面積比</th></tr>
{tr}
</table>
</div>
<p class="src">「築40年以上」は2026年時点・最古棟の建築年度による。
複合施設は母体施設側に面積計上されるため、校区の実感と差が出る場合がある。</p>
"""
    (SITE / "kouku.html").write_text(
        page("校区別に見る 豊橋市の公共施設", body), encoding="utf-8")
    print("wrote kouku.html")


def build_shisetsu():
    rows = read_csv("shisetsu_list.csv")
    tr = "".join(
        f'<tr><td>{H.escape(r["施設名"])}</td>'
        f'<td>{H.escape(r["施設分類_大分類"])}</td>'
        f'<td>{H.escape(r["小学校区"])}</td>'
        f'<td>{r["建築年度_最古棟"] or "－"}</td>'
        f'<td>{fmt(r["延べ床面積合計_m2"])}</td>'
        f'<td>{fmt(r["支出2024_円"])}</td>'
        f'<td>{fmt(r["利用者数2024_人"])}</td>'
        f'<td>{fmt(r["市民1人当たりコスト2024_円"])}</td></tr>'
        for r in rows)
    body = f"""
<p class="nav"><a href="index.html">← お金の地図（トップ）</a></p>
<h1>豊橋市の公共施設 全{len(rows)}施設</h1>
<p class="sub">出典: 豊橋市公共施設白書2025 個別票。金額は2024（令和6）年度。
「－」は原本に記載がないもの（複合施設内の施設など）。
建築年度は敷地内で最も古い棟の建設年度（本体より古い付属棟の年になる場合がある。
例: 総合体育館の本体は1988年だが、敷地内ポンプ場の1987年を表示）。
市営住宅の支出は全住宅の合計が各施設に記載されているため、住宅間の比較には使えない。</p>
<input type="search" id="q" placeholder="施設名・分類・校区で絞り込み（例: 市民館 / 牛川 / スポーツ）">
<div class="card tblwrap">
<table id="t">
<tr><th>施設名</th><th>分類</th><th>校区</th><th>建築年度</th>
<th>延べ床面積(㎡)</th><th>支出(円)</th><th>利用者数(人)</th><th>市民1人あたり(円)</th></tr>
{tr}
</table>
</div>
<p class="src">利用者数の定義は施設により異なる（入館者・児童数・入居戸数など）。
詳細と出典ページは<a href="https://github.com/Okaviet123/okaviet123.github.io/tree/main/TOYOHASHI">リポジトリのCSV</a>を参照。</p>
<script>
  const q = document.getElementById("q"), rows = document.querySelectorAll("#t tr");
  q.addEventListener("input", () => {{
    const v = q.value.trim();
    rows.forEach((tr, i) => {{ if (i) tr.style.display = tr.textContent.includes(v) ? "" : "none"; }});
  }});
</script>
"""
    (SITE / "shisetsu.html").write_text(
        page("豊橋市の公共施設 全施設一覧", body), encoding="utf-8")
    print("wrote shisetsu.html")


if __name__ == "__main__":
    build_index()
    build_kouku()
    build_shisetsu()
