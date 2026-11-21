import type { PlacedDesk } from "./model";

const SHIRTS = ["#4f8ff7", "#4ade80", "#f2b24c", "#f472b6", "#a78bfa", "#22d3ee", "#fb7185", "#94a3b8"];
const HAIR = ["#231b16", "#5b3825", "#d6a85f", "#8a5b3d", "#202938", "#6b4631", "#d7d2c8", "#b86b42"];

function rect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, colour: string): void {
  ctx.fillStyle = colour;
  ctx.fillRect(x, y, w, h);
}

function drawFloor(ctx: CanvasRenderingContext2D): void {
  const ratio = ctx.getTransform().a || 1;
  const width = ctx.canvas.width / ratio;
  const height = ctx.canvas.height / ratio;
  rect(ctx, 0, 0, width, height, "#101823");
  for (let y = 0; y < height; y += 32) {
    for (let x = 0; x < width; x += 32) {
      rect(ctx, x, y, 31, 31, (x / 32 + y / 32) % 2 ? "#121d29" : "#15212e");
    }
  }
}

function drawDesk(ctx: CanvasRenderingContext2D, desk: PlacedDesk, glow: boolean): void {
  const { x, y, scale: s } = desk;
  rect(ctx, x + 4 * s, y + 24 * s, 40 * s, 5 * s, "#8b5a32");
  rect(ctx, x + 6 * s, y + 29 * s, 4 * s, 17 * s, "#56361f");
  rect(ctx, x + 38 * s, y + 29 * s, 4 * s, 17 * s, "#56361f");
  rect(ctx, x + 13 * s, y + 11 * s, 22 * s, 14 * s, "#1d2733");
  rect(ctx, x + 15 * s, y + 13 * s, 18 * s, 10 * s, glow ? "#66d9ff" : "#263a4b");
  rect(ctx, x + 22 * s, y + 25 * s, 4 * s, 4 * s, "#29323e");
  rect(ctx, x + 15 * s, y + 38 * s, 18 * s, 8 * s, "#354252");
}

function drawPerson(ctx: CanvasRenderingContext2D, desk: PlacedDesk, frame: number): void {
  const { x, y, scale: s, employee } = desk;
  const blink = employee.pose === "idle" && frame === 1;
  rect(ctx, x + 35 * s, y + 8 * s, 10 * s, 10 * s, "#d99b72");
  rect(ctx, x + 35 * s, y + 7 * s, 10 * s, 4 * s, HAIR[employee.colour]);
  if (!blink) rect(ctx, x + 42 * s, y + 12 * s, 2 * s, 2 * s, "#1b1b22");
  rect(ctx, x + 34 * s, y + 18 * s, 12 * s, 13 * s, SHIRTS[employee.colour]);
  rect(ctx, x + 36 * s, y + 31 * s, 4 * s, 8 * s, "#273348");
  rect(ctx, x + 42 * s, y + 31 * s, 4 * s, 8 * s, "#273348");
  drawPose(ctx, desk, frame);
}

function drawPose(ctx: CanvasRenderingContext2D, desk: PlacedDesk, frame: number): void {
  const { x, y, scale: s, employee } = desk;
  if (employee.pose === "typing") {
    rect(ctx, x + (31 + frame) * s, y + 25 * s, 5 * s, 3 * s, "#d99b72");
    rect(ctx, x + (39 - frame) * s, y + 25 * s, 5 * s, 3 * s, "#d99b72");
  } else if (employee.pose === "reading") {
    rect(ctx, x + 27 * s, y + 22 * s, 9 * s, 8 * s, "#f0e1b5");
    rect(ctx, x + 36 * s, y + 22 * s, 9 * s, 8 * s, frame ? "#d7c594" : "#f0e1b5");
  } else if (employee.pose === "waiting") {
    rect(ctx, x + 45 * s, y + (2 - frame) * s, 5 * s, 8 * s, "#f2b24c");
    rect(ctx, x + 46 * s, y + (11 - frame) * s, 3 * s, 3 * s, "#f2b24c");
  } else if (employee.pose === "asleep") {
    ctx.fillStyle = "#80b5ff";
    ctx.font = `${6 * s}px monospace`;
    ctx.fillText(frame ? "z" : "Z", x + 45 * s, y + 8 * s);
  }
}

function drawLabel(ctx: CanvasRenderingContext2D, desk: PlacedDesk): void {
  const { x, y, scale: s, employee } = desk;
  rect(ctx, x + 4 * s, y + 48 * s, 44 * s, 8 * s, "#0b0f17");
  ctx.fillStyle = "#e5e9f0";
  ctx.font = `${5 * s}px monospace`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(employee.name.slice(0, 12), x + 26 * s, y + 52 * s, 40 * s);
  ctx.textAlign = "start";
  ctx.textBaseline = "alphabetic";
}

function drawSelection(ctx: CanvasRenderingContext2D, desk: PlacedDesk): void {
  const { x, y, scale: s } = desk;
  ctx.strokeStyle = "#f2b24c";
  ctx.lineWidth = 2 * s;
  ctx.strokeRect(x + s, y + s, 50 * s, 56 * s);
}

export function drawOffice(
  ctx: CanvasRenderingContext2D,
  placed: PlacedDesk[],
  tMs: number,
  selectedId: string | null,
): void {
  ctx.imageSmoothingEnabled = false;
  drawFloor(ctx);
  const frame = Math.floor(tMs / 375) % 2;
  for (const desk of placed) {
    drawDesk(ctx, desk, desk.employee.pose === "typing" && frame === 1);
    drawPerson(ctx, desk, frame);
    drawLabel(ctx, desk);
    if (desk.employee.id === selectedId) drawSelection(ctx, desk);
  }
}

export function hitTest(placed: PlacedDesk[], x: number, y: number): string | null {
  for (let index = placed.length - 1; index >= 0; index -= 1) {
    const desk = placed[index];
    if (x >= desk.x && x <= desk.x + 52 * desk.scale && y >= desk.y && y <= desk.y + 58 * desk.scale) {
      return desk.employee.id;
    }
  }
  return null;
}
