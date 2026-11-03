import { cardAgents, STATE_TEXT } from "../../lib/cards";
import { ago, fmtCost, fmtTokens, modelFamily, modelShort } from "../../lib/format";
import type { Card, Run, Session } from "../../lib/types";
import { openAgent } from "../../components/OutDialog";
import { openRunLog } from "../../panel/Panel";

interface Square {
  kind: "run" | "agent";
  id: string;
  sid?: string;
  state: string;
  model?: string;
  label: string;
  cause?: string;
}

function squareState(state: string): string {
  if (state === "running") return "running";
  if (["failed", "abandoned"].includes(state)) return "failed";
  return state === "stalled" ? "stalled" : "done";
}

function SquareButton({ card, square }: { card: Card; square: Square }) {
  const title =
    `${square.label} — ${square.state}${square.model ? ` · ${modelShort(square.model)}` : ""}` +
    `${square.cause ? `\n${square.cause}` : ""}`;
  const activate = (event: React.MouseEvent | React.KeyboardEvent) => {
    event.stopPropagation();
    if (square.kind === "run") openRunLog(card.key, square.id);
    else openAgent(square.sid || "", square.id);
  };
  const keyDown = (event: React.KeyboardEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      activate(event);
    }
  };
  const data =
    square.kind === "run"
      ? { "data-run-log": square.id, "data-run-card": card.key }
      : { "data-asid": square.sid, "data-agent": square.id };
  return (
    <button
      className={`sq m-${modelFamily(square.model)} ${squareState(square.state)}`}
      {...data}
      title={title}
      aria-label={`${square.label}, ${square.state}`}
      onClick={activate}
      onKeyDown={keyDown}
    />
  );
}

export function WorkerSquares({ card }: { card: Card }) {
  const runs: Square[] = (card.runs || []).map((run) => ({
    kind: "run",
    id: run.id,
    state: run.state,
    model: run.model || String(run.engine || ""),
    label: `${run.mode} ${run.unit || run.id}`,
    cause: run.cause,
  }));
  const agents: Square[] = cardAgents(card)
    .filter((agent) => !agent.shell)
    .map((agent) => ({
      kind: "agent",
      id: agent.id,
      sid: agent.sid,
      state: agent.state,
      model: String(agent.model || ""),
      label: String(agent.label || ""),
    }));
  const squares = [...runs, ...agents].slice(-60);
  if (!squares.length) return null;
  return (
    <div className="squares" role="group" aria-label="Workers">
      {squares.map((square, index) => (
        <SquareButton key={`${square.kind}-${square.id}-${index}`} card={card} square={square} />
      ))}
    </div>
  );
}

interface WorkerRow {
  name: string;
  kind: string;
  usage: Record<string, number | string | null | undefined>;
  state: string;
  lead?: boolean;
  at?: number;
  cause?: string;
}

function sessionRows(session: Session, card: Card): WorkerRow[] {
  const usage = (session.usage || { model: session.model }) as Record<string, unknown>;
  const agents = (usage.agents || {}) as Record<string, Record<string, number | string | null | undefined>>;
  return [
    { name: session.name, kind: "orchestrator", usage: usage as WorkerRow["usage"], state: session.state, lead: true },
    ...Object.entries(agents).map(([id, agent]) => {
      const live = cardAgents(card).find((item) => item.id === id);
      return {
        name: String(live?.label || agent.label || id),
        kind: "subagent",
        usage: agent,
        state: live?.state || "completed",
        at: live?.at,
      };
    }),
  ];
}

function runRow(run: Run): WorkerRow {
  return {
    name: `${run.mode} ${run.unit || run.id}`,
    kind: "implementer run",
    usage: { model: run.model || String(run.engine || "") },
    state: run.state,
    at: Number(run.started),
    cause: run.cause,
  };
}

export function Workers({ card }: { card: Card }) {
  const rows = card.sessions.flatMap((session) => sessionRows(session, card)).concat(card.runs.map(runRow));
  if (!rows.length) return null;
  return (
    <table className="usage-table">
      <thead>
        <tr>
          <th>Agent</th>
          <th>Model</th>
          <th>State</th>
          <th>Context</th>
          <th>Tokens</th>
          <th>Est. cost</th>
          <th>Age</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row, index) => (
          <WorkerTableRow row={row} key={`${row.name}-${index}`} />
        ))}
      </tbody>
    </table>
  );
}

function WorkerTableRow({ row }: { row: WorkerRow }) {
  const fill = row.usage.fill as number | undefined;
  const model = String(row.usage.model || "");
  return (
    <tr className={["failed", "abandoned"].includes(row.state) ? "bad" : ""}>
      <td>
        {row.lead ? <b>{row.name}</b> : row.name}
        <div className="s">
          {row.kind}
          {row.cause ? ` · ${row.cause}` : ""}
        </div>
      </td>
      <td>
        <span className={`mchip m-${modelFamily(model)}`}>{modelShort(model) || "?"}</span>
      </td>
      <td>{STATE_TEXT[row.state] || row.state || ""}</td>
      <td className="num">
        {fill === undefined ? (
          "—"
        ) : (
          <>
            {Math.round(fill * 100)}%
            <span className="orc-bar">
              <span style={{ width: `${Math.round(fill * 100)}%` }} />
            </span>
          </>
        )}
      </td>
      <td className="num">{row.usage.tokens == null ? "—" : fmtTokens(Number(row.usage.tokens))}</td>
      <td className="num">{fmtCost(row.usage.cost as number | null | undefined)}</td>
      <td className="num">{row.at ? ago(row.at) : ""}</td>
    </tr>
  );
}
