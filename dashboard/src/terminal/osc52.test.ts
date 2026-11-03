import { describe, expect, it } from "vitest";
import { createOsc52Scanner } from "./osc52";

const sequence = (text: string, terminator: number[]) => {
  const payload = btoa(String.fromCharCode(...new TextEncoder().encode(text)));
  return Uint8Array.from([0x1b, 0x5d, 0x35, 0x32, 0x3b, ...new TextEncoder().encode(`c;${payload}`), ...terminator]);
};

describe("createOsc52Scanner", () => {
  it.each([
    ["BEL", [0x07]],
    ["ST", [0x1b, 0x5c]],
  ])("decodes %s-terminated sequences", (_name, terminator) => {
    const received: string[] = [];
    createOsc52Scanner((text) => received.push(text))(sequence("Hello, OSC 52", terminator as number[]));
    expect(received).toEqual(["Hello, OSC 52"]);
  });

  it("decodes a sequence split across chunks", () => {
    const received: string[] = [];
    const scan = createOsc52Scanner((text) => received.push(text));
    sequence("byte at a time", [0x07]).forEach((byte) => scan(Uint8Array.of(byte)));
    expect(received).toEqual(["byte at a time"]);
  });

  it("ignores queries, plain output, malformed base64, and oversized sequences", () => {
    const received: string[] = [];
    const scan = createOsc52Scanner((text) => received.push(text));
    scan(new TextEncoder().encode("ordinary shell output\r\n\x1b]52;c;?\x07\x1b]52;c;%%%\x07"));
    scan(Uint8Array.from([0x1b, 0x5d, 0x35, 0x32, 0x3b]));
    scan(new Uint8Array((4 << 20) + 10).fill(0x41));
    scan(Uint8Array.of(0x07));
    expect(received).toEqual([]);
  });

  it("decodes UTF-8 payloads", () => {
    const received: string[] = [];
    createOsc52Scanner((text) => received.push(text))(sequence("héllo 世界", [0x07]));
    expect(received).toEqual(["héllo 世界"]);
  });
});
