# AWS — Terraform quick links

| Subfolder | Service | Use case |
|-----------|---------|----------|
| [emr/](emr/) | Amazon EMR | Long-running Spark clusters, `spark-submit`, Kafka connectors |
| [glue/](glue/) | AWS Glue | Managed Glue Spark jobs (scheduled or on-demand) |
| [eks/](eks/) | Amazon EKS | Spark Operator / EMR on EKS, PySpark in containers |

Shared IAM and S3 patterns are **not duplicated** across folders; pick the stack that matches your platform team’s standards.
