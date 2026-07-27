---
name: muni-facility-report
description: Builds a citizen-facing "translation" report on a Japanese municipality's public facility finances from open government data — the 公共施設等総合管理計画 (public facility management plan), 公共施設白書 (facility whitepaper), and 決算カード (settlement cards). Searches for and downloads the source PDFs, parses them into standardized CSVs, generates a static HTML site (30-year cost-gap chart, building-age distribution, ward/district breakdown, full facility list with real names), and produces a print-ready, non-technical fact-check sheet with page-level citations to the original PDFs for a local resident to verify before publication. Use this skill whenever the user asks to build a "[city name]-ish version of the Toyohashi report", wants to analyze a Japanese city/town's 公共施設等総合管理計画 or 決算カード, wants a plain-language civic translation of municipal facility/fiscal data, or wants to repeat this pipeline for a new 市町村 — even if they just say "do the same thing for Okazaki" without spelling out every step.
---

# 公共施設レポート・パイプライン（muni-facility-report）

任意の日本の市町村を指定すると、その市が自分で公表している資料（総合管理計画・
公共施設白書・決算カード）だけを使って、「これから30年のお金の地図」型の
市民向けレポートを作る。豊橋市#1で実証した手順をテンプレート化したもの。

このファイル一式の正典（canonical）の場所はリポジトリ直下 `SKILLS/
muni-facility-report/`。`TOYOHASHI/SKILLS/muni-facility-report/` に
同内容の古いコピーが残っている場合があるが、それは豊橋#1のブランチが
まだmainに統合されていないために生じた重複であり、統合時に解消する。
編集は必ずこの正典側（リポジトリ直下）に対して行うこと。

**このスキルの立ち位置は「翻訳」であって「提言」ではない。** 市に送りつけない。
形容詞と評価語を最小化し、事実と出典のみで構成する。改善案を書く場合も最終節に
一つだけ。この一線を越えないことが、このスキルの品質基準そのもの。

## 全体の流れ（7フェーズ）

各フェーズの詳細は `references/workflow.md` を参照。ここでは要点だけ。

1. **偵察** — その市の3資料（総合管理計画/白書/決算カード）のURLを検索で特定し、
   取得可能性を確認する。**着手前に、対象ドメインへのネットワークアクセスが
   許可されているか確認すること**（環境のegressポリシーで多くの外部サイトが
   ブロックされている場合がある。詳細は `references/guardrails.md`）。
2. **取得** — `scripts/collect_pdfs.py` でPDFを一括取得。レートリミット必須
   （1req/2s目安）、`LOG/download_ledger.csv` に出典URL・SHA256を必ず記録。
3. **構造化** — 決算カードは全国統一様式なので `scripts/parse_kessancard.py` を
   ほぼそのまま使える。白書・個別施設票は市ごとに様式が違うので、
   **1本のPDFで構造を完全に把握してから** パーサーを書く（いきなり全件処理しない）。
   出力は `references/data_schema.md` の標準スキーマに合わせる — ここを守ると
   複数市のデータが後で横串で比較できるようになる。
4. **分析・サイト生成** — `scripts/analyze_shisetsu.py` で年代分布・地区別集計・
   築古上位を計算し、`scripts/build_site.py` でサイトを生成する。中核図表は
   「必要な費用 vs 用意できる費用のギャップ」＋「建築年代分布」の2枚を基本形とする
   （理由は `references/workflow.md` の「型の固定」節）。dataviz skillの
   パレット検証を必ず通す。
5. **検証** — 公開前に、柱の数字を原本PDFと突き合わせる敵対的校閲を必ず1回行う
   （見つけるほど価値がある、という姿勢のレビュアーを使う）。
6. **事実確認・公開** — `scripts/make_kakunin_sheet.py` で非技術者向けの
   印刷用チェックシートを作る。原則は「当方が加工した抜粋ではなく、
   市の原本PDFのページ番号を直接指定する」こと（詳細は `references/quality_bar.md`）。
7. **地図統合・コード化公開** — シリーズが2市目以降になったら、
   `MUNICIPALITIES.csv` に対象市を登録し `map/build_map.py` を実行する。
   公開URLは市町村名ではなく総務省の全国地方公共団体コード（5桁）で
   固定し、日本地図から自分の市町村をクリックしてレポートに飛べる
   `map/index.html` を再生成する（詳細は `references/publish_map.md`）。

## このスキルを使うときに最初にすること

1. 対象の市町村名を確認する
2. `references/workflow.md` の「フェーズ1: 偵察」を読み、3資料のURLを探す
3. ネットワークアクセスの確認（`references/guardrails.md` 参照）
4. 前の市（あれば）のディレクトリ構成をコピーして流用してよいが、
   **数字は必ずゼロから取得し直す**。他市の値を使い回すことは絶対にしない

## ディレクトリ規則

スクリプトは対象市のプロジェクト直下、出力は子フォルダに分ける
（豊橋#1の構成をそのまま踏襲）:
```
<CITY>/
  CLAUDE.md          # このスキルを読み込んだ前提で、市固有の情報を書く
  collect_pdfs.py
  parse_kessancard.py
  analyze_shisetsu.py
  build_site.py
  make_kakunin_sheet.py
  RAW/               # 取得した生PDF
  DATA/              # 標準スキーマの中間CSV
  SITE/              # 公開用HTML
  KAKUNIN/           # 事実確認シート・書き写し一覧表
  NOTE/              # note要約・告知文の下書き
  LOG/               # 出典台帳
```

このローマ字ディレクトリ名は著者側の作業用であり、変えない。読者向けの
公開URL（日本地図からのリンク先）は別に `report/<全国地方公共団体コード>/`
で持つ（フェーズ7、`references/publish_map.md`）。市町村名の表記より
コードの方が恒久的なリンクとして安定するため。

## 品質の物差し

「その市に長年住んでいる、技術に詳しくない人が読んで、"これは市役所に
提出してもいいレベルだ"と自発的に言う」水準を目指す。具体条件は
`references/quality_bar.md`。ここが甘いと、シリーズ全体の信頼が崩れる。

## リファレンス一覧

- `references/workflow.md` — 7フェーズの詳細手順、中核図表の型の設計思想
- `references/data_schema.md` — 標準CSVスキーマ（横串比較の生命線）
- `references/guardrails.md` — ネットワーク・レートリミット・引用範囲・
  「市の発表」と「当方の集計」を混同しないルール。ネットワークブロック時の
  Claude Chromeフォールバック手順も含む
- `references/quality_bar.md` — 事実確認シートの設計原則、原本直接参照の理由
- `references/publish_map.md` — 日本地図からのコード化公開（フェーズ7）の設計
