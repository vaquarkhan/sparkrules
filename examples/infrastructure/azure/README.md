# Azure — Synapse / HDInsight / AKS + SparkRules (Terraform)

## Targets

| Service | SparkRules integration |
|---------|------------------------|
| **Azure Synapse Spark pools** | `%pip install sparkrules[spark]`, upload DRL to **workspace** or **ADLS** |
| **AKS** + Spark Operator | Same as EKS: PySpark image with wheel; IRSA equivalent = **managed identity** on pods |
| **HDInsight / HBase edge** | Legacy; prefer Synapse or OSS Spark on AKS |

## This Terraform

Optional **resource group**, **storage account**, and **container** for DRL + wheel staging. Synapse links to ADLS Gen2 via **linked service** (create in Synapse Studio or extend this TF with `azurerm_synapse_*`).

## Identity

- Use **user-assigned managed identity** on Synapse / Spark pool for **ABFS** (`abfss://`) read of rules.
- Never put production secrets in notebooks; use **Key Vault** references.

## References

- `deploy/azure-synapse/` in the repo root (if present).
