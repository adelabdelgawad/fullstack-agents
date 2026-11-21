import type { OfficeEmployee, OfficeLayout, PlacedRoom, Rect } from "./model";

/** A point on the floor where an agent's feet are. */
export interface Point {
  x: number;
  y: number;
}

/** A place in room-relative terms, so it survives a re-layout (rooms resize when sessions come and go). */
interface Anchor {
  room: string;
  fx: number;
  fy: number;
}

interface Walk {
  path: Point[];
  lengths: number[];
  total: number;
  start: number;
  duration: number;
  employee: OfficeEmployee;
  scale: number;
  /** Path segments [from, to) during which the agent carries a desk. */
  carry: [number, number];
  /** A subagent on its way in: its desk is not in the office until it arrives with it. */
  arriving: boolean;
}

export interface Walker extends Point {
  /** Leg phase, alternating while walking. */
  step: number;
  carrying: boolean;
  arriving: boolean;
  employee: OfficeEmployee;
  scale: number;
}

const SPEED = 55; // floor pixels per second at scale 1
const MIN_MS = 1500;
const MAX_MS = 9000;

interface Place extends Point {
  scale: number;
  employee: OfficeEmployee;
}

/** Where each agent sits: the feet below its chair at its desk. */
export function placesOf(layout: OfficeLayout): Map<string, Place> {
  return new Map(
    layout.desks.map((desk) => [
      desk.employee.id,
      { x: desk.x + 28 * desk.scale, y: desk.y + 42 * desk.scale, scale: desk.scale, employee: desk.employee },
    ]),
  );
}

function inside(rect: Rect, point: Point): boolean {
  return point.x >= rect.x && point.x <= rect.x + rect.width && point.y >= rect.y && point.y <= rect.y + rect.height;
}

function roomAt(layout: OfficeLayout, point: Point): PlacedRoom | undefined {
  return layout.rooms.find((room) => inside(room, point));
}

/** The walkway in front of a room's door: the corridor or lobby just below its bottom wall. */
function walkwayY(layout: OfficeLayout, bottom: number): number {
  const ways = [...layout.corridors.filter((c) => c.width > c.height), ...(layout.lobby ? [layout.lobby] : [])]
    .filter((way) => way.y >= bottom - 2)
    .sort((a, b) => a.y - b.y);
  const way = ways[0];
  return way ? way.y + Math.min(way.height / 2, 14) : bottom + 10;
}

/** Points from a place to its walkway: out through the room's door. A place outside any room is already there. */
function exit(layout: OfficeLayout, point: Point): { path: Point[]; out: Point } {
  const room = roomAt(layout, point);
  if (!room?.door) return { path: [point], out: point };
  const doorX = room.door.x + room.door.width / 2;
  const bottom = room.y + room.height;
  return { path: [point, { x: doorX, y: bottom - 4 }], out: { x: doorX, y: walkwayY(layout, bottom) } };
}

/** A walking route through doors and corridors; between floors of rooms it takes the side corridor. */
export function route(layout: OfficeLayout, from: Point, to: Point): Point[] {
  const a = exit(layout, from);
  const b = exit(layout, to);
  if (roomAt(layout, from) === roomAt(layout, to) && roomAt(layout, from)) return [from, to];
  const middle: Point[] = [a.out];
  if (Math.abs(a.out.y - b.out.y) > 2) {
    const spine = layout.corridors.find((c) => c.height > c.width);
    const x = spine ? spine.x + spine.width / 2 : a.out.x;
    middle.push({ x, y: a.out.y }, { x, y: b.out.y });
  }
  middle.push(b.out);
  return [...a.path, ...middle, ...b.path.slice().reverse()];
}

/** Two routes walked one after the other; returns the joined path and where the second one starts. */
function join(first: Point[], second: Point[]): [Point[], number] {
  return [[...first, ...second.slice(1)], first.length - 1];
}

export function entranceOf(layout: OfficeLayout): Point | null {
  return layout.lobby
    ? { x: layout.lobby.x + layout.lobby.width / 2, y: layout.lobby.y + layout.lobby.height - 4 }
    : null;
}

export function warehouseDoor(layout: OfficeLayout): Point | null {
  const w = layout.warehouse;
  return w ? { x: w.x + w.width / 2, y: w.y + w.height } : null;
}

function anchorOf(layout: OfficeLayout, point: Point): Anchor | null {
  const room = roomAt(layout, point);
  return room ? { room: room.key, fx: (point.x - room.x) / room.width, fy: (point.y - room.y) / room.height } : null;
}

