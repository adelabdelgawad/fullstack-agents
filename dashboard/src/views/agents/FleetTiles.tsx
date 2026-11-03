import { ago, fmtCost, fmtTokens } from "../../lib/format";
import { setFleet, useStore } from "../../store";
import { fleetTpm } from "./tpm";

interface PlanWindow {
  name: string;
  pct?: number | null;
  resets_at: string;
}
interface PlanData {
  plan?: string;
  windows?: PlanWindow[];
  stale?: string;
  error?: string;
  credits?: { balance: number; unlimited: boolean };
}
interface SpendData {
  plan?: string;
  spend?: Array<{ name: string; cost: number | null; tokens: number }>;
  last_at?: number;
  error?: string;
}

export function Sparkline({ points }: { points: number[] }) {
  if (points.length < 2) return null;
  const max = Math.max(...points, 1);
  const step = 100 / (points.length - 1);
  const value = points
    .map((point, index) => `${(index * step).toFixed(1)},${(21 - (point / max) * 19).toFixed(1)}`)
    .join(" ");
  return (
    <svg viewBox="0 0 100 22" preserveAspectRatio="none" aria-hidden="true">
      <polyline points={value} />
    </svg>
  );
}

function untilText(iso: string): string {
  const seconds = (Date.parse(iso) - Date.now()) / 1000;
  if (!(seconds > 0)) return "";
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  if (seconds < 172800) return `${Math.floor(seconds / 3600)}h ${Math.round((seconds % 3600) / 60)}m`;
  return `${Math.round(seconds / 86400)}d`;
}

function Credits({ plan }: { plan: PlanData }) {
  if (!plan.credits || !plan.windows) return null;
  const capped = plan.windows.some((window) => (window.pct ?? 0) >= 100);
  const balance = plan.credits.unlimited ? "unlimited" : Math.round(plan.credits.balance).toLocaleString();
  const title = capped
    ? "A plan window is used up; runs are paid from credits"
    : "Credit balance available after the plan limits";
  return (
    <div className={`plan-credits${capped ? " on" : ""}`} title={title}>
      {capped ? "on credits · " : "credits · "}
      {balance} left
    </div>
  );
}

function PlanTile({ label, plan }: { label: string; plan?: PlanData }) {
  if (!plan?.windows)
    return (
      <div className="ft">
        <div className="ft-l">{label}</div>
        <div className="ft-v">—</div>
        <div className="ft-s">{plan?.error || "no data"}</div>
      </div>
    );
  const worst = Math.max(0, ...plan.windows.map((window) => window.pct ?? 0));
  const cls = worst >= 90 ? "bad" : worst >= 75 ? "warn" : "";
  return (
    <div className={`ft plan ${cls}`} title={plan.stale || undefined}>
      <div className="ft-l">
        {label}
        {plan.plan ? ` · ${plan.plan}` : ""}
        {plan.stale && (
          <>
            {" "}
            <span className="stale">· stale</span>
          </>
        )}
      </div>
      {plan.windows.map((window) => (
        <PlanRow key={window.name} label={label} window={window} />
      ))}
      <Credits plan={plan} />
    </div>
  );
}

function PlanRow({ label, window }: { label: string; window: PlanWindow }) {
  const known = window.pct !== null && window.pct !== undefined;
  const tone = !known ? "ok" : window.pct! >= 90 ? "bad" : window.pct! >= 75 ? "warn" : "ok";
  const until = untilText(window.resets_at);
  const title = known
    ? `${label} ${window.name}: ${window.pct}% used${until ? `, resets in ${until}` : ""}`
    : `${label} ${window.name}: window reset since the last reading`;
  return (
    <div className="plan-row" title={title}>
      <span>{window.name}</span>
      <span className={`orc-bar ctx-${tone}`}>
        <span style={{ width: `${known ? Math.min(window.pct!, 100) : 0}%` }} />
      </span>
      <b>{known ? `${Math.round(window.pct!)}%` : "—"}</b>
      <em>{until ? `↻ ${until}` : known ? "" : "reset"}</em>
    </div>
  );
}

