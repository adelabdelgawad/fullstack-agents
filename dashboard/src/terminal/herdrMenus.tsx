import { useEffect, useLayoutEffect, useRef } from "react";

export interface HerdrMenuItem {
  label: string;
  run: () => void;
  disabled?: boolean;
  title?: string;
}

export interface HerdrMenuProps {
  items: HerdrMenuItem[];
  x: number;
  y: number;
  above?: boolean;
  close: (restore?: boolean) => void;
}

export function HerdrMenu({ items, x, y, above = false, close }: HerdrMenuProps) {
  const ref = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const menu = ref.current;
    if (!menu) return;
    menu.style.left = `${Math.max(8, Math.min(x, innerWidth - menu.offsetWidth - 8))}px`;
    menu.style.top = `${Math.max(8, Math.min(above ? y - menu.offsetHeight : y, innerHeight - menu.offsetHeight - 8))}px`;
  }, [above, x, y]);
  useEffect(() => {
    ref.current?.querySelector<HTMLButtonElement>("button:not(:disabled)")?.focus();
  }, []);
  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      close();
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      (document.activeElement as HTMLElement | null)?.click();
      return;
    }
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    const buttons = [...(ref.current?.querySelectorAll<HTMLButtonElement>("button:not(:disabled)") ?? [])];
    if (!buttons.length) return;
    event.preventDefault();
    const at = buttons.indexOf(document.activeElement as HTMLButtonElement);
    buttons[(at + (event.key === "ArrowDown" ? 1 : buttons.length - 1)) % buttons.length].focus();
  };
  return (
    <div ref={ref} className="herdr-menu" role="menu" onKeyDown={onKeyDown}>
      {items.map((item, index) => (
        <button
          key={index}
          role="menuitem"
          data-herdr-menu-item={index}
          disabled={item.disabled}
          title={item.disabled ? item.title || "" : undefined}
          onClick={() => {
            close(false);
            item.run();
          }}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
