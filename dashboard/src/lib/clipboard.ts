function execCopy(text: string): boolean {
  const host = document.fullscreenElement ?? document.querySelector("dialog[open]") ?? document.body;
  const ta = Object.assign(document.createElement("textarea"), { value: text, readOnly: true });
  ta.style.cssText = "position:fixed;opacity:0;top:0;left:0";
  host.appendChild(ta);
  ta.focus({ preventScroll: true });
  ta.select();
  ta.setSelectionRange(0, text.length);
  try {
    return document.execCommand("copy");
  } finally {
    ta.remove();
  }
}

export async function writeClipboard(text: string): Promise<boolean> {
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      return execCopy(text);
    }
  }
  return execCopy(text);
}

export async function copyText(text: string): Promise<void> {
  if (!(await writeClipboard(text))) throw new Error("copy failed");
}
