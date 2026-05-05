# Architecture Scope & Extension Points

This document describes SparkRules' architecture decisions and where to extend the system for your deployment. It complements [FEATURES.md](FEATURES.md) (capabilities) and [ROADMAP.md](ROADMAP.md) (planned work).

---

## Design philosophy

SparkRules is **Python-first, Spark-ready**. The core engine runs anywhere Python runs  -  laptops, CI, containers, serverless  -  with zero infrastructure dependencies. When you need cluster-scale evaluation, wire `apply_drl()` into your PySpark job. This separation is intentional: it keeps the development loop fast and the deployment flexible.

---

## Identity and access

SparkRules provides a flexible, layered authentication model designed to integrate with your existing infrastructure:

| Mode | Use case | How it works |
|------|----------|-------------|
| **API key** (`SPARKRULES_API_KEY`) | Simple deployments | Single shared key for all mutating + sensitive endpoints |
| **Header-based RBAC** | Gateway-fronted services | `X-Principal`, `X-Roles`, `X-Tenant-Id` headers from your gateway |
| **OIDC** | Enterprise SSO | JWT parsing with issuer/audience checks  -  pair with your IdP gateway for full verification |
| **mTLS** | Service mesh | Client cert subject from gateway header (`X-Client-Cert-Subject`) |
| **Local dev** | Development/CI | `SPARKRULES_DEV_ALLOW_DEFAULT_SUPERUSER=true` for frictionless local work |

**Built-in roles:** `rule_reader`, `rule_author`, `rule_admin`, `run_operator`, `dq_steward`, `ai_reviewer`, `pii_reveal`, `platform_admin`

**Extension point:** For production OIDC/SAML with full JWT signature verification, place SparkRules behind an API gateway (Kong, Envoy, AWS ALB, etc.) that handles token validation and passes identity headers. The service is designed for this pattern.

---

## Execution architecture

### Pure Python path (default)

The API server, Workbench, and simulations run in a single Python process. This is the fast-feedback path for rule authoring, validation, and testing.

**Important:** On the default API path, `SparkSession.getActiveSession()` is `None`. No Spark cluster is involved. PySpark may be installed as a library dependency, but the engine does not create a session or distribute work unless you explicitly wire `apply_drl()` in your own PySpark job.

| Characteristic | Detail |
|---------------|--------|
| Runtime | Single CPython process (uvicorn) |
| Throughput | ~199k raw `evaluate_rule`/sec; ~12k 10-rule chain/sec; ~200-500 API req/sec |
| Best for | Development, CI, low-volume APIs, rule authoring, batch jobs under 1M rows |

### Spark path (opt-in)

For high-volume batch processing, `apply_drl()` distributes rule evaluation across a Spark cluster via `mapPartitions`.

| Characteristic | Detail |
|---------------|--------|
| Runtime | Your Spark cluster (EMR, Databricks, Dataproc, etc.) |
| Throughput | Scales linearly with executor count |
| Best for | Millions/billions of rows, lakehouse pipelines |

**Extension point:** The `CompiledRulePackage` can be serialized and broadcast to workers. For maximum throughput, broadcast the compiled package instead of raw DRL text. See `sparkrules/transport/broadcaster.py`.

### Native Rust accelerator (optional, local only)

**`sparkrules[native]` / `sparkrules-native`** — optional PyO3 extension for faster **single-process** scoring (`sparkrules.native.NativeRuleExecutor`). Rules are still parsed in Python; the extension consumes `RulePack.to_native_json()`.

- **Not wired to Spark executors** — cluster rule evaluation remains `SparkRuleExecutor` / Catalyst; see [CHOOSING_A_BACKEND.md](CHOOSING_A_BACKEND.md) and [NATIVE_TIER1.md](NATIVE_TIER1.md).
- **Build:** requires a working Rust **linker** (MSVC Build Tools on Windows, or GNU/LLVM per [NATIVE_TIER1.md](NATIVE_TIER1.md)); CI runs `cargo fmt`, `clippy`, `test`, and **maturin** in `native-wheels.yml`.
- **`SPARKRULES_NATIVE_DISABLE=1`** — skip loading native even if the wheel is installed.

---

## Storage and data integration

### Metadata store

SparkRules ships with pluggable metadata backends:

