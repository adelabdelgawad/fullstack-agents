import { drawPlant } from "./draw";
import { BUILDING, type PlacedRoom, type PlacedSpot, type Rect } from "./model";

const SHIRTS = ["#4f8ff7", "#4ade80", "#f2b24c", "#f472b6", "#a78bfa", "#22d3ee", "#fb7185", "#e5e7eb"];
const HAIR = ["#231b16", "#5b3825", "#d6a85f", "#8a5b3d", "#202938", "#6b4631", "#d7d2c8", "#b86b42"];
const SKIN = "#e0a77f";

function rect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, colour: string): void {
  ctx.fillStyle = colour;
  ctx.fillRect(x, y, w, h);
}

function drawTiles(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, s: number): void {
  const tile = 8 * s;
  for (let row = 0; row * tile < h; row += 1) {
    for (let col = 0; col * tile < w; col += 1) {
      const colour = (row + col) % 2 ? "#cdbb98" : "#dccbaa";
      rect(ctx, x + col * tile, y + row * tile, Math.min(tile, w - col * tile), Math.min(tile, h - row * tile), colour);
    }
  }
}

function drawCoffeeBar(ctx: CanvasRenderingContext2D, x: number, y: number, s: number, tMs: number): void {
  rect(ctx, x, y + 10 * s, 40 * s, 10 * s, "#8b5a32");
  rect(ctx, x, y + 18 * s, 40 * s, 2 * s, "#5d4026");
  rect(ctx, x + 4 * s, y, 12 * s, 11 * s, "#3a3f47");
  rect(ctx, x + 6 * s, y + 2 * s, 8 * s, 3 * s, "#c0392b");
  rect(ctx, x + 8 * s, y + 7 * s, 4 * s, 4 * s, "#f4f1ea");
  const steam = Math.floor(tMs / 300) % 2;
  rect(ctx, x + (9 + steam) * s, y - 3 * s, s, 2 * s, "#cfd8e3");
  rect(ctx, x + 22 * s, y + 5 * s, 6 * s, 6 * s, "#9ad1f5");
  rect(ctx, x + 22 * s, y + 4 * s, 6 * s, s, "#e5e7eb");
  rect(ctx, x + 31 * s, y + 7 * s, 3 * s, 4 * s, "#f4f1ea");
  rect(ctx, x + 35 * s, y + 7 * s, 3 * s, 4 * s, "#f4f1ea");
}

function drawFridge(ctx: CanvasRenderingContext2D, x: number, y: number, s: number): void {
  rect(ctx, x, y, 16 * s, 28 * s, "#d9dee5");
  rect(ctx, x, y + 11 * s, 16 * s, s, "#9aa3ad");
  rect(ctx, x + 12 * s, y + 4 * s, 2 * s, 5 * s, "#6b7280");
  rect(ctx, x + 12 * s, y + 15 * s, 2 * s, 7 * s, "#6b7280");
  rect(ctx, x + 3 * s, y + 3 * s, 4 * s, 4 * s, "#f2b24c");
}

function drawVending(ctx: CanvasRenderingContext2D, x: number, y: number, s: number, tMs: number): void {
  rect(ctx, x, y, 18 * s, 28 * s, "#b91c1c");
  rect(ctx, x + 2 * s, y + 2 * s, 10 * s, 20 * s, "#1e293b");
  const snacks = ["#f2b24c", "#4ade80", "#60a5fa", "#f472b6"];
  for (let row = 0; row < 4; row += 1) {
    for (let col = 0; col < 2; col += 1) rect(ctx, x + (3 + col * 5) * s, y + (3 + row * 5) * s, 3 * s, 3 * s, snacks[(row + col) % 4]);
  }
  rect(ctx, x + 13 * s, y + 4 * s, 3 * s, 6 * s, Math.floor(tMs / 700) % 2 ? "#4ade80" : "#14532d");
  rect(ctx, x + 2 * s, y + 24 * s, 10 * s, 2 * s, "#0f172a");
}

