import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type MouseEvent,
  type MutableRefObject,
  type ReactNode,
  type RefObject,
} from "react";
import { STATE_TEXT } from "../lib/cards";
import type { Card, DashState, WaitingEntry } from "../lib/types";
import { openRunLog } from "../panel/Panel";
import { focusNode, openCard, setView, store, useStore } from "../store";
import { openNewSession } from "../terminal/HerdrOverlay";
import "../styles/office.css";
import { drawOffice, hitTest, pcHit, roomHit, zoomIconHit } from "./office/draw";
import { ChatConsole, endSession, renameSession, RUN_ID } from "./office/ChatConsole";
import { HistoryView } from "./HistoryView";
import { AgentSettings } from "./office/AgentSettings";
import { UsagePanel } from "./office/UsagePanel";
import { Walks } from "./office/walk";
import {
  CTO_ID,
  CTO_TEAM,
  EMPTY_LAYOUT,
  layoutOffice,
  officeOf,
  Seating,
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
function DecisionBox({ waiting, focus }: { waiting: WaitingEntry[]; focus: () => void }) {
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
              <button type="button" onClick={() => (focus(), entry.card && openCard(entry.card))}>
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

/** A session's live console: its card, full screen, on the Terminal tab (that session's herdr pane). */
function openConsole(key: string): void {
  openCard(key);
  store.set({ tab2: "terminal" });
}

/** A small right-click menu at the click point; closes on Escape or a click outside. */
function useMenu(close: () => void) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    ref.current?.querySelector("button")?.focus();
    const away = (event: Event) => {
      if (!ref.current?.contains(event.target as Node)) close();
    };
    const key = (event: KeyboardEvent) => event.key === "Escape" && close();
    window.addEventListener("mousedown", away);
    window.addEventListener("keydown", key);
    return () => {
      window.removeEventListener("mousedown", away);
      window.removeEventListener("keydown", key);
    };
  }, [close]);
  return ref;
}

/** Right-click on the CTO's office: start a session, the chat with every session, the herdr console, plan usage. */
function CtoMenu({
  at,
  close,
  chat,
  usage,
  history,
  settings,
}: {
  at: { x: number; y: number };
  close: () => void;
  chat: () => void;
  usage: () => void;
  history: () => void;
  settings: () => void;
}) {
  const ref = useMenu(close);
  const run = (action: () => void) => () => {
    close();
    action();
  };
  return (
    <div ref={ref} className="office-menu" role="menu" style={{ left: at.x, top: at.y }}>
      <button
        type="button"
        role="menuitem"
        onClick={(event) => {
          const anchor = event.currentTarget;
          close();
          void openNewSession(anchor);
        }}
      >
        New conversation
      </button>
      <button type="button" role="menuitem" onClick={run(chat)}>
        Open chat
      </button>
      <button type="button" role="menuitem" onClick={run(() => setView("herdr"))}>
        Open console
      </button>
      <button type="button" role="menuitem" onClick={run(usage)}>
        Open usage information
      </button>
      <button type="button" role="menuitem" onClick={run(history)}>
        History
      </button>
      <button type="button" role="menuitem" onClick={run(settings)} title="Applies to new sessions only">
        Default agent settings
      </button>
    </div>
  );
}

