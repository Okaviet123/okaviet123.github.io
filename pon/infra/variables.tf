variable "project_id" {
  description = "デプロイ先の Google Cloud プロジェクト ID"
  type        = string
}

variable "region" {
  description = "リソースを作成するリージョン"
  type        = string
  default     = "asia-northeast1"
}

variable "allowed_domain" {
  description = "IAP でアクセスを許可する Google Workspace ドメイン(例: example.com)"
  type        = string
}

variable "image" {
  description = "Cloud Run にデプロイするコンテナイメージ URL(例: asia-northeast1-docker.pkg.dev/PROJECT/pon/pon-server:latest)"
  type        = string
}

variable "retention_days" {
  description = "GCS 上のページを自動削除するまでの日数(置きっぱなしドキュメントの肥大化防止)"
  type        = number
  default     = 7
}

variable "service_name" {
  description = "Cloud Run サービス名"
  type        = string
  default     = "pon"
}
