import { useEffect } from "react";
import { cardOfSession, sessionOf } from "../lib/cards";
import { copyText } from "../lib/clipboard";
import { esc } from "../lib/format";
import { store } from "../store";
import { launcherOf, ownAgents, runFacts, shellFacts } from "../panel/RunCards";
import {
  diffHtml,
  dismiss,
  dismissButton,
  enc,
  isDone,
  keepScroll,
  LIVE,
  notDismissed,
  recentRuns,
  stc,
} from "../panel/panelLib";

interface OutState {
  sid: string;
  id: string;
  view: string;
  file: string | null;
  text: string | null;
}
let out: OutState | null = null,
  outTimer: ReturnType<typeof setInterval> | null = null;
const el = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;

function outItems(): any[] {
  if (!out) return [];
  const card = cardOfSession(out.sid, store.get().state);
  const runs = recentRuns(card, out.sid).map((r: any) => ({
    id: r.id,
    label: `run · ${r.unit || r.id}`,
    state: LIVE(r) ? "running" : r.state,
    run: r,
  }));
  return [...runs, ...ownAgents(card || ({ now: [], runs: [] } as any)).filter((a) => a.sid === out!.sid)].filter(
    notDismissed,
  );
}

function outInfo(cur: any): string {
  if (!out || !cur) return "";
  const card = cardOfSession(out.sid, store.get().state),
    bar = isDone(cur) ? `<div class="ls-actions">${dismissButton(cur)}</div>` : "";
  const view = (v: string) =>
    `<button data-view="${v}" aria-pressed="${out!.view === v}">${v === "changes" ? "Git changes" : "Console"}</button>`;
  if (cur.run)
    return (
      runFacts(cur.run, card) +
      bar +
      (cur.run.root ? `<div class="seg" role="group" aria-label="Show">${view("console")}${view("changes")}</div>` : "")
    );
  return (cur.shell ? shellFacts({ ...cur, sid: out.sid }, card) : "") + bar;
}

function wireOutInfo(box: HTMLElement, info: string): void {
  const opened = new Set(
    [...box.querySelectorAll("details")]
      .filter((detail) => detail.open)
      .map((detail) => detail.querySelector("summary")?.textContent),
  );
  keepScroll(box, () => {
    box.innerHTML = info;
    box.querySelectorAll("details").forEach((detail) => {
      if (opened.has(detail.querySelector("summary")?.textContent)) detail.open = true;
    });
  });
  box.dataset.html = info;
  box.querySelectorAll<HTMLElement>("[data-view]").forEach((button) => {
    button.onclick = () => {
      if (!out) return;
      out.view = button.dataset.view || "console";
      out.file = null;
      out.text = null;
      el("out-pre").textContent = "loading…";
      paintOutItems();
      void pollOutput();
    };
  });
  box.querySelectorAll<HTMLElement>("[data-dismiss]").forEach((button) => {
    button.onclick = () => {
      dismiss([button.dataset.dismiss || ""]);
      if (out) out.text = null;
      paintOutItems();
      void pollOutput();
    };
  });
}

function paintOutChooser(items: any[]): void {
  const chooser = el("out-items"),
    list = items
      .map(
        (item) =>
          `<button data-oid="${esc(item.id)}" aria-pressed="${item.id === out!.id}" title="${esc(item.label)}">` +
          `${item.state === "running" ? '<span class="live-dot"></span>' : ""}${esc(item.label || item.id)}</button>`,
      )
      .join("");
  if (chooser.dataset.html === list) return;
  keepScroll(chooser, () => {
    chooser.innerHTML = list;
  });
  chooser.dataset.html = list;
  chooser.querySelectorAll<HTMLElement>("[data-oid]").forEach((button) => {
    button.onclick = () => pickOut(button.dataset.oid || "");
  });
}

function paintOutItems(): void {
  if (!out) return;
  const items = outItems();
  if (!items.some((x) => x.id === out!.id) && items.length) out.id = items[0].id;
  const cur = items.find((x) => x.id === out!.id);
  el("out-title").textContent = `Monitor · ${sessionOf(out.sid, store.get().state)?.name || out.sid}`;
  el("out-meta").textContent = cur?.state || "";
  const box = el("out-info"),
    info = outInfo(cur);
  if (box.dataset.html !== info) wireOutInfo(box, info);
  paintOutChooser(items);
}

function pickOut(id: string): void {
  if (!out) return;
  out.id = id;
  out.file = null;
  out.text = null;
  el("out-pre").textContent = "loading…";
  paintOutItems();
  void pollOutput();
}
async function fetchOutput(url: string, gone: string): Promise<string> {
  const response = await fetch(url, { cache: "no-store" });
  return response.ok ? response.text() : response.status === 404 ? gone : `(error ${response.status})`;
}

function paintFiles(files: any[] | null, cur?: any): void {
  const box = el("out-files");
  if (!files || !out || !cur) {
    if (box.innerHTML) box.innerHTML = "";
    return;
  }
  const allowed = new Set(cur.run.allowed || []),
    inBrief = (f: any) => !allowed.size || allowed.has(f.path);
  const head = files.length
    ? `${files.length} uncommitted file${files.length > 1 ? "s" : ""} in ${cur.run.root}` +
      `${allowed.size ? ` · ${files.filter(inBrief).length} in the brief's allowed paths` : ""}`
    : `No uncommitted changes in ${cur.run.root} yet.`;
  const html =
    `<div class="s">${esc(head)}</div><div class="flist" role="group" aria-label="Changed files">` +
    files
      .map(
        (file) =>
          `<button data-file="${esc(file.path)}" aria-pressed="${file.path === out!.file}" ` +
          `title="${esc(inBrief(file) ? file.path : `${file.path} — outside the brief's allowed paths`)}">` +
          `<span class="st st-${esc(stc(file.status))}">${esc(file.status)}</span>` +
          `<span class="fp">${esc(file.path)}</span>` +
          `${inBrief(file) ? "" : '<span class="pill bad">outside brief</span>'}</button>`,
      )
      .join("") +
    `</div>`;
  if (box.dataset.html === html) return;
  keepScroll(box, () => {
    box.innerHTML = html;
  });
  box.dataset.html = html;
  box.querySelectorAll<HTMLElement>("[data-file]").forEach(
    (b) =>
      (b.onclick = () => {
        if (!out) return;
        out.file = b.dataset.file || null;
        out.text = null;
        el("out-pre").textContent = "loading…";
        void pollOutput();
      }),
  );
}

