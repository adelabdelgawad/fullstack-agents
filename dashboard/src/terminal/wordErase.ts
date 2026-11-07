import type { Terminal } from "@xterm/xterm";

const WORD_ERASE = "\u0017";

export function isCtrlBackspace(event: KeyboardEvent): boolean {
  return event.key === "Backspace" && event.ctrlKey && !event.altKey && !event.metaKey;
}

export function wireCtrlBackspaceWordErase(term: Pick<Terminal, "attachCustomKeyEventHandler" | "input">): void {
  term.attachCustomKeyEventHandler((event) => {
    if (!isCtrlBackspace(event)) return true;
    if (event.type === "keydown") {
      event.preventDefault();
      term.input(WORD_ERASE);
    }
    return false;
  });
}
