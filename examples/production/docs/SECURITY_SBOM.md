# Software bill of materials (SBOM) and supply chain

## 1. Goals

- **Identify** every dependency in the deployed artifact (Python wheel, container image, Databricks library).
- **Detect** known vulnerabilities before promotion (CVE gates).
- **Prove** provenance (who built what, from which commit).

## 2. Python (CycloneDX)

Generate SBOM from the **exact** environment that builds production wheels:

```bash
pip install cyclonedx-bom
cyclonedx-py environment -o sbom-cdx.json
```

Or SPDX:

```bash
pip install spdx-tools reuse  # tooling varies; pick org standard
```

**CI gate**: fail build if `pip-audit` (or OSV) reports **critical** CVEs without documented exception.

## 3. Container images

- Use **multi-stage** builds; run as **non-root**.
- Attach **SBOM** at build time (Docker BuildKit `--attest type=sbom` or Syft `syft packages -o cyclonedx-json`).
- Sign with **cosign**; verify in admission controller.

## 4. Databricks / EMR

- Pin **`sparkrules==x.y.z`** in job definition; export SBOM from the same `requirements.lock` used to install on the cluster.
- Store SBOM JSON next to job **run id** in your data catalog for auditors.

## 5. Transitive risk: native extensions

When `sparkrules_native` (or PyO3 modules) ship, SBOM must include **Rust** `cargo audit` output and linked **glibc** / **openssl** versions.

## 6. Retention

Keep SBOM + image digest + Git SHA for **7 years** if you operate in regulated industries (adjust to legal).

## 7. Template

See [../sbom/cyclonedx-pipeline.example.yml](../sbom/cyclonedx-pipeline.example.yml) for a GitHub Actions–style fragment you can paste into your org pipeline.
