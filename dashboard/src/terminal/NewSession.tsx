import { useEffect, useRef, useState } from "react";
import { nodeUrl } from "../lib/api";
import type { HerdrState } from "../lib/types";
import { focusNode, load, store, useStore } from "../store";

export const SESSION_ENGINES = {
  claude: ["Claude", "Opens a new tab in the space and runs cc -n '<name>'"],
  codex: ["Codex", "Opens a new tab in the space, named <name>, and runs codex"],
  grok: ["Grok", "Opens a new tab in the space, named <name>, and runs opencode -m xai/grok-4.7"],
} as const;

const NEW_SPACE = "\u0000new";

interface ActionResult {
  ok: boolean;
  error?: unknown;
  result?: unknown;
}
type Action = (action: string, params: Record<string, unknown>, ownerRoot: HTMLElement | null) => Promise<ActionResult>;

interface DirListing {
  path: string;
  parent: string | null;
  git: boolean;
  home: string;
  dirs: Array<{ name: string; path: string; git: boolean }>;
  truncated: boolean;
}

const field = (record: Record<string, unknown> | undefined, key: string): string => String(record?.[key] ?? "");
const baseName = (path: string): string => path.replace(/\/+$/, "").split("/").pop() || path;

async function fetchOn<T>(node: string, path: string): Promise<T> {
  const response = await fetch(nodeUrl(path, node), { cache: "no-store" });
  if (!response.ok) throw new Error((await response.text()) || `error ${response.status}`);
  return (await response.json()) as T;
}

/** A folder browser over one node's filesystem: click a folder to open it, "use" to pick the one shown. */
export function PathPicker({ node, start, pick }: { node: string; start: string; pick: (path: string) => void }) {
  const [listing, setListing] = useState<DirListing | null>(null);
  const [error, setError] = useState("");
  const open = (path: string) => {
    setError("");
    fetchOn<DirListing>(node, `/api/fs/dirs?path=${encodeURIComponent(path)}`)
      .then(setListing)
      .catch((err: Error) =>
        setError(err.message === "error 404" ? "This host's dashboard cannot list folders (update it)" : err.message),
      );
  };
  useEffect(() => open(start), [node]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="path-picker" role="group" aria-label="Choose a folder">
      <div className="path-picker-head">
        <button type="button" disabled={!listing?.parent} onClick={() => listing?.parent && open(listing.parent)} aria-label="Parent folder">
          ..
        </button>
        <span>{listing?.path || "…"}</span>
        <button type="button" disabled={!listing} onClick={() => listing && pick(listing.path)}>
          use this folder
        </button>
      </div>
      {error && <div className="path-picker-note herdr-modal-error">{error}</div>}
      <ul>
        {listing?.dirs.map((dir) => (
          <li key={dir.path}>
            <button type="button" onClick={() => open(dir.path)} onDoubleClick={() => pick(dir.path)}>
              <span>{dir.name}/</span>
              {dir.git && <span className="git">git</span>}
            </button>
          </li>
        ))}
      </ul>
      {listing && !listing.dirs.length && <div className="path-picker-note">no sub-folders</div>}
      {listing?.truncated && <div className="path-picker-note">only the first 500 folders are listed</div>}
    </div>
  );
}

/** The workspace ids a node's herdr reports. */
const spaceIds = (data: HerdrState | null): Set<string> =>
  new Set((data?.workspaces || []).map((space) => field(space as Record<string, unknown>, "workspace_id")));

/** The id herdr gave a workspace it just created: from its reply, else the one id that is new since before. */
function createdSpace(result: unknown, before: Set<string>): string {
  const reply = (result || {}) as Record<string, unknown>;
  const nested = (reply.workspace || {}) as Record<string, unknown>;
  const id = field(nested, "workspace_id") || field(reply, "workspace_id");
  if (id) return id;
  return [...spaceIds(store.get().herdrData)].find((space) => !before.has(space)) || "";
}

