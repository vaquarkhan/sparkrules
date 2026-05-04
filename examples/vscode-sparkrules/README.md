# VS Code / Cursor extension (SparkRules DRL)

Minimal extension that runs **`python -m sparkrules.tools.cli lsp-check --file <path>`** on save and publishes **Diagnostics** (errors/warnings from the parser).

## Setup

```bash
cd examples/vscode-sparkrules
npm install
npm run compile
```

Press **F5** in VS Code (Run Extension Development Host).

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `sparkrules.pythonPath` | `python` | Interpreter with `sparkrules` installed |

## Packaging

```bash
npm install -g @vscode/vsce
vsce package
```

Install the generated `.vsix` from the command palette (**Extensions: Install from VSIX**).
