import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { getJson, postJson } from "../../lib/api";
import { cardAgents, needsHuman, STATE_TEXT } from "../../lib/cards";
import { esc } from "../../lib/format";
import type { Card } from "../../lib/types";
import { keepOrder } from "./model";
import { load, openCard, toast, useStore } from "../../store";
import { openHerdrConfirm, openNewSession } from "../../terminal/HerdrOverlay";
import { filesFromPaste, LIVE_UPLOAD_MAX_BYTES, uploadFiles } from "../../terminal/files";
import { inline, Markdown } from "./markdown";
import { matchCommands, SlashMenu, useSlashCommands } from "./slash";
import { CardTerminal } from "../../terminal/CardTerminal";

interface Message {
  role: "user" | "assistant" | "tool";
  text: string;
  at: number;
}

const REFRESH_MS = 4000;
// Stable empty values: a selector returning a fresh [] or {} on every read makes React re-render forever.
const NO_CARDS: Card[] = [];
const NO_PANES: Record<string, string> = {};

function sessionTitle(card: Card): string {
  return card.sessions[0]?.name || card.title || card.label || card.key;
}

/** The lead session's chat, refreshed while open; empty until the first answer arrives. */
function useConversation(sid: string | undefined): Message[] {
  const [messages, setMessages] = useState<Message[]>([]);
  useEffect(() => {
    setMessages([]);
    if (!sid) return;
    let live = true;
    const load = () =>
      getJson<{ messages: Message[] }>(`/api/conversation?sid=${encodeURIComponent(sid)}`)
        .then((data) => live && setMessages(data.messages || []))
        .catch(() => undefined);
    void load();
    const timer = setInterval(load, REFRESH_MS);
    return () => {
      live = false;
      clearInterval(timer);
    };
  }, [sid]);
  return messages;
}

/** A subagent or background shell of the selected session. */
interface Worker {
  id: string;
  sid: string;
  label: string;
  state: string;
  shell: boolean;
}

function workersOf(card: Card | null): Worker[] {
  return (card ? cardAgents(card) : []).map((agent) => {
    const label = String(agent.label || agent.id);
    const shell = Boolean(agent.shell) || label.startsWith("shell · ");
    return { id: agent.id, sid: agent.sid, state: agent.state, shell, label: label.replace(/^shell · /, "") };
  });
}

/** The selected session's subagents and shells, grouped under it; picking one shows its output. */
function Workers({ workers, picked, pick }: { workers: Worker[]; picked: string | null; pick: (id: string) => void }) {
  const groups: Array<[string, Worker[]]> = [
    ["Subagents", workers.filter((worker) => !worker.shell)],
    ["Shells", workers.filter((worker) => worker.shell)],
  ];
  if (!workers.length) return <div className="chat-workers chat-workers-none">No subagents or shells running</div>;
  return (
    <div className="chat-workers">
      {groups.map(([name, items]) =>
        items.length ? (
          <div key={name} role="group" aria-label={name}>
            <span className="chat-workers-title">{`${name} (${items.length})`}</span>
            {items.map((worker) => (
              <button
                key={worker.id}
                type="button"
                className={worker.id === picked ? "on" : ""}
                aria-current={worker.id === picked}
                onClick={() => pick(worker.id)}
              >
                <span className={`chat-dot ${worker.state}`} aria-hidden="true" />
                <span className="chat-sidebar-title">{worker.label}</span>
              </button>
            ))}
          </div>
        ) : null,
      )}
    </div>
  );
}

/** Sessions in a fixed order: each keeps the place it first appeared in, new ones join at the end, so the list never
 * reshuffles while you work in it. Sessions that need a decision are marked red instead of moved. */
export function stableOrder(previous: string[], cards: Card[]): string[] {
  return keepOrder(
    previous,
    cards.map((card) => card.key),
  );
}

function useStableCards(cards: Card[]): Card[] {
  const order = useRef<string[]>([]);
  order.current = stableOrder(order.current, cards);
  const byKey = new Map(cards.map((card) => [card.key, card]));
  return order.current.map((key) => byKey.get(key)!);
}

