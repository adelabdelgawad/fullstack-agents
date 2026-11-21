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
import { esc, fmtCost, fmtTokens } from "../lib/format";
import { openCard, toast, useStore } from "../store";
import "../styles/office.css";
import { drawOffice, hitTest } from "./office/draw";
import { layoutOffice, officeOf, type Office, type OfficeEmployee, type OfficeLayout } from "./office/model";

interface SendResult {
  ok?: boolean;
  error?: string;
}

function redraw(
  canvas: HTMLCanvasElement,
  office: Office,
  selectedId: string | null,
  placed: MutableRefObject<OfficeLayout>,
): void {
  const initialBounds = canvas.getBoundingClientRect();
  const scale = initialBounds.width < 520 ? 1 : 2;
  placed.current = layoutOffice(office, initialBounds.width, scale);
  const contentHeight = placed.current.height;
  canvas.style.height = `${Math.max(canvas.parentElement?.clientHeight || 0, contentHeight)}px`;
  const bounds = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  const width = Math.max(1, Math.round(bounds.width * ratio));
  const height = Math.max(1, Math.round(bounds.height * ratio));
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  const context = canvas.getContext("2d");
  if (!context) return;
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  drawOffice(context, placed.current, performance.now(), selectedId);
}

function useOfficeCanvas(
  canvasRef: RefObject<HTMLCanvasElement>,
  office: Office,
  selectedId: string | null,
  placed: MutableRefObject<OfficeLayout>,
): void {
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    let frame = 0;
    let lastPaint = -Infinity;
    const paint = () => redraw(canvas, office, selectedId, placed);
    const tick = (now: number) => {
      if (now - lastPaint >= 125) {
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
  }, [canvasRef, office, placed, selectedId]);
}

function teamLabel(office: Office, employee: OfficeEmployee): string {
  return office.teams.find((team) => team.key === employee.cardKey)?.label || employee.cardKey;
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
          <dt>Cost</dt>
          <dd>{fmtCost(employee.cost)}</dd>
        </div>
        <div>
          <dt>Tokens</dt>
          <dd>{fmtTokens(employee.tokens)}</dd>
        </div>
      </dl>
      {employee.bubble && <blockquote className="office-bubble">{employee.bubble}</blockquote>}
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

export function OfficeView() {
  const state = useStore((storeState) => storeState.state);
  const office = useMemo(() => officeOf(state), [state]);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const placed = useRef<OfficeLayout>({ rooms: [], desks: [], height: 0 });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const employees = useMemo(() => office.teams.flatMap((team) => team.employees), [office]);
  const selected = employees.find((employee) => employee.id === selectedId) || null;
  useOfficeCanvas(canvasRef, office, selectedId, placed);
  useEffect(() => {
    if (selectedId && !selected) setSelectedId(null);
  }, [selected, selectedId]);
  const clickCanvas = (event: MouseEvent<HTMLCanvasElement>) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    setSelectedId(hitTest(placed.current.desks, event.clientX - bounds.left, event.clientY - bounds.top));
  };
  if (!employees.length) return <div className="office-empty">No live sessions</div>;
  return (
    <section className="office-view" aria-label="Live session office">
      <div className="office-canvas-wrap">
        <canvas ref={canvasRef} className="office-canvas" onClick={clickCanvas} aria-hidden="true" />
      </div>
      <AccessibleEmployees office={office} select={setSelectedId} />
      {selected && <EmployeeDialog key={selected.id} employee={selected} team={teamLabel(office, selected)} />}
    </section>
  );
}
