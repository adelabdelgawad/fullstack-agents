// @ts-expect-error Vitest provides node:fs while the application tsconfig omits Node declarations.
import { readdirSync, readFileSync } from "node:fs";
// @ts-expect-error Vitest provides node:path while the application tsconfig omits Node declarations.
import { join, resolve } from "node:path";
// @ts-expect-error Vitest provides node:process while the application tsconfig omits Node declarations.
import process from "node:process";
import { describe, expect, it } from "vitest";
import { copySelection, type CopyAction } from "./copy";
import { createOsc52Scanner } from "./osc52";

const removedNames = [
  "herdrSidebarHtml",
  "herdrTabsHtml",
  "wireHerdrPicks",
  "closeHerdrTab",
  "applyHerdrSidebarRatio",
  "herdrChromeSnapshot",
  "restoreHerdrChrome",
  "updateHerdrTabOverflow",
  "followNewHerdrTab",
  "herdrKnownTabs",
  "openHerdrGlobalMenu",
  "herdrSidebarRatio",
  "herdrDragging",
  "selectedHerdrPane",
  "sessionHerdrPane",
  "statusMeta",
  "statusHtml",
  "workspaceStatus",
  "fsa-herdr-sidebar-ratio",
  "herdr-view",
  "herdr-list",
  "herdr-sidebar-",
  "herdr-workspace",
  "herdr-agent",
  "herdr-tab",
  "herdr-main",
];

interface SourceEntry {
  name: string;
  isDirectory: () => boolean;
}

function base64(text: string): string {
  return btoa(String.fromCharCode(...new TextEncoder().encode(text)));
}

function sequence(text: string, terminator: number[] = [0x07]): Uint8Array {
  const payload = `c;${base64(text)}`;
  return Uint8Array.from([
    0x1b,
    0x5d,
    0x35,
    0x32,
    0x3b,
    ...[...payload].map((char) => char.charCodeAt(0)),
    ...terminator,
  ]);
}

function scan(chunks: Uint8Array[]): string[] {
  const received: string[] = [];
  const scanner = createOsc52Scanner((text) => received.push(text));
  chunks.forEach((chunk) => scanner(chunk));
  return received;
}

function sourceText(directory = resolve(process.cwd(), "src")): string {
  return (readdirSync(directory, { withFileTypes: true }) as SourceEntry[])
    .flatMap((entry) => {
      const path = join(directory, entry.name);
      if (entry.isDirectory()) return sourceText(path);
      return /\.test\.[^.]+$/.test(entry.name) ? [] : [readFileSync(path, "utf8")];
    })
    .join("\n");
}

describe("herdr client Python parity", () => {
  it("bel_terminated_sequence_decodes", () => {
    expect(scan([sequence("Hello, OSC 52")])).toEqual(["Hello, OSC 52"]);
  });

  it("st_terminated_sequence_decodes", () => {
    expect(scan([sequence("via ST", [0x1b, 0x5c])])).toEqual(["via ST"]);
  });

  it("sequence_split_byte_by_byte_across_chunks", () => {
    expect(scan([...sequence("byte at a time")].map((byte) => Uint8Array.of(byte)))).toEqual(["byte at a time"]);
  });

  it("query_payload_is_ignored", () => {
    const bytes = Uint8Array.from([
      0x1b,
      0x5d,
      0x35,
      0x32,
      0x3b,
      ...[..."c;?"].map((char) => char.charCodeAt(0)),
      0x07,
    ]);
    expect(scan([bytes])).toEqual([]);
  });

  it("utf8_payload_decodes_multibyte_text", () => {
    expect(scan([sequence("héllo 世界")])).toEqual(["héllo 世界"]);
  });

  it("oversize_sequence_is_dropped", () => {
    const chunks = [
      Uint8Array.from([0x1b, 0x5d, 0x35, 0x32, 0x3b]),
      new Uint8Array((4 << 20) + 10).fill(0x41),
      Uint8Array.of(0x07),
    ];
    expect(scan(chunks)).toEqual([]);
  });

  it("plain_output_calls_no_text", () => {
    expect(scan([new TextEncoder().encode("ordinary shell output\r\n")])).toEqual([]);
  });

  it("blocked_copy_offers_a_click_that_retries_the_same_text", async () => {
    const toasts: Array<[string, string | undefined]> = [];
    const actions: CopyAction[] = [];
    const writes: number[] = [];
    let allow = false;
    let restored = 0;
    const write = async (text: string) => (writes.push(text.length), allow);
    const show = (message: string, action?: CopyAction) => {
      toasts.push([message, action?.label]);
      if (action) actions.push(action);
    };
    const text = "x".repeat(40_000);
    await copySelection(text, () => restored++, write, show);
    allow = true;
    await actions[0].run();
    expect(toasts).toEqual([
      ["copy blocked by the browser", "copy 40000 chars"],
      ["copied 40000 chars", undefined],
    ]);
    expect(writes).toEqual([40_000, 40_000]);
    expect(restored).toEqual(2);
  });

  it("herdr_client_copy_reports_the_real_result", () => {
    const source = sourceText();
    expect(source).toMatch(
      /const onCopyText = \(text: string\) => \{[\s\S]*?if \(text\) void copySelection\(text, \(\) => term\.focus\(\)\);[\s\S]*?\};/,
    );
  });

  it("removed_herdr_sidebar_and_tab_chrome_left_no_references", () => {
    const source = sourceText();
    expect(removedNames.filter((name) => source.includes(name))).toEqual([]);
  });

  it("herdr_client_uses_the_websocket_endpoint", () => {
    expect(sourceText()).toContain("/api/herdr/client");
  });

  it("herdr_client_has_red_attach_button_using_the_file_endpoint", () => {
    const source = sourceText();
    expect(source).toContain("data-herdr-client-attach");
    expect(source).toMatch(/\.herdr-client-attach\s*\{[^}]*color:\s*var\(--herdr-red\)/);
    expect(source).toContain('uploadFiles(files, "/api/herdr/file?")');
    expect(source).toMatch(/wireFileDrop\(host, \(files\) => void attach\(files\)\)/);
  });
});