function drawCooler(ctx: CanvasRenderingContext2D, x: number, y: number, s: number): void {
  rect(ctx, x + 2 * s, y, 8 * s, 9 * s, "#93c5fd");
  rect(ctx, x + 3 * s, y + s, 3 * s, 6 * s, "#bfdbfe");
  rect(ctx, x, y + 9 * s, 12 * s, 16 * s, "#e5e7eb");
  rect(ctx, x + 4 * s, y + 13 * s, 4 * s, 2 * s, "#2563eb");
}

function drawCafeTable(ctx: CanvasRenderingContext2D, x: number, y: number, s: number): void {
  rect(ctx, x - 9 * s, y - 2 * s, 4 * s, 4 * s, "#6b4430");
  rect(ctx, x + 5 * s, y - 2 * s, 4 * s, 4 * s, "#6b4430");
  ctx.fillStyle = "#f4f1ea";
  ctx.beginPath();
  ctx.arc(x, y, 5 * s, 0, Math.PI * 2);
  ctx.fill();
  rect(ctx, x - s, y - 2 * s, 2 * s, 2 * s, "#8b5a32");
}

function drawRug(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, s: number): void {
  rect(ctx, x, y, w, h, "#3f5f7a");
  rect(ctx, x + 2 * s, y + 2 * s, w - 4 * s, h - 4 * s, "#4f7391");
  rect(ctx, x + 4 * s, y + h / 2 - s / 2, w - 8 * s, s, "#f2b24c");
}

function drawSink(ctx: CanvasRenderingContext2D, x: number, y: number, s: number): void {
  rect(ctx, x, y + 10 * s, 26 * s, 10 * s, "#8b5a32");
  rect(ctx, x, y + 18 * s, 26 * s, 2 * s, "#5d4026");
  rect(ctx, x + 6 * s, y + 11 * s, 12 * s, 5 * s, "#9aa3ad");
  rect(ctx, x + 11 * s, y + 6 * s, 2 * s, 6 * s, "#cbd5e1");
}

function drawSofa(ctx: CanvasRenderingContext2D, x: number, y: number, s: number): void {
  rect(ctx, x, y, 36 * s, 6 * s, "#9b2c48");
  rect(ctx, x, y + 6 * s, 36 * s, 6 * s, "#b8355a");
  rect(ctx, x - 3 * s, y + 2 * s, 4 * s, 10 * s, "#9b2c48");
  rect(ctx, x + 35 * s, y + 2 * s, 4 * s, 10 * s, "#9b2c48");
}

function drawTable(ctx: CanvasRenderingContext2D, table: Rect): void {
  const s = table.height / 14;
  const { x, y, width } = table;
  rect(ctx, x, y, width, 14 * s, "#2e7d4f");
  rect(ctx, x, y + 6.5 * s, width, s, "#f4f1ea");
  rect(ctx, x + width / 2 - s / 2, y - 3 * s, s, 18 * s, "#e5e7eb");
  rect(ctx, x + 2 * s, y + 14 * s, 2 * s, 6 * s, "#3b3b3b");
  rect(ctx, x + width - 4 * s, y + 14 * s, 2 * s, 6 * s, "#3b3b3b");
}

