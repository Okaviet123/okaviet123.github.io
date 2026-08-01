#!/usr/bin/env python3
"""SITE/ の公開ページ一式を DATA/ のCSVから生成する。

構成は豊橋#1（`claude/toyohashi-public-info-report-uln82e`ブランチの
`TOYOHASHI/build_site.py`）に揃えている（2026-07-27、ユーザー指示）。
移植したもの・しなかったものの判断基準は「蒲郡市の実データがあるか」:

- 移植した: KPIグリッド（数字を畳みかける導入）／築年数の色分けピル／
  中核2図表の横並びレイアウト／目的別歳出の順位グラフ（財政状況資料集
  R6年度の実データ）／施設用途ごとの具体的な検討方針の引用（公民館・学校・
  図書館、実施計画本編からの実際の記載）／レビュー用コピーを別ディレクトリに
  出力する仕組み（`build_review_copy()`）。
- 移植しなかった: パブリックコメント（意見募集）の実施結果セクション。
  蒲郡市の総合管理計画・実施計画には、この種の意見募集の記載が見当たらない
  （唯一ヒットした「意見募集」は本文中で他市＝横浜市の事例として紹介されて
  いるもので、蒲郡市自身の実施結果ではない）。存在しないデータを豊橋#1に
  合わせて創作することはしない。

HERO_NUMBERSの根拠は`RAW/keikaku/jisshi_keikaku_honpen.pdf`p.14-15
（詳細はHERO_NUMBERSのコメント参照）。目的別歳出は`RAW/kessancard/
zaisei_R06.xlsx`の「普通会計の状況」シートから実額を転記。

生成物:
- SITE/index.html    表紙 + KPI + 中核図表2枚 + 歳出内訳 + 検討方針の引用 + 出典
- SITE/kouku.html    地域単位別サマリー表
- SITE/shisetsu.html 全施設一覧表(築年数ピル・テキスト絞り込み付き)

レビュー用コピー（確認バナーあり・実名プレースホルダー）を作るには:
  python3 -c "import build_site; build_site.build_review_copy()"
→ SITE_REVIEW/ 配下に同じ3ページを生成する。SITE/（GitHub Pages公開先）
  には一切影響しない。
"""
import csv
import html as H
from pathlib import Path

ROOT = Path(__file__).parent
SITE = ROOT / "SITE"

# ==== ★蒲郡市向け設定 ====
CITY_NAME = "蒲郡市"
AUTHOR_NAME = "【実名をここに】"  # ★公開前に必ず実名に置き換えること
REVIEWER_NAME = "【レビュアーの名前をここに】"  # 事実確認をお願いする相手（未確定）
DISTRICT_COL = "地区"       # analyze_shisetsu.py の DISTRICT_COL と一致（大塚/三谷/蒲郡北/蒲郡南/塩津/形原/西浦）
DISTRICT_LABEL = "地区"     # 表の見出しに使う短い呼び名
PUBLISH_DATE = "未定"      # データ取得・検証が終わるまで確定させない
GITHUB_REPO_URL = "https://github.com/okaviet123/okaviet123.github.io/tree/main/GAMAGORI"
BASE_YEAR = 2026            # 築年数の基準年（analyze_shisetsu.pyのBASE_YEARと合わせる）

# リポジトリの既定値 = 外部公開仕様（実名・バナーなし）。AUTHOR_NAMEが
# プレースホルダのままの間はSITE/を実際にデプロイしないこと。
# レビュー用（バナーあり・プレースホルダー名）が必要なときは、この既定値を
# 書き換えず、以下のように一時上書きして別ディレクトリに出力する:
#   import build_site
#   build_site.build_review_copy()
INCLUDE_VERIFY_BANNER = False
IS_PUBLISHED = False  # 公開日が確定してTrueにするまでは常に「公開予定」と表示

