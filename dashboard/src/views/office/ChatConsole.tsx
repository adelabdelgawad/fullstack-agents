import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { getJson, postJson } from "../../lib/api";
import { needsHuman, STATE_TEXT } from "../../lib/cards";
import { esc } from "../../lib/format";
import type { Card } from "../../lib/types";
import { openCard, toast, useStore } from "../../store";
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

function Sidebar({ cards, current, pick }: { cards: Card[]; current: Card | null; pick: (key: string) => void }) {
  return (
    <nav className="chat-sidebar" aria-label="Running sessions">
      {cards.map((card) => {
        const state = card.sessions[0]?.state || "";
        return (
          <button
            key={card.key}
            type="button"
            className={card.key === current?.key ? "on" : ""}
            aria-current={card.key === current?.key}
            onClick={() => pick(card.key)}
          >
            <span className="chat-sidebar-title">{sessionTitle(card)}</span>
            <span className={`chat-state ${needsHuman(card) ? "ask" : state}`}>
              {needsHuman(card) ? "needs you" : STATE_TEXT[state] || state || card.phase}
            </span>
          </button>
        );
      })}
    </nav>
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
  useEffect(() => end.current?.scrollIntoView({ block: "end" }), [messages.length]);
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

/** The CTO console as a chat: running sessions on the left, the selected session's conversation on the right. */
export function ChatConsole({ close, decisions, title }: { close: () => void; decisions: boolean; title: string }) {
  const all = useStore((storeState) => storeState.state?.cards || []);
  const panes = useStore((storeState) => storeState.state?.session_panes || {});
  const cards = decisions ? all.filter(needsHuman) : all;
  const [key, setKey] = useState<string | null>(null);
  const [terminal, setTerminal] = useState(false);
  const current = cards.find((card) => card.key === key) || cards[0] || null;
  const sid = current?.sessions[0]?.id;
  const messages = useConversation(sid);
  useEffect(() => {
    const onKey = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") close();
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
        <Sidebar cards={cards} current={current} pick={setKey} />
        <section className="chat-main" aria-label="Conversation">
          {current ? (
            <>
              <header className="chat-head">
                <strong>{sessionTitle(current)}</strong>
                <div>
                  <button type="button" aria-pressed={terminal} onClick={() => setTerminal(!terminal)}>
                    {terminal ? "Chat" : "Terminal"}
                  </button>
                  <button type="button" onClick={() => openCard(current.key)}>
                    Open card
                  </button>
                </div>
              </header>
              {terminal ? <CardTerminal key={current.key} card={current} /> : <Thread messages={messages} />}
              {!terminal && <Composer pane={sid ? panes[sid] : undefined} />}
            </>
          ) : (
            <div className="chat-thread chat-empty">{decisions ? "No decisions waiting." : "No live sessions."}</div>
          )}
        </section>
      </div>
    </div>
  );
}
