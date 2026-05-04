# Module: `s3-artifacts-aws`

Creates an **encrypted private S3 bucket** for SparkRules DRL, wheels, job logs, and checkpoint path prefixes (bucket policies are caller-specific—attach in root module).

## Inputs

See `variables.tf`. Core: `create`, `name_prefix`, `account_id`.

## Outputs

`bucket_id`, `bucket_arn`, `bucket_domain_name`
