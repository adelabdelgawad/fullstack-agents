import { useEffect, useMemo, useRef, useState } from "react";
import type { Card, HerdrPane } from "../lib/types";
import { loadHerdr, useStore } from "../store";
import { mountTerminal, stopTerminal } from "./liveTerminal";

const cardPaneChoice = new Map<string, string>();

function matchedCardPane(card: Card, panes: HerdrPane[], owned: Record<string, string>): HerdrPane | null {
  const ids = [...(card.now || []), ...(card.sessions || [])].map((session) => owned[session.id]).filter(Boolean);
  const byId = panes.find((pane) => ids.includes(pane.pane_id));
  if (byId) return byId;
  const names = [
    ...(card.now || []).flatMap((session) => [session.title, session.name]),
    ...(card.sessions || []).map((session) => session.name),
  ].filter(Boolean);
  return panes.find((pane) => names.includes(pane.title)) || null;
}

interface TerminalMarkupProps {
  pane: HerdrPane | null;
  panes: HerdrPane[];
  pickMessage: string;
  onPick: (paneId: string) => void;
}

function TerminalHead({ pane }: { pane: HerdrPane }) {
  return (
    <div className="terminal-head">
      <span className="terminal-pane-title"> {pane.title || pane.pane_id} </span>
      <span className={`chip st-${pane.status}`}>{pane.status}</span>
      <div className="terminal-source">
        <button data-mode="live" aria-pressed="true">
          Live
        </button>
        <button data-mode="history" aria-pressed="false">
          History
        </button>
        <button data-attach="" aria-label="Attach files" title="Attach files: their paths are typed into the session">
          +
        </button>
        <input type="file" multiple hidden data-attach-input="" />
      </div>
    </div>
  );
}

function TerminalScreen({ pane }: { pane: HerdrPane }) {
  return (
    <div className="terminal-screen-box" data-herdr-pane-context={pane.pane_id}>
      <div className="terminal-live"></div>
      <div className="terminal-drop" aria-hidden="true">
        <span>+</span>
        <b>Drop to attach</b>
      </div>
      <div className="terminal-disconnected" hidden>
        <div className="terminal-blocked">
          <span data-terminal-reason=""></span>
          <button data-takeover="">take over</button>
        </div>
      </div>
      <pre className="terminal-screen" tabIndex={0} hidden>
        loading…
      </pre>
      <button className="terminal-jump" hidden>
        New output — jump to latest
      </button>
    </div>
  );
}

function TerminalCaption() {
  return (
    <div className="terminal-caption">
      <span data-terminal-status="">live · connecting</span>
      <span data-terminal-reconnect="" hidden>
        <button data-reconnect="">reconnect</button>
        <button data-takeover="">take over</button>
      </span>
    </div>
  );
}

function TerminalMarkup({ pane, panes, pickMessage, onPick }: TerminalMarkupProps) {
  const pick = pickMessage ? (
    <div className="terminal-pick">
      {pickMessage}{" "}
      {panes.length ? (
        <label>
          Pick a pane{" "}
          <select data-pane-pick="" defaultValue={pane?.pane_id || ""} onChange={(event) => onPick(event.target.value)}>
            <option value="">—</option>
            {panes.map((item) => (
              <option key={item.pane_id} value={item.pane_id}>
                {item.title || item.pane_id}
              </option>
            ))}
          </select>
        </label>
      ) : null}
    </div>
  ) : null;
  if (!pane) return <div className="terminal">{pick || <div className="hint">No Herdr panes are available.</div>}</div>;
  return (
    <div className="terminal" data-terminal-pane={pane.pane_id}>
      {pick}
      <TerminalHead pane={pane} />
      <TerminalScreen pane={pane} />
      <TerminalCaption />
      <div className="terminal-error" aria-live="polite"></div>
    </div>
  );
}

export function CardTerminal({ card }: { card: Card }) {
  const hostRef = useRef<HTMLDivElement>(null);
  const state = useStore((value) => value.state);
  const herdrData = useStore((value) => value.herdrData);
  const [, setChoiceVersion] = useState(0);
  const panes = herdrData?.panes || [];
  const match = useMemo(() => matchedCardPane(card, panes, state?.session_panes || {}), [card, panes, state]);
  const chosen = cardPaneChoice.get(card.key);
  const pane = match || panes.find((item) => item.pane_id === chosen) || null;

  useEffect(() => {
    if (!herdrData) void loadHerdr();
  }, [herdrData]);

  useEffect(() => {
    const root = hostRef.current?.querySelector<HTMLElement>(".terminal[data-terminal-pane]");
    if (root && pane) mountTerminal(root, pane.pane_id);
    return stopTerminal;
  }, [card.key, pane?.pane_id]);

  if (!herdrData)
    return (
      <div id="card-terminal" className="herdr-detail">
        <div className="hint">Loading Herdr…</div>
      </div>
    );
  if (!herdrData.running)
    return (
      <div id="card-terminal" className="herdr-detail">
        <div className="empty">herdr is not running on this server</div>
      </div>
    );
  const pickMessage = match ? "" : "No pane matches this card's session title or name.";
  const onPick = (paneId: string) => {
    if (paneId) cardPaneChoice.set(card.key, paneId);
    else cardPaneChoice.delete(card.key);
    setChoiceVersion((value) => value + 1);
  };
  return (
    <div id="card-terminal" className="herdr-detail" ref={hostRef}>
      <TerminalMarkup pane={pane} panes={panes} pickMessage={pickMessage} onPick={onPick} />
    </div>
  );
}
