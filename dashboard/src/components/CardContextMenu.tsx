import type { KeyboardEvent as ReactKeyboardEvent, MouseEvent as ReactMouseEvent } from "react";
import { useEffect, useLayoutEffect, useRef } from "react";
import { copyText } from "../lib/clipboard";
import { esc } from "../lib/format";
import { closeCtx, load, openCard, openCtx, store, toast, toggleFavourite, useStore } from "../store";
import { openHerdrConfirm, openHerdrContextMenu } from "../terminal/HerdrOverlay";

const cardPane = (card: HTMLElement): string => (store.get().state?.session_panes || {})[card.dataset.sid || ""] || "";

function endSession(card: HTMLElement): void {
  const pane = cardPane(card);
  const name = card.querySelector(".feature")?.textContent || card.dataset.sid || "";
  if (!pane) return;
  openHerdrConfirm(
    "End session?",
    `${name} — closes herdr pane ${pane} and stops the agent running in it. Unsaved work in that session is lost.`,
    "pane.close",
    { pane_id: pane },
    card,
    {
      confirm: "end session",
      after: () => {
        toast(`<b>Ended</b> ${esc(name)}`, "blue");
        load();
      },
    },
  );
}

interface MenuView {
  open: boolean;
  fav: boolean;
  favOn: boolean;
  copy: boolean;
  end: boolean;
  endTitle: string;
}

// Attributes appear on first open and persist while the menu is hidden.
function menuView(card: HTMLElement): MenuView {
  const favEl = card.querySelector("[data-fav]");
  const pane = cardPane(card);
  return {
    open: !card.dataset.key,
    fav: !favEl,
    favOn: !!favEl && favEl.getAttribute("aria-pressed") === "true",
    copy: !card.dataset.sid,
    end: !pane,
    endTitle: pane ? `Close herdr pane ${pane} and stop this session` : "This session is not running in a herdr pane",
  };
}

function onDocContextMenu(e: MouseEvent): void {
  const target = e.target as HTMLElement;
  const box = target.closest<HTMLElement>("[data-herdr-pane-context]");
  const herdrData = store.get().herdrData;
  const pane = box && herdrData && (herdrData.panes || []).find((x) => x.pane_id === box.dataset.herdrPaneContext);
  if (pane) {
    e.preventDefault();
    closeCtx();
    openHerdrContextMenu("pane", pane, e.clientX, e.clientY, box!);
    return;
  }
  const card = target.closest<HTMLElement>("#main .card");
  if (!card) {
    closeCtx();
    return;
  }
  e.preventDefault();
  const r = card.getBoundingClientRect();
  openCtx(card, e.clientX || r.left + 12, e.clientY || r.top + 12);
}

function onDocClick(e: MouseEvent): void {
  if (!(e.target as HTMLElement).closest("#ctx")) closeCtx();
}

const onDismiss = () => {
  closeCtx();
};

function useCtxListeners(): void {
  useEffect(() => {
    document.addEventListener("contextmenu", onDocContextMenu);
    document.addEventListener("click", onDocClick);
    addEventListener("scroll", onDismiss, true);
    addEventListener("resize", onDismiss);
    return () => {
      document.removeEventListener("contextmenu", onDocContextMenu);
      document.removeEventListener("click", onDocClick);
      removeEventListener("scroll", onDismiss, true);
      removeEventListener("resize", onDismiss);
    };
  }, []);
}

function onMenuKeyDown(m: HTMLElement | null, e: ReactKeyboardEvent<HTMLDivElement>): void {
  if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
  e.preventDefault();
  if (!m) return;
  const items = [...m.querySelectorAll<HTMLButtonElement>("button:not(:disabled)")];
  const i = items.indexOf(document.activeElement as HTMLButtonElement);
  items[(i + (e.key === "ArrowDown" ? 1 : items.length - 1)) % items.length].focus();
}

function onMenuClick(card: HTMLElement | undefined, e: ReactMouseEvent<HTMLDivElement>): void {
  const b = (e.target as HTMLElement).closest<HTMLButtonElement>("[data-act]");
  if (!b || b.disabled || !card) return;
  const act = b.dataset.act;
  closeCtx();
  if (act === "open") openCard(card.dataset.key!);
  else if (act === "fav") toggleFavourite(card.dataset.key!);
  else if (act === "end") endSession(card);
  else if (act === "copy") copyText(card.dataset.sid!).then(() => toast(`<b>Copied</b> ${esc(card.dataset.sid)}`, "blue"), () => toast("<b>Copy failed</b>", "red"));
}

export function CardContextMenu() {
  const ctx = useStore((s) => s.ctx);
  const ref = useRef<HTMLDivElement>(null);
  const last = useRef<MenuView | null>(null);
  useCtxListeners();

  useLayoutEffect(() => {
    const m = ref.current;
    if (!m || !ctx) return;
    m.style.left = Math.max(8, Math.min(ctx.x, innerWidth - m.offsetWidth - 8)) + "px";
    m.style.top = Math.max(8, Math.min(ctx.y, innerHeight - m.offsetHeight - 8)) + "px";
    const first = m.querySelector<HTMLButtonElement>("button:not(:disabled)");
    if (first) first.focus();
  }, [ctx]);

  if (ctx) last.current = menuView(ctx.cardEl);
  const v = last.current;

  return (
    <div id="ctx" role="menu" aria-label="Card actions" hidden={!ctx} ref={ref} onKeyDown={(e) => onMenuKeyDown(ref.current, e)} onClick={(e) => onMenuClick(ctx?.cardEl, e)}>
      <button role="menuitem" data-act="open" disabled={v?.open}>
        Open
      </button>
      <button role="menuitem" data-act="fav" disabled={v?.fav}>
        {v?.favOn ? "Unmark favourite" : "Mark favourite"}
      </button>
      <button role="menuitem" data-act="copy" disabled={v?.copy}>
        Copy session id
      </button>
      <button role="menuitem" data-act="end" className="danger" disabled={v?.end} title={v?.endTitle}>
        End session
      </button>
    </div>
  );
}
