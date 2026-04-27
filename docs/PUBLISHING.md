# Publishing (PyPI, containers, CI)

## Source builds (sdist + wheel)

The **Release build** workflow (`.github/workflows/release-sdist.yml`, name: *Release build*) runs when:

- You push a **version tag** matching `v*` (e.g. `v0.1.0`), or  
- You run it manually from **Actions → Release build → Run workflow**.

It always **builds** and uploads a **`dist/`** workflow artifact. **PyPI upload** runs when either:

1. **Manual run** with the input **“Upload dist/ to PyPI”** enabled, or  
2. **A tag push** `v*` (same as a release), so a tagged release **also publishes to PyPI** (after you set up trusted publishing — see below).

To publish only a build (no upload), use **Run workflow** and leave the checkbox off. To publish without auto-upload on every tag, do not create the `pypi` environment or adjust the workflow; for most teams, **tag = release to PyPI** is desired.

## PyPI: trusted publishing (one-time setup)

1. On [PyPI](https://pypi.org), register your project (or claim the `sparkrules` name) and add a **trusted publisher** pointing at this **GitHub repository** and workflow **Release build** (see [PyPI trusted publishers](https://docs.pypi.org/trusted-publishers/)).
2. In GitHub: **Settings → Environments** → create an environment named **`pypi`** (the publish job uses `environment: pypi`). Add protection rules if you want (e.g. required reviewers) before a publish runs.
3. The workflow uses **OIDC** (`id-token: write`); no long‑lived PyPI password in the repo.

**Local build (smoke test):**

```bash
python -m pip install -U build
python -m build
```

Artifacts appear under `dist/`.

**Tag a release (example):**

```bash
git tag -a v0.1.0 -m "v0.1.0"
git push origin v0.1.0
```

After CI succeeds, the package should appear on PyPI (if the environment and trusted publisher are configured).

---

## Docker (GitHub Container Registry)

The **Docker** workflow (`.github/workflows/docker-publish.yml`) **builds and pushes** the image in `Dockerfile` to **`ghcr.io/<owner>/sparkrules`**.

- **On push** to `main`, `master`, or `phase-2`: an image is built and pushed (branch-based tags; **`latest`** only for the default `main`/`master` branch per workflow expression).
- **On push** of a tag `v*`: version tags and semver-style tags are applied via `docker/metadata-action`.

**Pull (example, after a successful run):**

```bash
docker pull ghcr.io/vaquarkhan/sparkrules:latest
# or a specific tag shown on the package “Packages” page for this repo
```

**Run:**

```bash
docker run --rm -p 8042:8000 ghcr.io/vaquarkhan/sparkrules:latest
```

Open http://127.0.0.1:8042/workbench/ (container listens on **8000**).

**Local compose** (no registry): the repo `docker-compose.yml` still does `build: .` for development.

**Permissions:** the workflow uses `GITHUB_TOKEN` with `packages: write` to push to GHCR. For a **private** image, set package visibility in GitHub **Packages** settings.

**`.dockerignore`:** trims build context (excludes `tests/`, `.git`, etc.); the image build still includes `pyproject.toml`, `src/`, and files copied in the `Dockerfile`.

---

## Related docs

- [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) — local install and the `httpx` / TestClient version note
- [ROADMAP.md](ROADMAP.md) — release and phase notes
- [README.md](../README.md#docker) — Docker quick start
