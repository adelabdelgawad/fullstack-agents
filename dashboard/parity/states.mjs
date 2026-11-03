export const SEED = {
  "fsa-view": "agents", "fsa-fav-only": "0", "fsa-filter": "all", "fsa-sort": "stage",
  "fsa-feed": "1", "fsa-tiles": "1", "fsa-wall": "0",
};

export const ROOTS = ["header", "#main", "#panel", "#ctx", "#out", "#toasts"];

const CARD = "article.card[data-key]";
const TREE_CARD = 'article.card[data-key^="/"]';

export const STATES = [
  {name: "shell", unit: "U1", roots: ["header", "#ctx", "#out", "#toasts"]},
  {name: "ctx-menu", unit: "U1", roots: ["#ctx"], steps: [{rightclick: CARD}]},
  {name: "agents", unit: "U2", roots: ["#main"]},
  {name: "agents-fav-only", unit: "U2", seed: {"fsa-fav-only": "1"}, roots: ["header", "#main"]},
  {name: "agents-feed-off", unit: "U2", seed: {"fsa-feed": "0"}, roots: ["header", "#main"]},
  {name: "agents-tiles-off", unit: "U2", seed: {"fsa-tiles": "0"}, roots: ["#main"]},
  {name: "agents-wall", unit: "U2", steps: [{click: "#fwall"}], roots: ["header", "#main"]},
  {name: "agents-text-filter", unit: "U2", steps: [{fill: "#ftext", value: "a"}], roots: ["#main"]},
  {name: "agents-filter-running", unit: "U2", seed: {"fsa-filter": "running"}, roots: ["#main"]},
  {name: "agents-filter-blowouts", unit: "U2", seed: {"fsa-filter": "blowouts"}, roots: ["#main"]},
  {name: "agents-sort-cost", unit: "U2", steps: [{select: "#fsort", value: "cost"}], roots: ["#main"]},
  {name: "agents-feed-toggle", unit: "U2", steps: [{click: "#ffeed"}], roots: ["header", "#main"]},
  {name: "panel-info", unit: "U3", steps: [{click: CARD}], roots: ["#main", "#panel"]},
  {name: "panel-git", unit: "U3", steps: [{click: TREE_CARD}, {click: '.tab2[data-t="git"]'}], roots: ["#panel"]},
  {name: "panel-run-log", unit: "U3", steps: [{click: TREE_CARD}, {click: "#info [data-open-run]"}], roots: ["#panel"]},
  {name: "out-console", unit: "U3", steps: [{click: TREE_CARD}, {click: "#info [data-agent]"}], roots: ["#out"]},
  {name: "panel-close", unit: "U3", steps: [{click: CARD}, {key: "Escape"}], roots: ["#main", "#panel"]},
  {name: "panel-terminal", unit: "U4", steps: [{click: CARD}, {click: '.tab2[data-t="terminal"]'}], roots: ["#panel"]},
  {name: "herdr-new-session", unit: "U4", steps: [{click: "#newsess"}], roots: [".herdr-menu", ".herdr-modal-backdrop"]},
  {name: "herdr", unit: "U4", seed: {"fsa-view": "herdr"}, roots: ["header", "#main"]},
  {name: "history", unit: "U5", seed: {"fsa-view": "history"}, roots: ["header", "#main"]},
];
