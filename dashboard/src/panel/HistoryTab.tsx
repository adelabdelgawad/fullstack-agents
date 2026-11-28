import { useEffect, useState } from "react";
import { RetroCard } from "../components/RetroControls";
import { getJson } from "../lib/api";
import { ago, fmtCost, fmtTokens, modelFamily, modelShort } from "../lib/format";
import type { Card, HistoryEntry, SessionQuestion } from "../lib/types";
import { useStore } from "../store";
import { SessionsTable } from "../views/HistoryView";

const REFRESH_MS = 10000;

export interface Turn {
  prompt: string;
  model: string;
  state: string;
  tokens: number;
  cost: number | null;
  fill: number;
  compactions: number;
  started: number;
  updated: number;
}

export interface TurnTotals {
  turns?: number;
  tokens?: number;
  cost?: number | null;
  compactions?: number;
  interrupted?: number;
}

export interface SessionHistory {
  turns: Turn[];
  totals: TurnTotals;
  questions?: SessionQuestion[];
}

const OUTCOME: Record<string, string> = {
  answered: "answered",
  asked: "asked you",
  interrupted: "interrupted",
  working: "working",
};

function duration(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${s} s`;
  if (s < 3600) return `${Math.round(s / 60)} min`;
  return `${(s / 3600).toFixed(1)} h`;
}

/** One session's prompts with their usage, refreshed while the tab is open; null until the first answer. */
function useSessionHistory(sid: string | undefined, agent?: string): SessionHistory | null | "error" {
  const [data, setData] = useState<SessionHistory | null | "error">(null);
  useEffect(() => {
    setData(null);
    if (!sid) return;
    let live = true;
    const load = () =>
      getJson<SessionHistory>(
        `/api/session-history?sid=${encodeURIComponent(sid)}${agent ? `&agent=${encodeURIComponent(agent)}` : ""}`,
      )
        .then((d) => live && setData(d))
        .catch(() => live && setData((prev) => (prev && prev !== "error" ? prev : "error")));
    void load();
    const timer = setInterval(load, REFRESH_MS);
    return () => {
      live = false;
      clearInterval(timer);
    };
  }, [sid, agent]);
  return data;
}

function Stat({ label, value, cls = "" }: { label: string; value: string | number; cls?: string }) {
  return (
    <RetroCard className={`so-tile ${cls}`}>
      <div className="so-l">{label}</div>
      <div className="so-v">{value}</div>
    </RetroCard>
  );
}

export function SessionStats({ totals, fill }: { totals: TurnTotals; fill: number | null | undefined }) {
  return (
    <div className="so-tiles" aria-label="Session totals">
      <Stat label="Prompts" value={totals.turns ?? 0} />
      <Stat label="Tokens" value={fmtTokens(totals.tokens || 0)} />
      <Stat label="Est. cost" value={fmtCost(totals.cost ?? null)} />
      <Stat label="Context now" value={fill == null ? "—" : `${Math.round(fill * 100)}%`} />
      <Stat label="Compactions" value={totals.compactions || 0} cls={totals.compactions ? "bad" : ""} />
      <Stat label="Interrupted" value={totals.interrupted || 0} />
    </div>
  );
}

function TurnRow({ t }: { t: Turn }) {
  return (
    <tr>
      <td className="turn-prompt" title={t.prompt}>
        {t.prompt}
      </td>
      <td>
        <span className={`mchip m-${modelFamily(t.model)}`}>{modelShort(t.model) || "—"}</span>
      </td>
      <td>{OUTCOME[t.state] || t.state}</td>
      <td className="num">{fmtTokens(t.tokens)}</td>
      <td className="num">{fmtCost(t.cost)}</td>
      <td className="num">{`${Math.round((t.fill || 0) * 100)}%`}</td>
      <td className="num">{t.compactions || ""}</td>
      <td className="num" title={`took ${duration(t.updated - t.started)}`}>{`${ago(t.updated)} ago`}</td>
    </tr>
  );
}

/** The sessions this lead ran before, newest first: each handoff names the session it continued. */
function earlierSessions(history: HistoryEntry[], sid: string | undefined): HistoryEntry[] {
  const byId = new Map(history.filter((h) => !h.parent).map((h) => [h.id, h]));
  const out: HistoryEntry[] = [];
  for (let prev = sid && byId.get(sid)?.previous; prev && !out.some((h) => h.id === prev); ) {
    const h = byId.get(prev);
    if (!h) break;
    out.push(h);
    prev = h.previous;
  }
  return out;
}

/** The panel's History tab: this lead session's prompts, then its subagents and earlier sessions, each opening its own. */
export function HistoryTab({ card }: { card: Card }) {
  const history = useStore((s) => s.state?.history) || [];
  const sid = card.sessions[0]?.id;
  const earlier = earlierSessions(history, sid);
  const leads = new Set([sid, ...earlier.map((h) => h.id)]);
  const subs = history.filter((h) => h.parent && leads.has(h.parent));
  const own = subs.filter((h) => h.parent === sid);
  return (
    <>
      <SessionTurns sid={sid} fill={card.usage?.fill} />
      {own.length > 0 && (
        <section className="session-history" aria-label="Subagents of this session">
          <h4>{`Subagents of this session (${own.length})`}</h4>
          <SessionsTable rows={own} expandOnly />
        </section>
      )}
      {earlier.length > 0 && (
        <section className="session-history" aria-label="Earlier sessions of this lead">
          <h4>{`Earlier sessions of this lead (${earlier.length})`}</h4>
          <SessionsTable rows={[...earlier, ...subs.filter((h) => h.parent !== sid)]} expandOnly />
        </section>
      )}
    </>
  );
}

/** One session's or subagent's prompts with their usage: a live card's, or a finished one's from the History list. */
export function SessionTurns({
  sid,
  agent,
  fill,
}: {
  sid: string | undefined;
  agent?: string;
  fill: number | null | undefined;
}) {
  const data = useSessionHistory(sid, agent);
  if (data === "error") return <p className="empty">History is not available for this session.</p>;
  if (!data) return <p className="empty">Loading history…</p>;
  const turns = [...data.turns].reverse();
  return (
    <div className="session-history">
      <SessionStats totals={data.totals} fill={fill} />
      <div className="history">
        <table>
          <thead>
            <tr>
              <th>Prompt</th>
              <th>Model</th>
              <th>State</th>
              <th>Tokens</th>
              <th>Est. cost</th>
              <th>Context</th>
              <th>Compactions</th>
              <th>Updated</th>
            </tr>
          </thead>
          <tbody>
            {turns.length ? (
              turns.map((t) => <TurnRow key={`${t.started}-${t.prompt.slice(0, 20)}`} t={t} />)
            ) : (
              <tr>
                <td colSpan={8}>No prompts yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
