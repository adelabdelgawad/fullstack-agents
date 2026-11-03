import { useEffect, useRef } from "react";
import { gitBadge } from "../lib/cards";
import type { Card, DashState } from "../lib/types";
import { closePanel, openCard, store, useStore } from "../store";
import { CardTerminal } from "../terminal/CardTerminal";
import { GitTab, resetGit } from "./GitTab";
import { consumePreparedRun, InfoTab, prepareRunLog, repollLog, resetRunEffects } from "./InfoTab";
import { PanelHead } from "./PanelHead";

export function openRunLog(cardKey: string, runId: string): void {
  prepareRunLog(runId, cardKey);
  openCard(cardKey);
  store.set({ openRun: runId });
}

function PanelTabs({ tab, card }: { tab: string; card: Card }) {
  return (
    <div className="ptabs" id="ptabs" role="tablist">
      <button
        className="tab2"
        role="tab"
        data-t="info"
        aria-selected={tab === "info"}
        onClick={() => store.set({ tab2: "info" })}
      >
        Information
      </button>
      <button
        className="tab2"
        role="tab"
        data-t="git"
        aria-selected={tab === "git"}
        disabled={!card.tree}
        onClick={() => store.set({ tab2: "git" })}
      >
        Git changes
        {gitBadge(card) ? (
          <>
            {" "}
            <span className="badge">{gitBadge(card)}</span>
          </>
        ) : null}
      </button>
      <button
        className="tab2"
        role="tab"
        data-t="terminal"
        aria-selected={tab === "terminal"}
        onClick={() => store.set({ tab2: "terminal" })}
      >
        Terminal
      </button>
    </div>
  );
}

function PanelContent({
  card,
  state,
  openRun,
  tab,
}: {
  card: Card;
  state: DashState;
  openRun: string | null;
  tab: string;
}) {
  return (
    <>
      <div className="ptop">
        <PanelTabs tab={tab} card={card} />
        <button className="action-button close" id="close" onClick={closePanel}>
          Close
        </button>
      </div>
      <PanelHead card={card} state={state} />
      <div className="pbody" id="pbody">
        {tab === "terminal" ? (
          <CardTerminal card={card} />
        ) : tab === "git" && card.tree ? (
          <GitTab card={card} />
        ) : (
          <InfoTab card={card} state={state} openRun={openRun} />
        )}
      </div>
    </>
  );
}

export function Panel() {
  const state = useStore((s) => s.state),
    openKey = useStore((s) => s.openKey),
    openRun = useStore((s) => s.openRun),
    tab = useStore((s) => s.tab2);
  const previousKey = useRef(openKey),
    previousRun = useRef(openRun);
  const card = openKey && state?.cards.find((item) => item.key === openKey);
  useEffect(() => {
    if (previousKey.current !== openKey) {
      resetGit();
      previousKey.current = openKey;
    }
  }, [openKey]);
  useEffect(() => {
    if (previousRun.current !== openRun) {
      if (!consumePreparedRun(openRun)) resetRunEffects();
      previousRun.current = openRun;
    }
  }, [openRun]);
  useEffect(() => {
    const visible = () => {
      if (!document.hidden && store.get().openRun) repollLog();
    };
    document.addEventListener("visibilitychange", visible);
    return () => document.removeEventListener("visibilitychange", visible);
  }, []);
  const open = !!card && !!state;
  return (
    <aside id="panel" aria-label="Details" className={open ? "open" : ""}>
      {open ? <PanelContent card={card} state={state} openRun={openRun} tab={tab} /> : null}
    </aside>
  );
}
