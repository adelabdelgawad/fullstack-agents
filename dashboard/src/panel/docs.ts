import { writeClipboard } from "../lib/clipboard";
import { esc } from "../lib/format";
import { saidText } from "../lib/markup";
import type { DashState, Session } from "../lib/types";

export const COPY_ICON =
  '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';
const CHECK_ICON =
  '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m5 12 4 4L19 6"/></svg>';

export function resumeCmd(s: Session, state: DashState | null): string {
  if (s.engine === "codex") return `codex resume ${s.id}`;
  if (s.engine && s.engine !== "claude") return `${s.engine} in herdr pane ${state?.session_panes[s.id] || ""}`;
  return s.title ? `claude --resume "${s.title}"` : `claude --resume ${s.id}`;
}

export function resumeHtml(s: Session, state: DashState | null): string {
  return `<div class="now">
    <div><b>${esc(s.title || s.name)}</b></div>
    <div class="lbl">Session id</div><div class="mono">${esc(s.id)}</div>
    <div class="lbl">Resume with</div><div class="mono">${esc(resumeCmd(s, state))}</div>
  </div>`;
}

export async function copyDoc(button: HTMLButtonElement, state: DashState | null): Promise<void> {
  let ok = false;
  const title = button.dataset.title || (button.dataset.title = button.title);
  try {
    const response = button.dataset.said
      ? null
      : await fetch(
          `/api/doc?sid=${encodeURIComponent(button.dataset.docSid || "")}&path=${encodeURIComponent(button.dataset.doc || "")}`,
        );
    const text = button.dataset.said
      ? saidText(button.dataset.said, state)
      : response?.ok
        ? await response.text()
        : null;
    if (text !== null) ok = await writeClipboard(text || "");
  } catch {
    ok = false;
  }
  button.innerHTML = ok ? CHECK_ICON : "✕";
  button.classList.toggle("ok", ok);
  button.title = ok ? "Copied" : "Copy failed";
  setTimeout(() => {
    button.innerHTML = COPY_ICON;
    button.classList.remove("ok");
    button.title = title;
  }, 1500);
}
