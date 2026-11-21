import { useEffect, useMemo, useRef, useState, type MouseEvent, type MutableRefObject, type RefObject } from "react";
import { STATE_TEXT } from "../lib/cards";
import { openCard, useStore } from "../store";
import "../styles/office.css";
import { drawOffice, hitTest, pcHit, roomHit } from "./office/draw";
import { ChatConsole } from "./office/ChatConsole";
import { Walks } from "./office/walk";
import {
  CTO_ID,
  EMPTY_LAYOUT,
  layoutOffice,
  officeOf,
  type Office,
  type OfficeLayout,
} from "./office/model";

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
  placed.current = layoutOffice(office, initialBounds.width, available, scale);
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

/** One button per team: zoom the floor to that team's office (shared with a related team); "Whole floor" goes back. */
function TeamZoom({
  teams,
  zoom,
  setZoom,
}: {
  teams: Office["teams"];
  zoom: string | null;
  setZoom: (key: string | null) => void;
}) {
  return (
    <nav className="office-zoom" aria-label="Zoom to a team">
      <button type="button" aria-pressed={zoom === null} onClick={() => setZoom(null)}>
        Whole floor
      </button>
      {teams.map((team) => (
        <button
          key={team.key}
          type="button"
          aria-pressed={zoom === team.key}
          onClick={() => setZoom(zoom === team.key ? null : team.key)}
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

function AccessibleEmployees({ office, select }: { office: Office; select: (id: string) => unknown }) {
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
            {employee.person ? `${employee.person} (${employee.name})` : employee.name},{" "}
            {STATE_TEXT[employee.pose] || employee.pose}
          </button>
        ))}
    </div>
  );
}

export function OfficeView() {
  const state = useStore((storeState) => storeState.state);
  const office = useMemo(() => officeOf(state), [state]);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const placed = useRef<OfficeLayout>(EMPTY_LAYOUT);
  const [consoleId, setConsoleId] = useState<string | null>(null);
  const [zoom, setZoom] = useState<string | null>(null);
  const zoomTeams = useMemo(() => office.teams.filter((team) => team.key === zoom), [office, zoom]);
  const zoomTeam = zoomTeams.length ? zoom : null;
  const shown = useMemo(() => (zoomTeams.length ? { ...office, teams: zoomTeams } : office), [office, zoomTeams]);
  const employees = useMemo(() => office.teams.flatMap((team) => team.employees), [office]);
  const ctoName = employees.find((employee) => employee.id === CTO_ID)?.person || "CTO";
  useOfficeCanvas(canvasRef, shown, null, placed, Boolean(zoomTeam));
  /** An agent, or its screen, opens what that screen shows: the agent's card, or every session for the CTO. Named
   * staff with no session have nothing to open. */
  const open = (id: string | null): boolean => {
    if (!id) return false;
    if (id === CTO_ID) setConsoleId(CTO_ID);
    else {
      const agent = employees.find((employee) => employee.id === id);
      if (!agent?.cardKey) return false;
      openCard(agent.cardKey);
    }
    return true;
  };
  const clickCanvas = (event: MouseEvent<HTMLCanvasElement>) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    const x = event.clientX - bounds.left;
    const y = event.clientY - bounds.top;
    if (open(pcHit(placed.current, x, y)) || open(hitTest(placed.current, x, y))) return;
    // Clicking an office's floor or header zooms into that team; inside the zoom it goes back to the whole floor.
    const room = roomHit(placed.current, x, y);
    if (room) setZoom(zoomTeam ? null : room);
  };
  if (!employees.length) return <div className="office-empty">No live sessions</div>;
  return (
    <section className="office-view" aria-label="Live session office">
      <div className="office-canvas-wrap">
        <DecisionBox />
        <TeamZoom teams={office.teams} zoom={zoomTeam} setZoom={setZoom} />
        <canvas ref={canvasRef} className="office-canvas" onClick={clickCanvas} aria-hidden="true" />
      </div>
      <AccessibleEmployees office={office} select={open} />
      {consoleId === CTO_ID && <ChatConsole close={() => setConsoleId(null)} title={`${ctoName} · all sessions`} />}
    </section>
  );
}
