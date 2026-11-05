import { useEffect, type ReactNode } from "react";
import { esc } from "../lib/format";
import type { DashState } from "../lib/types";
import { setView, setWall, useStore, viewFromPath } from "../store";
import type { View } from "../store";

const VIEWS: Array<[View, string]> = [
  ["agents", "Agents"],
  ["herdr", "Herdr"],
  ["history", "History"],
];

function ViewIcon({ view }: { view: View }) {
  const paths: Record<View, string> = {
    agents:
      "M8 1.5a2.5 2.5 0 0 0-1 4.79v1.42a2.5 2.5 0 1 0 2 0V6.29A2.5 2.5 0 0 0 8 1.5ZM3.5 8a2 2 0 1 0 0 4 2 2 0 0 0 0-4Zm9 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4Z",
    herdr: "M2 2.5h12v9H8.75L6 14v-2.5H2v-9Zm2.25 2 2.25 2-2.25 2 1 1 3.25-3-3.25-3-1 1ZM9 9.5h3v-1.5H9v1.5Z",
    history:
      "M8 1.5a6.5 6.5 0 1 1-6.15 4.39l1.42.48A5 5 0 1 0 4.4 4.5H6v1.5H1.5V1.5H3v1.72A6.47 6.47 0 0 1 8 1.5Zm-.75 3h1.5v3.19l2.37 1.37-.75 1.3-3.12-1.8V4.5Z",
  };
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true">
      <path fill="currentColor" d={paths[view]} />
    </svg>
  );
}

function ViewTabs({ view, state }: { view: View; state: DashState | null }) {
  const count = (tab: View): number | null =>
    tab === "agents" ? (state?.cards.length ?? 0) : tab === "history" && state ? state.history.length : null;
  return (
    <div className="viewtabs" role="tablist" aria-label="Dashboard view">
      {VIEWS.map(([tab, label]) => (
        <a
          href={`/next/${tab}`}
          key={tab}
          className="viewtab"
          id={`view-${tab}`}
          role="tab"
          data-view={tab}
          aria-selected={view === tab}
          aria-label={label}
          onClick={(event) => {
            if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
            event.preventDefault();
            setView(tab);
          }}
        >
          <ViewIcon view={tab} />
          <span>{label}</span>
          {count(tab) !== null && <span className="viewtab-count">{count(tab)}</span>}
        </a>
      ))}
    </div>
  );
}

function metaHtml(state: DashState | null, offline: boolean): string {
  if (offline) return '<span class="dot"></span>offline — retrying';
  if (!state) return '<span class="dot"></span>loading…';
  const lock = state.locks.deploy ? '<span class="lock">deploy lock held</span> · ' : "";
  return `<span class="dot"></span>${esc(state.repo.split("/").pop())} · ${lock}${new Date(state.generated * 1000).toLocaleTimeString()}`;
}

export function Layout({ actions, children }: { actions?: ReactNode; children: ReactNode }) {
  const view = useStore((state) => state.view);
  const wall = useStore((state) => state.wall);
  const state = useStore((storeState) => storeState.state);
  const offline = useStore((storeState) => storeState.offline);
  useEffect(() => {
    if (["/", "/next", "/next/"].includes(window.location.pathname)) {
      window.history.replaceState(null, "", `/next/${view}${window.location.search}${window.location.hash}`);
    }
    const onPopState = () => setView(viewFromPath(window.location.pathname), false);
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);
  return (
    <>
      <header className={view === "herdr" ? undefined : "retro-header"}>
        <ViewTabs view={view} state={state} />
        <div className="hright">
          {actions}
          <button
            className="favsw"
            id="fwall"
            role="switch"
            aria-checked={wall}
            title="Wall mode: hide the sidebar, filters and feed (key w)"
            onClick={() => setWall(!wall)}
          >
            <span className="track" aria-hidden="true"></span>
            Wall mode
          </button>
          <div
            className={`status${offline ? " error" : ""}`}
            id="meta"
            title={state ? state.repo : undefined}
            dangerouslySetInnerHTML={{ __html: metaHtml(state, offline) }}
          />
        </div>
      </header>
      <main id="main" className={view === "herdr" ? undefined : "retro-workspace"}>
        {children}
      </main>
    </>
  );
}
