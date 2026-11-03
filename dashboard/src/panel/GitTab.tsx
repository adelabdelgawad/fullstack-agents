import { useEffect, useState } from "react";
import { ago } from "../lib/format";
import type { Card } from "../lib/types";
import { diffHtml, enc, stc } from "./panelLib";

interface GitFile {
  path: string;
  status: string;
  own?: boolean;
}
interface GitItems {
  dirty: number;
  own?: number;
  recent?: boolean;
  commits: Array<{ sha: string; subject: string; at: number }>;
}
const fresh = () => ({
  sig: "",
  at: 0,
  items: null as GitItems | null,
  open: { unc: true, com: true, other: false },
  item: null as string | null,
  files: null as GitFile[] | null,
  file: null as string | null,
  diff: "",
});
let git = { ...fresh(), hide1: false, hide2: false };
export const resetGit = () => {
  git = { ...fresh(), hide1: git.hide1, hide2: git.hide2 };
};

type Paint = () => void;

async function loadDiff(card: Card, paint: Paint): Promise<void> {
  const { item, file } = git;
  if (!item || !file) return;
  try {
    const text = await (
      await fetch(`/api/diff?key=${enc(card.key)}&ref=${enc(item)}&path=${enc(file)}`, { cache: "no-store" })
    ).text();
    if (git.item === item && git.file === file) {
      git.diff = text;
      paint();
    }
  } catch {}
}

function pickFile(card: Card, path: string, paint: Paint): void {
  git.file = path;
  git.diff = "";
  paint();
  void loadDiff(card, paint);
}

async function loadFiles(card: Card, paint: Paint): Promise<void> {
  const ref = git.item;
  if (!ref) return;
  try {
    git.files = await (await fetch(`/api/files?key=${enc(card.key)}&ref=${enc(ref)}`, { cache: "no-store" })).json();
  } catch {
    return;
  }
  if (git.item !== ref) return;
  if (git.file && !git.files!.some((f) => f.path === git.file)) git.file = null;
  const first = git.files!.find((f) => f.own !== false);
  if (!git.file && first) pickFile(card, first.path, paint);
  else {
    paint();
    if (git.file) void loadDiff(card, paint);
  }
}

function pickItem(card: Card, ref: string, paint: Paint): void {
  git.item = ref;
  git.files = null;
  git.file = null;
  git.diff = "";
  paint();
  void loadFiles(card, paint);
}

function GitChanges({ card, paint }: { card: Card; paint: Paint }) {
  const unc = git.items ? git.items.dirty : Number(card.tree?.dirty || 0),
    commits = git.items?.commits || [];
  return (
    <section className={`gcol g1${git.hide1 ? " hid" : ""}`} id="g1">
      {git.hide1 ? (
        <button
          className="rail"
          data-show="1"
          title="Show changes"
          aria-label="Show changes"
          onClick={() => {
            git.hide1 = false;
            paint();
          }}
        >
          »
        </button>
      ) : (
        <GitChangesBody card={card} paint={paint} unc={unc} commits={commits} />
      )}
    </section>
  );
}

function GitChangesBody({
  card,
  paint,
  unc,
  commits,
}: {
  card: Card;
  paint: Paint;
  unc: number;
  commits: GitItems["commits"];
}) {
  return (
    <>
      <div className="gh">
        <span className="gt">Changes</span>
        <button
          className="action-button"
          data-hide="1"
          title="Hide changes"
          onClick={() => {
            git.hide1 = true;
            paint();
          }}
        >
          Hide «
        </button>
      </div>
      <GitChangesList card={card} paint={paint} unc={unc} commits={commits} />
    </>
  );
}

function GitChangesList({
  card,
  paint,
  unc,
  commits,
}: {
  card: Card;
  paint: Paint;
  unc: number;
  commits: GitItems["commits"];
}) {
  return (
    <div className="gb">
      <button
        className="grp"
        data-g="unc"
        onClick={() => {
          git.open.unc = !git.open.unc;
          paint();
        }}
      >
        {git.open.unc ? "▾" : "▸"} Uncommitted changes <span className="badge">{unc}</span>
      </button>
      {git.open.unc ? <Uncommitted card={card} paint={paint} count={unc} /> : null}
      <button
        className="grp"
        data-g="com"
        onClick={() => {
          git.open.com = !git.open.com;
          paint();
        }}
      >
        {git.open.com ? "▾" : "▸"} {git.items?.recent ? "This task's commits" : "Commits ahead of main"}{" "}
        <span className="badge">{commits.length}</span>
      </button>
      {git.open.com ? <Commits card={card} paint={paint} commits={commits} /> : null}
    </div>
  );
}

function Uncommitted({ card, paint, count }: { card: Card; paint: Paint; count: number }) {
  if (!count) return <div className="hint">Working tree is clean.</div>;
  return (
    <button
      className={`gi${git.item === "WORKTREE" ? " on" : ""}`}
      data-ref="WORKTREE"
      onClick={() => pickItem(card, "WORKTREE", paint)}
    >
      <b>Working tree</b>
      <span className="sub">
        {count} file{count === 1 ? "" : "s"} · not committed yet
        {git.items && typeof git.items.own === "number"
          ? ` · ${git.items.own} from this task, ${count - git.items.own} other`
          : ""}
      </span>
    </button>
  );
}

