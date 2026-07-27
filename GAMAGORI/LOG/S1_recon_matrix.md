# S1 偵察ログ — データソース取得可能性マトリクス（蒲郡市）

- 実施日: 2026-07-27
- 実施者: Claude Code（自動リサーチ）+ WebSearchスニペットに基づく調査
- 注記: 本セッションの実行環境はネットワークポリシーにより、
  `city.gamagori.lg.jp` への直接アクセス（WebFetch/curl）が403でブロック
  されていた（実測: `curl https://www.city.gamagori.lg.jp/` → CONNECT
  tunnel failed, response 403）。下記はWebSearch（検索結果スニペット）に
  基づく間接調査であり、ファイル内部の構造・機械可読性・決算カードの
  年度別ファイル名は未検証。S2着手前に、外部アクセス可能な環境
  （ネットワークポリシー変更後の同セッション等）からの再確認が必須。

## テーマA: 公共施設×人口動態（豊橋#1と同一テーマを採用）

| 項目 | 内容 | 取得可能性 |
|---|---|---|
| 公共施設等総合管理計画 | 蒲郡市公共施設等総合管理計画（平成29年3月、令和4年3月一部改訂）。直リンクPDF確認済み: https://www.city.gamagori.lg.jp/uploaded/attachment/84078.pdf | 高（URL確定、PDFとして直接ダウンロード可能とみられる） |
| 公共施設マネジメント基本方針/実施計画 | 基本方針は平成28年3月策定、実施計画は平成29年3月策定。ページ: https://www.city.gamagori.lg.jp/site/management/jisshikeikaku.html （直リンクPDFは未確認） | 中 |
| 公共施設白書 | 蒲郡市公共施設白書（令和2年度改訂版、令和3年3月）。直リンクPDF確認済み: https://www.city.gamagori.lg.jp/uploaded/attachment/74398.pdf。初版は平成26年度策定（平成27年3月） | 高 |
| 決算カード／財政状況資料集 | 総務省の全国統一様式に再編後の「財政状況資料集」ページに集約: https://www.city.gamagori.lg.jp/unit/zaimu/zaiseijyokyoshiryosyu.html 。個別年度のPDFファイル名・パスはページ内リンクを開かないと分からない（ネットワーク制約で未確認）。年度別決算ページ（例: 令和5年度決算 https://www.city.gamagori.lg.jp/unit/zaimu/reiwa5kessan.html ）も別途存在 | 中（存在は確実、個別URLは未列挙） |
| 人口ビジョン・将来推計 | 「将来の人口の見通し」PDF: https://www.city.gamagori.lg.jp/uploaded/attachment/56861.pdf 。最新は「蒲郡市まち・ひと・しごと創生総合戦略2025-2030(案)」: https://www.city.gamagori.lg.jp/uploaded/attachment/106454.pdf 。令和42年(2060年)の目標人口61,000人という数値がスニペットに出た（要現物ページで確認、鵜呑みにしない） | 高 |
| 個別施設計画（地区別） | 中学校区単位でワークショップを実施し「地区別個別計画」を策定する方針。蒲郡北地区は策定済み: https://www.city.gamagori.lg.jp/unit/kyoikuseisaku/basicplan-formulate.html 。全地区分がまだ揃っているかは未確認 | 中（一部のみ確認、全地区分は未確認） |

## 想定取得手法

PDF直接ダウンロード → `pdftotext -layout` / 目視で構造把握 → 白書は
市ごとに設計し直すパーサーを新規作成、決算カードは
`SKILLS/muni-facility-report/scripts/parse_kessancard.py`（全国統一様式）
をほぼそのまま使う。豊橋#1と同規模（PDF数十点）とみられる。

## 懸念点

1. **ネットワーク制約が最優先の懸念。** 本セッション環境から
   `city.gamagori.lg.jp` への到達可否自体が403で拒否されており、
   S2（取得）に進むには環境のネットワークポリシー変更（許可リストへの
   ドメイン追加）が前提になる。豊橋#1のときと同型の制約。
2. 決算カードの個別年度PDFのファイル名規則が豊橋のように不規則
   （`R06kessancard.pdf` 等バラバラ）である可能性が高く、ページ内の
   リンクを実際に開いて一つずつ拾う必要がある（ネットワーク解禁後に実施）。
3. 地域単位が「中学校区」なのか「小学校区」なのか、白書内の実際の表記を
   確認するまで確定できない（`CLAUDE.md` に暫定値を記載、要修正）。
4. 個別施設計画が全地区分揃っているか未確認。揃っていない場合、
   白書の個別施設票（全施設一覧）の方を主データソースとして使う
   （豊橋#1と同じ構造）。

## 判定

**S1時点の結論: テーマA（公共施設×人口動態）を採用。** 豊橋#1と同一テーマ
だが、データは蒲郡市の資料からゼロで取得・計算する（他市の数値の流用は
スキルの禁止事項）。

## 次のアクション（S2着手前に解消すべき事項）

1. **環境のネットワークポリシーに `city.gamagori.lg.jp` / `www.city.gamagori.lg.jp`
   （必要なら `soumu.go.jp` / `e-stat.go.jp` も）を許可リストに追加してもらう**
   （ユーザーの画面操作が必要。豊橋#1のときと同じ対応）。
2. 許可後、`www.city.gamagori.lg.jp/unit/zaimu/zaiseijyokyoshiryosyu.html` と
   関連する年度別決算ページを開き、決算カードPDFの実URLを列挙する。
3. 総合管理計画PDF・白書PDF・人口ビジョン系PDFの実物を取得し、
   `pdftotext -layout` で1本ずつ構造を把握してからパーサーを設計する。
4. 個別施設計画（地区別）が全地区揃っているか確認し、揃っていなければ
   白書の個別施設票を主データソースとして使う方針を確定する。

## 追記（2026-07-27）: 決算カードURLをClaude Chromeフォールバックで解決

上記「次のアクション1」（ネットワークポリシー許可）はまだ未解決だが、
`SKILLS/muni-facility-report/references/guardrails.md` のフォールバック
手順に従い、ユーザーが自身のClaude Chromeで財政状況資料集ページ・
マネジメント計画ページを開いてURL一覧を確認・提供してくれた。
H18〜R6年度の決算カード/財政状況資料集（PDF/Excel混在）、マネジメント
基本方針・実施計画のURLが`collect_pdfs.py`のTARGETSに反映済み。
ただし実ファイルのダウンロード自体はこのセッションからまだ未実行
（ネットワークポリシー許可待ち、または手動配置待ち。`CLAUDE.md`参照）。