/** New session: the node, then a workspace on it (existing, or a new one at a folder picked there), agent and name. */
export function NewSessionModal({ action, close }: { action: Action; close: () => void }) {
  const focused = useStore((s) => s.node);
  const nodes = useStore((s) => s.nodes);
  const [node, setNode] = useState(focused);
  const [herdr, setHerdr] = useState<HerdrState | null>(null);
  const [herdrError, setHerdrError] = useState("");
  const [space, setSpace] = useState("");
  const [path, setPath] = useState("");
  const [browsing, setBrowsing] = useState(false);
  const [engine, setEngine] = useState<keyof typeof SESSION_ENGINES>("claude");
  const [busy, setBusy] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let live = true;
    setHerdr(null);
    setHerdrError("");
    setBrowsing(false);
    fetchOn<HerdrState>(node, "/api/herdr")
      .then((data) => {
        if (!live) return;
        setHerdr(data);
        const spaces = (data.workspaces || []) as Record<string, unknown>[];
        const panes = (data.panes || []) as Record<string, unknown>[];
        const current = field(panes.find((pane) => field(pane, "pane_id") === data.focused_pane_id), "workspace_id");
        setSpace(data.running && spaces.length ? current || field(spaces[0], "workspace_id") : NEW_SPACE);
      })
      .catch((err: Error) => live && setHerdrError(err.message));
    return () => {
      live = false;
    };
  }, [node]);
  const spaces = ((herdr?.workspaces || []) as Record<string, unknown>[]);
  const running = Boolean(herdr?.running);
  const fail = (message: string) => {
    const el = root.current?.querySelector<HTMLElement>(".herdr-modal-error");
    if (el) el.textContent = message;
  };
  const submit = async (form: HTMLFormElement) => {
    const name = (form.elements.namedItem("name") as HTMLInputElement).value.trim();
    if (!name || name.length > 80 || name.startsWith("-")) return fail('Name must be 1–80 characters and not start with "-"');
    if (space === NEW_SPACE && !path.startsWith("/")) return fail("Pick the workspace folder (an absolute path)");
    setBusy(true);
    const owner = root.current;
    focusNode(node);
    let workspace = space;
    if (space === NEW_SPACE) {
      const label = ((form.elements.namedItem("space-label") as HTMLInputElement).value.trim() || baseName(path)).slice(0, 80);
      const before = spaceIds(herdr);
      const made = await action("workspace.create", { label, cwd: path }, owner);
      workspace = made.ok ? createdSpace(made.result, before) : "";
      if (!workspace) {
        setBusy(false);
        if (made.ok) fail("The workspace was created but herdr did not report its id; pick it from the list");
        return;
      }
    }
    const started = await action("session.create", { workspace_id: workspace, name, engine }, owner);
    setBusy(false);
    if (!started.ok) return;
    close();
    void load();
  };
  return (
    <div className="herdr-modal-backdrop" ref={root}>
      <div className="herdr-modal new-session-modal" role="dialog" aria-modal="true" aria-labelledby="new-session-title">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void submit(event.currentTarget);
          }}
        >
          <h2 id="new-session-title">new session</h2>
          {nodes.length > 0 && (
            <label>
              node
              <select name="node" value={node} onChange={(event) => setNode(event.currentTarget.value)}>
                <option value="">This host</option>
                {nodes.map((n) => (
                  <option key={n.id} value={n.id}>
                    {n.label} ({n.host})
                  </option>
                ))}
              </select>
            </label>
          )}
          <label>
            agent
            <select name="engine" value={engine} onChange={(event) => setEngine(event.currentTarget.value as typeof engine)}>
              {Object.entries(SESSION_ENGINES).map(([key, value]) => (
                <option key={key} value={key}>
                  {value[0]}
                </option>
              ))}
            </select>
          </label>
          <label>
            name
            <input name="name" maxLength={80} autoComplete="off" required autoFocus />
          </label>
          <label>
            workspace
            <select name="space" value={space} disabled={!herdr || !running} onChange={(event) => setSpace(event.currentTarget.value)}>
              {spaces.map((workspace) => (
                <option key={field(workspace, "workspace_id")} value={field(workspace, "workspace_id")}>
                  {field(workspace, "label") || field(workspace, "workspace_id")}
                </option>
              ))}
              <option value={NEW_SPACE}>New workspace…</option>
            </select>
          </label>
          {space === NEW_SPACE && running && (
            <>
              <label>
                workspace name
                <input name="space-label" maxLength={80} autoComplete="off" placeholder={path ? baseName(path) : "the folder name"} />
              </label>
              <label htmlFor="new-space-path">folder</label>
              <div className="path-row">
                <input
                  id="new-space-path"
                  name="path"
                  value={path}
                  onChange={(event) => setPath(event.currentTarget.value)}
                  placeholder="/home/you/project"
                  autoComplete="off"
                />
                <button type="button" onClick={() => setBrowsing(!browsing)} aria-expanded={browsing}>
                  browse
                </button>
              </div>
              {browsing && (
                <PathPicker
                  node={node}
                  start={path}
                  pick={(picked) => {
                    setPath(picked);
                    setBrowsing(false);
                  }}
                />
              )}
            </>
          )}
          <p className="herdr-modal-note">
            {herdrError
              ? `Cannot reach this node: ${herdrError}`
              : herdr && !running
                ? "herdr is not running on this node"
                : SESSION_ENGINES[engine][1]}
          </p>
          <div className="herdr-modal-error" aria-live="polite"></div>
          <div className="herdr-modal-actions">
            <button type="button" data-herdr-cancel="" onClick={close}>
              cancel
            </button>
            <button type="submit" className="primary" disabled={busy || !running}>
              {busy ? "starting…" : "start"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