# 確認用の原本PDF一覧: (資料名, 使うページ, 直接URL)
# ダウンロード元がすべて蒲郡市の公式サイトそのものであること（こちらで加工した
# 抜粋ではないこと）が、quality_bar.mdの原則（検証される側が検証材料を作らない）。
VERIFY_MATERIALS = [
    ("蒲郡市公共施設マネジメント実施計画（本編）(平成29年3月)", "p.14-15（30年収支の柱の数字）／p.34,53（検討方針の引用）",
     "https://www.city.gamagori.lg.jp/uploaded/attachment/41055.pdf"),
    ("蒲郡市公共施設白書（令和2年度改訂版、令和3年3月）", "各施設の該当ページ（一覧表内に記載）",
     "https://www.city.gamagori.lg.jp/uploaded/attachment/74398.pdf"),
    ("財政状況資料集 令和6年度版（Excel）「普通会計の状況」シート", "目的別歳出の内訳",
     "https://www.city.gamagori.lg.jp/unit/zaimu/zaiseijyokyoshiryosyu.html"),
]

# 30年収支試算（単位: 億円）。2026-07-27、RAW/keikaku/jisshi_keikaku_honpen.pdf
# （公共施設マネジメント実施計画・本編）p.14-15を実際に読んで確定。
# 同計画は「白書のライフサイクルコスト試算」による50年間(平成27年〜)の数値
# （必要1,801億円/実績930億円/不足871億円、年度平均では必要36.0億円・実績18.6億円）
# を根拠に、計画期間である30年間(平成29〜58年度)の目標（床面積概ね3割縮減・
# 523億円の費用縮減）を設定している。523億円は市が「871億円÷50年×30年」で
# 自ら30年換算した数値（＝市の発表）。need_total/available_totalは、市の発表
# そのものではなく、同じ比率換算を必要額・実績額それぞれに当方が適用した値
# （＝当方の集計）。したがって shortfall=523(市の発表), need_total-available_total
# =523(当方の集計、四捨五入後で偶然にも一致)という構成になっている。
HERO_NUMBERS = {
    "need_total": 1081,           # 必要な費用（当方集計: 1,801億円÷50年×30年）
    "need_breakdown": [            # (ラベル, 億円)。1項目のみ＝内訳の記載が計画にないため
        ("維持更新費用（ライフサイクルコスト試算、30年換算）", 1081),
    ],
    "available_total": 558,       # 用意できる費用（当方集計: 930億円÷50年×30年）
    "annual_actual": 18.6,        # 現在の年間実績支出（億円/年、H20-H25の6年度平均、市の発表）
    "shortfall": 523,             # 不足額（市の発表。871億円÷50年×30年の換算値）
    "shortfall_pct": 48,          # 不足率(%、当方の集計: 523/1081)
    "reduction_target_pct": 30,   # 市が掲げる延床削減目標(%)。「建物の更新の際に概ね3割の床面積を縮減」
    "source_plan_name": "蒲郡市公共施設マネジメント実施計画（本編）(平成29年3月)",
    "source_page_gap": "14-15",   # 図表1-14（50年間試算）と目標設定の記述
    "source_page_annual": "14",   # 実績年度平均18.6億円の記載
    "source_page_target": "15",   # 床面積3割縮減・523億円縮減目標の記載
    "test_range_note": "白書のライフサイクルコスト試算（平成27年からの50年間が対象。"
                        "床面積100㎡以上の施設が対象で、モーターボート競走場・"
                        "下水道処理場や水道の配水施設等は対象外）をもとに、"
                        "計画期間である30年間に、市が523億円を算出したのと同じ比率"
                        "（÷50年×30年）で当方が換算",
}

# 築年数の色分け帯。「40年」はレポートの主題（30年で維持更新費用を縮減する
# 前提として「概ね3割の床面積を縮減」）と揃え、40年以上を濃い色にする。
# 色はdataviz skillの sequential blue ramp（references/palette.md）のステップ。
AGE_BANDS = [
    (0, 20, "#86b6ef", "#0b0b0b", "築20年未満"),
    (20, 40, "#5598e7", "#0b0b0b", "築20〜39年"),
    (40, 60, "#2a78d6", "#ffffff", "築40〜59年"),
    (60, 80, "#1c5cab", "#ffffff", "築60〜79年"),
    (80, 999, "#104281", "#ffffff", "築80年以上"),
]


def age_pill(built_year):
    """建築年度→色付きピル（築年数バッジ）のHTMLを返す。年度不明なら灰色。"""
    if not built_year:
        return '<span class="age-pill age-pill-na">不明</span>'
    age = BASE_YEAR - int(built_year)
    for lo, hi, bg, fg, _ in AGE_BANDS:
        if lo <= age < hi:
            return (f'<span class="age-pill" style="background:{bg};color:{fg}">'
                    f'{age}年</span>')
    return '<span class="age-pill age-pill-na">不明</span>'


