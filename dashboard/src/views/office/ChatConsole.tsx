import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { getJson, postJson } from "../../lib/api";
import { cardAgents, needsHuman, STATE_TEXT } from "../../lib/cards";
import { esc } from "../../lib/format";
import type { Card } from "../../lib/types";
import { load, openCard, toast, useStore } from "../../store";
import { openHerdrConfirm, openNewSession } from "../../terminal/HerdrOverlay";
import { CardTerminal } from "../../terminal/CardTerminal";

interface Message {
  role: "user" | "assistant";
  text: string;
  at: number;
}

const REFRESH_MS = 4000;

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

/** Sessions that need you first, then the rest; each group keeps the dashboard's order (most recent first). */
export function needsYouFirst(cards: Card[]): Card[] {
  return [...cards.filter(needsHuman), ...cards.filter((card) => !needsHuman(card))];
}

/** A heading where a group starts: "Needs you" over the first, "Other sessions" over the rest when both exist. */
function sectionHeading(cards: Card[], index: number): string {
  const asks = needsHuman(cards[index]);
  if (index > 0 && needsHuman(cards[index - 1]) === asks) return "";
  if (asks) return "Needs you";
  return index > 0 ? "Other sessions" : "";
}

/** Close the session's herdr pane after a confirmation, as the Agents page's "end session" does. */
function endSession(card: Card, pane: string, anchor: HTMLElement): void {
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
  const panes = useStore((storeState) => storeState.state?.session_panes || {});
  return (
    <nav className="chat-sidebar" aria-label="Running sessions">
      <button type="button" className="chat-new" onClick={(event) => void openNewSession(event.currentTarget)}>
        + New session
      </button>
      {cards.map((card, index) => {
        const state = card.sessions[0]?.state || "";
        const heading = sectionHeading(cards, index);
        const selected = card.key === current?.key;
        return (
          <div key={card.key}>
            {heading && <span className="chat-section">{heading}</span>}
            <div className={`chat-session${selected && !picked ? " on" : ""}`}>
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

/** Bold and inline code from Markdown, as React nodes (no HTML injection); everything else stays plain text. */
export function inline(text: string): Array<string | JSX.Element> {
  return text.split(/(\*\*[^*\n]+\*\*|`[^`\n]+`)/g).map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4)
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    if (part.startsWith("`") && part.endsWith("`") && part.length > 2)
      return <code key={index}>{part.slice(1, -1)}</code>;
    return part;
  });
}

function Thread({ messages }: { messages: Message[] }) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    // Newer browsers return a Promise here; an effect must return nothing or a cleanup function.
    void end.current?.scrollIntoView({ block: "end" });
  }, [messages.length]);
  if (!messages.length) return <div className="chat-thread chat-empty">No messages yet.</div>;
  return (
    <div className="chat-thread">
      {messages.map((message, index) => (
        <div key={`${message.at}-${index}`} className={`chat-message ${message.role}`}>
          <div className="chat-bubble">{inline(message.text)}</div>
        </div>
      ))}
      <div ref={end} />
    </div>
  );
}

/** Message box: sends to the session's terminal pane, like typing in it. Enter sends, Shift+Enter adds a line. */
function Composer({ pane }: { pane: string | undefined }) {
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
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
    if (event.key === "Enter" && !event.shiftKey) void send(event);
  };
  return (
    <form className="chat-composer" onSubmit={send}>
      <textarea
        value={text}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={onKey}
        placeholder={pane ? "Reply to this session…" : "This session has no terminal pane to send to"}
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
export function ChatConsole({ close, title }: { close: () => void; title: string }) {
  const all = useStore((storeState) => storeState.state?.cards || []);
  const panes = useStore((storeState) => storeState.state?.session_panes || {});
  const cards = needsYouFirst(all);
  const [key, setKey] = useState<string | null>(null);
  const [terminal, setTerminal] = useState(false);
  const [workerId, setWorkerId] = useState<string | null>(null);
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
      if (event.key === "Escape" && !document.querySelector(".herdr-modal-backdrop")) close();
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
                <Thread messages={messages} />
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
