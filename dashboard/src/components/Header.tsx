import { esc } from "../lib/format";
import type { DashState } from "../lib/types";
import { setFavOnly, setFleet, setView, setWall, useStore } from "../store";
import type { View } from "../store";
import { openNewSession } from "../terminal/HerdrOverlay";

const VIEWS: Array<[View, string]> = [
  ["agents", "Agents"],
  ["herdr", "Herdr"],
  ["history", "History"],
];

function ViewTabs({ view }: { view: View }) {
  return (
    <div className="viewtabs" role="tablist" aria-label="Dashboard view">
      {VIEWS.map(([v, label]) => (
        <button key={v} className="viewtab" id={`view-${v}`} role="tab" data-view={v} aria-selected={view === v} onClick={() => setView(v)}>
          {label}
        </button>
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

function AgentsControls({ state }: { state: DashState | null }) {
  const favOnly = useStore((s) => s.favOnly);
  const feed = useStore((s) => s.fleet.feed);
  const hidden = useStore((s) => s.view) !== "agents";
  const favCount = state && !hidden ? `Favourites only (${state.cards.filter((c) => c.favourite).length})` : "Favourites only";
  return (
    <>
      <button className="newsess" id="newsess" title="Open a new herdr tab and start Claude, Codex or Grok in it" hidden={hidden} onClick={(e) => openNewSession(e.currentTarget)}>
        + New session
      </button>
      <button className="favsw" id="favsw" role="switch" aria-checked={favOnly} hidden={hidden} onClick={() => setFavOnly(!favOnly)}>
        <span className="track" aria-hidden="true"></span>
        {favCount}
      </button>
      <button className="tbtn" id="ffeed" aria-pressed={feed} hidden={hidden} title="Show or hide the activity feed" onClick={() => setFleet({ feed: !feed })}>
        Activity
      </button>
    </>
  );
}

export function Header() {
  const view = useStore((s) => s.view);
  const wall = useStore((s) => s.wall);
  const state = useStore((s) => s.state);
  const offline = useStore((s) => s.offline);
  return (
    <header>
      <ViewTabs view={view} />
      <div className="hright">
        <AgentsControls state={state} />
        <button className="favsw" id="fwall" role="switch" aria-checked={wall} title="Wall mode: hide the sidebar, filters and feed (key w)" onClick={() => setWall(!wall)}>
          <span className="track" aria-hidden="true"></span>
          Wall mode
        </button>
        <div className={`status${offline ? " error" : ""}`} id="meta" title={state ? state.repo : undefined} dangerouslySetInnerHTML={{ __html: metaHtml(state, offline) }} />
      </div>
    </header>
  );
}
