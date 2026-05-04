# Workbench UX improvements (by user impact)

This document tracks **browser Workbench** (`pip install sparkrules[api]` → `/workbench/`) enhancements. Implementation lives mainly in `src/sparkrules/api/static/workbench/index.html`.

## High impact (recommended)

| Item | Status | Notes |
|------|--------|--------|
| **Namespace picker** | Done | Header **Namespace** `<select>` filled from `GET /governance/namespaces` and unique namespaces in `GET /rules/assets`, plus **Other (type)…** for custom values. Sends `X-Tenant-Id` consistently to reduce governance pinning / tenant mismatch bugs (e.g. BUG-39 class issues). |
| **Empty-store onboarding** | Done | When there are zero rule versions, Overview shows a **Get started** card (seed demo rule, import `.drl`, quick start link, Author tab) instead of only empty stat cards. |
| **Monaco DRL highlighting** | Done | `drl` language registered with Monarch tokenizer (keywords, strings, `//` and `#` comments, variables, operators). |
| **Version + author + created time in catalog** | Done | `RuleAssetResponse` includes `created_at` and `author`; assets table shows **Ver**, **Author**, **Created (UTC)**. |
| **Inline test from catalog** | Done | Each asset row has **Test** → modal with Monaco + fact JSON → `POST /simulations`. |

## Medium impact

| Item | Status | Notes |
|------|--------|--------|
| **RBAC header clutter** | Done | **X-Roles** moved under collapsible **Security** `<details>`; namespace stays visible. |
| **Toasts for HTTP errors** | Done | `getJson` / `postJson` / `patchJson` and export failures surface **toast** messages for 4xx/5xx (in addition to the status strip). |
| **Light / dark theme** | Already present | Header **Theme** toggles `data-theme` and Monaco theme (`vs` / `vs-dark`). |
| **Rule pack export** | Already present | **Download pack JSON** on Rule assets; export errors now toast. |
| **Drag-and-drop DRL on Author** | Done | Drop zone + file picker loads text into the Monaco author editor. |

## Low impact / polish

| Item | Status | Notes |
|------|--------|--------|
| **Loading feedback** | Done | `main` gets a subtle `wb-fetch-loading` opacity while assets load. |
| **Keyboard shortcuts hint** | Done | Hint under Security: Ctrl+Space, Ctrl+Enter; expand in-editor help as needed. |
| **Lineage as table** | Done | Columns: Time, Event, run_id, Principal, Resource/notes (from `payload`). |
| **Copy as curl** | Done | Advanced tools: template **curl** for `POST /simulations` (bash-style; add API key header manually if required). |
| **Cost / benchmark tab** | Done | **Cost estimate** nav tab calls `GET /workbench/cost-estimate` (same heuristic as `sparkrules-cli cost`). |

## Related docs

- [Beginner guide](beginner-guide.md) — Python-first tutorial; includes Workbench pointer.
- [Quick start](quickstart.md) — install and first API steps.
- [Governance](GOVERNANCE.md) — namespaces and pins (align header namespace with governance calls).