function SpendTile({ plan }: { plan?: SpendData }) {
  if (!plan?.spend)
    return (
      <div className="ft">
        <div className="ft-l">Grok</div>
        <div className="ft-v">—</div>
        <div className="ft-s">{plan?.error || "no data"}</div>
      </div>
    );
  return (
    <div className="ft plan" title="xAI reports no plan limits to opencode; cost is opencode's API-equivalent estimate">
      <div className="ft-l">Grok · {plan.plan}</div>
      {plan.spend.map((row) => (
        <div className="plan-row spend" key={row.name}>
          <span>{row.name}</span>
          <b>{fmtTokens(row.tokens)}</b>
          <em>{fmtCost(row.cost)}</em>
        </div>
      ))}
      <div className="plan-credits">
        last used {ago(plan.last_at || 0)} ago ·{" "}
        <a
          href="https://grok.com"
          target="_blank"
          rel="noopener noreferrer"
          title="The weekly SuperGrok limit is shown only on grok.com"
        >
          weekly limit on grok.com ↗
        </a>
      </div>
    </div>
  );
}

function Tile({
  label,
  value,
  sub,
  cls = "",
  children,
}: {
  label: string;
  value: string | number;
  sub: string;
  cls?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className={`ft ${cls}`}>
      <div className="ft-l">{label}</div>
      <div className="ft-v">{value}</div>
      {sub && <div className="ft-s">{sub}</div>}
      {children}
    </div>
  );
}

function TileCards() {
  const state = useStore((value) => value.state);
  const totals = (state?.totals || {}) as Record<string, number>;
  const plan = (state?.plan || {}) as Record<string, PlanData | SpendData>;
  return (
    <section className="fleet-tiles" id="fleet-tiles" aria-label="Fleet summary">
      <Tile
        label="Sessions active (1 h)"
        value={totals.live ?? 0}
        sub={`${totals.working || 0} working · ${totals.waiting || 0} waiting · ${totals.stale || 0} stale`}
      />
      <Tile
        label="Waiting on you"
        value={totals.waiting ?? 0}
        sub="approve, answer or decide"
        cls={totals.waiting ? "warn" : ""}
      />
      <Tile
        label="Workers running"
        value={totals.workers ?? 0}
        sub={
          totals.failed
            ? `${totals.failed} failed run${totals.failed === 1 ? "" : "s"}`
            : "subagents and implementer runs"
        }
        cls={totals.failed ? "bad" : ""}
      />
      <Tile
        label="Context blowouts"
        value={totals.blowouts ?? 0}
        sub="compacted or ≥ 90% full"
        cls={totals.blowouts ? "bad" : ""}
      />
      <PlanTile label="Claude plan" plan={plan.claude as PlanData} />
      <PlanTile label="Codex plan" plan={plan.codex as PlanData} />
      <SpendTile plan={plan.grok as SpendData} />
      <Tile
        label="Tokens, last minute"
        value={fmtTokens(totals.tpm)}
        sub={`${fmtTokens(totals.tokens_today)} today · ${fmtCost(totals.cost_today)} API-equivalent`}
      >
        <Sparkline points={fleetTpm} />
      </Tile>
    </section>
  );
}

export function SummaryToggle() {
  const hidden = useStore((state) => state.fleet.tilesHidden);
  return (
    <button
      type="button"
      id="ftiles"
      className="ft-toggle"
      aria-expanded={!hidden}
      aria-controls={hidden ? undefined : "fleet-tiles"}
      onClick={() => setFleet({ tilesHidden: !hidden })}
    >
      {hidden ? "▾ Show summary" : "▴ Hide summary"}
    </button>
  );
}

export function FleetTiles() {
  const hidden = useStore((state) => state.fleet.tilesHidden);
  return hidden ? null : <TileCards />;
}
