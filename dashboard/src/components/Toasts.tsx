import type { MouseEvent } from "react";
import { dismissToast, openCard, setView, store, useStore } from "../store";
import type { Toast } from "../store";

export function Toasts() {
  const toasts = useStore((s) => s.toasts);
  return (
    <div id="toasts" aria-live="polite">
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} />
      ))}
    </div>
  );
}

function ToastItem({ toast }: { toast: Toast }) {
  const handleClick = (e: MouseEvent<HTMLDivElement>) => {
    if ((e.target as HTMLElement).closest(".toast-x")) {
      e.stopPropagation();
      dismissToast(toast.id);
      return;
    }
    if (store.get().view === "herdr") setView("agents");
    if (toast.target) openCard(toast.target);
    dismissToast(toast.id);
  };
  const html = `<button class="toast-x" aria-label="Dismiss notification" title="Dismiss">×</button>${toast.html}`;
  return (
    <div className={`toast ${toast.tone}`.trim()} onClick={handleClick} dangerouslySetInnerHTML={{ __html: html }} />
  );
}
