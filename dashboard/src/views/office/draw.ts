import { drawBreakRoom, drawBreakSpot } from "./breakroom";
import { drawCorridor, drawDoor, drawLobby, drawMeetingRoom } from "./floorplan";
import { BREAK_ROOM, BUILDING, MEETING_ROOM, reportingLines, type OfficeLayout, type ReportingLine, type PlacedBuilding, type PlacedDesk, type PlacedRoom } from "./model";

const SHIRTS = ["#4f8ff7", "#4ade80", "#f2b24c", "#f472b6", "#a78bfa", "#22d3ee", "#fb7185", "#e5e7eb"];
const HAIR = ["#231b16", "#5b3825", "#d6a85f", "#8a5b3d", "#202938", "#6b4631", "#d7d2c8", "#b86b42"];
const BOOKS = ["#c0392b", "#2e86c1", "#27ae60", "#f1c40f", "#8e44ad", "#e67e22"];
const C = {
  outside: "#0b0f17",
  wall: "#151b27",
  wallTrim: "#0c1018",
  backWall: "#2a3650",
  backWallLow: "#222c42",
  floor: "#8a5634",
  floorAlt: "#82502f",
  plank: "#6e4227",
  desk: "#c8955a",
  deskFront: "#9a6b3c",
  deskLeg: "#5d4026",
  pc: "#e7e2d4",
  pcShade: "#b9b3a2",
  screenOn: "#3fae6a",
  screenOff: "#27352d",
  chair: "#6bb36b",
  chairDark: "#4b8a4f",
  skin: "#e0a77f",
  pot: "#8a5a3a",
  leaf: "#2f7d4a",
  leafLight: "#46a364",
  gold: "#f2b24c",
  label: "#0b0f17",
  text: "#e5e9f0",
};

export function rect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, colour: string): void {
  ctx.fillStyle = colour;
  ctx.fillRect(x, y, w, h);
}

export function text(ctx: CanvasRenderingContext2D, value: string, x: number, y: number, size: number, max: number): void {
  ctx.font = `bold ${size}px monospace`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(value, x, y, max);
  ctx.textAlign = "start";
  ctx.textBaseline = "alphabetic";
}

function drawOutside(ctx: CanvasRenderingContext2D): void {
  const ratio = ctx.getTransform().a || 1;
  rect(ctx, 0, 0, ctx.canvas.width / ratio, ctx.canvas.height / ratio, C.outside);
}

function drawBuilding(ctx: CanvasRenderingContext2D, building: PlacedBuilding): void {
  const { x, y, width, height, scale: s } = building;
  const sign = BUILDING.sign * s;
  rect(ctx, x, y, width, height, C.wall);
  rect(ctx, x, y, width, sign, C.wallTrim);
  const plate = Math.min(width - 16 * s, Math.max(80 * s, building.label.length * 4.5 * s + 24 * s));
  rect(ctx, x + (width - plate) / 2, y + 3 * s, plate, sign - 6 * s, "#1d2433");
  ctx.fillStyle = C.gold;
  text(ctx, building.label.toUpperCase(), x + width / 2, y + sign / 2, 7 * s, plate - 8 * s);
}

export function drawFloor(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, s: number): void {
  rect(ctx, x, y, w, h, C.floor);
  const plank = 6 * s;
  for (let row = 0; row * plank < h; row += 1) {
    const py = y + row * plank;
    if (row % 2) rect(ctx, x, py, w, Math.min(plank, y + h - py), C.floorAlt);
    rect(ctx, x, py, w, Math.max(1, s / 2), C.plank);
    for (let seam = (row % 3) * 9 * s; seam < w; seam += 28 * s) rect(ctx, x + seam, py, Math.max(1, s / 2), plank, C.plank);
  }
}

