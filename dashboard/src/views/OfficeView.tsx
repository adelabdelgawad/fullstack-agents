import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type MouseEvent,
  type MutableRefObject,
  type RefObject,
} from "react";
import { STATE_TEXT } from "../lib/cards";
import type { Card } from "../lib/types";
import { esc, fmtCost, fmtTokens } from "../lib/format";
import { openCard, toast, useStore } from "../store";
import "../styles/office.css";
import { CardTerminal } from "../terminal/CardTerminal";
import { drawOffice, hitTest, pcHit, roomHit } from "./office/draw";
import { Walks } from "./office/walk";
import { ASSISTANT_ID, BREAK_ROUND_MS, CTO_ID, EMPTY_LAYOUT, roomOfTeam, layoutOffice, officeOf, teamOfEmployee, type Office, type OfficeEmployee, type OfficeLayout } from "./office/model";

interface SendResult {
  ok?: boolean;
  error?: string;
}

function redraw(
  canvas: HTMLCanvasElement,
  office: Office,
  selectedId: string | null,
  placed: MutableRefObject<OfficeLayout>,
  zoomed: boolean,
  walks: Walks,
  animate: boolean,
): boolean {
  const available = canvas.parentElement?.clientHeight || canvas.getBoundingClientRect().height;
  const initialBounds = canvas.getBoundingClientRect();
  const scale = initialBounds.width < 520 ? 1 : 2;
  const now = performance.now();
  placed.current = layoutOffice(office, initialBounds.width, available, scale, !zoomed, Math.floor(Date.now() / BREAK_ROUND_MS));
  const view = `${zoomed ? office.teams.map((team) => team.key).join("+") : "floor"}:${Math.round(initialBounds.width)}`;
  walks.update(placed.current, view, now, animate);
  const walkers = walks.walkers(now);
  canvas.style.height = `${Math.max(available, placed.current.height)}px`;
  const bounds = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  const width = Math.max(1, Math.round(bounds.width * ratio));
  const height = Math.max(1, Math.round(bounds.height * ratio));
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  const context = canvas.getContext("2d");
  if (!context) return walkers.size > 0;
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  drawOffice(context, placed.current, now, selectedId, walkers);
  return walkers.size > 0;
}

function useOfficeCanvas(
  canvasRef: RefObject<HTMLCanvasElement>,
  office: Office,
  selectedId: string | null,
  placed: MutableRefObject<OfficeLayout>,
  zoomed: boolean,
): void {
  const walks = useRef(new Walks());
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    let frame = 0;
    let lastPaint = -Infinity;
    let walking = false;
    const paint = () => {
      walking = redraw(canvas, office, selectedId, placed, zoomed, walks.current, !reduced);
    };
    const tick = (now: number) => {
      // Smooth frames while someone walks between rooms; the pixel-art idle loop needs only 8 a second.
      if (now - lastPaint >= (walking ? 40 : 125)) {
        paint();
        lastPaint = now;
      }
      frame = requestAnimationFrame(tick);
    };
    const syncAnimation = () => {
      cancelAnimationFrame(frame);
      if (document.hidden) return;
      paint();
      lastPaint = performance.now();
      if (!reduced && !document.hidden) frame = requestAnimationFrame(tick);
    };
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(syncAnimation);
    observer?.observe(canvas);
    document.addEventListener("visibilitychange", syncAnimation);
    window.addEventListener("resize", syncAnimation);
    syncAnimation();
    return () => {
      observer?.disconnect();
      document.removeEventListener("visibilitychange", syncAnimation);
      window.removeEventListener("resize", syncAnimation);
      cancelAnimationFrame(frame);
    };
  }, [canvasRef, office, placed, selectedId, zoomed]);
}

function teamLabel(office: Office, employee: OfficeEmployee): string {
  return teamOfEmployee(office, employee.id)?.label || employee.cardKey;
}

function usePrompt(employee: OfficeEmployee) {
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const send = async (event: FormEvent) => {
    event.preventDefault();
    const prompt = text.trim();
    if (!prompt || !employee.pane || sending) return;
    setSending(true);
    try {
      const response = await fetch("/api/herdr/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pane: employee.pane, kind: "prompt", text: prompt }),
      });
      const result = (await response.json().catch(() => ({ ok: false }))) as SendResult;
      if (!response.ok || !result.ok) throw new Error(result.error || `HTTP ${response.status}`);
      setText("");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Could not send prompt";
      toast(`<b>Send failed</b> ${esc(message)}`, "red");
    } finally {
      setSending(false);
    }
  };
  return { text, setText, sending, send };
}

