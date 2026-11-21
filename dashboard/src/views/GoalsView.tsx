import type { Card, Goal } from "../lib/types";
import { openCard, setView, useStore } from "../store";
import "../styles/goals.css";

function cardName(card: Card | undefined, key: string): string {
  return card?.title || card?.label || key;
}

function showCard(key: string): void {
  setView("agents");
  openCard(key);
}

function GoalRow({ goal, cards }: { goal: Goal; cards: Card[] }) {
  const percent = goal.total ? Math.round((goal.done / goal.total) * 100) : 0;
  return (
    <article className={`goal-card goal-${goal.status}`}>
      <div className="goal-head">
        <span className="goal-id">{goal.id}</span>
        <h3>{goal.title}</h3>
        <span className="goal-status">{goal.status}</span>
      </div>
      <div className="goal-meta">
        {goal.owner ? `Owner: ${goal.owner}` : "No owner"}
        {goal.requests.length ? ` · Requests: ${goal.requests.join(", ")}` : ""}
      </div>
      <div
        className="goal-bar"
        role="progressbar"
        aria-label={`${goal.title} progress`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
      >
        <span style={{ width: `${percent}%` }} />
      </div>
      <div className="goal-meta">{`${goal.done} of ${goal.total} linked agents complete`}</div>
      {goal.cards.length > 0 && (
        <ul className="goal-cards">
          {goal.cards.map((key) => (
            <li key={key}>
              <button type="button" onClick={() => showCard(key)}>
                {cardName(
                  cards.find((card) => card.key === key),
                  key,
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}

const ORDER: Record<string, number> = { active: 0, done: 1, dropped: 2 };

export function GoalsView() {
  const goals = useStore((s) => s.state?.goals) || [];
  const cards = useStore((s) => s.state?.cards) || [];
  const sorted = [...goals].sort((a, b) => (ORDER[a.status] ?? 3) - (ORDER[b.status] ?? 3));
  return (
    <div className="goals">
      {sorted.length ? (
        sorted.map((goal) => <GoalRow key={`${goal.repo || ""}:${goal.id}`} goal={goal} cards={cards} />)
      ) : (
        <article className="goal-card">
          <p>No goals yet.</p>
          <p className="goal-meta">
            Create one with <code>fsa-task goal add --title "…" --owner CTO</code>, then link work to it with{" "}
            <code>fsa-task goal link --id G1 --requests R12</code>.
          </p>
        </article>
      )}
    </div>
  );
}
