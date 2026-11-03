import {
  activeStep,
  FLAG_TEXT,
  gitBadge,
  isRunning,
  isStale,
  needsHuman,
  STAGE_LABEL,
  stepsDone,
} from "../../lib/cards";
import { ago, fmtCost, fmtTokens, modelFamily, modelShort } from "../../lib/format";
import { lastPara, toolLine } from "../../lib/markup";
import type { Card, Session } from "../../lib/types";
import { openCard, store, toggleFavourite, useStore } from "../../store";
import { Sparkline } from "./FleetTiles";
import { WorkerSquares } from "./Workers";
import { cardTpm } from "./tpm";

export interface OrcState {
  key: string;
  label: string;
  icon: string;
}
export interface OrcPlanData {
  title: string;
  done: number;
  total: number;
}

export function orcState(card: Card): OrcState {
  if (needsHuman(card)) return { key: "waiting", label: "Waiting · needs you", icon: "⏸" };
  if (isRunning(card)) return { key: "running", label: "Running", icon: "▶" };
  if (isStale(card)) return { key: "stale", label: "Stale · no output for 5+ min", icon: "◌" };
  if (card.phase === "complete") return { key: "done", label: "Done", icon: "✓" };
  return { key: "idle", label: "Idle", icon: "■" };
}

export function orcPlan(card: Card): OrcPlanData | null {
  const tracking = card.sessions
    .map((session) => session.task_tracking)
    .find((item) => item && !item.error && item.total) as Record<string, any> | undefined;
  if (tracking) {
    const active = tracking.items.find(
      (item: Record<string, unknown>) => item.is_active === true && Date.parse(String(item.active_until)) > Date.now(),
    );
    const current = active || tracking.items.find((item: Record<string, string>) => item.status === "in_progress");
    return {
      title: [tracking.title, current?.title].filter(Boolean).join(" · "),
      done: tracking.completed,
      total: tracking.total,
    };
  }
  if (card.steps?.length)
    return { title: activeStep(card)?.text || "Lead steps", done: stepsDone(card), total: card.steps.length };
  const rounds = (card.rounds || []) as Array<Record<string, string>>;
  if (rounds.length)
    return {
      title: String(card.label || card.goal || "Implementer briefs"),
      done: rounds.filter((round) => round.state === "done").length,
      total: rounds.length,
    };
  return null;
}

export function orcWorkers(card: Card) {
  const states = [
    ...card.runs.map((run) => run.state),
    ...card.now
      .flatMap((session) => (session.agents || []) as Array<Record<string, unknown>>)
      .filter((agent) => !agent.shell)
      .map((agent) => String(agent.state)),
  ];
  const count = (values: string[]) => states.filter((state) => values.includes(state)).length;
  return {
    total: states.length,
    running: count(["running"]),
    done: count(["done", "completed"]),
    failed: count(["failed", "abandoned"]),
  };
}

function ModelChip({ model }: { model?: string }) {
  return model ? (
    <span className={`mchip m-${modelFamily(model)}`} title={model}>
      {modelShort(model)}
    </span>
  ) : null;
}

function CardNow({ card }: { card: Card }) {
  const step = activeStep(card);
  const session = card.now[0];
  const waiting = card.now.find((item) => item.state === "waiting" && item.need);
  if (!waiting && session?.state === "working") return <WorkingNow session={session} step={step?.text} />;
  const asking = waiting ? undefined : card.now.find((item) => item.state === "waiting");
  const line = waiting
    ? `Needs you: ${waiting.need}`
    : asking?.said
      ? `Needs you: ${lastPara(asking.said)}`
      : step
        ? `▸ ${step.text}`
        : session?.ask
          ? `“${session.ask}”`
          : "";
  return line ? (
    <div className="act" title={line}>
      {line}
    </div>
  ) : null;
}

function WorkingNow({ session, step }: { session: Session; step?: string }) {
  const top = step ? `▸ ${step}` : lastPara(session.said);
  const tool = toolLine(session);
  return (
    <>
      {top && (
        <div className="say" title={top}>
          {top}
        </div>
      )}
      {tool && (
        <div className={`act${session.action_running ? " run" : ""}`} title={tool}>
          {tool}
        </div>
      )}
    </>
  );
}

