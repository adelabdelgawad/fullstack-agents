import { writeClipboard } from "../lib/clipboard";

export interface CopyAction {
  label: string;
  run: () => Promise<void>;
}

export function showHerdrToast(message: string, action?: CopyAction): void {
  document.querySelector(".herdr-copy-toast")?.remove();
  const toast = document.createElement("div");
  toast.className = "herdr-copy-toast" + (action ? " is-failed" : "");
  const dot = Object.assign(document.createElement("span"), { className: "dot", textContent: "●" });
  const label = Object.assign(document.createElement("b"), { textContent: message });
  toast.append(dot, label);
  if (action) {
    const button = Object.assign(document.createElement("button"), { textContent: action.label });
    button.onclick = () => {
      toast.remove();
      void action.run();
    };
    toast.append(button);
  }
  ((document.fullscreenElement as HTMLElement | null) ?? document.body).append(toast);
  setTimeout(() => toast.remove(), action ? 15_000 : 1_800);
}

export async function copySelection(
  text: string,
  restore?: () => void,
  write: (value: string) => Promise<boolean> = writeClipboard,
  show: (message: string, action?: CopyAction) => void = showHerdrToast,
): Promise<void> {
  let ok = false;
  try {
    ok = await write(text);
  } catch {
    ok = false;
  }
  restore?.();
  if (ok) show(`copied ${text.length} chars`);
  else show("copy blocked by the browser", { label: `copy ${text.length} chars`, run: () => copySelection(text, restore, write, show) });
}
