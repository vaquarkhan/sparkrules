provider "aws" {
  region = var.aws_region
}

data "aws_partition" "current" {}
data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
}

# Cluster service role (attach node group / IRSA policies separately).
data "aws_iam_policy_document" "eks_cluster_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["eks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "eks_cluster" {
  count              = var.create_resources ? 1 : 0
  name               = "${var.name_prefix}-cluster-svc"
  assume_role_policy = data.aws_iam_policy_document.eks_cluster_assume.json
  tags = {
    Purpose = "sparkrules-eks"
  }
}

resource "aws_iam_role_policy_attachment" "eks_cluster_policy" {
  count      = var.create_resources ? 1 : 0
  role       = aws_iam_role.eks_cluster[0].name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonEKSClusterPolicy"
}

data "aws_iam_policy_document" "eks_node_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.${data.aws_partition.current.dns_suffix}"]
    }
  }
}

resource "aws_iam_role" "eks_node" {
  count              = var.create_resources ? 1 : 0
  name               = "${var.name_prefix}-node"
  assume_role_policy = data.aws_iam_policy_document.eks_node_assume.json
  tags = {
    Purpose = "sparkrules-eks-node"
  }
}

resource "aws_iam_role_policy_attachment" "eks_worker_node_policy" {
  count      = var.create_resources ? 1 : 0
  role       = aws_iam_role.eks_node[0].name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonEKSWorkerNodePolicy"
}

resource "aws_iam_role_policy_attachment" "eks_cni_policy" {
  count      = var.create_resources ? 1 : 0
  role       = aws_iam_role.eks_node[0].name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonEKS_CNI_Policy"
}

resource "aws_iam_role_policy_attachment" "ecr_readonly" {
  count      = var.create_resources ? 1 : 0
  role       = aws_iam_role.eks_node[0].name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

# Artifacts bucket + IAM: Spark workloads on nodes (e.g. Spark Operator) can load DRL / facts from S3.
module "artifacts" {
  source = "../../modules/s3-artifacts-aws"

  create        = var.create_resources
  name_prefix   = var.name_prefix
  account_id    = local.account_id
  force_destroy = false
}

module "eks_node_sparkrules_s3" {
  count  = var.create_resources ? 1 : 0
  source = "../../modules/iam-role-s3-bucket-access-aws"

  create      = true
  role_name   = aws_iam_role.eks_node[0].name
  policy_name = "${var.name_prefix}-node-sparkrules-s3"
  bucket_arn  = module.artifacts.bucket_arn
}
