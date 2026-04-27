# Publishing (PyPI, containers, CI)

Source builds and an uploadable `dist/` are produced by the **Release build** workflow (`.github/workflows/release-sdist.yml`, workflow name: `Release build`). It runs on `workflow_dispatch` and on tags `v*`, builds an sdist and wheel, and stores them as a workflow artifact.

## Local build

```bash
python -m pip install -U build
python -m build
```

Artifacts appear under `dist/`.

## PyPI (org-specific)

- Configure **[trusted publishing](https://docs.pypi.org/trusted-publishers/)** in your PyPI org for this repository, or use API tokens in a private release job.

### Optional: publish from GitHub Actions

The **Release build** workflow (`.github/workflows/release-sdist.yml`) can upload to PyPI **only** when you run it manually (**Actions → Release build → Run workflow**) and enable the input **“Upload dist/ to PyPI”**. Requirements:

1. In PyPI, add this repo as a **trusted publisher** for your package.
2. In GitHub, create an **environment** named **`pypi`** (the workflow uses `environment: pypi` for the publish job). Add any protection rules you need.
3. The publish job uses **OIDC** (`id-token: write`); it does not use a long‑lived PyPI password in the workflow.

The default `push` to tags `v*` only **builds** and uploads the **artifact**; it does **not** publish to PyPI unless you use `workflow_dispatch` with the checkbox set.

## Docker image

- `Dockerfile` and `docker-compose.yml` in the repo root build and run the API. Pushing a tag to a container registry and wiring CI is **org-specific**; mirror the same pattern you use for other services (GHCR, ECR, ACR, etc.).

## Related docs

- [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) — local PyPI build snippet and the `httpx` / TestClient version note.
- [ROADMAP.md](ROADMAP.md) — phase notes for release automation.
