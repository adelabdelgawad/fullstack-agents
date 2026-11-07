import { describe, expect, it } from "vitest";
import type { HerdrState } from "../lib/types";
import { herdrTabChips } from "./HerdrTabs";

const base: HerdrState = {
  running: true,
  workspaces: [{ workspace_id: "w1" }, { workspace_id: "w2" }],
  tabs: [
    { tab_id: "w1:t1", workspace_id: "w1", label: "asr-session02", agent_status: "working" },
    { tab_id: "w1:t2", workspace_id: "w1", label: "", number: 2, agent_status: "weird" },
    { tab_id: "w2:t3", workspace_id: "w2", label: "other", agent_status: "blocked" },
  ],
  panes: [],
  focused_pane_id: null,
};

describe("herdr tab chips", () => {
  it("lists the focused workspace's tabs with their agent state", () => {
    const chips = herdrTabChips({ ...base, focused_tab_id: "w1:t1", focused_workspace_id: "w1" });
    expect(chips).toEqual([
      { id: "w1:t1", label: "asr-session02", status: "working", focused: true },
      { id: "w1:t2", label: "2", status: "unknown", focused: false },
    ]);
  });

  it("follows the focused tab's workspace when the workspace id is missing", () => {
    const chips = herdrTabChips({ ...base, focused_tab_id: "w2:t3" });
    expect(chips.map((chip) => [chip.id, chip.status, chip.focused])).toEqual([["w2:t3", "blocked", true]]);
  });
});
