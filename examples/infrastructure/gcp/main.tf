provider "google" {
  project = var.project_id != "" ? var.project_id : null
  region  = var.region
}

resource "google_service_account" "dataproc_rules" {
  count        = var.create_resources && var.project_id != "" ? 1 : 0
  account_id   = "${var.name_prefix}-dataproc"
  display_name = "SparkRules Dataproc artifacts"
}

resource "google_storage_bucket" "artifacts" {
  count    = var.create_resources && var.project_id != "" ? 1 : 0
  name     = "${var.project_id}-${var.name_prefix}-rules-artifacts"
  location = var.region

  uniform_bucket_level_access = true

  labels = {
    purpose = "sparkrules"
  }
}

# Read + write objects (upload DRL / test JSON; Spark jobs read the same bucket).
resource "google_storage_bucket_iam_member" "sa_rules_data" {
  count  = var.create_resources && var.project_id != "" ? 1 : 0
  bucket = google_storage_bucket.artifacts[0].name
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${google_service_account.dataproc_rules[0].email}"
}
