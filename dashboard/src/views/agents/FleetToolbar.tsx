import { setFleet, useStore } from "../../store";

const FILTERS = [
  ["all", "All"],
  ["running", "Running"],
  ["waiting", "Waiting"],
  ["stale", "Stale"],
  ["blowouts", "Blowouts"],
];
const SORTS = [
  ["stage", "Stage order"],
  ["updated", "Last update"],
  ["cost", "Cost"],
  ["context", "Context fill"],
];

export function FleetToolbar({ shown, total }: { shown: number; total: number }) {
  const fleet = useStore((state) => state.fleet);
  return (
    <div className="fleet-toolbar">
      <div className="fseg" role="group">
        {FILTERS.map(([key, label]) => (
          <button
            key={key}
            data-ffilter={key}
            aria-pressed={fleet.filter === key}
            onClick={() => setFleet({ filter: key })}
          >
            {label}
          </button>
        ))}
      </div>
      <label>
        Sort{" "}
        <select id="fsort" value={fleet.sort} onChange={(event) => setFleet({ sort: event.target.value })}>
          {SORTS.map(([key, label]) => (
            <option value={key} key={key}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <input
        id="ftext"
        type="search"
        placeholder="Filter by name, branch or model"
        value={fleet.text}
        aria-label="Filter cards"
        onChange={(event) => setFleet({ text: event.target.value })}
      />
      <span className="fcount">{shown === total ? `${total} orchestrators` : `${shown} of ${total} shown`}</span>
    </div>
  );
}
