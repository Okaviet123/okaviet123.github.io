#!/usr/bin/env python3
"""日本地図の入口ページ(map/index.html)を MUNICIPALITIES.csv から生成する。

`SKILLS/muni-facility-report/references/publish_map.md`（フェーズ7）の
設計に基づく。新しい市を登録・公開するたびに実行すること。

やること:
1. MUNICIPALITIES.csv を読む。
2. 各行について、<ディレクトリ>/SITE/index.html が存在し、かつ
   状態列が「公開」の場合のみ、その SITE/ を report/<市町村コード>/ へ
   コピーする（両方の条件がそろわない限りリンクは張らない。存在しない
   URLへ飛ばさないことを優先する——ファイルの有無だけで自動公開判定は
   しない。状態列の明示的な変更をもって公開の意思表示とする）。
3. map/assets/japan-prefectures.svg を読み込み、
   都道府県コード→市町村一覧のJSONを組み立てる。
4. map/index.html を再生成する（テンプレートから）。手書き編集した
   場合は次回実行で上書きされる。

使い方: python3 map/build_map.py をリポジトリ直下から実行する。
"""
import csv
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).parent.parent
MAP_DIR = ROOT / "map"
CSV_PATH = ROOT / "MUNICIPALITIES.csv"
SVG_PATH = MAP_DIR / "assets" / "japan-prefectures.svg"
REPORT_DIR = ROOT / "report"


def load_registry():
    with CSV_PATH.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def publish_site(row):
    """条件がそろえば SITE/ を report/<code>/ にコピーし、公開URLを返す。
    条件がそろわなければ None（=地図上は「準備中」）。"""
    site_dir = ROOT / row["ディレクトリ"] / "SITE"
    index = site_dir / "index.html"
    code = row["市町村コード"]
    if row["状態"] != "公開" or not index.exists():
        return None
    dest = REPORT_DIR / code
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(site_dir, dest)
    return f"../report/{code}/"


def build_registry_json(rows):
    by_pref = {}
    for row in rows:
        # SVGの data-code はゼロ埋めなしの整数文字列（例: 北海道="1"）。
        # CSV側はどちらの表記（"01"でも"1"でも）でも受け付けられるよう正規化する。
        pref_code = str(int(row["都道府県コード"]))
        url = publish_site(row)
        by_pref.setdefault(pref_code, []).append({
            "code": row["市町村コード"],
            "name": row["市町村名"],
            "published": url is not None,
            "url": url,
        })
    return by_pref


CSS = """
  :root { color-scheme: light; }
  body {
    --surface-1:#fcfcfb; --page:#f9f9f7; --ink-1:#0b0b0b; --ink-2:#52514e;
    --ink-muted:#898781; --grid:#e1e0d9; --border:rgba(11,11,11,0.10);
    --accent:#2a78d6; --accent-fill:#bcd7f5; --idle-fill:#eeeeee;
    font-family: system-ui,-apple-system,"Segoe UI",sans-serif;
    background:var(--page); color:var(--ink-1);
    margin:0 auto; max-width:980px; padding:24px 16px 56px; line-height:1.75;
  }
  @media (prefers-color-scheme: dark) {
    :root:where(:not([data-theme="light"])) body {
      color-scheme:dark;
      --surface-1:#1a1a19; --page:#0d0d0d; --ink-1:#fff; --ink-2:#c3c2b7;
      --grid:#2c2c2a; --border:rgba(255,255,255,0.10);
      --accent:#3987e5; --accent-fill:#234872; --idle-fill:#242422;
    }
  }
  h1 { font-size:1.5rem; margin:4px 0 6px; }
  .sub { color:var(--ink-2); font-size:.92rem; margin:0 0 20px; }
  .layout { display:flex; gap:24px; flex-wrap:wrap; align-items:flex-start; }
  .map-card { flex:1 1 560px; background:var(--surface-1); border:1px solid var(--border);
    border-radius:12px; padding:16px; min-width:280px; }
  .panel { flex:1 1 260px; background:var(--surface-1); border:1px solid var(--border);
    border-radius:12px; padding:18px 20px; min-height:260px; }
  #mapwrap { width:100%; overflow:hidden; touch-action:manipulation; }
  #mapwrap svg { width:100%; height:auto; display:block; }
  .prefecture { cursor:pointer; transition: fill .15s; }
  .prefecture.has-report { fill:var(--accent-fill) !important; }
  .prefecture.idle { fill:var(--idle-fill) !important; }
  .prefecture:hover { fill:var(--accent) !important; }
  .map-controls { display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; }
  button.reset { font-size:.85rem; padding:6px 12px; border-radius:8px; border:1px solid var(--border);
    background:var(--page); color:var(--ink-1); cursor:pointer; }
  button.reset:disabled { opacity:.4; cursor:default; }
  .panel h2 { font-size:1.05rem; margin:0 0 4px; }
  .panel .pref-sub { color:var(--ink-muted); font-size:.82rem; margin:0 0 14px; }
  .city-list { list-style:none; margin:0; padding:0; }
  .city-list li { padding:10px 0; border-bottom:1px solid var(--grid); }
  .city-list a { color:var(--accent); text-decoration:none; font-weight:600; }
  .city-list a:hover { text-decoration:underline; }
  .status-pending { color:var(--ink-muted); font-size:.88rem; }
  .hint { color:var(--ink-muted); font-size:.88rem; }
  .src { font-size:.78rem; color:var(--ink-muted); margin-top:28px; line-height:1.6; }
  .src a { color:inherit; }
"""

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="日本地図から市町村をクリックして、公共施設・財政の公開情報レポートを読む">
<title>公開情報の地図 — 市町村から探す</title>
<style>{css}</style></head>
<body>
<h1>公共施設・財政の「公開情報の地図」</h1>
<p class="sub">市が自分で公表している資料だけを使った、市民向けの翻訳レポートシリーズ。
地図から自分の市町村を探してクリックしてください。まだレポートがない市町村も
クリックできます（今後の追加予定地として地図に含めています）。</p>

