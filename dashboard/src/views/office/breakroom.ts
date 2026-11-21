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
      const colour = (row + col) % 2 ? "#2b2f36" : "#d6d8dc";
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
  drawCoffeeBar(ctx, x + 6 * s, y + band + 4 * s, s, tMs);
  if (height - band > 40 * s) drawSofa(ctx, x + width - 46 * s, y + height - 16 * s, s);
  if (room.table) drawTable(ctx, room.table);
}

function drawStanding(ctx: CanvasRenderingContext2D, x: number, y: number, s: number, spot: PlacedSpot): void {
  const colour = spot.employee.colour;
  rect(ctx, x, y + 10 * s, 12 * s, 10 * s, SKIN);
  rect(ctx, x, y + 8 * s, 12 * s, 4 * s, HAIR[colour]);
  rect(ctx, x + 3 * s, y + 14 * s, 2 * s, 2 * s, "#1b1b22");
  rect(ctx, x + 7 * s, y + 14 * s, 2 * s, 2 * s, "#1b1b22");
  rect(ctx, x - s, y + 20 * s, 14 * s, 13 * s, SHIRTS[colour]);
  rect(ctx, x + s, y + 33 * s, 4 * s, 10 * s, "#273348");
  rect(ctx, x + 7 * s, y + 33 * s, 4 * s, 10 * s, "#273348");
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

/** Left player draws the shared table and the ball; each player stands at an outer end of its pair of cells. */
function drawPingPong(ctx: CanvasRenderingContext2D, spot: PlacedSpot, tMs: number): void {
  const { x, y, scale: s } = spot;
  const left = spot.activity === "pingpong-left";
  if (left) {
    const tableX = x + 24 * s;
    const tableW = 64 * s;
    const phase = (tMs % 1200) / 600;
    const t = phase < 1 ? phase : 2 - phase;
    const hop = Math.abs(Math.sin(t * Math.PI)) * 8 * s;
    rect(ctx, tableX + 6 * s + t * (tableW - 14 * s), y + 26 * s - hop, 2 * s, 2 * s, "#ffffff");
  }
  const px = left ? x + 8 * s : x + 36 * s;
  drawStanding(ctx, px, y, s, spot);
  drawPaddle(ctx, left ? px + 12 * s : px - 5 * s, y + 22 * s, s);
}

export function drawBreakSpot(ctx: CanvasRenderingContext2D, spot: PlacedSpot, tMs: number, frame: number): void {
  if (spot.activity === "meeting") drawStanding(ctx, spot.x + 22 * spot.scale, spot.y, spot.scale, spot);
  else if (spot.activity === "coffee") drawCoffee(ctx, spot, frame);
  else drawPingPong(ctx, spot, tMs);
}
