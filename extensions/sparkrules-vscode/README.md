# SparkRules (DRL) — VS Code extension

Minimal companion for editing `.drl` files locally: language id, comments/brackets, and a command to open hosted docs.

**Diagnostics and completions:** use the **Workbench** (`pip install 'sparkrules[api]'` → `/workbench/`) for server-backed LSP, or run `sparkrules-cli lsp-check`.

## Install from folder

```bash
code --install-extension /path/to/sparkrules/extensions/sparkrules-vscode
```

Or in VS Code: **Extensions** → **⋯** → **Install from VSIX…** after packaging with `vsce package` (optional dev dependency).

## Commands

- **SparkRules: Open documentation** — opens [sparkrules.readthedocs.io](https://sparkrules.readthedocs.io/).

## License

Apache-2.0 (same as SparkRules).
