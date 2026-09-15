output "bucket_name" {
  description = "ページ保存用 GCS バケット名"
  value       = google_storage_bucket.pages.name
}

output "service_url" {
  description = "ぽんの URL(Cloud Run のデフォルト URL。IAP 経由でアクセス)"
  value       = google_cloud_run_v2_service.pon.uri
}

output "service_account_email" {
  description = "Cloud Run が使用するサービスアカウント"
  value       = google_service_account.pon.email
}