export function drawPlant(ctx: CanvasRenderingContext2D, x: number, y: number, s: number): void {
  rect(ctx, x + 2 * s, y + 9 * s, 6 * s, 5 * s, C.pot);
  rect(ctx, x + 3 * s, y + 13 * s, 4 * s, s, "#6b4430");
  rect(ctx, x + 4 * s, y, 2 * s, 9 * s, C.leaf);
  rect(ctx, x, y + 3 * s, 4 * s, 2 * s, C.leafLight);
  rect(ctx, x + 6 * s, y + 2 * s, 4 * s, 2 * s, C.leafLight);
  rect(ctx, x + s, y + 6 * s, 3 * s, 2 * s, C.leaf);
  rect(ctx, x + 6 * s, y + 6 * s, 3 * s, 2 * s, C.leaf);
}

function drawShelf(ctx: CanvasRenderingContext2D, x: number, y: number, s: number): void {
  rect(ctx, x, y, 26 * s, 12 * s, "#8b5a32");
  rect(ctx, x + s, y + s, 24 * s, 4 * s, "#3b2617");
  rect(ctx, x + s, y + 7 * s, 24 * s, 4 * s, "#3b2617");
  for (let book = 0; book < 11; book += 1) {
    const colour = BOOKS[(book * 7 + Math.floor(x)) % BOOKS.length];
    rect(ctx, x + (2 + book * 2) * s, y + (book % 3 === 0 ? 2 : 1.5) * s, 1.5 * s, 3.5 * s, colour);
    if (book % 2) rect(ctx, x + (2 + book * 2) * s, y + 7.5 * s, 1.5 * s, 3.5 * s, BOOKS[(book + 2) % BOOKS.length]);
  }
}

