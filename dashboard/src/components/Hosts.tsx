import { useEffect, useRef, useState, type FormEvent } from "react";
import { focusNode, reloadNodes, useStore } from "../store";

async function postNodes(path: string, body: unknown): Promise<string> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return response.ok ? "" : (await response.text()) || `error ${response.status}`;
}

/** Which dashboard every view shows: this host or a linked one. */
export function NodeSelect() {
  const node = useStore((s) => s.node);
  const nodes = useStore((s) => s.nodes);
  const nodeStates = useStore((s) => s.nodeStates);
  if (!nodes.length) return null;
  return (
    <label className="node-select" title="The host every view shows">
      <span className="visually-hidden">Host</span>
      <select value={node} onChange={(event) => focusNode(event.currentTarget.value)} aria-label="Host">
        <option value="">This host</option>
        {nodes.map((n) => (
          <option key={n.id} value={n.id}>
            {n.label}
            {nodeStates[n.id]?.offline ? " (offline)" : ""}
          </option>
        ))}
      </select>
    </label>
  );
}

/** Link another host's dashboard (address, port and its URL token), list the links and remove one. */
export function HostsDialog({ close }: { close: () => void }) {
  const nodes = useStore((s) => s.nodes);
  const nodeStates = useStore((s) => s.nodeStates);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const first = useRef<HTMLInputElement>(null);
  useEffect(() => {
    first.current?.focus();
    const key = (event: KeyboardEvent) => event.key === "Escape" && close();
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [close]);
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const value = (name: string) => (form.elements.namedItem(name) as HTMLInputElement).value.trim();
    setBusy(true);
    setError("");
    const failed = await postNodes("/api/nodes", {
      label: value("label"),
      host: value("host"),
      port: Number(value("port")),
      token: value("token"),
    }).catch((err: Error) => err.message);
    setBusy(false);
    if (failed) return setError(failed);
    form.reset();
    await reloadNodes();
  };
  const remove = async (id: string) => {
    const failed = await postNodes("/api/nodes/remove", { id }).catch((err: Error) => err.message);
    if (failed) return setError(failed);
    await reloadNodes();
  };
  return (
    <div className="herdr-modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && close()}>
      <div className="herdr-modal hosts-modal" role="dialog" aria-modal="true" aria-labelledby="hosts-title">
        <form onSubmit={(event) => void submit(event)}>
          <h2 id="hosts-title">linked hosts</h2>
          {nodes.length > 0 && (
            <ul className="hosts-list">
              {nodes.map((n) => (
                <li key={n.id}>
                  <span className={`dot${nodeStates[n.id]?.offline ? " off" : ""}`} aria-hidden="true"></span>
                  <button type="button" className="hosts-open" onClick={() => (focusNode(n.id), close())}>
                    {n.label}
                  </button>
                  <span className="hosts-addr">
                    {n.host}:{n.port}
                    {nodeStates[n.id]?.offline ? " · offline" : ""}
                  </span>
                  <button type="button" className="danger" onClick={() => void remove(n.id)} aria-label={`Remove ${n.label}`}>
                    remove
                  </button>
                </li>
              ))}
            </ul>
          )}
          <label>
            name
            <input ref={first} name="label" maxLength={40} autoComplete="off" placeholder="GPU box" />
          </label>
          <label>
            IP or host name
            <input name="host" required maxLength={253} autoComplete="off" placeholder="10.0.0.12" />
          </label>
          <label>
            port
            <input name="port" required type="number" min={1} max={65535} defaultValue={8766} />
          </label>
          <label>
            token
            <input name="token" required type="password" autoComplete="off" placeholder="the t= value of its dashboard URL" />
          </label>
          <p className="herdr-modal-note">
            The token stays on this host; the browser never sees it. Traffic to the linked host is plain HTTP, so link
            hosts on a trusted network or through a tunnel.
          </p>
          <div className="herdr-modal-error" aria-live="polite">
            {error}
          </div>
          <div className="herdr-modal-actions">
            <button type="button" onClick={close}>
              close
            </button>
            <button type="submit" className="primary" disabled={busy}>
              {busy ? "linking…" : "link host"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

/** The header's "+ Host" button and its dialog. */
export function HostsButton() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" className="hosts-btn" onClick={() => setOpen(true)} title="Link another host's dashboard">
        + Host
      </button>
      {open && <HostsDialog close={() => setOpen(false)} />}
    </>
  );
}
