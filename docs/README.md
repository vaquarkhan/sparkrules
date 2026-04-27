# SparkRules — documentation

This folder is the **documentation hub** for the [sparkrules](https://github.com/vaquarkhan/sparkrules) repository (similar in spirit to [MCP-Bastion docs](https://github.com/vaquarkhan/MCP-Bastion/tree/main/docs): discoverable topics, stable links for citation, and clear navigation).

## Discover

| Document | What you get |
|----------|----------------|
| [**REQUIREMENTS.md**](REQUIREMENTS.md) | Full **requirements** (Introduction, Glossary, Architecture mermaid diagrams, **Requirement 1–42** with acceptance criteria). This is the canonical product/spec text for the Phase 1 reference build. |
| [**CURSOR_DOCS_MCP.md**](CURSOR_DOCS_MCP.md) | Editable install (`import sre`), where IDE/MCP fit, and how to attach files in Cursor. |
| [**PHASE1_STATUS.md**](PHASE1_STATUS.md) | One-page **done vs out-of-scope** for the blueprint (Phase 1 “full or nothing” checklist). |
| [Building & coverage](../BUILD_STATUS.md) | Current **pytest** counts, **100%** `sre` line coverage gate, and last-updated date. |
| [Examples](../examples/README.md) | **DRL** samples, **decision table JSON**, Python evaluation scripts. |
| [Roadmap & agent process](../idea-brainstrom.txt) | Phases, property ladder, and exit criteria (`idea-brainstrom.md` is the same content in Markdown). |
| [Repository README](../README.md) | **Overview**, quick start, discover table, citation, contributing. |

## File map (citations)

When you cite or link documentation in issues or papers, prefer **stable paths**:

| Citation key | Path |
|--------------|------|
| Requirements (full) | `docs/REQUIREMENTS.md` |
| This index | `docs/README.md` |
| IDE / MCP setup | `docs/CURSOR_DOCS_MCP.md` |
| Build status | `BUILD_STATUS.md` (repository root) |
| Examples | `examples/README.md` |
| Citation file (CFF) | `CITATION.cff` (repository root) |

## External reference (style)

The layout here follows a **discoverable docs + root README + CITATION** pattern as used in [MCP-Bastion](https://github.com/vaquarkhan/MCP-Bastion) ([docs tree](https://github.com/vaquarkhan/MCP-Bastion/tree/main/docs), [CITATION.cff](https://github.com/vaquarkhan/MCP-Bastion/blob/main/CITATION.cff)).

## `.kiro` blueprint

The repository may refer to `.kiro/specs/.../requirements.md`. That path is **not** shipped here; use [**REQUIREMENTS.md**](REQUIREMENTS.md) instead for in-tree work.