/** Close the session's herdr pane after a confirmation, as the Agents page's "end session" does. */
export function endSession(card: Card, pane: string, anchor: HTMLElement): void {
  const name = sessionTitle(card);
  openHerdrConfirm(
    "End session?",
    `${name} — closes herdr pane ${pane} and stops the agent running in it. Unsaved work in that session is lost.`,
    "pane.close",
    { pane_id: pane },
    anchor,
    {
      confirm: "end session",
      after: () => {
        toast(`<b>Ended</b> ${esc(name)}`, "blue");
        void load();
      },
    },
  );
}

function Sidebar({
  cards,
  current,
  pick,
  picked,
  pickWorker,
}: {
  cards: Card[];
  current: Card | null;
  pick: (key: string) => void;
  picked: string | null;
  pickWorker: (id: string) => void;
}) {
  const panes = useStore((storeState) => storeState.state?.session_panes) || NO_PANES;
  return (
    <nav className="chat-sidebar" aria-label="Running sessions">
      <button type="button" className="chat-new" onClick={(event) => void openNewSession(event.currentTarget)}>
        + New session
      </button>
      {cards.map((card) => {
        const state = card.sessions[0]?.state || "";
        const selected = card.key === current?.key;
        return (
          <div key={card.key}>
            <div
              className={`chat-session${selected && !picked ? " on" : ""}${
                needsHuman(card) ? " ask" : state === "working" ? " working" : ""
              }`}
            >
              <button type="button" aria-current={selected} onClick={() => pick(card.key)}>
                <span className="chat-sidebar-title">{sessionTitle(card)}</span>
                <span className={`chat-state ${needsHuman(card) ? "ask" : state}`}>
                  {needsHuman(card) ? "needs you" : STATE_TEXT[state] || state || card.phase}
                </span>
              </button>
              {panes[card.sessions[0]?.id || ""] && (
                <button
                  type="button"
                  className="chat-end"
                  title="End session"
                  aria-label={`End session ${sessionTitle(card)}`}
                  onClick={(event) => endSession(card, panes[card.sessions[0].id], event.currentTarget)}
                >
                  ×
                </button>
              )}
            </div>
            {selected && <Workers workers={workersOf(card)} picked={picked} pick={pickWorker} />}
          </div>
        );
      })}
    </nav>
  );
}

/** A subagent's transcript or a shell's output, refreshed while shown. */
function WorkerOutput({ worker }: { worker: Worker }) {
  const [text, setText] = useState("");
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let live = true;
    const url = `/api/output?sid=${encodeURIComponent(worker.sid)}&id=${encodeURIComponent(worker.id)}`;
    const load = () =>
      fetch(url, { cache: "no-store" })
        .then((response) => (response.ok ? response.text() : "(this item is no longer listed)"))
        .then((body) => live && setText(body))
        .catch(() => undefined);
    void load();
    const timer = setInterval(load, REFRESH_MS);
    return () => {
      live = false;
      clearInterval(timer);
    };
  }, [worker.sid, worker.id]);
  useEffect(() => {
    void end.current?.scrollIntoView({ block: "end" });
  }, [text]);
  return (
    <div className="chat-thread">
      <pre className="chat-output">{text || "No output yet."}</pre>
      <div ref={end} />
    </div>
  );
}