function PromptForm({ employee }: { employee: OfficeEmployee }) {
  const { text, setText, sending, send } = usePrompt(employee);
  return (
    <form className="office-prompt" onSubmit={(event) => void send(event)}>
      <label htmlFor="office-prompt-text">Send a prompt</label>
      <textarea
        id="office-prompt-text"
        value={text}
        disabled={!employee.pane || sending}
        onChange={(event) => setText(event.target.value)}
        rows={4}
      />
      {!employee.pane && <p>View only: this session has no herdr pane</p>}
      <button type="submit" disabled={!employee.pane || !text.trim() || sending}>
        {sending ? "Sending…" : "Send"}
      </button>
    </form>
  );
}

/** Who the agent reports to and who it delegates to: the CTO leads every agent; a lead leads its workers and subagents. */
function ReportingChain({ employee }: { employee: OfficeEmployee }) {
  const reports = employee.reports || [];
  return (
    <div className="office-chain">
      {employee.id !== CTO_ID && <p>Reports to: CTO</p>}
      <p>{reports.length ? `Delegates to (${reports.length}):` : "Delegates to: nobody right now"}</p>
      {reports.length > 0 && (
        <ul>
          {reports.map((report) => (
            <li key={report.id}>
              <span className={`office-chain-dot pose-${report.pose}`} aria-hidden="true" />
              {report.name} · {report.role} · {STATE_TEXT[report.pose] || report.pose}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** One button per team: zoom the floor to that team's office (shared with a related team); "Whole floor" goes back. */
function TeamZoom({ teams, zoom, setZoom }: { teams: Office["teams"]; zoom: string | null; setZoom: (key: string | null) => void }) {
  return (
    <nav className="office-zoom" aria-label="Zoom to a team">
      <button type="button" aria-pressed={zoom === null} onClick={() => setZoom(null)}>
        Whole floor
      </button>
      {teams.map((team) => (
        <button
          key={team.key}
          type="button"
          aria-pressed={zoom === roomOfTeam(team)}
          onClick={() => setZoom(zoom === roomOfTeam(team) ? null : roomOfTeam(team))}
        >
          {team.label}
          <span>{team.employees.filter((employee) => employee.sessions > 0 || employee.fixed).length}</span>
        </button>
      ))}
    </nav>
  );
}

/** Everything waiting on the user, in one box: each entry opens its card. */
function DecisionBox() {
  const waiting = useStore((storeState) => storeState.state?.waiting || []);
  const [open, setOpen] = useState(false);
  if (!waiting.length) return null;
  return (
    <aside className="office-decisions" aria-label="Decisions waiting on you">
      <button type="button" className="office-decisions-head" aria-expanded={open} onClick={() => setOpen(!open)}>
        Decision box · {waiting.length} waiting on you
      </button>
      {open && (
        <ul>
          {waiting.map((entry) => (
            <li key={entry.key}>
              <button type="button" onClick={() => entry.card && openCard(entry.card)}>
                <strong>{entry.name}</strong>
                <span>{entry.snippet || "Waiting for your answer"}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}

function EmployeeDialog({ employee, team }: { employee: OfficeEmployee; team: string }) {
  const titleId = `office-dialog-${employee.id.replace(/[^a-z0-9_-]/gi, "-")}`;
  return (
    <section className="office-dialog" role="dialog" aria-labelledby={titleId}>
      <div className="office-dialog-head">
        <div>
          <h2 id={titleId}>{employee.name}</h2>
          <p>
            {team} · {employee.role}
          </p>
        </div>
        <button type="button" onClick={() => openCard(employee.cardKey)}>
          Open card
        </button>
      </div>
      <dl className="office-details">
        <div>
          <dt>Pose</dt>
          <dd>{STATE_TEXT[employee.pose] || employee.pose}</dd>
        </div>
        <div>
          <dt>Sessions</dt>
          <dd>
            {employee.sessions} active of {employee.total}
          </dd>
        </div>
        <div>
          <dt>Cost</dt>
          <dd>{fmtCost(employee.cost)}</dd>
        </div>
        <div>
          <dt>Tokens</dt>
          <dd>{fmtTokens(employee.tokens)}</dd>
        </div>
      </dl>
      {employee.bubble && <blockquote className="office-bubble">{employee.bubble}</blockquote>}
      <ReportingChain employee={employee} />
      <PromptForm employee={employee} />
    </section>
  );
}

function AccessibleEmployees({ office, select }: { office: Office; select: (id: string) => void }) {
  return (
    <div className="office-visually-hidden" aria-label="Office employees">
      {office.teams
        .flatMap((team) => team.employees)
        .map((employee) => (
          <button
            key={`${employee.cardKey}-${employee.role}-${employee.id}`}
            type="button"
            onClick={() => select(employee.id)}
          >
            {employee.name}, {employee.role}, {STATE_TEXT[employee.pose] || employee.pose}
          </button>
        ))}
    </div>
  );
}

function sessionTitle(card: Card): string {
  return card.sessions[0]?.name || card.title || card.label || card.key;
}

/** The CTO sees every session: one tab per live session, each with its live console. */
function CtoConsole({ close }: { close: () => void }) {
  const cards = useStore((storeState) => storeState.state?.cards || []);
  const [tab, setTab] = useState<string | null>(null);
  const current = cards.find((card) => card.key === tab) || cards[0] || null;
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [close]);
  return (
    <div className="office-console office-console-full" role="dialog" aria-modal="true" aria-label="CTO: all sessions">
      <div className="office-console-head">
        <h2>CTO · all sessions</h2>
        <button type="button" onClick={close}>
          Close
        </button>
      </div>
      <div className="office-console-tabs" role="tablist" aria-label="Sessions">
        {cards.map((card) => (
          <button
            key={card.key}
            type="button"
            role="tab"
            aria-selected={card.key === current?.key}
            className={card.key === current?.key ? "on" : ""}
            onClick={() => setTab(card.key)}
          >
            {sessionTitle(card)}
          </button>
        ))}
      </div>
      {current ? <CardTerminal key={current.key} card={current} /> : <div className="empty">No live sessions</div>}
    </div>
  );
}

export function OfficeView() {
  const state = useStore((storeState) => storeState.state);
  const office = useMemo(() => officeOf(state), [state]);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const placed = useRef<OfficeLayout>(EMPTY_LAYOUT);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [consoleId, setConsoleId] = useState<string | null>(null);
  const [zoom, setZoom] = useState<string | null>(null);
  const zoomTeams = useMemo(() => office.teams.filter((team) => roomOfTeam(team) === zoom), [office, zoom]);
  const zoomTeam = zoomTeams.length ? zoom : null;
  const shown = useMemo(() => (zoomTeams.length ? { ...office, teams: zoomTeams } : office), [office, zoomTeams]);
  const employees = useMemo(() => office.teams.flatMap((team) => team.employees), [office]);
  const selected = employees.find((employee) => employee.id === selectedId) || null;
  useOfficeCanvas(canvasRef, shown, selectedId, placed, Boolean(zoomTeam));
  useEffect(() => {
    if (selectedId && !selected) setSelectedId(null);
  }, [selected, selectedId]);
  const clickCanvas = (event: MouseEvent<HTMLCanvasElement>) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    const x = event.clientX - bounds.left;
    const y = event.clientY - bounds.top;
    const pc = pcHit(placed.current, x, y);
    const found = hitTest(placed.current, x, y);
    // Named staff without a session and the assistant have no card to show.
    const person = found === ASSISTANT_ID || found?.startsWith("member:") || found?.startsWith("team:") ? null : found;
    const agent = pc && pc !== CTO_ID ? employees.find((employee) => employee.id === pc) : null;
    // A PC screen opens the agent's full card (Information, Git changes, Terminal), as on the Agents page.
    if (agent?.cardKey) openCard(agent.cardKey);
    else if (pc === CTO_ID || person === CTO_ID) setConsoleId(CTO_ID);
    else if (person) setSelectedId(person);
    else {
      // Clicking an office's floor or header zooms into that team; inside the zoom it goes back to the whole floor.
      const room = roomHit(placed.current, x, y);
      if (room) setZoom(zoomTeam ? null : room);
      setSelectedId(null);
    }
  };
  if (!employees.length) return <div className="office-empty">No live sessions</div>;
  return (
    <section className={selected ? "office-view has-selection" : "office-view"} aria-label="Live session office">
      <div className="office-canvas-wrap">
        <DecisionBox />
        <TeamZoom teams={office.teams} zoom={zoomTeam} setZoom={setZoom} />
        <canvas ref={canvasRef} className="office-canvas" onClick={clickCanvas} aria-hidden="true" />
      </div>
      <AccessibleEmployees office={office} select={setSelectedId} />
      {selected && <EmployeeDialog key={selected.id} employee={selected} team={teamLabel(office, selected)} />}
      {consoleId === CTO_ID && <CtoConsole close={() => setConsoleId(null)} />}
    </section>
  );
}
