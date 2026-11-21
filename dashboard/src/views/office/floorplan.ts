import { drawBackWall, drawPlant, rect, text } from "./draw";
import { BUILDING, type PlacedBuilding, type PlacedRoom, type Rect } from "./model";

const CARPET = "#3b4456";
const RUNNER = "#46516a";
const LOBBY_A = "#cfc8b8";
const LOBBY_B = "#c2baa8";

/** A corridor: grey carpet with a lighter runner down its length and a plant at the far end. */
export function drawCorridor(ctx: CanvasRenderingContext2D, corridor: Rect, s: number): void {
  const { x, y, width, height } = corridor;
  rect(ctx, x, y, width, height, CARPET);
  if (width >= height) rect(ctx, x, y + height / 2 - 2 * s, width, 4 * s, RUNNER);
  else rect(ctx, x + width / 2 - 2 * s, y, 4 * s, height, RUNNER);
  if (width >= height && width > 60 * s) drawPlant(ctx, x + 4 * s, y + height / 2 - 8 * s, s * 0.8);
}

function drawReception(ctx: CanvasRenderingContext2D, x: number, y: number, s: number): void {
  rect(ctx, x, y, 60 * s, 10 * s, "#8b5a32");
  rect(ctx, x, y + 8 * s, 60 * s, 3 * s, "#5d4026");
  rect(ctx, x + 50 * s, y - 14 * s, 10 * s, 24 * s, "#8b5a32");
  rect(ctx, x + 14 * s, y - 6 * s, 12 * s, 7 * s, "#e7e2d4");
  rect(ctx, x + 15 * s, y - 5 * s, 10 * s, 4 * s, "#3fae6a");
  rect(ctx, x + 34 * s, y + 2 * s, 8 * s, 4 * s, "#f4f1ea");
  ctx.fillStyle = "#f2b24c";
  text(ctx, "RECEPTION", x + 30 * s, y + 18 * s, 5 * s, 60 * s);
}

/** The lobby across the bottom: tiled floor, reception desk, waiting sofa and the building entrance. */
export function drawLobby(ctx: CanvasRenderingContext2D, lobby: Rect, building: PlacedBuilding): void {
  const { x, y, width, height } = lobby;
  const s = building.scale;
  const tile = 10 * s;
  for (let row = 0; row * tile < height; row += 1) {
    for (let col = 0; col * tile < width; col += 1) {
      const w = Math.min(tile, width - col * tile);
      rect(
        ctx,
        x + col * tile,
        y + row * tile,
        w,
        Math.min(tile, height - row * tile),
        (row + col) % 2 ? LOBBY_A : LOBBY_B,
      );
    }
  }
  const door = x + width / 2;
  rect(ctx, door - 16 * s, y + height, 32 * s, building.y + building.height - y - height, LOBBY_A);
  rect(ctx, door - 12 * s, y + height - 6 * s, 24 * s, 6 * s, "#7a2e2e");
  if (width > 200 * s) drawReception(ctx, door - 90 * s, y + 14 * s, s);
  if (width > 160 * s) {
    rect(ctx, door + 40 * s, y + 16 * s, 36 * s, 10 * s, "#9b2c48");
    rect(ctx, door + 40 * s, y + 24 * s, 36 * s, 4 * s, "#7d2239");
  }
  drawPlant(ctx, x + 4 * s, y + 6 * s, s);
  drawPlant(ctx, x + width - 14 * s, y + 6 * s, s);
}

/** The door gap in a room's bottom wall with its leaf swung open into the room. */
export function drawDoor(ctx: CanvasRenderingContext2D, room: PlacedRoom): void {
  if (!room.door) return;
  const s = room.scale;
  const sill = room.y + room.height;
  const { x, width, depth } = room.door;
  rect(ctx, x, sill, width, depth, "#8a5634");
  rect(ctx, x, sill - width, 2 * s, width, "#6b4430");
  ctx.strokeStyle = "rgba(240, 225, 190, 0.45)";
  ctx.lineWidth = Math.max(1, s / 2);
  ctx.beginPath();
  ctx.arc(x, sill, width, -Math.PI / 2, 0);
  ctx.stroke();
}

function drawWhiteboard(ctx: CanvasRenderingContext2D, x: number, y: number, s: number): void {
  rect(ctx, x, y, 44 * s, 16 * s, "#9aa3ad");
  rect(ctx, x + s, y + s, 42 * s, 14 * s, "#f7f7f2");
  rect(ctx, x + 4 * s, y + 4 * s, 10 * s, 6 * s, "#4f8ff7");
  rect(ctx, x + 18 * s, y + 4 * s, 10 * s, 6 * s, "#4ade80");
  rect(ctx, x + 14 * s, y + 6.5 * s, 4 * s, s, "#333");
  rect(ctx, x + 28 * s, y + 6.5 * s, 4 * s, s, "#333");
  rect(ctx, x + 32 * s, y + 4 * s, 8 * s, 6 * s, "#f472b6");
  rect(ctx, x + 4 * s, y + 12 * s, 26 * s, s, "#c0392b");
}