/** A run of tool steps between messages: the last few, with the rest behind "+N earlier steps". */
function Steps({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  const lines = text.split("\n");
  const shown = open ? lines : lines.slice(-3);
  return (
    <div className="chat-steps">
      {lines.length > shown.length && (
        <button type="button" onClick={() => setOpen(true)}>{`+${lines.length - shown.length} earlier steps`}</button>
      )}
      {shown.map((line, index) => (
        <div key={index}>⚙ {line}</div>
      ))}
    </div>
  );
}

/** "Working" while the session runs, with what it is doing right now. */
export function workingLine(session: Card["sessions"][number] | undefined): string {
  if (!session || session.state !== "working") return "";
  const action = session.action_running && typeof session.action === "string" ? session.action : "";
  return action ? `Working · ${action}` : "Working…";
}

function Thread({ messages, working }: { messages: Message[]; working: string }) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    // Newer browsers return a Promise here; an effect must return nothing or a cleanup function.
    void end.current?.scrollIntoView({ block: "end" });
  }, [messages.length, working]);
  if (!messages.length && !working) return <div className="chat-thread chat-empty">No messages yet.</div>;
  return (
    <div className="chat-thread">
      {messages.map((message, index) =>
        message.role === "tool" ? (
          <Steps key={`${message.at}-${index}`} text={message.text} />
        ) : (
          <div key={`${message.at}-${index}`} className={`chat-message ${message.role}`}>
            <div className="chat-bubble">
              {message.role === "assistant" ? <Markdown text={message.text} /> : inline(message.text)}
            </div>
          </div>
        ),
      )}
      {working && (
        <div className="chat-working" role="status">
          <span className="chat-pulse" aria-hidden="true" />
          {working}
        </div>
      )}
      <div ref={end} />
    </div>
  );
}

/** Message box: sends to the session's terminal pane, like typing in it. Enter sends, Shift+Enter adds a line. */
function Composer({ pane }: { pane: string | undefined }) {
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const commands = useSlashCommands();
  const [active, setActive] = useState(0);
  const [hidden, setHidden] = useState(false);
  const suggestions = hidden ? [] : matchCommands(commands, text);
  const [uploading, setUploading] = useState(false);
  const picker = useRef<HTMLInputElement>(null);
  /** Upload the files to this machine and add their paths to the message, as the Herdr terminal's attach does;
   * the session reads them from there (images, PDFs, code). */
  const attach = async (files: File[]) => {
    if (!files.length) return;
    if (files.some((file) => file.size > LIVE_UPLOAD_MAX_BYTES))
      return toast("<b>Attach failed</b> 50 MB maximum", "red");
    setUploading(true);
    try {
      const paths = await uploadFiles(files, "/api/herdr/file?");
      setText((current) => `${current}${current && !current.endsWith(" ") ? " " : ""}${paths.join(" ")} `);
    } catch (error) {
      toast(`<b>Attach failed</b> ${esc(error instanceof Error ? error.message : "upload failed")}`, "red");
    } finally {
      setUploading(false);
    }
  };
  const complete = (name: string) => {
    setText(`/${name} `);
    setActive(0);
  };
  const send = async (event?: FormEvent) => {
    event?.preventDefault();
    const prompt = text.trim();
    if (!prompt || !pane || sending) return;
    setSending(true);
    try {
      const result = await postJson<{ ok?: boolean; error?: string }>("/api/herdr/send", {
        pane,
        kind: "prompt",
        text: prompt,
      });
      if (!result?.ok) throw new Error(result?.error || "not sent");
      setText("");
    } catch (error) {
      toast(`<b>Send failed</b> ${esc(error instanceof Error ? error.message : "Could not send")}`, "red");
    } finally {
      setSending(false);
    }
  };
  const onKey = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    // While suggestions show: arrows move, Tab or Enter completes, Escape hides them (not the console).
    if (suggestions.length) {
      const step = { ArrowDown: 1, ArrowUp: -1 }[event.key];
      if (step) {
        event.preventDefault();
        setActive((active + step + suggestions.length) % suggestions.length);
        return;
      }
      if (event.key === "Tab" || (event.key === "Enter" && !event.shiftKey)) {
        event.preventDefault();
        complete(suggestions[Math.min(active, suggestions.length - 1)].name);
        return;
      }
      if (event.key === "Escape") {
        event.preventDefault();
        setHidden(true);
        return;
      }
    }
    if (event.key === "Enter" && !event.shiftKey) void send(event);
  };
  return (
    <form className="chat-composer" onSubmit={send}>
      <input
        ref={picker}
        type="file"
        multiple
        hidden
        onChange={(event) => {
          void attach([...(event.target.files || [])]);
          event.target.value = "";
        }}
      />
      <button
        type="button"
        className="chat-attach"
        title="Attach files"
        aria-label="Attach files"
        disabled={!pane || uploading}
        onClick={() => picker.current?.click()}
      >
        {uploading ? "…" : "📎"}
      </button>
      {suggestions.length > 0 && (
        <SlashMenu items={suggestions} active={Math.min(active, suggestions.length - 1)} pick={complete} />
      )}
      <textarea
        value={text}
        onChange={(event) => {
          setText(event.target.value);
          setActive(0);
          setHidden(false);
        }}
        onKeyDown={onKey}
        onPaste={(event) => void attach(filesFromPaste(event.nativeEvent))}
        placeholder={pane ? "Reply to this session… (/ for commands)" : "This session has no terminal pane to send to"}
        aria-label="Message"
        disabled={!pane}
        rows={2}
      />
      <button type="submit" disabled={!pane || sending || !text.trim()}>
        {sending ? "Sending…" : "Send"}
      </button>
    </form>
  );
}

