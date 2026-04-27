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
- The repository workflow does **not** auto-upload to the index; it only verifies the build and archives artifacts. Add an upload step in your fork or org’s pipeline when you are ready to publish a package name you control.

## Docker image

- `Dockerfile` and `docker-compose.yml` in the repo root build and run the API. Pushing a tag to a container registry and wiring CI is **org-specific**; mirror the same pattern you use for other services (GHCR, ECR, ACR, etc.).

## Related docs

- [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) — local PyPI build snippet and the `httpx` / TestClient version note.
- [ROADMAP.md](ROADMAP.md) — phase notes for release automation.
