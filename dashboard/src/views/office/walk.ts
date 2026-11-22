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
  /** Path segments [from, to) during which the agent carries its desk. */
  carry: [number, number];
  /** An agent on its way in: its desk is not in the office until it arrives with it. */
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

/** The team space a point is in (CTO office or a session's area), for anchors that survive a re-layout. */
function spaceAt(layout: OfficeLayout, point: Point): PlacedRoom | undefined {
  return layout.rooms.find((room) => inside(room, point));
}

/** The walled office a point is in. */
function hallAt(layout: OfficeLayout, point: Point): PlacedRoom | undefined {
  return layout.halls.find((hall) => inside(hall, point));
}

/** The walkway across the lobby, just below the offices' doors. */
function walkwayY(layout: OfficeLayout, bottom: number): number {
  return layout.lobby ? layout.lobby.y + Math.min(layout.lobby.height / 2, 14) : bottom + 10;
}

/**
 * A walk between two points in one office. In the Sessions office it keeps to the aisles: down out of the session space
 * to the aisle below it, along the aisle (by the left wall to change rows) and up into the other space.
 */
function withinHall(layout: OfficeLayout, hall: PlacedRoom, from: Point, to: Point): Point[] {
  const spaces = layout.rooms.filter((room) => room.key !== hall.key && inside(hall, room));
  const a = spaces.find((space) => inside(space, from));
  const b = spaces.find((space) => inside(space, to));
  if (!spaces.length || (a && a === b)) return [from, to];
  const margin = Math.min(...spaces.map((space) => space.x)) - hall.x;
  const lane = (space: PlacedRoom | undefined, point: Point) => (space ? space.y + space.height + margin / 2 : point.y);
  const [ya, yb] = [lane(a, from), lane(b, to)];
  const x = hall.x + margin / 2;
  const turn =
    Math.abs(ya - yb) > 1
      ? [
          { x, y: ya },
          { x, y: yb },
        ]
      : [];
  return [from, { x: from.x, y: ya }, ...turn, { x: to.x, y: yb }, to];
}

/** Points from a place out through its office's door onto the lobby walkway. A place in the lobby is already there. */
function exit(layout: OfficeLayout, point: Point): { path: Point[]; out: Point } {
  const hall = hallAt(layout, point);
  if (!hall?.door) return { path: [point], out: point };
  const doorX = hall.door.x + hall.door.width / 2;
  const bottom = hall.y + hall.height;
  return {
    path: withinHall(layout, hall, point, { x: doorX, y: bottom - 4 }),
    out: { x: doorX, y: walkwayY(layout, bottom) },
  };
}

/** A walking route: along the aisles within one office, otherwise out of its door, along the lobby and in. */
export function route(layout: OfficeLayout, from: Point, to: Point): Point[] {
  const hall = hallAt(layout, from);
  if (hall && hall === hallAt(layout, to)) return withinHall(layout, hall, from, to);
  const a = exit(layout, from);
  const b = exit(layout, to);
  return [...a.path, a.out, b.out, ...b.path.slice().reverse()];
}

export function entranceOf(layout: OfficeLayout): Point | null {
  return layout.lobby
    ? { x: layout.lobby.x + layout.lobby.width / 2, y: layout.lobby.y + layout.lobby.height - 4 }
    : null;
}

function anchorOf(layout: OfficeLayout, point: Point): Anchor | null {
  const room = spaceAt(layout, point);
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
 * Remembers where every agent was and walks it when that changes. A new agent (a session's leader or a subagent) comes
 * in from the lobby entrance carrying its desk and sets it down at its place; one that leaves picks its desk up and
 * carries it out. The CTO never moves. A new view (zoom or resize) starts fresh, without walks.
 */
export class Walks {
  private anchors = new Map<string, Anchor>();
  private people = new Map<string, { employee: OfficeEmployee; scale: number; point: Point }>();
  private walks = new Map<string, Walk>();
  private view = "";

  update(layout: OfficeLayout, view: string, now: number, animate = true): void {
    const fresh = view !== this.view;
    this.view = view;
    if (fresh) this.walks.clear();
    const places = placesOf(layout);
    const entrance = entranceOf(layout);
    for (const [id, place] of places) {
      const anchor = anchorOf(layout, place);
      const before = this.anchors.get(id);
      if (anchor) this.anchors.set(id, anchor);
      this.people.set(id, { employee: place.employee, scale: place.scale, point: { x: place.x, y: place.y } });
      if (fresh || !animate || !anchor || !entrance || place.employee.fixed) continue;
      if (!before) {
        const path = route(layout, entrance, place);
        this.walks.set(id, walkOf(path, now, place, { carry: [0, path.length], arriving: true }));
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
      // A session that ended took its space with it: start from where the agent last sat.
      const from = pointOf(layout, anchor) || person?.point;
      if (fresh || !animate || !person || !from || !entrance || person.employee.fixed) continue;
      const path = route(layout, from, entrance);
      this.walks.set(id, walkOf(path, now, person, { carry: [0, path.length] }));
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