function QuestionLine({ card }: { card: Card }) {
  const question = card.now.find((session) => session.question)?.question;
  return question ? (
    <div className="act ask-q" title={question}>
      Question for you: {question}
    </div>
  ) : null;
}

function BranchIcon() {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true">
      <path
        fill="currentColor"
        d={
          "M5 3.25a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 0Zm0 9.5a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 0Z" +
          "m7-7a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 0ZM4.25 1a2.25 2.25 0 0 0-.75 4.37v5.26a2.25 2.25 0 1 0 1.5 0" +
          "V9.5c.5.3 1.1.5 1.75.5h1.5a2.25 2.25 0 0 0 2.12-1.5 2.25 2.25 0 1 0-1.5-.88A.75.75 0 0 1 8.25 8.5h-1.5" +
          "A1.75 1.75 0 0 1 5 6.75V5.37A2.25 2.25 0 0 0 4.25 1Z"
        }
      />
    </svg>
  );
}

function Metrics({ card }: { card: Card }) {
  const usage = card.usage;
  const tone = usage ? (Number(usage.fill) >= 0.9 ? "bad" : Number(usage.fill) >= 0.8 ? "warn" : "") : "";
  const metric = (label: React.ReactNode, value: React.ReactNode, extra?: React.ReactNode) => (
    <span className="orc-metric">
      <span>{label}</span>
      <b>{value}</b>
      {extra}
    </span>
  );
  return (
    <div className="orc-metrics">
      {metric("Cost", fmtCost(usage?.cost))}
      {metric("Tokens", fmtTokens(Number(usage?.tokens)))}
      {metric("Updated", ago(card.updated))}
      {metric(
        <>
          Context
          {usage?.compactions ? (
            <>
              {" "}
              <span className="cbadge">{usage.compactions}×</span>
            </>
          ) : null}
        </>,
        usage ? <span className={tone}>{Math.round(Number(usage.fill) * 100)}%</span> : "—",
        usage && (
          <span className={`orc-bar ctx-${tone || "ok"}`}>
            <span style={{ width: `${Math.round(Number(usage.fill) * 100)}%` }} />
          </span>
        ),
      )}
    </div>
  );
}

function respondTo(card: Card): void {
  const sid = card.now[0]?.id;
  store.set({ tab2: sid && store.get().state?.session_panes?.[sid] ? "terminal" : "info" });
  openCard(card.key, true);
}

function OrcHead({ card, state, lead }: { card: Card; state: OrcState; lead: Session }) {
  return (
    <header className="orc-head">
      <span className="orc-ico" aria-hidden="true">
        {state.icon}
      </span>
      <h3 title={card.title}>{card.title}</h3>
      <span className="stage">{STAGE_LABEL(card)}</span>
      <ModelChip model={String(card.usage?.model || lead.model || "") || undefined} />
      <button
        className="star"
        data-fav={card.key}
        aria-pressed={!!card.favourite}
        aria-label={card.favourite ? "Remove from favourites" : "Add to favourites"}
        onClick={(event) => {
          event.stopPropagation();
          void toggleFavourite(card.key);
        }}
        onKeyDown={(event) => event.stopPropagation()}
      >
        {card.favourite ? "★" : "☆"}
      </button>
    </header>
  );
}

function OrcIdentity({ card, lead }: { card: Card; lead: Session }) {
  const branch = card.tree ? card.tree.branch : lead.branch,
    dirty = gitBadge(card),
    cwd = String(card.worktree || card.repo || "");
  return (
    <div className="orc-meta" title={cwd}>
      <span className="orc-role">orchestrator · {lead.engine || "claude"}</span>
      <span aria-hidden="true">·</span>
      <span className="br" title="branch">
        <BranchIcon />
        {branch || "no branch"}
      </span>
      <span aria-hidden="true">·</span>
      <span className="chip">{card.worktree && card.worktree !== card.repo ? "worktree" : "main checkout"}</span>
      <span aria-hidden="true">·</span>
      <span className={dirty ? "dirty" : "clean"}>{dirty ? `${dirty} modified` : "clean"}</span>
      {card.sessions.length > 1 && (
        <>
          <span aria-hidden="true">·</span>
          <span>{card.sessions.length} sessions</span>
        </>
      )}
    </div>
  );
}

