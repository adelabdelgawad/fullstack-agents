import { RetroCard, RetroInput } from "../components/RetroControls";
import type { HistoryEntry } from "../lib/types";
import { STATE_TEXT } from "../lib/cards";
import { ago, fmtCost, fmtTokens, modelFamily, modelShort } from "../lib/format";
import { openCard, setFleet, setView, store, useStore } from "../store";
import { FleetTiles, SummaryToggle } from "./agents/FleetTiles";

function openSession(sid: string): void {
  const c = store.get().state?.cards.find((x) => x.sessions.some((s) => s.id === sid));
  if (c) {
    setView("agents");
    openCard(c.key);
  }
}

function HistoryRow({ h }: { h: HistoryEntry }) {
  return (
    <tr
      data-hsid={h.id}
      tabIndex={0}
      onClick={() => openSession(h.id)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          openSession(h.id);
        }
      }}
    >
      <td>{h.name}</td>
      <td>
        <span className={`mchip m-${modelFamily(h.model)}`}>{modelShort(h.model) || h.engine}</span>
      </td>
      <td>{STATE_TEXT[h.state] || h.state}</td>
      <td>{h.branch}</td>
      <td className="num">{fmtTokens(h.tokens as number)}</td>
      <td className="num">{fmtCost(h.cost)}</td>
      <td className="num">{`${Math.round((h.fill || 0) * 100)}%`}</td>
      <td className="num">{h.compactions || ""}</td>
      <td className="num">{`${ago(h.updated)} ago`}</td>
    </tr>
  );
}

export function HistoryView() {
  const history = useStore((s) => s.state?.history) || [];
  const text = useStore((s) => s.fleet.text);
  const rows = history.filter(
    (h) => !text || `${h.name} ${h.branch} ${h.model}`.toLowerCase().includes(text.toLowerCase()),
  );
  return (
    <>
      <FleetTiles />
      <div className="fleet-toolbar">
        <RetroInput
          id="ftext"
          type="search"
          placeholder="Filter sessions"
          value={text}
          aria-label="Filter sessions"
          onChange={(e) => setFleet({ text: e.target.value })}
        />
        <span className="fcount">{`${rows.length} sessions, last 48 h`}</span>
        <SummaryToggle />
      </div>
      <RetroCard className="history-surface">
        <div className="history">
          <table>
            <thead>
              <tr>
                <th>Session</th>
                <th>Model</th>
                <th>State</th>
                <th>Branch</th>
                <th>Tokens</th>
                <th>Est. cost</th>
                <th>Context</th>
                <th>Compactions</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              {rows.length ? (
                rows.map((h) => <HistoryRow key={h.id} h={h} />)
              ) : (
                <tr>
                  <td colSpan={9}>No sessions.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </RetroCard>
    </>
  );
}