/** A scrollable modal over the Office: the CTO's usage view or the session history. */
function OfficeModal({ title, close, children }: { title: string; close: () => void; children: ReactNode }) {
  useEffect(() => {
    const key = (event: KeyboardEvent) => event.key === "Escape" && close();
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [close]);
  return (
    <div className="office-usage-backdrop" onMouseDown={(event) => event.target === event.currentTarget && close()}>
      <section className="office-usage" role="dialog" aria-modal="true" aria-label={title}>
        <header>
          <h2>{title}</h2>
          <button type="button" onClick={close}>
            Close
          </button>
        </header>
        {children}
      </section>
    </div>
  );
}

// Stable empty values: a selector returning a fresh [] or {} on every read makes React re-render forever.
const NO_CARDS: Card[] = [];
const NO_PANES: Record<string, string> = {};
const NO_WAITING: WaitingEntry[] = [];

/** The right-click menu of a session's office: its chat, its card, its live console, or end it. */
function OfficeMenu({
  menu,
  card,
  pane,
  close,
  chat,
  settings,
}: {
  menu: { key: string; x: number; y: number };
  card: Card | undefined;
  pane: Record<string, string>;
  close: () => void;
  chat: (key: string) => void;
  settings: (sid: string) => void;
}) {
  const ref = useMenu(close);
  if (!card) return null;
  const sid = card.sessions[0]?.id;
  const sessionPane = pane[sid || ""];
  const run = (action: () => void) => () => {
    close();
    action();
  };
  return (
    <div ref={ref} className="office-menu" role="menu" style={{ left: menu.x, top: menu.y }}>
      <button type="button" role="menuitem" onClick={run(() => chat(card.key))}>
        Open chat conversation
      </button>
      <button type="button" role="menuitem" onClick={run(() => openCard(card.key))}>
        Open dashboard
      </button>
      <button type="button" role="menuitem" onClick={run(() => openConsole(card.key))}>
        Open console
      </button>
      <button type="button" role="menuitem" disabled={!sid} onClick={run(() => sid && settings(sid))}>
        Agent settings
      </button>
      <button
        type="button"
        role="menuitem"
        disabled={!sessionPane}
        title={
          sessionPane ? "Renames the herdr tab and sends /rename to the session" : "This session has no herdr pane"
        }
        onClick={(event) => {
          const anchor = event.currentTarget;
          close();
          renameSession(card, sessionPane, anchor);
        }}
      >
        Rename
      </button>
      <button
        type="button"
        role="menuitem"
        className="danger"
        disabled={!sessionPane}
        title={sessionPane ? "" : "This session has no herdr pane"}
        onClick={(event) => {
          const anchor = event.currentTarget;
          close();
          endSession(card, sessionPane, anchor);
        }}
      >
        End session
      </button>
    </div>
  );
}

/** The Office: this host's building, then one building per linked host. With no linked host it is exactly the one
 * building it always was. */
export function OfficeView() {
  const node = useStore((s) => s.node);
  const nodes = useStore((s) => s.nodes);
  const nodeStates = useStore((s) => s.nodeStates);
  const state = useStore((s) => s.state);
  if (!nodes.length) return <OfficeBuilding node="" state={state} />;
  const hosts = [{ id: "", label: "This host", host: "" }, ...nodes];
  return (
    <div className="office-buildings">
      {hosts.map((host) => {
        const shown = host.id === node ? state : nodeStates[host.id]?.state ?? null;
        const offline = Boolean(nodeStates[host.id]?.offline);
        return (
          <section key={host.id || "local"} className="office-building" aria-label={`${host.label} office`}>
            <h2 className="office-building-title">
              <span className={`dot${offline ? " off" : ""}`} aria-hidden="true"></span>
              {host.label}
              <small>
                {host.host || (shown?.repo ? String(shown.repo).split("/").pop() : "")}
                {offline ? " · offline" : host.id === node ? " · in focus" : ""}
              </small>
            </h2>
            <OfficeBuilding node={host.id} state={shown} multi />
          </section>
        );
      })}
    </div>
  );
}

/** One host's office: its CTO and sessions. Any click focuses that host first, so what opens talks to it. */
function OfficeBuilding({ node, state, multi = false }: { node: string; state: DashState | null; multi?: boolean }) {
  const focus = () => focusNode(node);
  // Desks stay put while agents work: sessions keep the order they arrived in and subagents keep their seats.
  const seating = useRef(new Seating());
  const office = useMemo(() => seating.current.apply(officeOf(state)), [state]);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const placed = useRef<OfficeLayout>(EMPTY_LAYOUT);
  const [consoleId, setConsoleId] = useState<string | null>(null);
  const [chatKey, setChatKey] = useState<string | undefined>(undefined);
  const [usage, setUsage] = useState(false);
  const [history, setHistory] = useState(false);
  /** Whose agent settings are open: "" for the CTO default, a session id, or null when closed. */
  const [agentSettings, setAgentSettings] = useState<string | null>(null);
  const [chatWorker, setChatWorker] = useState<string | undefined>(undefined);
  const [menu, setMenu] = useState<{ key: string; x: number; y: number } | null>(null);
  const cards = state?.cards || NO_CARDS;
  const panes = state?.session_panes || NO_PANES;
  const waiting = state?.waiting || NO_WAITING;
  /** Right-click on a session's office: a menu for that session. */
  const contextCanvas = (event: MouseEvent<HTMLCanvasElement>) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    const key = roomHit(placed.current, event.clientX - bounds.left, event.clientY - bounds.top);
    if (!key || (key !== CTO_TEAM && !cards.some((card) => card.key === key))) return;
    event.preventDefault();
    focus();
    setMenu({ key, x: event.clientX - bounds.left, y: event.clientY - bounds.top });
  };
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
    focus();
    if (id === CTO_ID) {
      setConsoleId(CTO_ID);
      return true;
    }
    const agent = employees.find((employee) => employee.id === id);
    if (!agent?.cardKey) return false;
    // A subagent, implementer run or shell opens live in the chat console (an older worker record its run log); a leader its console.
    if (agent.role === "worker" && !RUN_ID.test(agent.id)) openRunLog(agent.cardKey, agent.id);
    else if (agent.role !== "lead") {
      setChatKey(agent.cardKey);
      setChatWorker(agent.id);
      setConsoleId(CTO_ID);
    } else openConsole(agent.cardKey);
    return true;
  };
  const clickCanvas = (event: MouseEvent<HTMLCanvasElement>) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    const x = event.clientX - bounds.left;
    const y = event.clientY - bounds.top;
    // The magnifier zooms into that office (or back out); anywhere else in a session's office opens its console.
    focus();
    const icon = zoomIconHit(placed.current, x, y);
    if (icon) return setZoom(zoomTeam ? null : icon);
    if (open(pcHit(placed.current, x, y)) || open(hitTest(placed.current, x, y))) return;
    const room = roomHit(placed.current, x, y);
    const card = cards.find((item) => item.key === room);
    if (card) openConsole(card.key);
  };
  if (!employees.length) return <div className="office-empty">{state ? "No live sessions" : "Not reachable yet"}</div>;
  return (
    <section className={`office-view${multi ? " office-view-multi" : ""}`} aria-label="Live session office">
      <div className="office-canvas-wrap">
        <DecisionBox waiting={waiting} focus={focus} />
        <TeamZoom teams={office.teams} zoom={zoomTeam} setZoom={setZoom} />
        <canvas
          ref={canvasRef}
          className="office-canvas"
          onClick={clickCanvas}
          onContextMenu={contextCanvas}
          aria-hidden="true"
        />
        {menu?.key === CTO_TEAM && (
          <CtoMenu
            at={menu}
            close={() => setMenu(null)}
            chat={() => {
              setChatKey(undefined);
              setChatWorker(undefined);
              setConsoleId(CTO_ID);
            }}
            usage={() => setUsage(true)}
            history={() => setHistory(true)}
            settings={() => setAgentSettings("")}
          />
        )}
        {menu && menu.key !== CTO_TEAM && (
          <OfficeMenu
            menu={menu}
            card={cards.find((card) => card.key === menu.key)}
            pane={panes}
            close={() => setMenu(null)}
            chat={(key) => {
              setChatKey(key);
              setChatWorker(undefined);
              setConsoleId(CTO_ID);
            }}
            settings={setAgentSettings}
          />
        )}
      </div>
      <AccessibleEmployees office={office} select={open} />
      {consoleId === CTO_ID && (
        <ChatConsole
          key={`${chatKey || "all"}:${chatWorker || ""}`}
          initial={chatKey}
          initialWorker={chatWorker}
          close={() => {
            setConsoleId(null);
            setChatKey(undefined);
            setChatWorker(undefined);
          }}
          title={`${ctoName} · all sessions`}
        />
      )}
      {usage && (
        <OfficeModal title="Usage" close={() => setUsage(false)}>
          <UsagePanel />
        </OfficeModal>
      )}
      {history && (
        <OfficeModal title="History" close={() => setHistory(false)}>
          <HistoryView />
        </OfficeModal>
      )}
      {agentSettings !== null && (
        <OfficeModal
          title={agentSettings ? "Agent settings" : "Default agent settings"}
          close={() => setAgentSettings(null)}
        >
          <AgentSettings key={agentSettings} sid={agentSettings || undefined} close={() => setAgentSettings(null)} />
        </OfficeModal>
      )}
    </section>
  );
}
