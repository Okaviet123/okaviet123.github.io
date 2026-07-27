#!/usr/bin/env python3
"""事実確認シート（印刷用A4）を生成するテンプレート。
豊橋#1で「改訂2版」まで作り直した設計を反映済み——最初から以下を守ること:

1. 検証対象を作った本人（Claude）が検証材料も加工して用意しない。
   市の原本PDFをそのまま資料記号(A,B,C...)で指定する。抜粋PDFを
   こちらで組んで渡す方式は不信感を生むので避ける
   （references/quality_bar.md 参照）。
2. 「当方の集計」は計算過程を開示し、全件見直しではなく数件の
   サンプル照合で検証できる形にする。

使い方: 下の CONFIG を市の実データで埋めてから実行する。
出力: KAKUNIN/kakunin_sheet.html （ブラウザの印刷機能でPDF化する）
"""
import html as H
from pathlib import Path

ROOT = Path(__file__).parent

# ==== ★蒲郡市向けに書き換え（実データ取得・校閲後に確定させること） ====
CONFIG = {
    "city_name": "蒲郡市",
    "report_title": "「蒲郡市の公共施設 — これから30年のお金の地図」",
    "publish_date": "未定",
    # 資料一覧: 記号, 正式名, 使うページ, (入手元URLは下のsource_urlsで別掲)
    "materials": [
        ("Ａ", "蒲郡市公共施設等総合管理計画(平成29年3月、令和4年3月一部改訂)", "TBD"),
        ("Ｂ", "蒲郡市公共施設白書(令和2年度改訂版)", "TBD"),
    ],
    "source_urls": [
        "資料Ａ: https://www.city.gamagori.lg.jp/uploaded/attachment/84078.pdf",
        "資料Ｂ: https://www.city.gamagori.lg.jp/uploaded/attachment/74398.pdf",
    ],
    # 用語: (用語, 説明)
    "terms": [
        ("延べ床面積", "建物の全部の階の床の広さを合計したもの。"),
        ("更新", "古くなった建物の建て替えのこと。"),
        ("改修", "建て替えずに大きく直すこと（屋根・配管・外壁など）。"),
        ("建物系施設", "市民館や学校など「建物」の施設。道路・橋・水道（インフラ）や"
                        "市民病院は、この試算には入っていません。"),
    ],
    # 柱になる数字: (項目文, 出どころ, チェック選択肢)
    "pillars": [
        ("〇〇市の建物系公共施設をこれから30年維持・更新するのに必要なお金は "
         "<b>約X,XXX億円</b>。<br>内訳: 更新 約X,XXX億円 ＋ 改修 約X,XXX億円 ＋ "
         "維持・修繕 約XXX億円。",
         "資料Ａ 52〜53ページの図", "資料と一致していた/違っていた/わからない"),
        ("一方、市が用意できる見込みは <b>約X,XXX億円</b>（直近年度の実績を30年続けた場合）。",
         "資料Ａ 52〜53ページ（実績額は34ページ）",
         "資料と一致していた/違っていた/わからない"),
        ("つまり <b>約XXX億円（約XX%）足りない</b>、と市自身が試算している。",
         "資料Ａ 52〜53ページ", "資料と一致していた/違っていた/わからない"),
        ("市の結論は「<b>施設の延べ床面積を30年間でXX%程度減らす</b>」という目標。",
         "資料Ａ 53ページ「保有量の目標」の枠内",
         "資料と一致していた/違っていた/わからない"),
    ],
    # 「当方の集計」の項目（市の発表ではない独自計算）
    "own_aggregation": {
        "claim": "市の公共施設白書に個別票があるXXX施設のうち、建築年度が公表されている"
                 "XXX施設を集計すると、<b>延べ床面積のXX%が築XX年以上</b>。",
        "method_lines": [
            "元の数字: 個別票がXXX枚あります。各票の1ページ目「施設延べ床面積合計」と、"
            "2ページ目の建物一覧のいちばん古い「建設年度」を、全部書き写しました。",
            "計算: 建設年度が基準年より前（＝築XX年以上）の施設の延べ床面積を合計し、"
            "建築年度が公表されている施設の延べ床面積合計で割りました。",
        ],
        "verify_note": "書き写した一覧表（全施設について出典ページを明記したもの）を"
                        "一緒にお渡しします。お好きな施設を2〜3件選んで、個別票の該当"
                        "ページと一覧表の行が一致するか確認してください。",
    },
    # よく知られた施設: (施設名, 地域単位, 建設年度, 広さ, 支出, 利用者, 出典記号+ページ)
    "known_facilities": [
        ("〇〇施設", "〇〇地区", "19XX年", "X,XXX㎡", "約X.X億円", "XXX,XXX人", "Ｂ 1〜2"),
    ],
    "district_label": "地区",
}
# ============================

CSS = """
  body { font-family:"Hiragino Mincho ProN","Yu Mincho",serif; color:#111; background:#fff;
    margin:0 auto; max-width:720px; padding:24px 20px 60px; line-height:1.9; font-size:11.5pt; }
  h1 { font-size:15pt; border-bottom:2px solid #111; padding-bottom:6px; }
  h2 { font-size:12.5pt; margin-top:28px; border-left:5px solid #111; padding-left:8px; }
  .lead { font-size:11pt; }
  .item { border:1px solid #999; border-radius:4px; padding:12px 14px; margin:14px 0;
    page-break-inside:avoid; }
  .no { font-weight:bold; }
  .src { font-size:9.5pt; color:#444; }
  .check { margin-top:8px; font-size:10.5pt; }
  .memo, .memo2 { border-bottom:1px dotted #888; height:2em; }
  .memo { margin-top:6px; }
  table { border-collapse:collapse; width:100%; font-size:9.5pt; margin:8px 0; }
  th, td { border:1px solid #999; padding:4px 6px; text-align:right; }
  th:first-child, td:first-child { text-align:left; }
  th { background:#eee; font-weight:600; }
  .term { font-size:10pt; margin:4px 0; }
  .term b { display:inline-block; min-width:8em; }
  @media print { body { padding:0; max-width:none; font-size:10.5pt; } }
"""


