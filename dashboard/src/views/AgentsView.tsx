import { Layout } from "../components/Layout";
import { fleetCompare, fleetMatches } from "../lib/cards";
import type { DashState } from "../lib/types";
import { setFavOnly, setFleet, useStore } from "../store";
import { openNewSession } from "../terminal/HerdrOverlay";
import { Orchestrators } from "./agents/Orchestrators";

function AgentsActions({ state }: { state: DashState | null }) {
  const favouriteOnly = useStore((value) => value.favOnly);
  const feed = useStore((value) => value.fleet.feed);
  const favouriteCount = state
    ? `Favourites only (${state.cards.filter((card) => card.favourite).length})`
    : "Favourites only";
  return (
    <>
      <button
        className="newsess"
        id="newsess"
        title="Open a new herdr tab and start Claude, Codex or Grok in it"
        onClick={(event) => openNewSession(event.currentTarget)}
      >
        + New session
      </button>
      <button
        className="favsw"
        id="favsw"
        role="switch"
        aria-checked={favouriteOnly}
        onClick={() => setFavOnly(!favouriteOnly)}
      >
        <span className="track" aria-hidden="true"></span>
        {favouriteCount}
      </button>
      <button
        className="tbtn"
        id="ffeed"
        aria-pressed={feed}
        title="Show or hide the activity feed"
        onClick={() => setFleet({ feed: !feed })}
      >
        Activity
      </button>
    </>
  );
}

export function AgentsView() {
  const state = useStore((value) => value.state);
  const favouriteOnly = useStore((value) => value.favOnly);
  const fleet = useStore((value) => value.fleet);
  if (!state) return <Layout actions={<AgentsActions state={state} />}>{null}</Layout>;
  const pool = favouriteOnly ? state.cards.filter((card) => card.favourite) : state.cards;
  const cards = pool
    .filter((card) => fleetMatches(card, fleet))
    .sort((left, right) => fleetCompare(left, right, fleet));
  return (
    <Layout actions={<AgentsActions state={state} />}>
      <Orchestrators cards={cards} total={pool.length} />
    </Layout>
  );
}
