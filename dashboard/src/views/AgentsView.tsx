import { fleetCompare, fleetMatches } from "../lib/cards";
import { useStore } from "../store";
import { Orchestrators } from "./agents/Orchestrators";

export function AgentsView() {
  const state = useStore((value) => value.state);
  const favouriteOnly = useStore((value) => value.favOnly);
  const fleet = useStore((value) => value.fleet);
  if (!state) return null;
  const pool = favouriteOnly ? state.cards.filter((card) => card.favourite) : state.cards;
  const cards = pool.filter((card) => fleetMatches(card, fleet)).sort((left, right) => fleetCompare(left, right, fleet));
  return <Orchestrators cards={cards} total={pool.length} />;
}