| Backend | Status | Use case |
|---------|--------|----------|
| `in_memory` | Production-ready | Development, testing, single-process deployments |
| `duckdb` | Production-ready (optional `duckdb` extra) | Embedded SQL file via `db_path`; versioned metadata |
| `postgres` | Production-ready (optional driver extra) | Shared metadata; pass `database_url` / `dsn` |
| `iceberg` | Partial | `IcebergHydratingRuleStore` with callable `iceberg_version_sink` or `pyiceberg_table` append sink; **without** a sink, falls back to `PickleFileStore` on disk (`store_path`) for dev/tests |

> **Note:** `create_rule_store` accepts `in_memory`, `duckdb`, `postgres`, and `iceberg` (see `sparkrules.store.backends`). For ad-hoc file persistence without SQL, use the `iceberg` backend without a sink (pickle fallback) or construct `PickleFileStore` directly from `sparkrules.store`.

**Extension point:** Implement the store interface for your preferred backend (Redis, DynamoDB, etc.).

### Output sinks

Supported output formats: `iceberg`, `delta`, `hudi`, `parquet`  -  configured via `EngineConfig`, no code changes needed.

---

## Workbench capabilities

The browser-based Rules Workbench provides:

- Monaco DRL editor with syntax highlighting
- Real-time validation and LSP diagnostics
- Rule simulation with fact input
- Asset management with search and filters
- Governance pane (promotion pins, deprecations)
- Light/dark theme
- Overview dashboard with stats and charts
- Optional **browser login** (`SPARKRULES_WORKBENCH_AUTH`): default **`admin` / `admin`** only in documented dev settings; production operators set **`SPARKRULES_WORKBENCH_USER`** / **`SPARKRULES_WORKBENCH_PASSWORD`** and redeploy—see **[WORKBENCH_LOGIN.md](WORKBENCH_LOGIN.md)**.

**Extension point:** The Workbench is a static HTML/JS shell calling the REST API. Add custom views by extending the API and the static shell, or build a separate React/Vue frontend against the same endpoints.

---

## Performance optimization paths

SparkRules prioritizes correctness and portability. For teams needing higher throughput:

| Optimization | Approach |
|-------------|----------|
| **Parse caching** | LRU cache keyed by DRL hash to avoid re-parsing on repeated calls |
| **Compiled packages** | Use `RuleCompiler` to pre-compile rule sets; broadcast to Spark workers |
| **Discrimination networks** | `DiscriminationNetwork` is available for alpha-node filtering on large rule sets |
| **Batch evaluation** | `BatchEvaluator` amortizes setup cost across multiple facts |
| **Typed output columns** | Replace JSON `out_json` with typed Spark structs for Catalyst optimization |

---

## Platform deployment

SparkRules runs on any platform that supports Python 3.11+:

| Platform | Support | Notes |
|----------|---------|-------|
| **Local / Docker** | Full | `docker compose up --build` |
| **Kubernetes** | Full | Manifests in `deploy/k8s/` |
| **AWS Glue** | Config-driven | See `deploy/aws-glue/` |
| **Databricks** | Config-driven | See `deploy/databricks/` |
| **GCP Dataproc** | Config-driven | See `deploy/gcp-dataproc/` |
| **Azure Synapse** | Config-driven | See `deploy/azure-synapse/` |

Platform switching is configuration-only  -  no code changes between environments.

---

## Non-blocking backlog

Optional items are summarized in **[PENDING_NON_BLOCKING.md](PENDING_NON_BLOCKING.md)**. They do not block using the core engine or API in production.

**Native Cython/Rust acceleration:** Not implemented as a supported wheel in this repository—the **`examples/native/`** tree is a **bridge template and PyO3 starter**, not a finished hot loop. The engine you install from PyPI uses **CPython** paths unless you build and wire your own native extension separately.

---

## Future directions

See [ROADMAP.md](ROADMAP.md) for planned work. Community contributions welcome for:

- CEP (Complex Event Processing) patterns
- Full DMN (FEEL, DRD, DMN-TCK conformance) beyond the minimal Camunda-style table subset
- Visual rule graph designer (React Flow)
- Bulk simulation upload (CSV/JSONL)
- Full run history browser
- Additional metadata store backends