/** The CTO console as a chat: running sessions on the left with the selected one's subagents and shells under it,
 * and the conversation (or the picked subagent's or shell's output) on the right. */
export function ChatConsole({
  close,
  title,
  initial,
  initialWorker,
}: {
  close: () => void;
  title: string;
  initial?: string;
  initialWorker?: string;
}) {
  const all = useStore((storeState) => storeState.state?.cards) || NO_CARDS;
  const panes = useStore((storeState) => storeState.state?.session_panes) || NO_PANES;
  const cards = useStableCards(all);
  const [key, setKey] = useState<string | null>(initial ?? null);
  const [terminal, setTerminal] = useState(false);
  const [workerId, setWorkerId] = useState<string | null>(initialWorker ?? null);
  const current = cards.find((card) => card.key === key) || cards[0] || null;
  const worker = workersOf(current).find((item) => item.id === workerId) || null;
  const pickSession = (next: string) => {
    setKey(next);
    setWorkerId(null);
  };
  const sid = current?.sessions[0]?.id;
  const messages = useConversation(sid);
  useEffect(() => {
    const onKey = (event: globalThis.KeyboardEvent) => {
      // Escape in a dialog opened from here (new or end session) closes only that dialog.
      if (event.key === "Escape" && !event.defaultPrevented && !document.querySelector(".herdr-modal-backdrop"))
        close();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [close]);
  return (
    <div className="office-console office-console-full chat-console" role="dialog" aria-modal="true" aria-label={title}>
      <div className="office-console-head">
        <h2>{title}</h2>
        <button type="button" onClick={close}>
          Close
        </button>
      </div>
      <div className="chat-layout">
        <Sidebar
          cards={cards}
          current={current}
          pick={pickSession}
          picked={worker?.id || null}
          pickWorker={setWorkerId}
        />
        <section className="chat-main" aria-label="Conversation">
          {current ? (
            <>
              <header className="chat-head">
                <strong>{worker ? `${sessionTitle(current)} › ${worker.label}` : sessionTitle(current)}</strong>
                <div>
                  <button
                    type="button"
                    aria-pressed={terminal}
                    onClick={() => {
                      setWorkerId(null);
                      setTerminal(!terminal);
                    }}
                  >
                    {terminal ? "Chat" : "Terminal"}
                  </button>
                  <button type="button" onClick={() => openCard(current.key)}>
                    Open card
                  </button>
                </div>
              </header>
              {worker ? (
                <WorkerOutput key={worker.id} worker={worker} />
              ) : terminal ? (
                <CardTerminal key={current.key} card={current} />
              ) : (
                <Thread messages={messages} working={workingLine(current.sessions[0])} />
              )}
              {!terminal && !worker && <Composer pane={sid ? panes[sid] : undefined} />}
            </>
          ) : (
            <div className="chat-thread chat-empty">No live sessions.</div>
          )}
        </section>
      </div>
    </div>
  );
}
