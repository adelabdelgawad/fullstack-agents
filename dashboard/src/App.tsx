import { useEffect } from "react";
import { CardContextMenu } from "./components/CardContextMenu";
import { Layout } from "./components/Layout";
import { isOutOpen, OutDialog } from "./components/OutDialog";
import { Toasts } from "./components/Toasts";
import { Panel } from "./panel/Panel";
import { closeCtx, closePanel, load, setWall, store, useStore } from "./store";
import { HerdrOverlay } from "./terminal/HerdrOverlay";
import { AgentsActions, AgentsView } from "./views/AgentsView";
import { HerdrView } from "./views/HerdrView";
import { HistoryView } from "./views/HistoryView";

function onEscape(e: KeyboardEvent): void {
  if (e.key !== "Escape") return;
  const t = e.target as HTMLElement;
  if (isOutOpen() || t.closest?.(".terminal, .herdr-client")) return;
  if (closeCtx()) return;
  if (store.get().openRun) store.set({ openRun: null });
  else closePanel();
}

function onWallKey(e: KeyboardEvent): void {
  const t = e.target as HTMLElement;
  const typing = t.closest && t.closest("input, textarea, select, [contenteditable], .terminal, dialog");
  if (typing || e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.key === "w" && store.get().view !== "herdr") {
    e.preventDefault();
    setWall(!store.get().wall);
  } else if (e.key === "Escape" && store.get().wall && !store.get().openKey) {
    setWall(false);
  }
}

function useAppEffects(view: string, wall: boolean): void {
  useEffect(() => {
    document.documentElement.classList.toggle("agents-page", view === "agents");
    document.documentElement.classList.toggle("herdr-page", view === "herdr");
  }, [view]);
  useEffect(() => {
    document.documentElement.classList.toggle("wall", wall);
  }, [wall]);
  useEffect(() => {
    load();
    const id = setInterval(load, 4000);
    document.addEventListener("keydown", onEscape);
    document.addEventListener("keydown", onWallKey);
    return () => {
      clearInterval(id);
      document.removeEventListener("keydown", onEscape);
      document.removeEventListener("keydown", onWallKey);
    };
  }, []);
}

export function App() {
  const view = useStore((s) => s.view);
  const wall = useStore((s) => s.wall);
  useAppEffects(view, wall);
  const View = view === "herdr" ? HerdrView : view === "history" ? HistoryView : AgentsView;
  return (
    <>
      <Layout actions={view === "agents" ? <AgentsActions /> : undefined}>
        <View />
      </Layout>
      <Panel />
      <Toasts />
      <div className="wall-hint">wall mode · press w or Esc to exit</div>
      <OutDialog />
      <CardContextMenu />
      <HerdrOverlay />
    </>
  );
}
