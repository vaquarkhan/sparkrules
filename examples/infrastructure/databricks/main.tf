# Authenticate via env: DATABRICKS_HOST + DATABRICKS_TOKEN (or config profile).
provider "databricks" {
}

# When you are ready to materialize jobs, uncomment and fill:
# resource "databricks_job" "sparkrules_batch" {
#   count = var.create_resources ? 1 : 0
#   name  = "${var.prefix}-sparkrules-batch"
#   job_cluster {
#     job_cluster_key = "sparkrules"
#     new_cluster {
#       num_workers   = 2
#       spark_version = "14.3.x-scala2.12"
#       node_type_id  = "i3.xlarge"
#     }
#   }
#   task {
#     task_key        = "score"
#     job_cluster_key = "sparkrules"
#     spark_python_task {
#       python_file = "/Workspace/Repos/your-repo/jobs/score_facts.py"
#     }
#   }
# }

locals {
  readme_hint = "pip install sparkrules[spark] on cluster; load DRL from DBFS or UC volume"
}
