import { execFileSync } from "child_process";
import * as vscode from "vscode";

const COLLECTION = vscode.languages.createDiagnosticCollection("sparkrules");

function runLspCheck(python: string, filePath: string): vscode.Diagnostic[] {
  const raw = execFileSync(
    python,
    ["-m", "sparkrules.tools.cli", "lsp-check", "--file", filePath],
    { encoding: "utf-8", maxBuffer: 32 * 1024 * 1024 },
  );
  const parsed = JSON.parse(raw) as {
    diagnostics: { severity: string; message: string; line: number; col: number }[];
  };
  const diags: vscode.Diagnostic[] = [];
  for (const d of parsed.diagnostics || []) {
    const s = (d.severity || "").toLowerCase();
    const sev =
      s === "error"
        ? vscode.DiagnosticSeverity.Error
        : s === "warning"
          ? vscode.DiagnosticSeverity.Warning
          : vscode.DiagnosticSeverity.Information;
    const line = Math.max(0, (d.line ?? 1) - 1);
    const col = Math.max(0, (d.col ?? 1) - 1);
    const range = new vscode.Range(line, col, line, col + 1);
    diags.push(new vscode.Diagnostic(range, d.message, sev));
  }
  return diags;
}

function refreshDocument(doc: vscode.TextDocument, python: string): void {
  if (doc.languageId !== "drl" && !doc.fileName.endsWith(".drl")) {
    return;
  }
  if (doc.isUntitled) {
    COLLECTION.set(doc.uri, [
      new vscode.Diagnostic(
        new vscode.Range(0, 0, 0, 0),
        "Save the file to enable SparkRules diagnostics (lsp-check needs a path).",
        vscode.DiagnosticSeverity.Information,
      ),
    ]);
    return;
  }
  try {
    const diags = runLspCheck(python, doc.fileName);
    COLLECTION.set(doc.uri, diags);
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    COLLECTION.set(doc.uri, [
      new vscode.Diagnostic(
        new vscode.Range(0, 0, 0, 0),
        `sparkrules lsp-check failed: ${msg}`,
        vscode.DiagnosticSeverity.Error,
      ),
    ]);
  }
}

export function activate(context: vscode.ExtensionContext): void {
  const python =
    vscode.workspace.getConfiguration("sparkrules").get<string>("pythonPath") || "python";

  context.subscriptions.push(
    vscode.workspace.onDidSaveTextDocument((doc) => {
      refreshDocument(doc, python);
    }),
    vscode.workspace.onDidOpenTextDocument((doc) => {
      refreshDocument(doc, python);
    }),
  );

  if (vscode.window.activeTextEditor) {
    refreshDocument(vscode.window.activeTextEditor.document, python);
  }
}

export function deactivate(): void {
  COLLECTION.clear();
}
