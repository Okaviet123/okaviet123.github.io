# pon 🫳 — 配信/アップロードサーバー

HTMLファイルを「ポン」と置くだけで社内URLを発行できる、社内HTMLホスティング環境
([BASE社のブログ記事](https://devblog.thebase.in/entry/pon) で紹介された「pon」のクローン)の
配信/アップロードサーバー本体です。

- ランタイム: Node.js 20+ / TypeScript / [Hono](https://hono.dev/)
- 保存先: Google Cloud Storage(ローカル開発時はローカルファイルシステム)
- デプロイ先: Cloud Run(認証は前段の IAP を想定)

## ⏳ ページの自動削除について

アップロードされたページは **デフォルト7日で自動削除** されます。
削除処理はこのサーバーではなく **GCS バケットのライフサイクルルール**(Terraform 側で設定)で
実現しているため、サーバー実装には削除ロジックはありません。
一覧UIに表示する日数は環境変数 `PON_RETENTION_DAYS` で変更できます(表示のみ。
実際の削除日数は GCS 側の設定に合わせてください)。

## ローカル起動

```bash
cd pon/server
npm install

# ローカルFSを保存先にして起動(GCS不要)
PON_LOCAL_DIR=./data npm run dev
# → http://localhost:8080
```

GCS を使う場合:

```bash
# 事前に gcloud auth application-default login などで認証しておく
PON_BUCKET=my-pon-bucket npm run dev
```

動作確認:

```bash
# アップロード
curl -X POST http://localhost:8080/api/pages \
  -H "Content-Type: application/json" \
  -d '{"title": "テストページ", "html": "<h1>こんにちは</h1>"}'
# => {"slug":"sunny-panda-1234","url":"https://localhost:8080/p/sunny-panda-1234/","title":"テストページ"}

# 閲覧
curl http://localhost:8080/p/sunny-panda-1234/

# 一覧
curl http://localhost:8080/api/pages
```

テスト:

```bash
npm test
```

## 環境変数

| 変数 | 必須 | 説明 |
| --- | --- | --- |
| `PON_BUCKET` | ○(GCS利用時) | 保存先の GCS バケット名 |
| `PON_LOCAL_DIR` | - | 設定すると GCS の代わりにローカルFSのこのディレクトリを保存先に使う(開発・テスト用) |
| `PORT` | - | リッスンポート(デフォルト `8080`。Cloud Run が自動注入) |
| `PON_RETENTION_DAYS` | - | 一覧UIに表示する自動削除までの日数(デフォルト `7`) |

`PON_LOCAL_DIR` と `PON_BUCKET` の両方が設定されている場合は `PON_LOCAL_DIR` が優先されます。

## API

### `POST /api/pages` — ページのアップロード

リクエスト(JSON):

```json
{
  "title": "週次レポート",
  "html": "<h1>...</h1>",
  "slug": "weekly-report"
}
```

- `title`(必須): ページタイトル。GCS オブジェクトのカスタムメタデータに保存されます。
- `html`(必須): ページ本体の HTML。
- `slug`(任意): URL に使う識別子(英小文字・数字・ハイフン、100文字以内)。
  未指定の場合は `sunny-panda-4821` のような読みやすいランダム slug を自動生成します。
  **既存 slug を指定した場合は上書き(更新)します。**

レスポンス `201`:

```json
{
  "slug": "weekly-report",
  "url": "https://<host>/p/weekly-report/",
  "title": "週次レポート"
}
```

保存先は GCS の `pages/<slug>/index.html`。アップロード者は IAP のヘッダー
`x-goog-authenticated-user-email`(`accounts.google.com:user@example.com` 形式)から
取得し、メタデータ `uploader` に保存します(ヘッダーが無ければ `anonymous`)。

### `GET /p/:slug/` — ページ配信

- `GET /p/:slug` は `GET /p/:slug/` へ 301 リダイレクト。
- `GET /p/:slug/` は `pages/<slug>/index.html` を配信。
- `GET /p/:slug/<subpath>` は `pages/<slug>/<subpath>` を配信
  (相対パスの画像などのアセットも置けます)。Content-Type は拡張子から判定します。
- 存在しない場合は日本語の 404 ページを返します。

### `GET /api/pages` — ページ一覧(JSON)

```json
{
  "pages": [
    {
      "slug": "weekly-report",
      "title": "週次レポート",
      "uploader": "taro@example.com",
      "updatedAt": "2026-07-26T09:00:00.000Z",
      "url": "https://<host>/p/weekly-report/"
    }
  ]
}
```

更新日時の降順で返します。

### `GET /` — ページ一覧(HTML)

タイトル・アップロード者・更新日時を新しい順に表示する日本語UIの一覧ページです。
自動削除までの日数の注記も表示します。

### `GET /healthz` — ヘルスチェック

`{"ok":true}` を返します。

## Docker / Cloud Run

```bash
cd pon/server
docker build -t pon-server .
docker run --rm -p 8080:8080 -e PON_LOCAL_DIR=/tmp/pon-data pon-server
```

Cloud Run では `PON_BUCKET` を設定してデプロイしてください。
`PORT` は Cloud Run が注入する値をそのまま使用します。

## ディレクトリ構成

```
pon/server/
├── src/
│   ├── index.ts    # エントリポイント(env読み込み・サーバー起動)
│   ├── routes.ts   # Hono ルーティング(API・配信・一覧UI・404)
│   ├── storage.ts  # ストレージ抽象化(GCS実装 / ローカルFS実装)
│   └── slug.ts     # ランダムslug生成・バリデーション
├── test/
│   └── server.test.ts  # node:test によるE2E寄りのテスト(ローカルFS使用)
├── Dockerfile      # multi-stage(Node 20 slim)
├── package.json
└── tsconfig.json
```
