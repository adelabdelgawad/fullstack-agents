import { describe, expect, it } from "vitest";
import { matchCommands } from "./slash";

const commands = [
  "clear",
  "compact",
  "config",
  "fullstack-agents:debug",
  "fullstack-agents:review",
  "review",
  "security-review",
].map((name) => ({ name, description: "" }));
const names = (text: string) => matchCommands(commands, text).map((command) => command.name);

describe("slash suggestions", () => {
  it("match by prefix, also after a plugin prefix, then by substring", () => {
    expect(names("/co")).toEqual(["compact", "config"]);
    expect(names("/rev")).toEqual(["fullstack-agents:review", "review", "security-review"]);
    expect(names("/deb")).toEqual(["fullstack-agents:debug"]);
  });

  it("show everything for a bare slash and nothing once the command has arguments or text is not a command", () => {
    expect(names("/")).toHaveLength(commands.length);
    expect(names("/compact keep the plan")).toEqual([]);
    expect(names("hello /co")).toEqual([]);
  });
});
