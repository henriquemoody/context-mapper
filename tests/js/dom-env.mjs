// A real DOM for the node tests: the page's pure logic never touches it,
// but the panel renders into #info, and htm/preact needs a document.
import { Window } from "happy-dom";

export function installDom() {
  if (globalThis.__domInstalled) return;
  globalThis.__domInstalled = true;
  const win = new Window();
  globalThis.document = win.document;
  globalThis.Node = win.Node;
  const info = win.document.createElement("div");
  info.id = "info";
  win.document.body.appendChild(info);
}
