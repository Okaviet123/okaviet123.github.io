terraform {
  required_version = ">= 1.7"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 6.44.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = ">= 6.44.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

# ---------------------------------------------------------------------------
# 必要な API の有効化
# ---------------------------------------------------------------------------

locals {
  services = [
    "run.googleapis.com",
    "iap.googleapis.com",
    "compute.googleapis.com",
    "storage.googleapis.com",
    "cloudresourcemanager.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each = toset(local.services)

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

# ---------------------------------------------------------------------------
# 保存先: GCS バケット(非公開・uniform bucket-level access)
# ---------------------------------------------------------------------------

resource "google_storage_bucket" "pages" {
  name     = "${var.project_id}-pon-pages"
  location = var.region

  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  # 置きっぱなしのドキュメントが肥大化しないよう、デフォルト 7 日で自動削除
  lifecycle_rule {
    condition {
      age = var.retention_days
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [google_project_service.apis]
}

# ---------------------------------------------------------------------------
# Cloud Run 用サービスアカウント(バケットへの読み書き権限のみ)
# ---------------------------------------------------------------------------

resource "google_service_account" "pon" {
  account_id   = "${var.service_name}-server"
  display_name = "pon server (Cloud Run)"
}

resource "google_storage_bucket_iam_member" "pon_object_admin" {
  bucket = google_storage_bucket.pages.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.pon.email}"
}

# ---------------------------------------------------------------------------
# 配信: Cloud Run v2 サービス(IAP を直接有効化)
#
# 以前は IAP を使うには Load Balancer が必要でしたが、
# 現在は Cloud Run に IAP を直接設定できるため低コストで実現できます。
# ---------------------------------------------------------------------------

resource "google_cloud_run_v2_service" "pon" {
  name     = var.service_name
  location = var.region

  ingress             = "INGRESS_TRAFFIC_ALL" # 認証は手前の IAP が行う
  iap_enabled         = true
  deletion_protection = false

  template {
    service_account = google_service_account.pon.email

    containers {
      image = var.image

      # PORT は Cloud Run が自動注入するため設定不要
      env {
        name  = "PON_BUCKET"
        value = google_storage_bucket.pages.name
      }
    }
  }

  depends_on = [google_project_service.apis]
}

# ---------------------------------------------------------------------------
# IAP
#
# 注: かつて必要だった OAuth brand / client(google_iap_brand 等)は、
# IAP OAuth Admin API の廃止(2026-03)に伴い不要になりました。
# Cloud Run への直接 IAP 有効化では Google 管理の OAuth が使われます。
# ---------------------------------------------------------------------------

# IAP のサービスエージェントを作成し、Cloud Run の起動権限を付与する
# (IAP がユーザーの代わりに Cloud Run を呼び出せるようにする)
resource "google_project_service_identity" "iap" {
  provider = google-beta

  project = var.project_id
  service = "iap.googleapis.com"

  depends_on = [google_project_service.apis]
}

resource "google_cloud_run_v2_service_iam_member" "iap_invoker" {
  project  = var.project_id
  location = google_cloud_run_v2_service.pon.location
  name     = google_cloud_run_v2_service.pon.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_project_service_identity.iap.email}"
}

# Google Workspace の社内ドメインユーザーのみアクセスを許可
resource "google_iap_web_cloud_run_service_iam_member" "allowed_domain" {
  project                = var.project_id
  location               = google_cloud_run_v2_service.pon.location
  cloud_run_service_name = google_cloud_run_v2_service.pon.name
  role                   = "roles/iap.httpsResourceAccessor"
  member                 = "domain:${var.allowed_domain}"
}
