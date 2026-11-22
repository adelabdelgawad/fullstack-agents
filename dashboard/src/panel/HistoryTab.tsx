import { useEffect, useState } from "react";
import { RetroCard } from "../components/RetroControls";
import { getJson } from "../lib/api";
import { ago, fmtCost, fmtTokens, modelFamily, modelShort } from "../lib/format";
import type { Card } from "../lib/types";

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
function useSessionHistory(sid: string | undefined): SessionHistory | null | "error" {
  const [data, setData] = useState<SessionHistory | null | "error">(null);
  useEffect(() => {
    setData(null);
    if (!sid) return;
    let live = true;
    const load = () =>
      getJson<SessionHistory>(`/api/session-history?sid=${encodeURIComponent(sid)}`)
        .then((d) => live && setData(d))
        .catch(() => live && setData((prev) => (prev && prev !== "error" ? prev : "error")));
    void load();
    const timer = setInterval(load, REFRESH_MS);
    return () => {
      live = false;
      clearInterval(timer);
    };
  }, [sid]);
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

export function SessionStats({ totals, card }: { totals: TurnTotals; card: Card }) {
  const fill = card.usage?.fill;
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

/** The panel's History tab: the dashboard's History table, one row per prompt of this card's lead session. */
export function HistoryTab({ card }: { card: Card }) {
  const data = useSessionHistory(card.sessions[0]?.id);
  if (data === "error") return <p className="empty">History is not available for this session.</p>;
  if (!data) return <p className="empty">Loading history…</p>;
  const turns = [...data.turns].reverse();
  return (
    <div className="session-history">
      <SessionStats totals={data.totals} card={card} />
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
