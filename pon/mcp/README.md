# pon-mcp

社内HTMLホスティング環境「ぽん」🫳 に Claude Code などの MCP クライアントからワンアクションでHTMLをアップロードするための MCP サーバーです(stdio トランスポート)。

「この分析結果をぽんに置いて」と言うだけで、社内URLが発行されます。

## 提供ツール

| ツール | 説明 |
| --- | --- |
| `pon_upload` | HTMLをぽんにアップロードして社内URLを発行。`html_file`(ローカルHTMLファイルのパス)か `html`(HTML文字列)のどちらか一方が必須。既存の `slug` を指定すると上書き更新。 |
| `pon_list` | ぽんに置かれているページ一覧(タイトル・URL・更新者・更新日時)を取得。`limit` で件数を絞れます。 |

`pon_upload` の成功時は次のようなメッセージが返ります:

```
ぽん🫳 https://pon.example.com/p/weekly-report に置きました
```

## セットアップ

Node.js 20 以上が必要です。

```sh
cd pon/mcp
npm install
npm run build
```

### Claude Code への登録

ローカルパス指定で登録する場合:

```sh
claude mcp add pon \
  --env PON_BASE_URL=https://pon.example.com \
  -- node /path/to/pon/mcp/dist/index.js
```

`npm link` や社内レジストリに publish していれば npx でも登録できます:

```sh
claude mcp add pon \
  --env PON_BASE_URL=https://pon.example.com \
  -- npx pon-mcp
```

## 環境変数

| 変数 | 必須 | 説明 |
| --- | --- | --- |
| `PON_BASE_URL` | ✅ | ぽんサーバーのベースURL。例: `https://pon.example.com` |
| `PON_ID_TOKEN` | - | IAP 越えに使う ID トークンをそのまま指定。設定されていれば最優先で `Authorization: Bearer <値>` を付与 |
| `PON_IAP_AUDIENCE` | - | IAP の OAuth クライアントID (audience)。`google-auth-library` の `getIdTokenClient(audience)` で ID トークンを取得して付与 |

## IAP(Identity-Aware Proxy)認証について

ぽんは Cloud Run + IAP(Google Workspace 認証)の背後で動いています。ブラウザなら Google ログインで通れますが、MCP サーバーからのAPI呼び出しには ID トークンを `Authorization` ヘッダーに付ける必要があります。

Authorization ヘッダーは以下の優先順で決まります:

1. **`PON_ID_TOKEN`** が設定されていれば `Bearer <その値>` を付与
   - 手元で短期的に使う場合など。例: `gcloud auth print-identity-token` の出力を渡す
2. **`PON_IAP_AUDIENCE`** が設定されていれば、`google-auth-library` の `getIdTokenClient(audience)` で ID トークンを自動取得して付与
   - サービスアカウント(`GOOGLE_APPLICATION_CREDENTIALS`)や ADC(`gcloud auth application-default login`)を利用
   - audience には IAP の OAuth クライアントID(`xxxx.apps.googleusercontent.com`)を指定
3. どちらも無ければ **ヘッダーなし**(IAP を挟まないローカル開発サーバー用)

### 設定例

サービスアカウントで自動取得する場合:

```sh
claude mcp add pon \
  --env PON_BASE_URL=https://pon.example.com \
  --env PON_IAP_AUDIENCE=123456789-abcdefg.apps.googleusercontent.com \
  --env GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json \
  -- node /path/to/pon/mcp/dist/index.js
```

ローカル開発サーバー(IAPなし)に向ける場合:

```sh
claude mcp add pon --env PON_BASE_URL=http://localhost:8080 \
  -- node /path/to/pon/mcp/dist/index.js
```

## 使用例

Claude Code でこう頼むだけです:

> この分析結果をぽんに置いて

Claude が分析結果をHTMLにまとめ、`pon_upload` を呼んで社内URLを返してくれます。

> ぽんにあるページを一覧して

`pon_list` が呼ばれ、置かれているページの一覧が表示されます。

> さっきの weekly-report を更新して

同じ `slug` を指定して `pon_upload` すると上書き更新されます。

## サーバーAPI契約

このMCPサーバーは、ぽんサーバーの以下のAPIを呼びます:

- `POST /api/pages` — JSON `{ "title": string, "html": string, "slug"?: string }` → 201 `{ "slug", "url", "title" }`(既存slug指定で上書き更新)
- `GET /api/pages` — `{ "pages": [{ "slug", "title", "uploader", "updatedAt", "url" }] }`

## 開発

```sh
npm run build   # TypeScript をビルド
npm test        # ビルドして node:test でテスト実行(モックHTTPサーバー使用)
npm start       # stdio で MCP サーバーを起動
```