function OrcProgress({ plan }: { plan: OrcPlanData | null }) {
  const percent = plan ? Math.round((plan.done / Math.max(plan.total, 1)) * 100) : 0;
  return (
    <div className="orc-plan">
      {plan ? (
        <>
          <div className="orc-plan-t">
            <span title={plan.title}>{plan.title}</span>
            <b>
              {plan.done}/{plan.total}
            </b>
          </div>
          <div className="orc-bar" aria-hidden="true">
            <span style={{ width: `${percent}%` }} />
          </div>
        </>
      ) : (
        <div className="orc-plan-t muted">No plan reported. Workers launched ad hoc.</div>
      )}
    </div>
  );
}

function OrcNow({ card }: { card: Card }) {
  return (
    <div className="orc-now">
      {card.now.some((session) => session.question) ? <QuestionLine card={card} /> : <CardNow card={card} />}
    </div>
  );
}

function OrcWorkers({ card, workers }: { card: Card; workers: ReturnType<typeof orcWorkers> }) {
  return (
    <div className="orc-workers">
      <WorkerSquares card={card} />
      <div className="orc-wsum">
        <span>
          {workers.total ? (
            <>
              {workers.running} running · {workers.done} done
              {workers.failed ? (
                <>
                  {" "}
                  · <span className="bad">{workers.failed} failed</span>
                </>
              ) : null}
            </>
          ) : (
            "no workers"
          )}
        </span>
        <Sparkline points={cardTpm.get(card.key) || []} />
      </div>
    </div>
  );
}

function OrcFooter({
  card,
  state,
  flag,
  workers,
}: {
  card: Card;
  state: OrcState;
  flag: string;
  workers: ReturnType<typeof orcWorkers>;
}) {
  return (
    <footer className="orc-footer">
      <Metrics card={card} />
      <OrcWorkers card={card} workers={workers} />
      <span className="orc-actions">
        <span className="orc-state">
          <span aria-hidden="true">{state.icon}</span>
          <span>{state.label}</span>
          {flag && <span className="flag">{flag}</span>}
        </span>
        {state.key === "waiting" && <RespondButton card={card} />}
      </span>
    </footer>
  );
}

function RespondButton({ card }: { card: Card }) {
  return (
    <button
      className="tbtn orc-respond"
      data-respond={card.key}
      onClick={(event) => {
        event.stopPropagation();
        respondTo(card);
      }}
      onKeyDown={(event) => event.stopPropagation()}
    >
      Respond
    </button>
  );
}

export function OrcCard({ card }: { card: Card }) {
  const openKey = useStore((state) => state.openKey);
  const state = orcState(card),
    plan = orcPlan(card),
    workers = orcWorkers(card),
    lead = card.sessions[0] || ({} as Session);
  const flag = card.needs_you.length ? FLAG_TEXT[card.needs_you[0]] || card.needs_you[0] : "";
  const open = () => openCard(card.key);
  const keyDown = (event: React.KeyboardEvent<HTMLElement>) => {
    if ((event.key === "Enter" || event.key === " ") && event.target === event.currentTarget) {
      event.preventDefault();
      open();
    }
  };
  return (
    <article
      className={`card orc st-${state.key}${card.usage?.blowout ? " blowout" : ""}${openKey === card.key ? " open-here" : ""}`}
      tabIndex={0}
      data-key={card.key}
      data-sid={lead.id || ""}
      onClick={open}
      onKeyDown={keyDown}
    >
      <OrcHead card={card} state={state} lead={lead} />
      <OrcIdentity card={card} lead={lead} />
      <OrcProgress plan={plan} />
      <OrcNow card={card} />
      <OrcFooter card={card} state={state} flag={flag} workers={workers} />
    </article>
  );
}