async function changesText(want: OutState, cur: any): Promise<string> {
  const key = enc(cur.run.root),
    response = await fetch(`/api/files?key=${key}&ref=WORKTREE`, { cache: "no-store" });
  if (!response.ok) {
    paintFiles(null);
    return response.status === 404 ? `${cur.run.root} is not a known worktree any more.` : `(error ${response.status})`;
  }
  const files = await response.json();
  if (out?.id === want.id && out.view === "changes") paintFiles(files, cur);
  if (!want.file) return files.length ? "Select a file to see its diff." : "";
  if (!files.some((f: any) => f.path === want.file)) return `${want.file} no longer has uncommitted changes.`;
  return fetchOutput(`/api/diff?key=${key}&ref=WORKTREE&path=${enc(want.file)}`, "(no diff for this file)");
}

async function outText(want: OutState, cur: any): Promise<string> {
  if (cur?.run && want.view === "changes" && cur.run.root) return changesText(want, cur);
  paintFiles(null);
  const runLog = (id: string) => fetchOutput(`/api/log?id=${enc(id)}&full=1`, "(no log for this run)");
  if (cur?.run) {
    const log = (await runLog(cur.id)) || "(the run has not written to its log yet)",
      shell = launcherOf(cur.run, cardOfSession(want.sid, store.get().state));
    if (!shell) return log;
    const tail = await fetchOutput(`/api/output?sid=${enc(shell.sid)}&id=${enc(shell.id)}`, "");
    return /\S/.test(tail) && tail !== "(no output yet)"
      ? `${log}\n\n──── launcher shell ${shell.id} · ${shell.state} ────\n${tail}`
      : log;
  }
  return fetchOutput(`/api/output?sid=${enc(want.sid)}&id=${enc(want.id)}`, "(this item is no longer listed)");
}

async function pollOutput(): Promise<void> {
  if (!out || document.hidden) return;
  const want = { ...out },
    cur = outItems().find((x) => x.id === want.id);
  try {
    const text = await outText(want, cur);
    if (
      !out ||
      out.sid !== want.sid ||
      out.id !== want.id ||
      out.view !== want.view ||
      out.file !== want.file ||
      text === out.text
    )
      return;
    const pre = el<HTMLPreElement>("out-pre"),
      atEnd = out.text === null || pre.scrollHeight - pre.scrollTop - pre.clientHeight < 40;
    out.text = text;
    const diff = want.view === "changes" && want.file && /^diff --git /m.test(text);
    pre.classList.toggle("diff", Boolean(diff));
    if (diff) pre.innerHTML = diffHtml(text);
    else pre.textContent = text || "(no output yet)";
    if (atEnd) pre.scrollTop = pre.scrollHeight;
  } catch {}
}

export function openAgent(sid: string, id: string, view = "console"): void {
  out = { sid, id, view, file: null, text: null };
  el("out-pre").textContent = "loading…";
  paintOutItems();
  el<HTMLDialogElement>("out").showModal();
  void pollOutput();
  if (outTimer) clearInterval(outTimer);
  outTimer = setInterval(() => {
    if (out) {
      paintOutItems();
      void pollOutput();
    }
  }, 3000);
}
export function isOutOpen(): boolean {
  return Boolean(document.getElementById("out") && el<HTMLDialogElement>("out").open);
}

export function OutDialog() {
  useEffect(() => {
    const dialog = el<HTMLDialogElement>("out"),
      close = () => {
        out = null;
        if (outTimer) clearInterval(outTimer);
        outTimer = null;
      };
    dialog.addEventListener("close", close);
    el<HTMLButtonElement>("out-close").onclick = () => dialog.close();
    el<HTMLButtonElement>("out-copy").onclick = () => {
      const button = el<HTMLButtonElement>("out-copy"),
        done = (label: string) => {
          button.textContent = label;
          setTimeout(() => {
            button.textContent = "Copy";
          }, 1500);
        };
      copyText(el("out-pre").textContent || "").then(
        () => done("Copied"),
        () => done("Copy failed"),
      );
    };
    return () => {
      close();
      dialog.removeEventListener("close", close);
    };
  }, []);
  return (
    <dialog id="out" aria-labelledby="out-title">
      <div className="oh">
        <h3 id="out-title"></h3>
        <span className="s" id="out-meta"></span>
        <button className="action-button" id="out-copy" style={{ marginLeft: 0 }}>
          Copy
        </button>
        <button className="action-button" id="out-close" style={{ marginLeft: 0 }}>
          Close
        </button>
      </div>
      <div className="items" id="out-items" role="group" aria-label="Choose output"></div>
      <div id="out-info"></div>
      <div id="out-files"></div>
      <pre id="out-pre" tabIndex={0} aria-label="Console output"></pre>
    </dialog>
  );
}
