# Phase 1 status (reference build)

Single-page view of what **is done** vs **out of scope** for the `idea-brainstrom.md` blueprint. Authoritative test numbers: root [**BUILD_STATUS.md**](../BUILD_STATUS.md).

| Area | Status | Notes |
|------|--------|--------|
| **Tests** (default `pytest tests`) | **Done** | 328 passed, 2 skipped, 1 deselected (see BUILD_STATUS) |
| **Perf** | **Done** | `pytest tests/perf -m perf` — 1 passed |
| **Line coverage** `sre` | **Done** | 100% (`fail_under=100` in `pyproject.toml`) |
| **P1–P38 properties** | **Done** | `tests/property/`, ≥100 examples where `@given` is used |
| **Integration use cases** | **Done** | `tests/integration/` (4 modules per blueprint) |
| **Unit / ladder** | **Done** | `tests/unit/`, `test_requirement_ladder` |
| **Docs** | **Done** | `docs/REQUIREMENTS.md`, `docs/README.md`, root `README.md`, `CITATION.cff` |
| **Examples** | **Done** | `examples/` (DRL, JSON, scripts) |
| **Requirements spec source** | **Done** | `docs/REQUIREMENTS.md` is the in-repo canonical requirements/spec text |
| **Real Spark cluster / JVM** | **Out of scope** for Phase 1 gate | PySpark optional; `tests/spark` may skip without Java |
| **Real Iceberg / Delta in prod** | **Out of scope** | `IcebergLikeTable` and tests are in-process stand-ins |
| **Scala port** | **Future** (Phase 4) | |
| **Phase 2a–2n, Phase 3 UI** | **Future** | Per roadmap in `idea-brainstrom.md` §12, §28 |

**“Full or nothing” for Phase 1:** the measurable gate is green in **BUILD_STATUS.md** and the items above marked **Done**. Anything marked **Future** or **Out of scope** is not a Phase 1 partial—it is explicitly not required for the reference build.
