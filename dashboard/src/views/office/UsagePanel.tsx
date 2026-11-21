import { ago, fmtCost, fmtTokens } from "../../lib/format";
import { useStore } from "../../store";
import { Sparkline, untilText, type PlanData, type PlanWindow, type SpendData } from "../agents/FleetTiles";
import { fleetTpm } from "../agents/tpm";

const tone = (pct: number | null | undefined) => (pct == null ? "ok" : pct >= 90 ? "bad" : pct >= 75 ? "warn" : "ok");

function Stat({
  label,
  value,
  note,
  level = "",
}: {
  label: string;
  value: string | number;
  note: string;
  level?: string;
}) {
  return (
    <div className={`usage-stat ${level}`}>
      <span className="usage-stat-value">{value}</span>
      <span className="usage-stat-label">{label}</span>
      <span className="usage-stat-note">{note}</span>
    </div>
  );
}

function WindowBar({ window }: { window: PlanWindow }) {
  const known = window.pct !== null && window.pct !== undefined;
  const until = untilText(window.resets_at);
  return (
    <div className="usage-window">
      <div className="usage-window-head">
        <span>{window.name === "5h" ? "5-hour window" : window.name === "week" ? "Weekly" : window.name}</span>
        <strong className={`usage-pct ${tone(window.pct)}`}>{known ? `${Math.round(window.pct!)}%` : "—"}</strong>
      </div>
      <div
        className={`usage-bar ${tone(window.pct)}`}
        role="meter"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={known ? window.pct! : 0}
        aria-label={`${window.name} used`}
      >
        <span style={{ width: `${known ? Math.min(window.pct!, 100) : 0}%` }} />
      </div>
      <div className="usage-window-foot">
        {until ? `Resets in ${until}` : known ? "" : "Reset since the last reading"}
      </div>
    </div>
  );
}

function PlanCard({ name, plan }: { name: string; plan?: PlanData }) {
  return (
    <article className="usage-plan">
      <header>
        <h3>{name}</h3>
        {plan?.plan && <span className="usage-tag">{plan.plan}</span>}
        {plan?.stale && <span className="usage-tag stale">stale</span>}
      </header>
      {plan?.windows ? (
        plan.windows.map((window) => <WindowBar key={window.name} window={window} />)
      ) : (
        <p className="usage-none">{plan?.error || "No data yet"}</p>
      )}
      {plan?.credits && (
        <div className="usage-credits">
          Credits left:{" "}
          <strong>{plan.credits.unlimited ? "unlimited" : Math.round(plan.credits.balance).toLocaleString()}</strong>
        </div>
      )}
    </article>
  );
}

function SpendCard({ plan }: { plan?: SpendData }) {
  return (
    <article className="usage-plan">
      <header>
        <h3>Grok</h3>
        {plan?.plan && <span className="usage-tag">{plan.plan}</span>}
      </header>
      {plan?.spend ? (
        <>
          {plan.spend.map((row) => (
            <div className="usage-spend" key={row.name}>
              <span>{row.name}</span>
              <strong>{fmtTokens(row.tokens)}</strong>
              <em>{fmtCost(row.cost)}</em>
            </div>
          ))}
          <p className="usage-none">{plan.last_at ? `Last used ${ago(plan.last_at)} ago` : "Not used yet"}</p>
        </>
      ) : (
        <p className="usage-none">{plan?.error || "No data yet"}</p>
      )}
    </article>
  );
}

/** The CTO's usage view: activity at a glance, each plan's limits as full-width bars, and token throughput. */
export function UsagePanel() {
  const state = useStore((value) => value.state);
  const totals = (state?.totals || {}) as Record<string, number>;
  const plan = (state?.plan || {}) as Record<string, PlanData | SpendData>;
  return (
    <div className="usage-panel">
      <section className="usage-stats" aria-label="Activity">
        <Stat
          label="Active sessions"
          value={totals.live ?? 0}
          note={`${totals.working || 0} working · ${totals.stale || 0} stale (last hour)`}
        />
        <Stat
          label="Waiting on you"
          value={totals.waiting ?? 0}
          note="approve, answer or decide"
          level={totals.waiting ? "warn" : ""}
        />
        <Stat
          label="Workers running"
          value={totals.workers ?? 0}
          note={totals.failed ? `${totals.failed} failed` : "subagents and Codex runs"}
          level={totals.failed ? "bad" : ""}
        />
        <Stat
          label="Context blowouts"
          value={totals.blowouts ?? 0}
          note="compacted or ≥ 90% full"
          level={totals.blowouts ? "bad" : ""}
        />
      </section>
      <h3 className="usage-section">Plan limits</h3>
      <section className="usage-plans">
        <PlanCard name="Claude" plan={plan.claude as PlanData} />
        <PlanCard name="Codex" plan={plan.codex as PlanData} />
        <SpendCard plan={plan.grok as SpendData} />
      </section>
      <h3 className="usage-section">Tokens</h3>
      <section className="usage-tokens">
        <div className="usage-token-figures">
          <Stat label="per minute now" value={fmtTokens(totals.tpm)} note="all sessions" />
          <Stat
            label="today"
            value={fmtTokens(totals.tokens_today)}
            note={`${fmtCost(totals.cost_today)} API-equivalent`}
          />
        </div>
        <div className="usage-chart" aria-label="Tokens per minute, recent">
          {fleetTpm.length < 2 ? (
            <p className="usage-none">
              Collecting: the chart fills in while this page stays open (one point every refresh).
            </p>
          ) : (
            <>
              <div className="usage-chart-head">
                <span>Tokens per minute, last {Math.max(1, Math.round((fleetTpm.length * 4) / 60))} min</span>
                <span>peak {fmtTokens(Math.max(...fleetTpm))}/min</span>
              </div>
              <Sparkline points={fleetTpm} />
            </>
          )}
        </div>
      </section>
    </div>
  );
}
