import { useEffect, useState } from "react";
import { isRunning, isStale, needsHuman } from "../../lib/cards";
import { modelFamily, modelShort } from "../../lib/format";
import type { Card } from "../../lib/types";
import { closePanel, openCard, useStore } from "../../store";
import { Activity } from "./Activity";
import { FleetTiles } from "./FleetTiles";
import { FleetToolbar } from "./FleetToolbar";
import { OrcCard, orcPlan, orcState, orcWorkers } from "./OrcCard";

const MODELS = [
  ["opus", "Opus"],
  ["sonnet", "Sonnet"],
  ["haiku", "Haiku"],
  ["fable", "Fable"],
  ["gpt", "Codex"],
  ["grok", "Grok"],
];

function savedCollapsed(): boolean {
  try {
    return localStorage.getItem("fsa-orc-collapsed") === "1";
  } catch {
    return false;
  }
}

function SidebarRow({ card }: { card: Card }) {
  const openKey = useStore((state) => state.openKey);
  const status = orcState(card),
    plan = orcPlan(card),
    workers = orcWorkers(card),
    usage = card.usage || {};
  const pct = plan ? Math.round((plan.done / Math.max(plan.total, 1)) * 100) : 0;
  return (
    <button
      className={`orc-row${openKey === card.key ? " sel" : ""} st-${status.key}`}
      data-orc={card.key}
      aria-current={openKey === card.key}
      title={`${card.title} — ${status.label}`}
      onClick={() => openCard(card.key, true)}
    >
      <span className="orc-row-top">
        <span className="dot" aria-hidden="true" />
        <b>{card.title}</b>
        {usage.compactions ? <span className="cbadge">{usage.compactions}×</span> : null}
        {usage.model && (
          <span className={`mchip m-${modelFamily(String(usage.model))}`} title={String(usage.model)}>
            {modelShort(String(usage.model))}
          </span>
        )}
      </span>
      <span className="orc-row-sub">
        {plan ? `${plan.done}/${plan.total} plan` : "no plan"}
        <span>{workers.total ? `${workers.done}/${workers.total} workers` : ""}</span>
      </span>
      <span className="orc-mini" aria-hidden="true">
        <span style={{ width: `${pct}%` }} />
      </span>
    </button>
  );
}

function Sidebar({ cards }: { cards: Card[] }) {
  const openKey = useStore((state) => state.openKey);
  const [collapsed, setCollapsed] = useState(savedCollapsed);
  const count = (key: string) => cards.filter((card) => orcState(card).key === key).length;
  const toggle = () => {
    const value = !collapsed;
    setCollapsed(value);
    try {
      localStorage.setItem("fsa-orc-collapsed", value ? "1" : "0");
    } catch {}
  };
  return (
    <nav className={`orc-side${collapsed ? " collapsed" : ""}`} aria-label="Orchestrators">
      <div className="orc-side-head">
        <span>Orchestrators</span>
        <span className="fcount">{cards.length}</span>
        <button
          className="tbtn orc-collapse"
          id="orc-collapse"
          aria-label={`${collapsed ? "Expand" : "Collapse"} orchestrator list`}
          onClick={toggle}
        >
          {collapsed ? "›" : "‹"}
        </button>
      </div>
      <button
        className={`orc-row orc-all${openKey ? "" : " sel"}`}
        data-orc=""
        aria-current={!openKey}
        onClick={closePanel}
      >
        <b>All orchestrators</b>
        <span className="orc-row-sub">
          {count("running")} running · {count("waiting")} waiting · {count("stale")} stale
        </span>
      </button>
      {cards.map((card) => (
        <SidebarRow card={card} key={card.key} />
      ))}
    </nav>
  );
}

function Legend() {
  return (
    <div className="legend" aria-label="Legend">
      <span>Square colour is the model:</span>
      {MODELS.map(([key, label]) => (
        <span key={key}>
          <span className={`sq m-${key}`} />
          {label}
        </span>
      ))}
      <span>
        <span className="sq m-other running" />
        running
      </span>
      <span>
        <span className="sq m-other done" />
        done
      </span>
      <span>
        <span className="sq failed" />
        failed
      </span>
      <span>Context bar: green &lt; 80%, amber &lt; 90%, red above · N× = compactions</span>
    </div>
  );
}

function useInlinePanel(inline: boolean): void {
  useEffect(() => {
    const panel = document.getElementById("panel");
    const slot = document.getElementById("orc-detail");
    if (panel && inline && slot && panel.parentNode !== slot) slot.appendChild(panel);
    if (panel && !inline && panel.parentNode !== document.body) document.body.appendChild(panel);
    return () => {
      if (panel && panel.parentNode !== document.body) document.body.appendChild(panel);
    };
  }, [inline]);
}

export function Orchestrators({ cards, total }: { cards: Card[]; total: number }) {
  const feed = useStore((state) => state.fleet.feed);
  const openKey = useStore((state) => state.openKey);
  const inline = !!openKey && typeof matchMedia === "function" && matchMedia("(min-width: 1101px)").matches;
  useInlinePanel(inline);
  return (
    <>
      <div id="fleet-top">
        <FleetTiles />
        <FleetToolbar shown={cards.length} total={total} />
      </div>
      <div className={`orc-shell${feed && !inline ? " with-feed" : ""}${inline ? " inline-detail" : ""}`}>
        <div id="orc-side-wrap">
          <Sidebar cards={cards} />
        </div>
        <div className="orc-main">
          <div id="orc-cards">
            <div className="orc-grid">
              {cards.length ? (
                cards.map((card) => <OrcCard card={card} key={card.key} />)
              ) : (
                <div className="none">No orchestrators match.</div>
              )}
            </div>
          </div>
        </div>
        {inline ? (
          <div className="orc-detail" id="orc-detail" />
        ) : (
          <div id="feed-wrap">
            <Activity />
          </div>
        )}
      </div>
      <div id="orc-legend">
        <Legend />
      </div>
    </>
  );
}

export { isRunning, isStale, needsHuman };
