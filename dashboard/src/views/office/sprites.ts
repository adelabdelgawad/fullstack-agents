/** People sprites shared by the office drawing: a figure walking between rooms, optionally carrying a desk. */
const SHIRTS = ["#4f8ff7", "#4ade80", "#f2b24c", "#f472b6", "#a78bfa", "#22d3ee", "#fb7185", "#e5e7eb"];
const HAIR = ["#231b16", "#5b3825", "#d6a85f", "#8a5b3d", "#202938", "#6b4631", "#d7d2c8", "#b86b42"];
const SKIN = "#e0a77f";

function rect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, colour: string): void {
  ctx.fillStyle = colour;
  ctx.fillRect(x, y, w, h);
}

/** A standing person seen from the front; `step` swings the legs (-1, 0, 1) for walking. */
function drawFigure(ctx: CanvasRenderingContext2D, x: number, y: number, s: number, colour: number, step = 0): void {
  rect(ctx, x, y + 10 * s, 12 * s, 10 * s, SKIN);
  rect(ctx, x, y + 8 * s, 12 * s, 4 * s, HAIR[colour]);
  rect(ctx, x + 3 * s, y + 14 * s, 2 * s, 2 * s, "#1b1b22");
  rect(ctx, x + 7 * s, y + 14 * s, 2 * s, 2 * s, "#1b1b22");
  rect(ctx, x - s, y + 20 * s, 14 * s, 13 * s, SHIRTS[colour]);
  rect(ctx, x + s, y + (33 - Math.max(0, step) * 2) * s, 4 * s, (10 - Math.max(0, step) * 2) * s, "#273348");
  rect(ctx, x + 7 * s, y + (33 + Math.min(0, step) * 2) * s, 4 * s, (10 + Math.min(0, step) * 2) * s, "#273348");
}

/** A small desk held in front of the body while it is carried in or out of the office. */
function drawCarriedDesk(ctx: CanvasRenderingContext2D, fx: number, fy: number, s: number): void {
  rect(ctx, fx - 13 * s, fy - 26 * s, 26 * s, 7 * s, "#c8955a");
  rect(ctx, fx - 13 * s, fy - 19 * s, 26 * s, 2 * s, "#9a6b3c");
  rect(ctx, fx - 12 * s, fy - 17 * s, 2 * s, 5 * s, "#5d4026");
  rect(ctx, fx + 10 * s, fy - 17 * s, 2 * s, 5 * s, "#5d4026");
}

/** An agent walking between rooms, feet at (fx, fy); when carrying, its hands hold a desk in front of it. */
export function drawWalking(
  ctx: CanvasRenderingContext2D,
  fx: number,
  fy: number,
  s: number,
  colour: number,
  step: number,
  carrying = false,
): void {
  drawFigure(ctx, fx - 6 * s, fy - 43 * s, s, colour, step ? 1 : -1);
  if (carrying) {
    drawCarriedDesk(ctx, fx, fy, s);
    rect(ctx, fx - 14 * s, fy - 24 * s, 3 * s, 3 * s, SKIN);
    rect(ctx, fx + 11 * s, fy - 24 * s, 3 * s, 3 * s, SKIN);
    return;
  }
  rect(ctx, fx - 9 * s, fy - 22 * s + (step ? s : 0), 3 * s, 8 * s, SHIRTS[colour]);
  rect(ctx, fx + 6 * s, fy - 22 * s + (step ? 0 : s), 3 * s, 8 * s, SHIRTS[colour]);
}