/** The break room: checkered kitchen floor, a coffee corner, the table-tennis table and a sofa. */
export function drawBreakRoom(ctx: CanvasRenderingContext2D, room: PlacedRoom, tMs: number): void {
  const { x, y, width, height, scale: s } = room;
  const band = BUILDING.header * s;
  drawTiles(ctx, x, y + band, width, height - band, s);
  rect(ctx, x, y, width, band, "#2a3650");
  rect(ctx, x, y + band - 3 * s, width, 3 * s, "#222c42");
  const plate = Math.min(width - 24 * s, Math.max(60 * s, room.label.length * 4 * s + 16 * s));
  rect(ctx, x + (width - plate) / 2, y + 3 * s, plate, 9 * s, "#8b5a32");
  rect(ctx, x + (width - plate) / 2 + s, y + 4 * s, plate - 2 * s, 7 * s, "#151b26");
  ctx.fillStyle = "#f2b24c";
  ctx.font = `bold ${5 * s}px monospace`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(room.label, x + width / 2, y + 7.5 * s, plate - 6 * s);
  ctx.textAlign = "start";
  ctx.textBaseline = "alphabetic";
  const floor = y + band;
  const roomy = width > 150 * s;
  drawCoffeeBar(ctx, x + 6 * s, floor + 4 * s, s, tMs);
  if (roomy) drawSink(ctx, x + 46 * s, floor + 4 * s, s);
  if (width > 110 * s) {
    drawFridge(ctx, x + width - 22 * s, floor + 2 * s, s);
    drawVending(ctx, x + width - 44 * s, floor + 2 * s, s, tMs);
    if (roomy) drawCooler(ctx, x + width - 60 * s, floor + 5 * s, s);
  }
  if (height - band > 40 * s) {
    drawRug(ctx, x + width - 54 * s, y + height - 24 * s, 52 * s, 22 * s, s);
    drawSofa(ctx, x + width - 46 * s, y + height - 16 * s, s);
    if (height - band > 70 * s) drawTv(ctx, x + width - 43 * s, y + height - 52 * s + 6 * s, s, tMs);
  }
  if (roomy && height - band > 70 * s) {
    drawCafeTable(ctx, x + 22 * s, y + height - 14 * s, s);
    drawCafeTable(ctx, x + 52 * s, y + height - 14 * s, s);
    drawPlant(ctx, x + 3 * s, y + height - 20 * s, s);
  }
  if (room.table) drawTable(ctx, room.table);
}

function drawStanding(ctx: CanvasRenderingContext2D, x: number, y: number, s: number, spot: PlacedSpot, step = 0): void {
  drawFigure(ctx, x, y, s, spot.employee.colour, step);
}

/** A standing person seen from the front; `step` swings the legs (-1, 0, 1) for walking or shuffling. */
function drawFigure(ctx: CanvasRenderingContext2D, x: number, y: number, s: number, colour: number, step = 0): void {
  rect(ctx, x, y + 10 * s, 12 * s, 10 * s, SKIN);
  rect(ctx, x, y + 8 * s, 12 * s, 4 * s, HAIR[colour]);
  rect(ctx, x + 3 * s, y + 14 * s, 2 * s, 2 * s, "#1b1b22");
  rect(ctx, x + 7 * s, y + 14 * s, 2 * s, 2 * s, "#1b1b22");
  rect(ctx, x - s, y + 20 * s, 14 * s, 13 * s, SHIRTS[colour]);
  rect(ctx, x + s, y + (33 - Math.max(0, step) * 2) * s, 4 * s, (10 - Math.max(0, step) * 2) * s, "#273348");
  rect(ctx, x + 7 * s, y + (33 + Math.min(0, step) * 2) * s, 4 * s, (10 + Math.min(0, step) * 2) * s, "#273348");
}

/** An agent walking between rooms, feet at (fx, fy). */
export function drawWalking(ctx: CanvasRenderingContext2D, fx: number, fy: number, s: number, colour: number, step: number): void {
  drawFigure(ctx, fx - 6 * s, fy - 43 * s, s, colour, step ? 1 : -1);
  rect(ctx, fx - 9 * s, fy - 22 * s + (step ? s : 0), 3 * s, 8 * s, SHIRTS[colour]);
  rect(ctx, fx + 6 * s, fy - 22 * s + (step ? 0 : s), 3 * s, 8 * s, SHIRTS[colour]);
}

/** Seen from behind: hair, shoulders and back, seated on a bar stool or the sofa. */
function drawBack(ctx: CanvasRenderingContext2D, x: number, y: number, s: number, colour: number): void {
  rect(ctx, x, y, 12 * s, 10 * s, HAIR[colour]);
  rect(ctx, x - s, y + 3 * s, s, 3 * s, SKIN);
  rect(ctx, x + 12 * s, y + 3 * s, s, 3 * s, SKIN);
  rect(ctx, x - 2 * s, y + 10 * s, 16 * s, 12 * s, SHIRTS[colour]);
  rect(ctx, x + 5 * s, y + 11 * s, 2 * s, 10 * s, "rgba(0,0,0,0.15)");
}