def checks(opts):
    return "　".join(f"□ {o}" for o in opts.split("/"))


def render():
    c = CONFIG
    mat_rows = "".join(
        f"<tr><td>{sym}</td><td>{H.escape(name)}</td><td>{pages}</td></tr>"
        for sym, name, pages in c["materials"])
    term_rows = "".join(
        f'<p class="term"><b>{H.escape(t)}</b>: {H.escape(d)}</p>' for t, d in c["terms"])
    pillar_items = "".join(
        f'''<div class="item">
<span class="no">{"①②③④⑤⑥⑦⑧"[i]}</span> {text}<br>
<span class="src">出どころ: {src}</span>
<div class="check">{checks(chk)}</div>
<div class="memo"></div>
</div>''' for i, (text, src, chk) in enumerate(c["pillars"]))

    oa = c["own_aggregation"]
    method = "<br>・".join(H.escape(m) for m in oa["method_lines"])
    own_agg_item = f'''<div class="item">
<span class="no">※</span> {oa["claim"]}<br>
<span class="src"><b>これだけは市の発表ではなく、当方の計算です。</b>計算のしかた:<br>
・{method}<br>
・確かめ方: {H.escape(oa["verify_note"])}</span>
<div class="check">□ 話の筋が通っている　□ 疑問がある　□ わからない</div>
<div class="memo"></div>
</div>'''

    fac_rows = "".join(
        f"<tr><td>{H.escape(n)}</td><td>{H.escape(d)}</td><td>{y}</td>"
        f"<td>{a}</td><td>{s}</td><td>{u}</td><td>{src}</td></tr>"
        for n, d, y, a, s, u, src in c["known_facilities"])

    urls = "<br>".join(H.escape(u) for u in c["source_urls"])

    return f"""<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8">
<title>事実確認シート — {H.escape(c["city_name"])} 公開情報の地図 #1</title>
<style>{CSS}</style></head><body>

<h1>事実確認のお願い<br><span style="font-size:11pt">{H.escape(c["report_title"])}</span></h1>

<p class="lead">
これは、{H.escape(c["city_name"])}が自分で公表している計画書や白書の数字を、
市民が読める形にまとめ直したものを、<b>公開前に間違いがないか確かめていただくための紙</b>です。
お願いしたいことは3つです。
</p>
<ol class="lead">
<li><b>数字の写し間違いがないか</b> — 各項目の「出どころ」に、下の資料記号とページを
書いてあります。市の資料そのものと見比べてください。</li>
<li><b>実感と合うか</b> — 「これはおかしいだろう」という数字や施設の情報があれば教えてください。</li>
<li><b>読んで分かるか</b> — 意味の分からない言葉、誤解しそうな言い回しに印をつけてください。</li>
</ol>
<p class="lead">この紙に赤ペンで直接書き込んでいただければ結構です。
「わからない」「自信がない」も大事な答えですので、遠慮なくそのまま書いてください。</p>

<h2>見比べていただく市の資料（{H.escape(c["city_name"])}が公開しているPDFそのもの）</h2>
<p class="lead" style="font-size:10pt">いずれも公式サイトで誰でも入手できる資料で、
加工していません。ご自分でダウンロードして確かめていただいても構いません。</p>
<table>
<tr><th>記号</th><th>資料の正式名</th><th>今回使うページ</th></tr>
{mat_rows}
</table>
<p class="lead" style="font-size:10pt">入手元: {urls}</p>

<h2>まず、言葉の説明</h2>
{term_rows}

<h2>Ⅰ. レポートの柱になる数字</h2>
{pillar_items}
{own_agg_item}

<h2>Ⅱ. よく知られた施設の情報（見比べと実感チェック）</h2>
<p class="lead">出典欄の記号は上の資料一覧表と対応しています。</p>
<table>
<tr><th>施設</th><th>{H.escape(c["district_label"])}</th><th>建設年度</th>
<th>広さ(延べ床)</th><th>支出</th><th>利用者</th><th>出どころ</th></tr>
{fac_rows}
</table>
<div class="check">気になった施設と理由:</div>
<div class="memo2"></div><div class="memo2"></div>

<h2>Ⅲ. 読みやすさ</h2>
<div class="item">
一緒にお渡しするレポート本文を読んで:<br>
・意味の分からなかった言葉: <div class="memo2"></div>
・誤解しそう・引っかかった言い回し: <div class="memo2"></div>
・全体の印象（率直に）: <div class="memo2"></div>
</div>

<h2>Ⅳ. その他、お気づきの点があれば何でも</h2>
<div class="memo2"></div><div class="memo2"></div><div class="memo2"></div>

<p style="margin-top:28px">確認が済みましたら、この紙をそのまま返してください。<br>
公開予定日: {H.escape(c["publish_date"])}</p>
</body></html>"""


if __name__ == "__main__":
    out_dir = ROOT / "KAKUNIN"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / "kakunin_sheet.html"
    out.write_text(render(), encoding="utf-8")
    print(f"wrote {out}")
    print("次のいずれかでPDF化: ブラウザで開いて印刷 / "
          "chromium --headless --print-to-pdf=KAKUNIN/kakunin_sheet.pdf KAKUNIN/kakunin_sheet.html")
