# Inline least-privilege S3 access for one bucket (list + read/write/delete objects).
# Use for SparkRules DRL packs, test facts JSON/Parquet, and job scratch under prefixes.

data "aws_iam_policy_document" "bucket_rw" {
  statement {
    sid    = "SparkRulesS3List"
    effect = "Allow"
    actions = [
      "s3:ListBucket",
      "s3:GetBucketLocation",
    ]
    resources = [var.bucket_arn]
  }

  statement {
    sid    = "SparkRulesS3Objects"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:AbortMultipartUpload",
    ]
    resources = ["${var.bucket_arn}/*"]
  }
}

resource "aws_iam_role_policy" "sparkrules_s3" {
  count  = var.create ? 1 : 0
  name   = var.policy_name
  role   = var.role_name
  policy = data.aws_iam_policy_document.bucket_rw.json
}
