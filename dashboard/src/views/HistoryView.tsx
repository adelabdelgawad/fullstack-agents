import { Fragment, useState } from "react";
import { SessionTurns } from "../panel/HistoryTab";
import { RetroCard, RetroInput } from "../components/RetroControls";
import type { HistoryEntry } from "../lib/types";
import { STATE_TEXT } from "../lib/cards";
import { ago, fmtCost, fmtTokens, modelFamily, modelShort } from "../lib/format";
import { openCard, setFleet, setView, store, useStore } from "../store";
import { FleetTiles, SummaryToggle } from "./agents/FleetTiles";

const rowKey = (h: HistoryEntry) => `${h.parent || ""}/${h.id}`;

/** A live session opens its card; a finished one (no card any more) and every subagent show their prompts under the row. */
function openSession(h: HistoryEntry, toggle: () => void, expandOnly: boolean): void {
  const c = !expandOnly && !h.parent && store.get().state?.cards.find((x) => x.sessions.some((s) => s.id === h.id));
  if (!c) return toggle();
  setView("agents");
  openCard(c.key);
}

interface RowProps {
  h: HistoryEntry;
  open: boolean;
  toggle: () => void;
  expandOnly: boolean;
  subs?: { count: number; open: boolean; toggle: () => void };
}

function HistoryRow({ h, open, toggle, expandOnly, subs }: RowProps) {
  const act = () => openSession(h, toggle, expandOnly);
  return (
    <tr
      data-hsid={h.id}
      className={h.parent ? "history-sub" : undefined}
      tabIndex={0}
      aria-expanded={open}
      onClick={act}
      onKeyDown={(e) => {
        if (e.target === e.currentTarget && (e.key === "Enter" || e.key === " ")) {
          e.preventDefault();
          act();
        }
      }}
    >
      <td title={h.name}>
        {h.parent ? `↳ ${h.name}` : h.name}
        {subs && subs.count > 0 && (
          <button
            type="button"
            className="history-subs-toggle"
            aria-expanded={subs.open}
            onClick={(e) => {
              e.stopPropagation();
              subs.toggle();
            }}
          >
            {`${subs.open ? "▾" : "▸"} ${subs.count} subagent${subs.count === 1 ? "" : "s"}`}
          </button>
        )}
      </td>
      <td>
        <span className={`mchip m-${modelFamily(h.model)}`}>{modelShort(h.model) || h.engine}</span>
      </td>
      <td>{h.parent ? "subagent" : STATE_TEXT[h.state] || h.state}</td>
      <td>{h.branch}</td>
      <td className="num">{fmtTokens(h.tokens as number)}</td>
      <td className="num">{fmtCost(h.cost)}</td>
      <td className="num">{`${Math.round((h.fill || 0) * 100)}%`}</td>
      <td className="num">{h.compactions || ""}</td>
      <td className="num">{`${ago(h.updated)} ago`}</td>
    </tr>
  );
}

/** Sessions with their subagents nested under them; any row expands to its prompts (a live lead opens its card unless expandOnly). */
export function SessionsTable({
  rows,
  expandOnly = false,
  subsOpen = false,
}: {
  rows: HistoryEntry[];
  expandOnly?: boolean;
  subsOpen?: boolean;
}) {
  const [opened, setOpened] = useState<string | null>(null);
  const [shown, setShown] = useState<Record<string, boolean>>({});
  const leads = rows.filter((h) => !h.parent);
  const ids = new Set(leads.map((h) => h.id));
  const subsOf = (id: string) => rows.filter((h) => h.parent === id).sort((a, b) => b.updated - a.updated);
  const orphans = rows.filter((h) => h.parent && !ids.has(h.parent));
  const line = (h: HistoryEntry, subs?: RowProps["subs"]) => (
    <Fragment key={rowKey(h)}>
      <HistoryRow
        h={h}
        open={opened === rowKey(h)}
        toggle={() => setOpened(opened === rowKey(h) ? null : rowKey(h))}
        expandOnly={expandOnly}
        subs={subs}
      />
      {opened === rowKey(h) && (
        <tr className="history-turns">
          <td colSpan={9}>
            <SessionTurns sid={h.parent || h.id} agent={h.parent ? h.id : undefined} fill={h.fill} />
          </td>
        </tr>
      )}
    </Fragment>
  );
  return (
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
            <>
              {leads.map((h) => {
                const subs = subsOf(h.id);
                const open = shown[h.id] ?? subsOpen;
                const toggle = () => setShown({ ...shown, [h.id]: !open });
                return (
                  <Fragment key={`lead-${rowKey(h)}`}>
                    {line(h, { count: subs.length, open, toggle })}
                    {open && subs.map((s) => line(s))}
                  </Fragment>
                );
              })}
              {orphans.map((h) => line(h))}
            </>
          ) : (
            <tr>
              <td colSpan={9}>No sessions.</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

export function HistoryView() {
  const history = useStore((s) => s.state?.history) || [];
  const raw = useStore((s) => s.fleet.text);
  const text = raw.toLowerCase();
  const hit = (h: HistoryEntry) => !text || `${h.name} ${h.branch} ${h.model}`.toLowerCase().includes(text);
  const leads = new Set(history.filter((h) => !h.parent && hit(h)).map((h) => h.id));
  const rows = history.filter((h) => (h.parent ? leads.has(h.parent) || hit(h) : leads.has(h.id)));
  return (
    <>
      <FleetTiles />
      <div className="fleet-toolbar">
        <RetroInput
          id="ftext"
          type="search"
          placeholder="Filter sessions"
          value={raw}
          aria-label="Filter sessions"
          onChange={(e) => setFleet({ text: e.target.value })}
        />
        <span className="fcount">{`${leads.size} sessions, last 48 h`}</span>
        <SummaryToggle />
      </div>
      <RetroCard className="history-surface">
        <SessionsTable rows={rows} subsOpen={!!text} />
      </RetroCard>
    </>
  );
}