/** At the bar on a stool, back to us; every few seconds the agent lifts its cup. */
function drawBarSeat(ctx: CanvasRenderingContext2D, spot: PlacedSpot, tMs: number): void {
  const { x, y, scale: s, employee } = spot;
  const px = x + 22 * s;
  rect(ctx, px + s, y + 34 * s, 10 * s, 3 * s, "#5d4026");
  rect(ctx, px + 5 * s, y + 37 * s, 2 * s, 6 * s, "#3b2617");
  drawBack(ctx, px, y + 12 * s, s, employee.colour);
  const sip = (tMs + employee.colour * 900) % 5000 < 900;
  rect(ctx, px + 12 * s, y + (sip ? 14 : 20) * s, 3 * s, (sip ? 9 : 4) * s, SHIRTS[employee.colour]);
  if (sip) rect(ctx, px + 12 * s, y + 11 * s, 4 * s, 4 * s, "#f4f1ea");
}

/** On the sofa playing PlayStation, back to us, controller in hand; the head bobs with the game. */
function drawGamer(ctx: CanvasRenderingContext2D, spot: PlacedSpot, tMs: number): void {
  const { x, y, scale: s, employee } = spot;
  const px = x + 22 * s;
  const bob = Math.floor((tMs + employee.colour * 170) / 260) % 3 === 0 ? s : 0;
  drawBack(ctx, px, y + 20 * s - bob, s, employee.colour);
  rect(ctx, px - 3 * s, y + 30 * s, 4 * s, 4 * s, SKIN);
  rect(ctx, px + 11 * s, y + 30 * s, 4 * s, 4 * s, SKIN);
  rect(ctx, px + s, y + 30 * s, 10 * s, 3 * s, "#1f2937");
}

/** A TV with a game on, and the console below it, facing the sofa. */
function drawTv(ctx: CanvasRenderingContext2D, x: number, y: number, s: number, tMs: number): void {
  rect(ctx, x, y, 30 * s, 17 * s, "#111827");
  const scene = Math.floor(tMs / 400) % 4;
  rect(ctx, x + 2 * s, y + 2 * s, 26 * s, 13 * s, ["#1e3a8a", "#065f46", "#7c2d12", "#312e81"][scene]);
  rect(ctx, x + (4 + scene * 5) * s, y + 9 * s, 4 * s, 4 * s, "#facc15");
  rect(ctx, x + (22 - scene * 4) * s, y + 5 * s, 3 * s, 3 * s, "#f87171");
  rect(ctx, x + 2 * s, y + 13 * s, 26 * s, 2 * s, "#16a34a");
  rect(ctx, x + 13 * s, y + 17 * s, 4 * s, 3 * s, "#374151");
  rect(ctx, x + 6 * s, y + 20 * s, 18 * s, 4 * s, "#1f2937");
  rect(ctx, x + 8 * s, y + 21 * s, 8 * s, 2 * s, "#e5e7eb");
  rect(ctx, x + 19 * s, y + 21 * s, 2 * s, 2 * s, "#3b82f6");
}

