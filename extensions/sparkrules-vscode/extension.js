"use strict";

const vscode = require("vscode");

/**
 * @param {vscode.ExtensionContext} context
 */
function activate(context) {
  const disposable = vscode.commands.registerCommand("sparkrules.openDocs", async () => {
    await vscode.env.openExternal(vscode.Uri.parse("https://sparkrules.readthedocs.io/"));
  });
  context.subscriptions.push(disposable);
}

function deactivate() {}

module.exports = { activate, deactivate };
