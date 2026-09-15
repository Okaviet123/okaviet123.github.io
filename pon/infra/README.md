# pon/infra — Terraform によるインフラ構築

「ぽん」の本番環境(GCS + Cloud Run + IAP)を Terraform で構築します。

以前は IAP を利用するには Load Balancer などが必要で大変でしたが、現在は Cloud Run に
IAP を直接設定できるため、ロードバランサなしの低コストな構成になっています。

## 構成されるリソース

| リソース | 内容 |
|---|---|
| GCS バケット | ページ保存用。非公開(public access prevention)+ uniform bucket-level access。**デフォルト 7 日で自動削除**(`retention_days` で変更可) |
| Cloud Run v2 サービス | `pon/server` のコンテナを配信。`PON_BUCKET` 環境変数にバケット名を注入。`iap_enabled = true` で IAP を直接有効化 |
| サービスアカウント | Cloud Run 実行用。バケットへの `roles/storage.objectAdmin` のみ付与 |
| IAP サービスエージェント | IAP がユーザーの代わりに Cloud Run を呼べるよう `roles/run.invoker` を付与 |
| IAP アクセスポリシー | `domain:<allowed_domain>` に `roles/iap.httpsResourceAccessor` を付与し、Google Workspace の社内ドメインユーザーのみ閲覧可能に |

※ かつて IAP に必要だった OAuth brand / client(`google_iap_brand` など)は、IAP OAuth Admin API の廃止(2026 年 3 月)により不要になりました。Google 管理の OAuth 設定が自動で使われます。

## 前提

- [Terraform](https://developer.hashicorp.com/terraform) >= 1.7
- [gcloud CLI](https://cloud.google.com/sdk/docs/install)(認証済み: `gcloud auth application-default login`)
- Google Cloud プロジェクト(課金有効)
- プロジェクトが Google Workspace の組織に属していること(IAP のドメイン制限に必要)

## 1. コンテナイメージを Artifact Registry に push する

Terraform を適用する前に、`pon/server` のイメージをビルドして push しておきます。

```bash
PROJECT_ID=your-project-id
REGION=asia-northeast1

# Artifact Registry リポジトリを作成(初回のみ)
gcloud artifacts repositories create pon \
  --project="$PROJECT_ID" \
  --location="$REGION" \
  --repository-format=docker

# pon/server の Dockerfile からビルドして push
cd ../server
gcloud builds submit \
  --project="$PROJECT_ID" \
  --tag "$REGION-docker.pkg.dev/$PROJECT_ID/pon/pon-server:latest"
```

## 2. terraform apply

```bash
cd ../infra

cat > terraform.tfvars <<EOF
project_id     = "your-project-id"
region         = "asia-northeast1"
allowed_domain = "example.com"   # 社内の Google Workspace ドメイン
image          = "asia-northeast1-docker.pkg.dev/your-project-id/pon/pon-server:latest"
EOF

terraform init
terraform plan
terraform apply
```

apply が完了すると以下が出力されます。

- `bucket_name` — ページ保存用バケット名
- `service_url` — ぽんの URL(Cloud Run のデフォルト URL、例: `https://pon-xxxxxx-an.a.run.app`)
- `service_account_email` — Cloud Run のサービスアカウント

`service_url` をブラウザで開くと Google ログインを求められ、`allowed_domain` の
アカウントでのみ一覧ページが表示されれば成功です。

## 3. MCP / CI からのアップロード(IAP 越え)

IAP の背後にある API を人間以外(MCP・CI)が叩くには、許可されたサービスアカウントの
**ID トークン**を `Authorization: Bearer` で送ります。

1. アップロード用サービスアカウントを作成し、IAP のアクセス権を付与する

   ```bash
   gcloud iam service-accounts create pon-uploader --project="$PROJECT_ID"
   # IAP のアクセス許可(コンソールの IAP 画面、または iap web add-iam-policy-binding)
   ```

2. ID トークンの audience(IAP のクライアント ID)を確認し、MCP の環境変数
   `PON_IAP_AUDIENCE` に設定する(取得方法は Cloud Run の「セキュリティ」タブ、
   または `gcloud iap settings get` を参照)。

3. `pon/mcp` を `PON_BASE_URL=<service_url>` と `PON_IAP_AUDIENCE` 付きで登録する
   (詳細は [`../README.md`](../README.md) と `pon/mcp` の README を参照)。

## カスタムドメイン(オプション)

Cloud Run のデフォルト URL のままでも運用できますが、`pon.example.com` のような
社内向けホスト名を付けたい場合は Cloud Run のカスタムドメインマッピングが使えます。

```bash
gcloud beta run domain-mappings create \
  --project="$PROJECT_ID" --region="$REGION" \
  --service=pon --domain=pon.example.com
```

コマンドが表示する DNS レコード(CNAME `ghs.googlehosted.com.` など)を社内ドメインの
DNS に登録すると、マネージド証明書が自動発行されます。

## 運用メモ

- **7 日で自動削除**: バケットのライフサイクルルールで、アップロードから
  `retention_days`(デフォルト 7)日経過したページは自動削除されます。
  恒久的に残したいドキュメントは正規のドキュメント基盤に置いてください。
- イメージ更新: `gcloud builds submit` で新タグを push → `image` 変数を更新して
  `terraform apply`(または `gcloud run deploy`)。
- 削除: `terraform destroy`(バケットにオブジェクトが残っていると失敗します。
  先に空にするか `force_destroy` を検討してください)。
