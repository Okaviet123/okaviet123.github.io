# GAMAGORI — 蒲郡市 公開情報レポート

このディレクトリは `okaviet123.github.io`（個人のGitHub Pagesリポジトリ）内の
サブプロジェクト。`TOYOHASHI/SKILLS/muni-facility-report` スキルの手順に従い、
豊橋市#1と同じ構成で作る2市目。蒲郡市の公開情報を市民が読める形に「翻訳」し、
実名で公開するレポートシリーズの1本。

## テーマ（S1偵察 2026-07-27 時点の暫定方針）

豊橋#1と同じ**テーマA: 公共施設×人口動態**を採用する。理由: 蒲郡市も
総合管理計画・公共施設白書・決算カードの3資料が既に公表されており、
件数規模もPDF中心で見積もりやすい（詳細は `LOG/S1_recon_matrix.md`）。
他テーマ（議会議事録等）は検討していない。

## 最上位規則（スキルの憲章を継承）

- 事実と出典のみ。形容詞・評価語を最小化。全データポイントに出典リンク。
- 個人への言及は公職者の公的発言の引用に限定。動機の推測は書かない。
- 「改善案」は最終節に一つだけ。主体は見える化であって提言ではない。
- 明暗の結論比率をあらかじめ決めて分析しない。市の文書が言っていることを
  そのまま構造化する。
- **数字は豊橋#1から一切使い回さない。** 蒲郡市の数字はすべてゼロから
  取得・計算する（`SKILLS/muni-facility-report/SKILL.md` の禁止事項）。
- 公開はWeb（静的サイト）が基本。市役所へ直接提出しない。
- 公開日: **未定**。実データの取得・検証が終わるまで確定させない
  （品質を理由に延期しないという豊橋#1の原則を尊重しつつ、着手前に
  日付を仮置きしない）。

## ファイル階層規則（豊橋#1を踏襲）

- スクリプトはこのディレクトリ直下に置く。
- `RAW/` 取得した生データ（PDF等）。keikaku/ hakusho/ kessancard/ jinko/ に分類。
- `DATA/` 構造化済み中間データ（CSV）。`references/data_schema.md` の標準スキーマ準拠。
- `SITE/` 公開物（GitHub Pagesのソース）。
- `KAKUNIN/` 事実確認シート・書き写し一覧表。
- `NOTE/` note要約・告知文の下書き。
- `LOG/` 取得日時・出典URLの台帳（`download_ledger.csv`）。

## S1偵察で判明した対象3資料（2026-07-27、WebSearch経由）

| 資料 | 名称・状態 | URL |
|---|---|---|
| 総合管理計画 | 蒲郡市公共施設等総合管理計画（平成29年3月、令和4年3月一部改訂） | https://www.city.gamagori.lg.jp/uploaded/attachment/84078.pdf |
| 公共施設白書 | 蒲郡市公共施設白書（令和2年度改訂版、令和3年3月） | https://www.city.gamagori.lg.jp/uploaded/attachment/74398.pdf |
| 決算カード/財政状況資料集 | 「財政状況資料集」ページに集約。個別年度PDFのURLは未確認（要ページ内リンク列挙） | https://www.city.gamagori.lg.jp/unit/zaimu/zaiseijyokyoshiryosyu.html |
| 参考: 人口ビジョン | 将来の人口の見通し／まち・ひと・しごと創生総合戦略2025-2030(案) | https://www.city.gamagori.lg.jp/uploaded/attachment/56861.pdf ／ https://www.city.gamagori.lg.jp/uploaded/attachment/106454.pdf |
| 参考: 個別施設計画（地区別） | 中学校区単位のワークショップで地区別個別計画を策定（蒲郡北地区は策定済み） | https://www.city.gamagori.lg.jp/unit/kyoikuseisaku/basicplan-formulate.html |

地域単位は蒲郡市の場合「中学校区」で計画が組まれている模様（要確認）。
`analyze_shisetsu.py` / `build_site.py` の `DISTRICT_COL` は暫定で
`中学校区` としている。白書の個別票を読んだ時点で校区表記の実際に
合わせて修正すること。

## ネットワークアクセスに関する既知の制約（2026-07-27時点）

この作業セッションの環境ネットワークポリシーでは、
`www.city.gamagori.lg.jp` / `city.gamagori.lg.jp` への直接アクセス
（curl・WebFetch）が **403（egressポリシー拒否）** でブロックされている
（`WebSearch` はブロックされておらず、フェーズ1の偵察はこれで実施した）。

- ブロックされているため、PDFの実ダウンロード（フェーズ2）・HTMLページ内の
  リンク列挙（決算カードの年度別ファイル名特定等）が実行できていない。
- ガードレール（`SKILLS/muni-facility-report/references/guardrails.md`）の
  「403/407が出たら報告する、回避しない」原則に従い、プロキシ回避等は行っていない。
- **ユーザーへの依頼**: 豊橋#1のとき（環境「Default」のネットワークポリシーを
  カスタム許可リストに変更）と同様に、以下のドメインをこの環境の許可リストに
  追加してほしい。
  - `www.city.gamagori.lg.jp` / `city.gamagori.lg.jp`（総合管理計画・白書・決算カード本体）
  - `www.soumu.go.jp` / `soumu.go.jp`（決算カードの総務省全国一覧。市サイト側で
    十分な場合は不要になる可能性あり）
  - `www.e-stat.go.jp` / `e-stat.go.jp` / `api.e-stat.go.jp`（人口動態の補助データ、必要になった場合のみ）
- 許可リスト更新後にフェーズ2（`collect_pdfs.py`実行）以降を再開する。

## 事実確認プロセス（豊橋#1と同一の水準を適用）

- 品質目標: 蒲郡市に長年住む非技術者が読んで「市役所に提出してもいいレベルだ」と
  自発的に言う水準（`SKILLS/muni-facility-report/references/quality_bar.md`）。
- 事実確認シートは市の原本PDFを無加工のまま渡し、資料記号＋ページ番号だけを示す
  （こちらが加工した抜粋で検証させない）。
- 「当方の集計」は計算過程を開示し、数件のサンプル照合で検証できる形にする。
- 公開前に、柱の数字を原本PDFと突き合わせる敵対的校閲を最低1回行う。