function Commits({ card, paint, commits }: { card: Card; paint: Paint; commits: GitItems["commits"] }) {
  if (!git.items) return <div className="hint">Loading…</div>;
  if (!commits.length)
    return <div className="hint">{git.items.recent ? "No commits from this task." : "No commits."}</div>;
  return commits.map((commit) => (
    <button
      className={`gi${git.item === commit.sha ? " on" : ""}`}
      data-ref={commit.sha}
      onClick={() => pickItem(card, commit.sha, paint)}
      key={commit.sha}
    >
      <span className="sha">{commit.sha}</span>
      {commit.subject}
      <span className="sub">{ago(commit.at)} ago</span>
    </button>
  ));
}

function fileRow(card: Card, file: GitFile, paint: Paint) {
  const index = file.path.lastIndexOf("/");
  return (
    <button
      className={`gf${git.file === file.path ? " on" : ""}`}
      data-file={file.path}
      onClick={() => pickFile(card, file.path, paint)}
      key={file.path}
    >
      <span className={`st st-${stc(file.status)}`}>{file.status}</span>
      <span className="fn">{file.path.slice(index + 1)}</span>
      <span className="fd">{index < 0 ? "" : file.path.slice(0, index)}</span>
    </button>
  );
}

function GitFiles({ card, paint }: { card: Card; paint: Paint }) {
  const scoped = git.files?.some((file) => "own" in file),
    mine = scoped ? git.files?.filter((file) => file.own) : git.files,
    rest = scoped ? git.files?.filter((file) => !file.own) : [];
  return (
    <section className={`gcol g2${git.hide2 ? " hid" : ""}`} id="g2">
      {git.hide2 ? (
        <button
          className="rail"
          data-show="2"
          title="Show files"
          aria-label="Show files"
          onClick={() => {
            git.hide2 = false;
            paint();
          }}
        >
          »
        </button>
      ) : (
        <GitFilesBody card={card} paint={paint} mine={mine} rest={rest} />
      )}
    </section>
  );
}

function GitFilesBody({
  card,
  paint,
  mine,
  rest,
}: {
  card: Card;
  paint: Paint;
  mine?: GitFile[] | null;
  rest?: GitFile[];
}) {
  const rows = (files: GitFile[]) => files.map((file) => fileRow(card, file, paint));
  return (
    <>
      <div className="gh">
        <span className="gt">Files</span>
        <button
          className="action-button"
          data-hide="2"
          title="Hide files"
          onClick={() => {
            git.hide2 = true;
            paint();
          }}
        >
          Hide «
        </button>
      </div>
      <GitFileList mine={mine} rest={rest} rows={rows} paint={paint} />
    </>
  );
}

function GitFileList({
  mine,
  rest,
  rows,
  paint,
}: {
  mine?: GitFile[] | null;
  rest?: GitFile[];
  rows: (files: GitFile[]) => React.ReactNode;
  paint: Paint;
}) {
  if (!git.item)
    return (
      <div className="gb">
        <div className="hint">Pick a change on the left.</div>
      </div>
    );
  if (!git.files)
    return (
      <div className="gb">
        <div className="hint">Loading…</div>
      </div>
    );
  if (!git.files.length)
    return (
      <div className="gb">
        <div className="hint">No files.</div>
      </div>
    );
  return (
    <div className="gb">
      {mine?.length ? rows(mine) : <div className="hint">No uncommitted files from this task.</div>}
      {rest?.length ? (
        <>
          <button
            className="grp"
            data-g="other"
            onClick={() => {
              git.open.other = !git.open.other;
              paint();
            }}
          >
            {git.open.other ? "▾" : "▸"} Not from this task <span className="badge">{rest.length}</span>
          </button>
          {git.open.other ? rows(rest) : null}
        </>
      ) : null}
    </div>
  );
}

function GitDiff() {
  return (
    <section className="gcol g3" id="g3">
      <div className="gh">
        <span className="gt">{git.file || "Changes"}</span>
      </div>
      <div className="gb">
        {git.file ? (
          <pre className="diff" dangerouslySetInnerHTML={{ __html: diffHtml(git.diff) }}></pre>
        ) : (
          <div className="hint">Pick a file to see its changes.</div>
        )}
      </div>
    </section>
  );
}

export function GitTab({ card }: { card: Card }) {
  const [, repaint] = useState(0),
    paint = () => repaint((n) => n + 1);
  useEffect(() => {
    let active = true;
    void (async () => {
      const tree: any = card.tree,
        sig = tree ? `${tree.head}|${tree.dirty}|${tree.edited}` : "";
      if (git.items && git.sig === sig && Date.now() - git.at < 15000) return;
      git.sig = sig;
      git.at = Date.now();
      try {
        git.items = await (await fetch(`/api/changes?key=${enc(card.key)}`, { cache: "no-store" })).json();
      } catch {
        return;
      }
      if (!active) return;
      const pick = git.items!.dirty ? "WORKTREE" : git.items!.commits[0]?.sha;
      if (!git.item && pick) pickItem(card, pick, paint);
      else {
        paint();
        if (git.item) void loadFiles(card, paint);
      }
    })();
    return () => {
      active = false;
    };
  }, [card]);
  return (
    <div className="gitview">
      <GitChanges card={card} paint={paint} />
      <GitFiles card={card} paint={paint} />
      <GitDiff />
    </div>
  );
}
