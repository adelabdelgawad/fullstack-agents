export function openNewSession(_anchor: HTMLElement): void {}

export interface HerdrConfirmOpts {
  confirm?: string;
  after?: () => void;
}

export function openHerdrConfirm(
  _title: string,
  _text: string,
  _action: string,
  _params: Record<string, unknown>,
  _returnFocus: HTMLElement | null,
  _opts?: HerdrConfirmOpts,
): void {}

export function openHerdrContextMenu(_kind: string, _item: unknown, _x: number, _y: number, _anchor: HTMLElement): void {}

export function closeHerdrOverlay(_restoreFocus = true): void {}

export async function herdrAction(_action: string, _params?: Record<string, unknown>, _ownerRoot?: HTMLElement | null): Promise<{ ok: boolean }> {
  return { ok: false };
}

export function HerdrOverlay(): null {
  return null;
}