function pointOf(layout: OfficeLayout, anchor: Anchor): Point | null {
  const room = layout.rooms.find((item) => item.key === anchor.room);
  return room ? { x: room.x + anchor.fx * room.width, y: room.y + anchor.fy * room.height } : null;
}

function segmentLengths(path: Point[]): number[] {
  return path.slice(1).map((point, index) => Math.hypot(point.x - path[index].x, point.y - path[index].y));
}

function walkOf(
  path: Point[],
  start: number,
  place: { scale: number; employee: OfficeEmployee },
  extra: Partial<Walk> = {},
): Walk {
  const lengths = segmentLengths(path);
  const total = lengths.reduce((sum, length) => sum + length, 0);
  const duration = Math.min(MAX_MS, Math.max(MIN_MS, (total / (SPEED * place.scale)) * 1000));
  return {
    path,
    lengths,
    total,
    start,
    duration,
    employee: place.employee,
    scale: place.scale,
    carry: [0, 0],
    arriving: false,
    ...extra,
  };
}

function along(walk: Walk, now: number): Point & { segment: number } {
  let distance = Math.min(1, (now - walk.start) / walk.duration) * walk.total;
  for (let index = 0; index < walk.lengths.length; index += 1) {
    const length = walk.lengths[index];
    if (distance <= length || index === walk.lengths.length - 1) {
      const t = length ? Math.min(1, distance / length) : 1;
      const a = walk.path[index];
      const b = walk.path[index + 1];
      return { x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t, segment: index };
    }
    distance -= length;
  }
  return { ...walk.path[walk.path.length - 1], segment: walk.lengths.length };
}

/**
 * Remembers where every agent was and walks it when that changes. A new subagent comes in from the lobby, collects a
 * desk at the warehouse and carries it to its session's office; a finished one carries its desk back and leaves. A new
 * session's leader walks in from the lobby. A new view (zoom or resize) starts fresh, without walks.
 */
export class Walks {
  private anchors = new Map<string, Anchor>();
  private people = new Map<string, { employee: OfficeEmployee; scale: number }>();
  private walks = new Map<string, Walk>();
  private view = "";

  update(layout: OfficeLayout, view: string, now: number, animate = true): void {
    const fresh = view !== this.view;
    this.view = view;
    if (fresh) this.walks.clear();
    const places = placesOf(layout);
    const entrance = entranceOf(layout);
    const store = warehouseDoor(layout);
    for (const [id, place] of places) {
      const anchor = anchorOf(layout, place);
      const before = this.anchors.get(id);
      if (anchor) this.anchors.set(id, anchor);
      this.people.set(id, { employee: place.employee, scale: place.scale });
      if (fresh || !animate || !anchor || !entrance) continue;
      if (!before) {
        const subagent = place.employee.role !== "lead";
        if (subagent && store) {
          const [path, from] = join(route(layout, entrance, store), route(layout, store, place));
          this.walks.set(id, walkOf(path, now, place, { carry: [from, path.length], arriving: true }));
        } else this.walks.set(id, walkOf(route(layout, entrance, place), now, place));
        continue;
      }
      if (before.room === anchor.room && Math.abs(before.fx - anchor.fx) + Math.abs(before.fy - anchor.fy) < 0.01)
        continue;
      const current = this.walks.get(id);
      const from = current ? along(current, now) : pointOf(layout, before);
      if (from) this.walks.set(id, walkOf(route(layout, from, place), now, place));
    }
    for (const [id, anchor] of this.anchors) {
      if (places.has(id)) continue;
      this.anchors.delete(id);
      const person = this.people.get(id);
      this.people.delete(id);
      const from = pointOf(layout, anchor);
      if (fresh || !animate || !person || !from || !entrance || person.employee.role === "lead") continue;
      // A finished subagent takes its desk back to the warehouse, then goes home.
      const [path, from2] = store
        ? join(route(layout, from, store), route(layout, store, entrance))
        : [route(layout, from, entrance), 0];
      this.walks.set(id, walkOf(path, now, person, { carry: [0, store ? from2 : 0] }));
    }
  }

  /** Agents walking right now, with their position; finished walks are dropped. */
  walkers(now: number): Map<string, Walker> {
    const out = new Map<string, Walker>();
    for (const [id, walk] of this.walks) {
      if (now - walk.start >= walk.duration) {
        this.walks.delete(id);
        continue;
      }
      const point = along(walk, now);
      out.set(id, {
        x: point.x,
        y: point.y,
        step: Math.floor((now - walk.start) / 180) % 2,
        carrying: point.segment >= walk.carry[0] && point.segment < walk.carry[1],
        arriving: walk.arriving,
        employee: walk.employee,
        scale: walk.scale,
      });
    }
    return out;
  }
}
