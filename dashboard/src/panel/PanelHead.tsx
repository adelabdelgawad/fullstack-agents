import { gitBadge, STAGE_LABEL, worktreesOf } from "../lib/cards";
import type { Card, DashState } from "../lib/types";
import { openCard } from "../store";

export function PanelHead({ card, state }: { card: Card; state: DashState }) {
  const worktrees = worktreesOf(card, state);
  if (worktrees.length <= 1) return <div id="phead"></div>;
  return (
    <div id="phead">
      <div className="wtbar" role="group" aria-label={`Worktrees of session ${card.sessions[0].name}`}>
        {worktrees.map((item) => {
          const count = gitBadge(item);
          return (
            <button
              className="wt"
              data-wt={item.key}
              aria-current={item.key === card.key}
              title={item.key}
              onClick={() => item.key !== card.key && openCard(item.key, true)}
              key={item.key}
            >
              <span className="wt-name">{item.tree?.branch || item.key.split("/").pop()}</span>
              {count ? <span className="chip">{count} uncommitted</span> : null}
              <span className="chip">{STAGE_LABEL(item)}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