/** Meeting room for plan and design work: carpet, a whiteboard, a long table with chairs and laptops. */
export function drawMeetingRoom(ctx: CanvasRenderingContext2D, room: PlacedRoom): void {
  const { x, y, width, height, scale: d } = room;
  const band = BUILDING.header * d;
  rect(ctx, x, y + band, width, height - band, "#34506b");
  for (let line = y + band + 6 * d; line < y + height; line += 6 * d)
    rect(ctx, x, line, width, Math.max(1, d / 3), "#3c5a77");
  drawBackWall(ctx, room);
  if (width > 140 * d) drawWhiteboard(ctx, x + 4 * d, y + 5 * d, d * 0.9);
  const table = room.table;
  if (!table) return;
  const s = table.height / 22;
  const seats = Math.max(1, Math.round(table.width / (34 * s)));
  const step = table.width / seats;
  for (let seat = 0; seat < seats; seat += 1) {
    const cx = table.x + step * (seat + 0.5);
    rect(ctx, cx - 6 * s, table.y - 8 * s, 12 * s, 6 * s, "#6b7280");
    rect(ctx, cx - 6 * s, table.y + table.height + 2 * s, 12 * s, 6 * s, "#6b7280");
  }
  rect(ctx, table.x, table.y, table.width, table.height, "#6b4430");
  rect(ctx, table.x + 2 * s, table.y + 2 * s, table.width - 4 * s, table.height - 6 * s, "#7d5236");
  for (let seat = 0; seat < seats; seat += 1) {
    const cx = table.x + step * (seat + 0.5);
    rect(ctx, cx - 4 * s, table.y + 3 * s, 8 * s, 5 * s, "#cfd5dd");
    rect(ctx, cx - 3 * s, table.y + table.height - 9 * s, 6 * s, 4 * s, "#f4f1ea");
  }
}

/** The CTO's executive office: deep carpet with a gold-trimmed rug, a leather sofa, art, a globe and tall plants. */
export function drawExecutiveRoom(ctx: CanvasRenderingContext2D, room: PlacedRoom): void {
  const { x, y, width, height, scale: s } = room;
  const band = BUILDING.header * s;
  rect(ctx, x, y + band, width, height - band, "#2d1f3d");
  for (let row = 0; row * 10 * s < height - band; row += 1) {
    if (row % 2) rect(ctx, x, y + band + row * 10 * s, width, 5 * s, "#33244a");
  }
  const rugW = Math.min(width - 24 * s, 120 * s);
  const rugH = Math.min(height - band - 30 * s, 70 * s);
  if (rugH > 20 * s) {
    const rx = x + (width - rugW) / 2;
    const ry = y + band + 10 * s;
    rect(ctx, rx, ry, rugW, rugH, "#c8a24a");
    rect(ctx, rx + 2 * s, ry + 2 * s, rugW - 4 * s, rugH - 4 * s, "#7a1f2b");
    rect(ctx, rx + 6 * s, ry + 6 * s, rugW - 12 * s, rugH - 12 * s, "#8f2a37");
  }
  drawBackWall(ctx, room);
  if (width > 110 * s) {
    rect(ctx, x + 22 * s, y + 4 * s, 18 * s, 13 * s, "#c8a24a");
    rect(ctx, x + 23 * s, y + 5 * s, 16 * s, 11 * s, "#1e3a5f");
    rect(ctx, x + 25 * s, y + 11 * s, 12 * s, 4 * s, "#e9c46a");
    rect(ctx, x + 30 * s, y + 7 * s, 3 * s, 3 * s, "#f4f1ea");
  }
  // Leather sofa and coffee table by the door wall; a globe in the far corner.
  if (height - band > 70 * s && width > 120 * s) {
    const sx = x + width - 50 * s;
    const sy = y + height - 18 * s;
    rect(ctx, sx, sy, 40 * s, 5 * s, "#4a2c1a");
    rect(ctx, sx, sy + 5 * s, 40 * s, 7 * s, "#6b3e24");
    rect(ctx, sx - 3 * s, sy + 2 * s, 4 * s, 10 * s, "#4a2c1a");
    rect(ctx, sx + 39 * s, sy + 2 * s, 4 * s, 10 * s, "#4a2c1a");
    rect(ctx, sx + 10 * s, sy - 12 * s, 20 * s, 7 * s, "#2b2b2b");
    rect(ctx, sx + 11 * s, sy - 11 * s, 18 * s, 2 * s, "#c8a24a");
    ctx.fillStyle = "#2a6f97";
    ctx.beginPath();
    ctx.arc(x + width - 16 * s, y + band + 14 * s, 6 * s, 0, Math.PI * 2);
    ctx.fill();
    rect(ctx, x + width - 18 * s, y + band + 10 * s, 5 * s, 3 * s, "#52b788");
    rect(ctx, x + width - 17 * s, y + band + 20 * s, 2 * s, 4 * s, "#c8a24a");
  }
  drawPlant(ctx, x + 2 * s, y + height - 15 * s, s);
  drawPlant(ctx, x + 14 * s, y + height - 15 * s, s);
}
