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

  it("falls back to execCommand when navigator.clipboard rejects", async () => {
    Object.assign(navigator, { clipboard: { writeText: vi.fn().mockRejectedValue(new Error("NotAllowedError")) } });
    vi.stubGlobal("isSecureContext", true);
    document.execCommand = vi.fn().mockReturnValue(true);

    await expect(writeClipboard("retry")).resolves.toBe(true);
    expect(document.execCommand).toHaveBeenCalledWith("copy");
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

    it("selects the textarea inside an open modal dialog", async () => {
      const dialog = document.body.appendChild(document.createElement("dialog"));
      dialog.setAttribute("open", "");
      let parent: Element | null = null;
      document.execCommand = vi.fn(() => {
        parent = document.querySelector("textarea")?.parentElement ?? null;
        return true;
      });

      await expect(writeClipboard("in dialog")).resolves.toBe(true);
      expect(parent).toBe(dialog);
      dialog.remove();
    });

    it("reports failure when execCommand fails", async () => {
      document.execCommand = vi.fn().mockReturnValue(false);

      await expect(writeClipboard("fallback text")).resolves.toBe(false);
    });
  });
});
