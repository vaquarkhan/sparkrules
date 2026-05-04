# iam-role-s3-bucket-access-aws

Attaches an **inline IAM policy** to a role so Spark / Glue / EMR jobs can **list** the bucket and **read/write/delete** objects (e.g. `rules/*.drl`, `test-data/*.json`).

Use **one artifacts bucket** and separate prefixes; you rarely need a second bucket for “test data” unless compliance requires isolation.

Parent roots pass `create = true` only when the target role and bucket exist in the same apply.
