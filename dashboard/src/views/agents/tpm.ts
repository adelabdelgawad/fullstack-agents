import { onStateLoaded, store } from "../../store";

export const fleetTpm: number[] = [];
export const cardTpm = new Map<string, number[]>();

export function noteTpm(): void {
  const totals = store.get().state?.totals as Record<string, number> | undefined;
  if (!totals) return;
  fleetTpm.push(totals.tpm || 0);
  if (fleetTpm.length > 60) fleetTpm.shift();
}

export function noteCardTpm(): void {
  for (const card of store.get().state?.cards || []) {
    const points = cardTpm.get(card.key) || [];
    points.push(Number(card.usage?.tpm) || 0);
    if (points.length > 40) points.shift();
    cardTpm.set(card.key, points);
  }
}

onStateLoaded(noteTpm);
onStateLoaded(noteCardTpm);
