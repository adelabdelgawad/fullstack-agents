import { useEffect } from "react";
import type { HerdrState } from "../lib/types";
import { setHerdrTabTintChips } from "../terminal/herdrTabTint";

export interface HerdrTabChip {
  id: string;
  label: string;
  status: string;
  focused: boolean;
}

const STATUSES = new Set(["working", "blocked", "done", "idle"]);

function text(record: Record<string, unknown>, key: string): string {
  const value = record[key];
  return typeof value === "string" || typeof value === "number" ? String(value) : "";
}

export function herdrTabChips(data: HerdrState): HerdrTabChip[] {
  const tabs = data.tabs as Record<string, unknown>[];
  const focusedTab = typeof data.focused_tab_id === "string" ? data.focused_tab_id : "";
  const workspace =
    (typeof data.focused_workspace_id === "string" && data.focused_workspace_id) ||
    text(tabs.find((tab) => text(tab, "tab_id") === focusedTab) ?? {}, "workspace_id") ||
    text((data.workspaces as Record<string, unknown>[])[0] ?? {}, "workspace_id");
  return tabs
    .filter((tab) => text(tab, "workspace_id") === workspace)
    .map((tab) => {
      const status = text(tab, "agent_status");
      return {
        id: text(tab, "tab_id"),
        label: text(tab, "label") || text(tab, "number") || text(tab, "tab_id"),
        status: STATUSES.has(status) ? status : "unknown",
        focused: text(tab, "tab_id") === focusedTab,
      };
    });
}

export function HerdrTabs({ data }: { data: HerdrState }) {
  useEffect(() => setHerdrTabTintChips(herdrTabChips(data)), [data]);
  return null;
}