/** A seated meeting attendee: north of the table facing it, hands on the table; south seen from behind. */
function drawSeated(ctx: CanvasRenderingContext2D, spot: PlacedSpot): void {
  const { x: ox, y: oy, scale: s, employee } = spot;
  const x = ox + 20 * s;
  const colour = employee.colour;
  if (spot.seat === "south") {
    const y = oy + 24 * s;
    rect(ctx, x - 2 * s, y, 20 * s, 10 * s, SHIRTS[colour]);
    rect(ctx, x + 2 * s, y + 8 * s, 12 * s, 10 * s, HAIR[colour]);
    rect(ctx, x - 3 * s, y + 17 * s, 22 * s, 5 * s, "#4b5563");
    return;
  }
  const y = oy + 58 * s;
  rect(ctx, x - 3 * s, y, 22 * s, 5 * s, "#4b5563");
  rect(ctx, x + 2 * s, y + 2 * s, 12 * s, 4 * s, HAIR[colour]);
  rect(ctx, x + 2 * s, y + 6 * s, 12 * s, 7 * s, SKIN);
  rect(ctx, x + 5 * s, y + 8 * s, 2 * s, 2 * s, "#1b1b22");
  rect(ctx, x + 9 * s, y + 8 * s, 2 * s, 2 * s, "#1b1b22");
  rect(ctx, x - 2 * s, y + 13 * s, 20 * s, 9 * s, SHIRTS[colour]);
  rect(ctx, x, y + 20 * s, 4 * s, 3 * s, SKIN);
  rect(ctx, x + 12 * s, y + 20 * s, 4 * s, 3 * s, SKIN);
}

function drawCoffee(ctx: CanvasRenderingContext2D, spot: PlacedSpot, frame: number): void {
  const { x, y, scale: s } = spot;
  const px = x + 22 * s;
  drawStanding(ctx, px, y, s, spot);
  rect(ctx, px + 12 * s, y + 23 * s, 4 * s, 4 * s, SKIN);
  rect(ctx, px + 13 * s, y + 19 * s, 5 * s, 5 * s, "#f4f1ea");
  rect(ctx, px + 18 * s, y + 20 * s, s, 3 * s, "#f4f1ea");
  rect(ctx, px + (14 + frame) * s, y + 16 * s, s, 2 * s, "#cfd8e3");
  if (spot.employee.pose === "asleep") {
    ctx.fillStyle = "#80b5ff";
    ctx.font = `bold ${6 * s}px monospace`;
    ctx.fillText(frame ? "z" : "Z", px + 14 * s, y + 8 * s);
  }
}

function drawPaddle(ctx: CanvasRenderingContext2D, x: number, y: number, s: number): void {
  rect(ctx, x, y, 5 * s, 5 * s, "#d63031");
  rect(ctx, x + 2 * s, y + 5 * s, s, 3 * s, "#5d4026");
}

/** A rally: the ball crosses the table and each player shuffles, then swings as the ball arrives. */
function drawPingPong(ctx: CanvasRenderingContext2D, spot: PlacedSpot, tMs: number): void {
  const { x, y, scale: s } = spot;
  const left = spot.activity === "pingpong-left";
  const phase = (tMs % 1200) / 600;
  const t = phase < 1 ? phase : 2 - phase;
  if (left) {
    const tableX = x + 24 * s;
    const tableW = 64 * s;
    const hop = Math.abs(Math.sin(t * Math.PI)) * 8 * s;
    const bx = tableX + 6 * s + t * (tableW - 14 * s);
    rect(ctx, bx, y + 30 * s, 2 * s, s, "rgba(0,0,0,0.25)");
    rect(ctx, bx, y + 26 * s - hop, 2 * s, 2 * s, "#ffffff");
  }
  const near = left ? 1 - t : t;
  const swing = near > 0.82;
  const shuffle = Math.round(Math.sin(tMs / 160 + (left ? 0 : 2)) * 1.5);
  const px = (left ? x + 8 * s : x + 36 * s) + shuffle * s;
  drawStanding(ctx, px, y - (swing ? s : 0), s, spot, Math.sign(shuffle));
  const reach = swing ? 4 * s : 0;
  drawPaddle(ctx, left ? px + 12 * s + reach : px - 5 * s - reach, y + (swing ? 17 : 22) * s, s);
}

export function drawBreakSpot(ctx: CanvasRenderingContext2D, spot: PlacedSpot, tMs: number, frame: number): void {
  if (spot.activity === "meeting") drawSeated(ctx, spot);
  else if (spot.activity === "bar") drawBarSeat(ctx, spot, tMs);
  else if (spot.activity === "gaming") drawGamer(ctx, spot, tMs);
  else if (spot.activity === "coffee") drawCoffee(ctx, spot, frame);
  else drawPingPong(ctx, spot, tMs);
}