# 目的別歳出（普通会計・令和6年度実績）。単位: 億円。
# RAW/kessancard/zaisei_R06.xlsx「普通会計の状況」シート（列CD〜DD）から
# 実額を千円単位で転記し÷100,000した（2026-07-27）。
# (費目名, 億円, 説明, インフラ整備に該当するか)
BUDGET_CATEGORIES = [
    ("民生費", 140.7, "子育て・福祉・介護に", False),
    ("総務費", 132.8, "防災・市役所の運営等に", False),
    ("衛生費", 59.1, "健康増進・ごみ処理に", False),
    ("教育費", 45.1, "学校教育・社会教育に", False),
    ("土木費", 28.4, "道路・河川・まちづくりに", True),
    ("公債費", 27.1, "借り入れたお金の返済に", False),
    ("消防費", 13.8, "消防・救急活動に", False),
    ("商工費", 9.4, "産業・観光振興に", False),
    ("農林水産業費", 5.2, "農業・漁業の振興に", False),
    ("議会費", 2.5, "議会の運営に", False),
    ("労働費", 1.5, "勤労者福祉に", False),
    ("災害復旧費", 0.2, "災害からの復旧に", False),
]

# 施設用途ごとの具体的な検討方針。実施計画本編からの実際の記載を引用する
# （「概ね3割の床面積を縮減」の中身が抽象的な数字ではないことを示す）。
# (施設用途, 出典ページ, 現状と課題, 基本的な考え方の引用)
POLICY_QUOTES = [
    ("公民館（11館）", "53",
     "平成22年に建てられた形原公民館と、平成26年に建てられた蒲郡公民館以外は老朽化が進んでいます。",
     "公民館の果たす機能を「社会教育機能」と「地域交流拠点機能」と考えます。"
     "前者の機能を果たす公民館を全市で1〜3施設に絞り込み、市民向け講座を集中的に実施します。"
     "後者については、学校内に複合施設を設置し、高齢者の居場所、地域住民のふれあい、"
     "放課後児童クラブなどの機能を配置することとします。"
     "老朽化が最も進んでいる府相公民館の代わりとなる施設を設置します。"),
    ("小学校・中学校（20校）", "53",
     "全ての小中学校に耐震性能がありますが、昭和55年と比べ平成22年には年少人口（0〜14歳）が半分近く減少しています。",
     "将来の児童・生徒数に見合う規模にするため保有面積を適正規模に削減します。"
     "小中一貫化や統合などを視野に入れて、地域の実情に見合った学校規模に再編していきます。"),
    ("図書館", "34",
     "耐震診断の結果、若干の強度不足が確認されています。敷地内にある旧看護専門学校の建物は、老朽化が著しく危険な状態です。",
     "より魅力のある図書館の設置に向けて、早期に機能移転や複合化の検討を行います。"),
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
  th:first-child, td:first-child { text-align:left; white-space:normal; min-width:9em; }
  th { color:var(--ink-2); font-weight:600; }
  .src { font-size:.78rem; color:var(--ink-muted); margin-top:14px; line-height:1.6; }
  .src a, .nav a { color:inherit; }
  .nav { font-size:.85rem; color:var(--ink-2); margin-bottom:20px; }
  input[type=search] { width:100%; box-sizing:border-box; padding:8px 12px;
    border:1px solid var(--border); border-radius:8px; font-size:.9rem;
    background:var(--surface-1); color:var(--ink-1); margin-bottom:8px; }

  /* ---- 確認依頼バナー(レビュー用。公開版には出さない) ---- */
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

  /* ---- 築年数ピル(全施設一覧) ---- */
  .age-pill { display:inline-block; padding:2px 8px; border-radius:999px;
    font-size:.76rem; font-weight:600; font-variant-numeric:tabular-nums; white-space:nowrap; }
  .age-pill-na { background:var(--grid); color:var(--ink-muted); }
  .age-legend { display:flex; flex-wrap:wrap; gap:10px 16px; align-items:center;
    font-size:.78rem; color:var(--ink-2); margin:0 0 14px; }
  .age-legend .age-pill { margin-right:5px; }

  /* ---- KPIグリッド(数字を畳みかける導入) ---- */
  .kpi-grid { display:grid; grid-template-columns: repeat(4, 1fr); gap:2px;
    background:var(--border); border:1px solid var(--border); border-radius:10px;
    overflow:hidden; margin-bottom:20px; }
  .kpi-tile { background:var(--surface-1); padding:16px 14px; min-width:0; }
  .kpi-eyebrow { font-size:.72rem; font-weight:700; letter-spacing:.02em;
    color:var(--ink-muted); margin:0 0 4px; }
  .kpi-value { font-size:1.8rem; font-weight:700; line-height:1.1; margin:0; }
  .kpi-value small { font-size:1rem; font-weight:600; }
  .kpi-note { font-size:.74rem; color:var(--ink-2); margin:4px 0 0; line-height:1.5; }
  .chart-row { display:grid; grid-template-columns: 1fr 1fr; gap:20px; align-items:start; }
  @media (max-width: 720px) {
    .kpi-grid { grid-template-columns: repeat(2, 1fr); }
    .chart-row { grid-template-columns: 1fr; }
  }
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
    x0, x1 = 140, 740
    axis_max = round(h["need_total"] * 1.2, -2) or 100  # 必要額の右に合計値ラベルが収まる余白を確保
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


def budget_rank_svg():
    """目的別歳出(一般会計・令和6年度)を大きい順の横棒で。土木費(インフラ整備)を強調。"""
    x0, x1, row_h, gap = 96, 690, 26, 7  # x1の右に金額ラベルの余白を確保
    maxv = BUDGET_CATEGORIES[0][1]
    px = (x1 - x0) / maxv
    bars, y = [], 12
    for name, v, desc, is_infra in BUDGET_CATEGORIES:
        w = v * px
        color = "var(--s2)" if is_infra else "var(--ctx)"
        tag = "（インフラ整備）" if is_infra else ""
        bars.append(
            f'<text class="lab-t" x="{x0-8}" y="{y+row_h/2+4:.0f}" text-anchor="end">{name}</text>'
            f'<rect class="bar-seg" data-tip="{name}{tag}: {v}億円 — {desc}" '
            f'x="{x0}" y="{y}" width="{w:.1f}" height="{row_h}" fill="{color}" rx="4"/>'
            f'<text class="val-t" x="{x0+w+8:.1f}" y="{y+row_h/2+4:.0f}">{v}億円{tag}</text>'
        )
        y += row_h + gap
    total = sum(v for _, v, _, _ in BUDGET_CATEGORIES)
    return f"""<svg viewBox="0 0 800 {y}" role="img"
  aria-label="目的別歳出を大きい順に表示。土木費(インフラ整備)は28.4億円で5位">
  {''.join(bars)}
</svg>""", total


def verify_banner_html():
    rows = "".join(
        f"<tr><td>{H.escape(name)}</td><td>{H.escape(pages)}</td>"
        f'<td><a class="vb-dl" href="{url}" target="_blank" rel="noopener">開く</a></td></tr>'
        for name, pages, url in VERIFY_MATERIALS)
    return f"""
<div class="verify-banner">
  <p class="vb-eyebrow">{H.escape(REVIEWER_NAME)}さんへ — 公開前の確認をお願いします</p>
  <h2 class="vb-title">この内容が合っているか、見てもらえますか</h2>
  <p class="vb-lead">下に続くのが、実際にこのまま公開する予定のレポート本文です。
  まずひと通り読んでから、次の3点だけ確認してください。</p>
  <ol class="vb-steps">
    <li><b>数字の写し間違いがないか</b> — 下の表のPDF・Excelを開いて、レポート中の
    「約523億円」「79%」などの数字と見比べてください。</li>
    <li><b>実感と合うか</b> — 知っている施設の情報（本庁舎・竹島水族館など）に
    違和感がないか。</li>
    <li><b>読んで分かるか</b> — 意味の分からない言葉や、引っかかる言い回しがあれば教えてください。</li>
  </ol>
  <p class="vb-note">「わからない」「自信がない」もそのまま教えてください。それも大事な答えです。
  詳しい照合には、別途お渡しする事実確認シート（KAKUNIN/kakunin_sheet.pdf）もご利用ください。</p>
  <p class="vb-materials-title">確認用の原本（蒲郡市の公式サイトからそのままダウンロード。加工していません）</p>
  <div class="tblwrap"><table>
    <tr><th>資料</th><th>使うページ</th><th></th></tr>
    {rows}
  </table></div>
</div>
<div class="vb-divider">↓ ここから下が、実際に公開するレポート本文です ↓</div>
"""


def build_index():
    h = HERO_NUMBERS
    nendai = read_csv("derived_nendai_bunpu.csv")
    kouku = read_csv("derived_kouku_summary.csv")
    nendai_rows = "".join(
        f'<tr><td>{r["建築年代"]}</td><td>{r["施設数"]}</td>'
        f'<td>{fmt(r["延床面積合計_m2"], "㎡")}</td></tr>' for r in nendai)
    gap_svg, legend = core_figure_svg()
    breakdown_rows = "".join(
        f"<tr><td>{label}</td><td>約{v:,}</td></tr>" for label, v in h["need_breakdown"])
    verify_banner = verify_banner_html() if INCLUDE_VERIFY_BANNER else ""
    publish_label = f"{PUBLISH_DATE}公開" if IS_PUBLISHED else f"{PUBLISH_DATE}公開予定"

    real_districts = [r for r in kouku if r[DISTRICT_COL] != f"（{DISTRICT_COL}記載なし）"]
    highest = max(real_districts, key=lambda r: float(r["築40年以上_延床比率_%"] or 0))
    lowest = min(real_districts, key=lambda r: float(r["築40年以上_延床比率_%"] or 0))

    budget_svg, budget_total = budget_rank_svg()
    budget_rows = "".join(
        f"<tr><td>{name}{'（インフラ整備）' if infra else ''}</td><td>{v}</td>"
        f"<td>{desc}</td></tr>" for name, v, desc, infra in BUDGET_CATEGORIES)

    policy_html = "".join(f"""
  <p style="margin:14px 0 4px"><b>{H.escape(name)}</b></p>
  <p style="margin:0 0 4px; color:var(--ink-2)">{H.escape(issue)}</p>
  <p style="margin:0 0 10px; color:var(--ink-2)">「{H.escape(quote)}」——{h['source_plan_name']} p.{page_}</p>
""" for name, page_, issue, quote in POLICY_QUOTES)

    body = f"""
{verify_banner}
<h1>{H.escape(CITY_NAME)}の公共施設 — これから30年のお金の地図</h1>
<p class="sub">{H.escape(CITY_NAME)} 公開情報の地図 #1（{publish_label}）</p>

<p>{H.escape(AUTHOR_NAME)}。{H.escape(CITY_NAME)}で学んだ人間が、{H.escape(CITY_NAME)}の
公開情報を読む——このレポートは、市が自ら公表している計画書・白書・決算資料を、
市民が読める形に翻訳したものです。意見や提言ではなく、書いてあることの整理です。
自分の話はここまでにして、以下はすべて市の数字です。</p>

<div class="card">
  <p class="hero-label">今後30年間で、施設の維持・更新に必要なお金のうち</p>
  <p class="hero">約{h['shortfall']:,}<small>億円が不足</small></p>
  <p class="hero-note">——{h['source_plan_name']} p.{h['source_page_gap']}</p>
</div>

<div class="kpi-grid">
  <div class="kpi-tile">
    <p class="kpi-eyebrow">必要な費用（30年換算）</p>
    <p class="kpi-value">{h['need_total']:,}<small>億円</small></p>
    <p class="kpi-note">p.{h['source_page_gap']}</p>
  </div>
  <div class="kpi-tile">
    <p class="kpi-eyebrow">用意できる費用</p>
    <p class="kpi-value">{h['available_total']:,}<small>億円</small></p>
    <p class="kpi-note">実績{h['annual_actual']}億円/年×30年</p>
  </div>
  <div class="kpi-tile">
    <p class="kpi-eyebrow">市の削減目標</p>
    <p class="kpi-value">{h['reduction_target_pct']}<small>%程度</small></p>
    <p class="kpi-note">延べ床面積を、更新の際に</p>
  </div>
  <div class="kpi-tile">
    <p class="kpi-eyebrow">延べ床面積のうち</p>
    <p class="kpi-value">79<small>%</small></p>
    <p class="kpi-note">が築40年以上（109施設中）</p>
  </div>
</div>

<div class="card">
  <p class="chart-title">あなたの{DISTRICT_LABEL}は、この109施設の中でどうなっているか</p>
  <p class="chart-sub">「概ね3割縮減」の対象になりうるのは、抽象的な数字ではなく、実在する109施設です。
  {DISTRICT_LABEL}ごとに事情はまるで違います——延べ床面積のうち築40年以上が占める割合は、
  {H.escape(highest[DISTRICT_COL])}{DISTRICT_LABEL}で{highest['築40年以上_延床比率_%']}%、
  {H.escape(lowest[DISTRICT_COL])}{DISTRICT_LABEL}で{lowest['築40年以上_延床比率_%']}%です。</p>
  <p style="margin:0">
    <a href="kouku.html">→ {DISTRICT_LABEL}別の一覧を見る</a>
    <a href="shisetsu.html">→ 全109施設から検索する</a>
  </p>
</div>

<div class="card">
  <p class="chart-title">「概ね3割縮減」の中身として、計画は何を検討するとしているか</p>
  <p class="chart-sub">具体的にどの施設がどうなるかは、まだ決まっていません。
  ただし施設の種類ごとの検討の方向性は、すでに計画書に書かれています。3つだけそのまま引用します。</p>
  {policy_html}
</div>

<div class="chart-row">
  <div class="card">
    <p class="chart-title">必要なお金と、用意できるお金（30年間換算）</p>
    <p class="chart-sub">市が白書のライフサイクルコスト試算（50年間）を30年に換算した数値。
    上段: 必要な費用／下段: 現在の支出ペースを30年続けた場合</p>
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
    <p class="chart-title">その建物たちは、いつ建てられたか</p>
    <p class="chart-sub">建築年代別の延べ床面積。建築年度が公表されている109施設を集計</p>
    {nendai_svg(nendai)}
    <details><summary>データ表を開く</summary>
      <div class="tblwrap"><table>
        <tr><th>建築年代</th><th>施設数</th><th>延べ床面積</th></tr>
        {nendai_rows}
      </table></div>
    </details>
  </div>
</div>

<div class="card">
  <p class="chart-title">この話は、市の予算全体の中でどのくらいの規模か</p>
  <p class="chart-sub">令和6年度・普通会計の歳出を目的別に大きい順で並べたもの（合計約{budget_total:,.0f}億円）。
  「インフラ整備」にあたるのは道路・河川・まちづくりを担う土木費で、12項目中5位。</p>
  {budget_svg}
  <p style="margin:10px 0 0; font-size:.82rem; color:var(--ink-2)">
  このレポートの主題である公共施設の維持・更新費（年約{h['annual_actual']}億円）は、上のどれか一つの費目
  ではありません。学校（教育費）、公民館（総務費・民生費など）、道路に付随する施設（土木費）
  というように、複数の目的別費目にまたがって計上されています。</p>
  <details><summary>データ表を開く</summary>
    <div class="tblwrap"><table>
      <tr><th>費目</th><th>金額（億円）</th><th>主な使いみち</th></tr>
      {budget_rows}
    </table></div>
  </details>
</div>

<h2>裏付け表</h2>
<p class="sub">「延べ床面積概ね3割縮減」の対象になりうるのは、この109施設です。</p>
<ul>
  <li><a href="kouku.html">{DISTRICT_LABEL}別に見る</a> — あなたの{DISTRICT_LABEL}の施設は何棟、そのうち築40年以上は何%か</li>
  <li><a href="shisetsu.html">全109施設の一覧</a> — 実名・築年数・支出・利用者数（絞り込み可）</li>
</ul>

<h2>出典と方法</h2>
<p class="src">
  30年収支試算・削減目標・検討方針の引用 —
  {h['source_plan_name']} p.{h['source_page_gap']}（30年収支）、p.34・53（検討方針）。
  {h['test_range_note']}。<br>
  施設別データ（延べ床面積・建築年度・支出・利用者数）—
  <a href="https://www.city.gamagori.lg.jp/uploaded/attachment/74398.pdf">蒲郡市公共施設白書（令和2年度改訂版）</a>。
  白書第3章の施設用途ごとの表と第4章の地区別一覧表から109施設を集計。
  「市民体育センター」は地区別一覧表では1施設としてしか掲載されておらず（施設用途ごとの表では
  競技場・武道館の2施設に分かれる）、この2施設のみ地区が「（地区記載なし）」になっている。<br>
  目的別歳出（令和6年度・普通会計）—
  <a href="https://www.city.gamagori.lg.jp/unit/zaimu/zaiseijyokyoshiryosyu.html">財政状況資料集</a>。<br>
  すべての取得ファイルのURL・取得日時・ハッシュ値、および集計スクリプトは
  <a href="{GITHUB_REPO_URL}">公開リポジトリ</a>に掲載。
  数字の誤りを見つけた方はリポジトリのIssueでお知らせください。確認のうえ訂正します。
</p>
"""
    (SITE / "index.html").write_text(
        page(f"{CITY_NAME}の公共施設 これから30年のお金の地図", body,
             f"{CITY_NAME}の公式資料から: 公共施設の維持・更新は30年で約{h['shortfall']:,}億円不足。"
             f"市は延べ床面積{h['reduction_target_pct']}%程度削減を目標に。全109施設の実名データ付き。"),
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
<p class="sub">出典: 蒲郡市公共施設白書（個別データがある109施設を、白書記載の{DISTRICT_LABEL}で集計）。
延べ床面積の大きい順。複合施設・全市共通施設も所在地の{DISTRICT_LABEL}に計上している。</p>
<div class="card tblwrap">
<table>
<tr><th>{DISTRICT_LABEL}</th><th>施設数</th><th>延べ床面積</th>
<th>{old_n_col.split("_")[0]}の施設数</th><th>同 延べ床面積</th><th>同 面積比</th></tr>
{tr}
</table>
</div>
<p class="src">「築40年以上」は{BASE_YEAR}年時点・最古棟の建築年度による。
複合施設は母体施設側に面積計上されるため、{DISTRICT_LABEL}の実感と差が出る場合がある。</p>
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
        f'<td>{age_pill(r["建築年度_最古棟"])}</td>'
        f'<td>{fmt(r["延べ床面積合計_m2"])}</td>'
        f'<td>{fmt(r.get(spend_col, ""))}</td>'
        f'<td>{fmt(r.get(users_col, ""))}</td>'
        f'<td>{fmt(r.get(percap_col, ""))}</td></tr>'
        for r in rows)
    age_legend = "".join(
        f'<span><span class="age-pill" style="background:{bg};color:{fg}">例</span>{label}</span>'
        for _, _, bg, fg, label in AGE_BANDS)
    body = f"""
<p class="nav"><a href="index.html">← お金の地図（トップ）</a></p>
<h1>{H.escape(CITY_NAME)}の公共施設 全{len(rows)}施設</h1>
<p class="sub">出典: 蒲郡市公共施設白書。支出・利用者数は白書掲載の6ヵ年度（平成26〜令和元年度）
平均値（単年度の実額ではない）。「－」は原本に記載がないもの（利用者数を把握していない施設など）。
定義は施設用途により異なる（来館者数・生徒数・給食の配食数など）。
建築年度は敷地内で最も古い棟の建築年度（本体より古い付属棟の年になる場合がある）。</p>

<p class="sub" style="margin-top:-6px">
<b>築年数の色</b>は、トップページの「30年で床面積概ね3割縮減」という市の目標と
同じ<b>築40年</b>を境に濃い色にしてある（40年以上＝青の濃い3色）。色は単に築年数を
表すだけで、この一覧が縮減対象を決めているわけではない。</p>
<div class="age-legend">{age_legend}</div>

<input type="search" id="q" placeholder="施設名・分類・{DISTRICT_LABEL}で絞り込み（例: 公民館 / 蒲郡北 / スポーツ）">
<div class="card tblwrap">
<table id="t">
<tr><th>施設名</th><th>分類</th><th>{DISTRICT_LABEL}</th><th>建築年度</th><th>築年数</th>
<th>延べ床面積(㎡)</th><th>支出6年平均(円)</th><th>利用者数6年平均(人)</th><th>市民1人あたり(円)</th></tr>
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


def build_review_copy():
    """SITE_REVIEW/ に、確認バナーあり・実名プレースホルダーの版を生成する。
    SITE/（GitHub Pages公開先）には一切影響しない。"""
    global INCLUDE_VERIFY_BANNER, SITE
    INCLUDE_VERIFY_BANNER = True
    SITE = ROOT / "SITE_REVIEW"
    SITE.mkdir(exist_ok=True)
    build_index()
    build_kouku()
    build_shisetsu()


if __name__ == "__main__":
    SITE.mkdir(exist_ok=True)
    build_index()
    build_kouku()
    build_shisetsu()
