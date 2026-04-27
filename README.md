# sparkrules

**SparkRules** is a **Drools-style business rule engine** designed to pair with **Apache Spark**: parse rules in DRL-like syntax, evaluate them over facts, and scale execution across batches or streaming workloads. This repository is the **Python reference implementation** (`src/sre/`), with tests, a small FastAPI surface, and decision-table (XLSX) import.

**Repository:** [github.com/vaquarkhan/sparkrules](https://github.com/vaquarkhan/sparkrules)

| Topic | Link |
|--------|------|
| **Full requirements (R1–R42, glossary, architecture diagrams)** | [**docs/REQUIREMENTS.md**](docs/REQUIREMENTS.md) |
| **Phase 1 done vs out-of-scope (“full or nothing” checklist)** | [**docs/PHASE1_STATUS.md**](docs/PHASE1_STATUS.md) |
| **Documentation hub (discover, citation paths, MCP-bastion-style index)** | [**docs/README.md**](docs/README.md) |
| **Build, coverage, test counts** | [BUILD_STATUS.md](BUILD_STATUS.md) |
| **Examples (DRL, JSON, scripts)** | [examples/README.md](examples/README.md) |
| **Roadmap, phases, agent rules** | [idea-brainstrom.txt](idea-brainstrom.txt) |
| **Contributing** | [CONTRIBUTING.md](CONTRIBUTING.md) |
| **Cite this repository** | [CITATION.cff](CITATION.cff) (GitHub “Cite this repository” uses CFF) |

> **Layout note:** The long-form requirements and glossary that previously lived in this file are now in [**docs/REQUIREMENTS.md**](docs/REQUIREMENTS.md) so the README stays a short entry point. The documentation layout follows a **discoverable `docs/` + CITATION** pattern (same family as [MCP-Bastion](https://github.com/vaquarkhan/MCP-Bastion): [docs](https://github.com/vaquarkhan/MCP-Bastion/tree/main/docs), [CITATION.cff](https://github.com/vaquarkhan/MCP-Bastion/blob/main/CITATION.cff)).

---

## Why SparkRules

- **Familiar rules language** — DRL-like `when` / `then` with facts bound as `$name : Type ( condition )`, plus salience, agenda, decision tables, and simulation.
- **Spark integration path** — `sre.spark` helpers for RDD / DataFrame-style evaluation where PySpark is available.
- **Test-backed** — See [BUILD_STATUS.md](BUILD_STATUS.md) for the current `pytest` command and `sre` line coverage.

---

## Quick start

```bash
git clone https://github.com/vaquarkhan/sparkrules.git
cd sparkrules
python -m pip install -e ".[test]"
python -c "import sre; print('ok', sre.__version__)"
pytest tests/ -q
```

Use **`python -m pip`** and the **same** `python` to avoid `ModuleNotFoundError: sre` (details: [docs/CURSOR_DOCS_MCP.md](docs/CURSOR_DOCS_MCP.md)).

**Smoke the DRL parser / printer:**

```bash
python -m sre.tools.smoke_drl
python -m sre.tools.smoke_drl examples/drl/minimal.drl
```

**HTTP API (optional):**

```bash
uvicorn sre.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for OpenAPI.

---

## Who should read what

| Role | Start here |
|------|------------|
| **Developers** | [BUILD_STATUS.md](BUILD_STATUS.md), [CONTRIBUTING.md](CONTRIBUTING.md), `src/sre/` |
| **Product / compliance / BAs** | [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) (Glossary, architecture, requirements) |
| **QA** | [BUILD_STATUS.md](BUILD_STATUS.md), `tests/property/`, `tests/integration/` |
| **Platform / SRE** | [deploy/k8s/](deploy/k8s/) (sample manifests) |

---

## License

[MIT](LICENSE) — Copyright (c) 2026 Vaquar Khan (see [LICENSE](LICENSE). If `pyproject.toml` and `LICENSE` ever diverge, treat **`LICENSE` as the source of truth** for the project snapshot.)

---

## Citation

For academic or technical references, use [**CITATION.cff**](CITATION.cff) or point to the stable spec path [**docs/REQUIREMENTS.md**](docs/REQUIREMENTS.md) and this README URL.

### Related (documentation pattern reference)

- [MCP-Bastion](https://github.com/vaquarkhan/MCP-Bastion) — example of `docs/`, `CITATION.cff`, and root README structure used as a **style reference** (not a runtime dependency of sparkrules).
