# Where documentation lives, and Cursor / MCP

## Project documentation (in this repository)

| What | Path |
|------|------|
| Onboarding and **requirements** (glossary, architecture) | [README.md](../README.md) |
| Current **test counts** and **coverage** gate | [BUILD_STATUS.md](../BUILD_STATUS.md) |
| Roadmap, phases, agent rules, exit criteria | [idea-brainstrom.txt](../idea-brainstrom.txt) or [idea-brainstrom.md](../idea-brainstrom.md) (same content, choose one) |
| kiro blueprint | Referenced in README — `.kiro/specs/...` is **not** in this tree; README + tests are the Phase 1 spec surface |

**Tip in Cursor / VS Code:** Use **Go to file** (Ctrl+P) and type `README` or `BUILD` to open these quickly. You can also **@ mention** a file in chat (e.g. `@README.md`) to attach it to the model context.

## Why `import sre` can fail after `pip install`

On Windows, **`pip` and `python` may point to different installations**. Always use the same interpreter for install and for running code:

```powershell
cd path\to\sparkrules
py -3.11 -m pip install -e ".[test]"
py -3.11 -c "import sre; print('ok', sre.__name__)"
```

If you are not in an activated venv, use **the same** `python` (or `py -3.11`) for both commands. Do not rely on a bare `pip` from another PATH entry.

**Temporary** run without install (e.g. CI or one-off script):

```powershell
$env:PYTHONPATH = "src"
python -c "import sre; print('ok')"
```

## MCP in Cursor (not stored in this repo)

**MCP (Model Context Protocol)** is a way to connect **Cursor** (or other clients) to **external tools and data** (databases, docs sites, etc.). It is **configured in the Cursor / IDE app**, not inside the `sparkrules` git tree.

- To see or add MCP servers: open **Cursor Settings** → search for **MCP** or use the official [Cursor documentation](https://docs.cursor.com) (search “MCP”).
- This project does **not** ship an MCP config file; your team can add a server that indexes your wiki or `README.md` if you want the AI to pull that context automatically.

**Docs you “cannot see” in chat:** The model only sees what you **paste**, **@ attach**, or what your **MCP / rules / codebase index** provide. If something is not in the repo, attach a link or file, or add an MCP server for that source.
