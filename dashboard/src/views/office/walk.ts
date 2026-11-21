import type { OfficeLayout, PlacedRoom, Rect } from "./model";

/** A point on the floor where an agent's feet are. */
export interface Point {
  x: number;
  y: number;
}

/** A place in room-relative terms, so it survives a re-layout (rooms resize when people come and go). */
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
}

export interface Walker extends Point {
  /** Leg phase, alternating while walking. */
  step: number;
}

const SPEED = 55; // floor pixels per second at scale 1
const MIN_MS = 1200;
const MAX_MS = 7000;

/** Where each agent stands: the feet below its chair at a desk, or at its break or meeting spot. */
export function placesOf(layout: OfficeLayout): Map<string, Point & { scale: number }> {
  const places = new Map<string, Point & { scale: number }>();
  for (const desk of layout.desks) {
    if (!desk.away)
      places.set(desk.employee.id, { x: desk.x + 28 * desk.scale, y: desk.y + 42 * desk.scale, scale: desk.scale });
  }
  for (const spot of layout.spots) {
    const s = spot.scale;
    const dx = spot.activity === "pingpong-left" ? 14 : spot.activity === "pingpong-right" ? 42 : 28;
    places.set(spot.employee.id, { x: spot.x + dx * s, y: spot.y + 42 * s, scale: s });
  }
  return places;
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

function anchorOf(layout: OfficeLayout, point: Point): Anchor | null {
  const room = roomAt(layout, point);
  return room ? { room: room.key, fx: (point.x - room.x) / room.width, fy: (point.y - room.y) / room.height } : null;
}

function pointOf(layout: OfficeLayout, anchor: Anchor): Point | null {
  const room = layout.rooms.find((item) => item.key === anchor.room);
  return room ? { x: room.x + anchor.fx * room.width, y: room.y + anchor.fy * room.height } : null;
}

function walkOf(path: Point[], start: number, scale: number): Walk {
  const lengths = path.slice(1).map((point, index) => Math.hypot(point.x - path[index].x, point.y - path[index].y));
  const total = lengths.reduce((sum, length) => sum + length, 0);
  const duration = Math.min(MAX_MS, Math.max(MIN_MS, (total / (SPEED * scale)) * 1000));
  return { path, lengths, total, start, duration };
}

function along(walk: Walk, now: number): Point {
  let distance = Math.min(1, (now - walk.start) / walk.duration) * walk.total;
  for (let index = 0; index < walk.lengths.length; index += 1) {
    const length = walk.lengths[index];
    if (distance <= length || index === walk.lengths.length - 1) {
      const t = length ? Math.min(1, distance / length) : 1;
      const a = walk.path[index];
      const b = walk.path[index + 1];
      return { x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t };
    }
    distance -= length;
  }
  return walk.path[walk.path.length - 1];
}

/**
 * Remembers where every agent was and walks it to its new place when that changes: desk to break room, one break
 * activity to the next, or in from the lobby when a session starts. A new view (zoom or resize) starts fresh.
 */
export class Walks {
  private anchors = new Map<string, Anchor>();
  private walks = new Map<string, Walk>();
  private view = "";

  update(layout: OfficeLayout, view: string, now: number, animate = true): void {
    const fresh = view !== this.view;
    this.view = view;
    if (fresh) this.walks.clear();
    const places = placesOf(layout);
    const entrance = layout.lobby
      ? { x: layout.lobby.x + layout.lobby.width / 2, y: layout.lobby.y + layout.lobby.height - 4 }
      : null;
    for (const [id, place] of places) {
      const anchor = anchorOf(layout, place);
      const before = this.anchors.get(id);
      if (anchor) this.anchors.set(id, anchor);
      if (fresh || !animate || !anchor) continue;
      if (
        before &&
        before.room === anchor.room &&
        Math.abs(before.fx - anchor.fx) + Math.abs(before.fy - anchor.fy) < 0.01
      )
        continue;
      const current = this.walks.get(id);
      const from = current ? along(current, now) : before ? pointOf(layout, before) : entrance;
      if (!from) continue;
      this.walks.set(id, walkOf(route(layout, from, place), now, place.scale));
    }
    for (const id of this.anchors.keys()) if (!places.has(id)) this.anchors.delete(id);
  }

  /** Agents walking right now, with their position; finished walks are dropped. */
  walkers(now: number): Map<string, Walker> {
    const out = new Map<string, Walker>();
    for (const [id, walk] of this.walks) {
      if (now - walk.start >= walk.duration) {
        this.walks.delete(id);
        continue;
      }
      out.set(id, { ...along(walk, now), step: Math.floor((now - walk.start) / 180) % 2 });
    }
    return out;
  }
}