function drawClock(ctx: CanvasRenderingContext2D, x: number, y: number, s: number): void {
  ctx.fillStyle = "#d94a3a";
  ctx.beginPath();
  ctx.arc(x, y, 4.5 * s, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#f4f1ea";
  ctx.beginPath();
  ctx.arc(x, y, 3.5 * s, 0, Math.PI * 2);
  ctx.fill();
  rect(ctx, x - 0.5 * s, y - 2.5 * s, s, 2.5 * s, "#222");
  rect(ctx, x, y - 0.5 * s, 2 * s, s, "#222");
}

export function drawBackWall(ctx: CanvasRenderingContext2D, room: PlacedRoom): void {
  const { x, y, width, scale: s } = room;
  const band = BUILDING.header * s;
  rect(ctx, x, y, width, band, C.backWall);
  rect(ctx, x, y + band - 3 * s, width, 3 * s, C.backWallLow);
  const plate = Math.min(width - 24 * s, Math.max(60 * s, room.label.length * 4 * s + 16 * s));
  rect(ctx, x + (width - plate) / 2, y + 3 * s, plate, 9 * s, "#8b5a32");
  rect(ctx, x + (width - plate) / 2 + s, y + 4 * s, plate - 2 * s, 7 * s, "#151b26");
  ctx.fillStyle = C.gold;
  text(ctx, room.label, x + width / 2, y + 7.5 * s, 5 * s, plate - 6 * s);
  const free = (width - plate) / 2;
  if (free > 42 * s) {
    drawShelf(ctx, x + 14 * s, y + 6 * s, s);
    drawShelf(ctx, x + width - 40 * s, y + 6 * s, s);
  }
  if (free > 60 * s) drawClock(ctx, x + width / 2 + plate / 2 + (free - 30 * s) / 2, y + 12 * s, s);
  drawPlant(ctx, x + 2 * s, y + band - 12 * s, s);
  drawPlant(ctx, x + width - 12 * s, y + band - 12 * s, s);
}

function drawRoom(ctx: CanvasRenderingContext2D, room: PlacedRoom): void {
  const { x, y, width, height, scale: s } = room;
  const band = BUILDING.header * s;
  drawFloor(ctx, x, y + band, width, height - band, s);
  drawBackWall(ctx, room);
  drawPlant(ctx, x + 2 * s, y + height - 15 * s, s);
  drawSideTable(ctx, x + width - 22 * s, y + height - 14 * s, s);
}

function drawSideTable(ctx: CanvasRenderingContext2D, x: number, y: number, s: number): void {
  rect(ctx, x, y + 4 * s, 20 * s, 8 * s, C.desk);
  rect(ctx, x, y + 10 * s, 20 * s, 2 * s, C.deskFront);
  rect(ctx, x + 4 * s, y + s, 4 * s, 4 * s, "#e5e7eb");
  rect(ctx, x + 8 * s, y + 2 * s, s, 2 * s, "#e5e7eb");
  rect(ctx, x + 12 * s, y - 2 * s, 5 * s, 7 * s, "#9ad1f5");
  rect(ctx, x + 12 * s, y - 3 * s, 5 * s, s, "#e5e7eb");
}

function screenColour(desk: PlacedDesk, frame: number): string {
  if (desk.away) return C.screenOff;
  return desk.employee.pose === "typing" && frame ? "#6fe39a" : C.screenOn;
}

function drawDesk(ctx: CanvasRenderingContext2D, desk: PlacedDesk, frame: number): void {
  const { x, y, scale: s } = desk;
  rect(ctx, x + 6 * s, y + 14 * s, 44 * s, 12 * s, C.desk);
  rect(ctx, x + 6 * s, y + 26 * s, 44 * s, 4 * s, C.deskFront);
  rect(ctx, x + 8 * s, y + 30 * s, 3 * s, 6 * s, C.deskLeg);
  rect(ctx, x + 45 * s, y + 30 * s, 3 * s, 6 * s, C.deskLeg);
  rect(ctx, x + 18 * s, y + 2 * s, 20 * s, 13 * s, C.pc);
  rect(ctx, x + 18 * s, y + 13 * s, 20 * s, 2 * s, C.pcShade);
  rect(ctx, x + 20 * s, y + 4 * s, 16 * s, 8 * s, screenColour(desk, frame));
  if (!desk.away) {
    const line = (frame + Math.floor(x)) % 3;
    rect(ctx, x + 22 * s, y + (5 + line * 2) * s, 9 * s, s, "#d9ffe6");
    rect(ctx, x + 22 * s, y + (6 + ((line + 1) % 3) * 2) * s, 6 * s, s, "#a7f3c0");
    rect(ctx, x + 30 * s, y + 5 * s, 6 * s, 6 * s, "#0f3d24");
    ctx.fillStyle = "#d9ffe6";
    text(ctx, String(desk.employee.sessions), x + 33 * s, y + 8.2 * s, 5 * s, 6 * s);
  }
  rect(ctx, x + 25 * s, y + 15 * s, 6 * s, 2 * s, C.pcShade);
  rect(ctx, x + 20 * s, y + 18 * s, 16 * s, 3 * s, "#d8d3c4");
  rect(ctx, x + 39 * s, y + 18 * s, 3 * s, 3 * s, "#d8d3c4");
}

function drawChair(ctx: CanvasRenderingContext2D, desk: PlacedDesk): void {
  const { x, y, scale: s } = desk;
  rect(ctx, x + 19 * s, y + 40 * s, 18 * s, 4 * s, C.chair);
  rect(ctx, x + 19 * s, y + 43 * s, 18 * s, s, C.chairDark);
  rect(ctx, x + 21 * s, y + 44 * s, 2 * s, 3 * s, "#555");
  rect(ctx, x + 33 * s, y + 44 * s, 2 * s, 3 * s, "#555");
}

const RING: Record<string, string> = { typing: "#4ade80", reading: "#60a5fa", waiting: "#f87171", idle: "#94a3b8", asleep: "#475569" };

/** A status ring on the floor under the agent: green working, blue reading, pulsing red waiting on you. */
function drawRing(ctx: CanvasRenderingContext2D, desk: PlacedDesk, tMs: number): void {
  const { x, y, scale: s, employee } = desk;
  const pulse = employee.pose === "waiting" ? 0.5 + 0.5 * Math.abs(Math.sin(tMs / 400)) : 1;
  ctx.save();
  ctx.globalAlpha = 0.85 * pulse;
  ctx.strokeStyle = RING[employee.pose] || RING.idle;
  ctx.lineWidth = Math.max(1, s);
  ctx.beginPath();
  ctx.ellipse(x + 28 * s, y + 41 * s, 12 * s, 4 * s, 0, 0, Math.PI * 2);
  ctx.stroke();
  ctx.restore();
}

/** Org-chart lines from the CTO to each agent; a work packet travels down the line of every working agent. */
function drawReportingLines(ctx: CanvasRenderingContext2D, lines: ReportingLine[], tMs: number, s: number): void {
  ctx.save();
  ctx.lineWidth = Math.max(1, s / 2);
  ctx.setLineDash([4 * s, 3 * s]);
  for (const line of lines) {
    ctx.strokeStyle = SHIRTS[line.colour];
    ctx.globalAlpha = line.active ? 0.55 : 0.25;
    ctx.beginPath();
    ctx.moveTo(line.from.x, line.from.y);
    ctx.lineTo(line.to.x, line.to.y);
    ctx.stroke();
  }
  ctx.setLineDash([]);
  ctx.globalAlpha = 1;
  lines.forEach((line, index) => {
    if (!line.active) return;
    const t = ((tMs / 2400 + index * 0.37) % 1 + 1) % 1;
    const px = line.from.x + (line.to.x - line.from.x) * t;
    const py = line.from.y + (line.to.y - line.from.y) * t;
    rect(ctx, px - 3 * s, py - 4 * s, 6 * s, 8 * s, "#f4f1ea");
    rect(ctx, px - 2 * s, py - 2 * s, 4 * s, s, "#64748b");
    rect(ctx, px - 2 * s, py, 4 * s, s, "#64748b");
  });
  ctx.restore();
}

function drawPerson(ctx: CanvasRenderingContext2D, desk: PlacedDesk, frame: number): void {
  const { x, y, scale: s, employee } = desk;
  const bob = employee.pose === "asleep" ? s : 0;
  rect(ctx, x + 20 * s, y + (31 + bob / s) * s, 16 * s, 10 * s, SHIRTS[employee.colour]);
  rect(ctx, x + 23 * s, y + 29 * s + bob, 10 * s, 3 * s, C.skin);
  rect(ctx, x + 22 * s, y + 20 * s + bob, 12 * s, 11 * s, HAIR[employee.colour]);
  rect(ctx, x + 21 * s, y + 23 * s + bob, s, 4 * s, C.skin);
  rect(ctx, x + 34 * s, y + 23 * s + bob, s, 4 * s, C.skin);
  drawPose(ctx, desk, frame);
}

function drawPose(ctx: CanvasRenderingContext2D, desk: PlacedDesk, frame: number): void {
  const { x, y, scale: s, employee } = desk;
  if (employee.pose === "typing") {
    rect(ctx, x + (18 + frame) * s, y + (27 - frame) * s, 4 * s, 4 * s, C.skin);
    rect(ctx, x + (34 - frame) * s, y + (26 + frame) * s, 4 * s, 4 * s, C.skin);
  } else if (employee.pose === "reading") {
    rect(ctx, x + 24 * s, y + 21 * s, 8 * s, 6 * s, "#f0e1b5");
    rect(ctx, x + 28 * s, y + 21 * s, 4 * s, 6 * s, frame ? "#d7c594" : "#f0e1b5");
  } else if (employee.pose === "waiting") {
    rect(ctx, x + 40 * s, y + (18 - frame) * s, 8 * s, 10 * s, "#ffffff");
    rect(ctx, x + 43 * s, y + (20 - frame) * s, 2 * s, 4 * s, C.gold);
    rect(ctx, x + 43 * s, y + (25 - frame) * s, 2 * s, 2 * s, C.gold);
  } else if (employee.pose === "asleep") {
    ctx.fillStyle = "#80b5ff";
    ctx.font = `bold ${6 * s}px monospace`;
    ctx.fillText(frame ? "z" : "Z", x + 38 * s, y + 22 * s);
  }
}

function drawLabel(ctx: CanvasRenderingContext2D, desk: { x: number; y: number; scale: number; employee: PlacedDesk["employee"] }): void {
  const { x, y, scale: s, employee } = desk;
  rect(ctx, x + 6 * s, y + 48 * s, 44 * s, 8 * s, C.label);
  ctx.fillStyle = C.text;
  ctx.font = `${5 * s}px monospace`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(employee.name.slice(0, 14), x + 28 * s, y + 52 * s, 42 * s);
  ctx.textAlign = "start";
  ctx.textBaseline = "alphabetic";
}

function drawSelection(ctx: CanvasRenderingContext2D, desk: { x: number; y: number; scale: number }): void {
  const { x, y, scale: s } = desk;
  ctx.strokeStyle = C.gold;
  ctx.lineWidth = 2 * s;
  ctx.strokeRect(x + 3 * s, y + s, 50 * s, 56 * s);
}

export function drawOffice(ctx: CanvasRenderingContext2D, layout: OfficeLayout, tMs: number, selectedId: string | null): void {
  ctx.imageSmoothingEnabled = false;
  drawOutside(ctx);
  if (layout.building) drawBuilding(ctx, layout.building);
  for (const corridor of layout.corridors) drawCorridor(ctx, corridor, layout.building?.scale || 2);
  if (layout.lobby && layout.building) drawLobby(ctx, layout.lobby, layout.building);
  for (const room of layout.rooms) {
    if (room.key === BREAK_ROOM) drawBreakRoom(ctx, room, tMs);
    else if (room.key === MEETING_ROOM) drawMeetingRoom(ctx, room);
    else drawRoom(ctx, room);
    drawDoor(ctx, room);
  }
  const frame = Math.floor(tMs / 375) % 2;
  drawReportingLines(ctx, reportingLines(layout), tMs, layout.building?.scale || 2);
  for (const desk of layout.desks) {
    drawDesk(ctx, desk, frame);
    drawChair(ctx, desk);
    if (desk.away) continue;
    drawRing(ctx, desk, tMs);
    drawPerson(ctx, desk, frame);
    drawLabel(ctx, desk);
    if (desk.employee.id === selectedId) drawSelection(ctx, desk);
  }
  for (const spot of layout.spots) {
    drawBreakSpot(ctx, spot, tMs, frame);
    drawLabel(ctx, spot);
    if (spot.employee.id === selectedId) drawSelection(ctx, spot);
  }
}

/** The running computer of an agent at its desk, for opening that agent's session console. */
export function pcHit(layout: OfficeLayout, x: number, y: number): string | null {
  const desk = layout.desks.find(
    (item) => !item.away && x >= item.x + 16 * item.scale && x <= item.x + 40 * item.scale
      && y >= item.y && y <= item.y + 18 * item.scale,
  );
  return desk ? desk.employee.id : null;
}

/** People in the break room first, then the employees seated at their desks. */
export function hitTest(layout: OfficeLayout, x: number, y: number): string | null {
  const placed = [...layout.desks.filter((desk) => !desk.away), ...layout.spots];
  for (let index = placed.length - 1; index >= 0; index -= 1) {
    const desk = placed[index];
    if (x >= desk.x && x <= desk.x + 56 * desk.scale && y >= desk.y && y <= desk.y + 58 * desk.scale) {
      return desk.employee.id;
    }
  }
  return null;
}