<div class="layout">
  <div class="map-card">
    <div class="map-controls">
      <span class="hint">都道府県をクリックすると拡大します</span>
      <button class="reset" id="resetBtn" disabled>全国に戻る</button>
    </div>
    <div id="mapwrap">{svg}</div>
  </div>
  <div class="panel" id="panel">
    <h2>都道府県を選んでください</h2>
    <p class="pref-sub">クリックすると、その都道府県内でレポートがある市町村が
    ここに表示されます。</p>
  </div>
</div>

<p class="src">
  地図データ: <a href="https://github.com/geolonia/japanese-prefectures">Geolonia の
  都道府県SVG地図</a>（<a href="https://ja.wikipedia.org/wiki/%E3%83%95%E3%82%A1%E3%82%A4%E3%83%AB:%E6%97%A5%E6%9C%AC%E5%9C%B0%E5%9B%B3.svg">Wikipedia「日本地図.svg」</a>ベース、GFDL）を使用。<br>
  各レポートの出典・取得方法は、それぞれのレポートページおよび
  <a href="https://github.com/okaviet123/okaviet123.github.io">リポジトリ</a>内の
  市町村ディレクトリに記載。
</p>

<script id="registry-data" type="application/json">{registry_json}</script>
<script>
(function() {{
  const registry = JSON.parse(document.getElementById("registry-data").textContent);
  const svg = document.querySelector("#mapwrap svg");
  const prefGroups = svg.querySelectorAll(".prefecture");
  const panel = document.getElementById("panel");
  const resetBtn = document.getElementById("resetBtn");
  const viewBox = svg.viewBox.baseVal;
  const natural = {{x: viewBox.x, y: viewBox.y, w: viewBox.width, h: viewBox.height}};

  prefGroups.forEach(function(g) {{
    const code = g.getAttribute("data-code");
    g.classList.add(registry[code] ? "has-report" : "idle");
    g.addEventListener("click", function() {{ selectPref(code, g); }});
  }});

  function prefName(g) {{
    const t = g.querySelector("title");
    return t ? t.textContent.split("/")[0].trim() : "この都道府県";
  }}

  // getBBox()は要素自身のtransform属性を含まない「ローカル座標系」を返すため、
  // 祖先グループの入れ子transform（この地図は3重）がある場合そのままではズレる。
  // getCTM()はHTML埋め込みSVGだと実装によりCSSピクセル系を返すことがあり
  // viewBoxのuser unit系とは食い違う（実測で確認済み: そのままviewBoxに
  // 使うと表示領域外に大きくズレる）。そのため、要素→画面ピクセル
  // （getScreenCTM）→SVGルートのuser unit系（svgRoot.getScreenCTM()の逆行列）
  // という経路で変換し、必ずSVGルート自身のviewBox unit系に正規化する。
  function bboxInRootSpace(el) {{
    const elToScreen = el.getScreenCTM();
    const rootToScreen = svg.getScreenCTM();
    const screenToRoot = rootToScreen.inverse();
    const bbox = el.getBBox();
    const corners = [
      [bbox.x, bbox.y], [bbox.x + bbox.width, bbox.y],
      [bbox.x, bbox.y + bbox.height], [bbox.x + bbox.width, bbox.y + bbox.height],
    ].map(function(p) {{
      const pt = svg.createSVGPoint();
      pt.x = p[0]; pt.y = p[1];
      const screenPt = pt.matrixTransform(elToScreen);
      return screenPt.matrixTransform(screenToRoot);
    }});
    const xs = corners.map(function(p) {{ return p.x; }});
    const ys = corners.map(function(p) {{ return p.y; }});
    const minX = Math.min.apply(null, xs), maxX = Math.max.apply(null, xs);
    const minY = Math.min.apply(null, ys), maxY = Math.max.apply(null, ys);
    return {{x: minX, y: minY, width: maxX - minX, height: maxY - minY}};
  }}

  // viewBoxはCSS transitionの対象外(属性でありCSSプロパティではない)なので、
  // requestAnimationFrameで手動補間してズームの動きを付ける。
  let zoomRaf = null;
  function animateViewBox(target, duration) {{
    const start = {{x: viewBox.x, y: viewBox.y, w: viewBox.width, h: viewBox.height}};
    const t0 = performance.now();
    if (zoomRaf) cancelAnimationFrame(zoomRaf);
    function ease(t) {{ return 1 - Math.pow(1 - t, 3); }}
    function step(now) {{
      const t = Math.min(1, (now - t0) / duration);
      const e = ease(t);
      const x = start.x + (target.x - start.x) * e;
      const y = start.y + (target.y - start.y) * e;
      const w = start.w + (target.w - start.w) * e;
      const h = start.h + (target.h - start.h) * e;
      svg.setAttribute("viewBox", x + " " + y + " " + w + " " + h);
      if (t < 1) zoomRaf = requestAnimationFrame(step);
    }}
    zoomRaf = requestAnimationFrame(step);
  }}

  function selectPref(code, g) {{
    const rootBox = bboxInRootSpace(g);
    const pad = Math.max(rootBox.width, rootBox.height) * 0.25;
    const x = rootBox.x - pad, y = rootBox.y - pad;
    const w = rootBox.width + pad * 2, h = rootBox.height + pad * 2;
    animateViewBox({{x: x, y: y, w: w, h: h}}, 450);
    resetBtn.disabled = false;

    const cities = (registry[code] || []).slice().sort(function(a, b) {{
      return (b.published - a.published) || a.code.localeCompare(b.code);
    }});
    let body = "<h2>" + prefName(g) + "</h2>";
    if (!cities.length) {{
      body += '<p class="pref-sub">この都道府県のレポートはまだありません。</p>';
    }} else {{
      body += '<ul class="city-list">' + cities.map(function(c) {{
        return c.published
          ? '<li><a href="' + c.url + '">' + c.name + '</a></li>'
          : '<li>' + c.name + ' <span class="status-pending">— 準備中</span></li>';
      }}).join("") + "</ul>";
    }}
    panel.innerHTML = body;
  }}

  resetBtn.addEventListener("click", function() {{
    animateViewBox({{x: natural.x, y: natural.y, w: natural.w, h: natural.h}}, 450);
    resetBtn.disabled = true;
    panel.innerHTML = "<h2>都道府県を選んでください</h2><p class=\\"pref-sub\\">" +
      "クリックすると、その都道府県内でレポートがある市町村がここに表示されます。</p>";
  }});
}})();
</script>
</body></html>"""


def main():
    rows = load_registry()
    registry_json = build_registry_json(rows)
    svg_markup = SVG_PATH.read_text(encoding="utf-8")
    # <svg ...> に直接 class を付けているので、ID衝突を避けるためそのままインライン展開する
    html = HTML_TEMPLATE.format(
        css=CSS, svg=svg_markup, registry_json=json.dumps(registry_json, ensure_ascii=False))
    (MAP_DIR / "index.html").write_text(html, encoding="utf-8")
    published = sum(1 for cities in registry_json.values() for c in cities if c["published"])
    pending = sum(1 for cities in registry_json.values() for c in cities if not c["published"])
    print(f"wrote map/index.html ({published}件公開 / {pending}件準備中)")


if __name__ == "__main__":
    main()
