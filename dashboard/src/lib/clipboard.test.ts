import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { writeClipboard } from "./clipboard";

describe("writeClipboard", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("uses navigator.clipboard in a secure context", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    vi.stubGlobal("isSecureContext", true);

    await expect(writeClipboard("hello")).resolves.toBe(true);
    expect(writeText).toHaveBeenCalledWith("hello");
  });

  describe("execCommand fallback", () => {
    beforeEach(() => {
      Object.assign(navigator, { clipboard: undefined });
      vi.stubGlobal("isSecureContext", false);
    });

    it("falls back to a hidden textarea and execCommand", async () => {
      const execCommand = vi.fn().mockReturnValue(true);
      document.execCommand = execCommand;

      await expect(writeClipboard("fallback text")).resolves.toBe(true);
      expect(execCommand).toHaveBeenCalledWith("copy");
      expect(document.querySelector("textarea")).toBeNull();
    });

    it("reports failure when execCommand fails", async () => {
      document.execCommand = vi.fn().mockReturnValue(false);

      await expect(writeClipboard("fallback text")).resolves.toBe(false);
    });
  });
});
