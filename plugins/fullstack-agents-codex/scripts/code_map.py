"""Code map: a per-worktree, content-hashed index of framework facts, refreshed lazily, that falls back instead of failing."""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import team_conf

FORMAT = 1
RACY_S = 2.0
LOCK_TIMEOUT_S = 5.0
MAX_BYTES = 1_000_000
DEFAULT_BUDGET = 40
EXTENSIONS = {".py", ".rs", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".sql", ".yaml", ".yml", ".toml", ".json",
              ".sh", ".example", ".env"}
PROVIDER = "provider"
PREFIX = "prefix"
ROUTE = "route"
ANY = "*"


class CodeMapError(Exception):
    """Any condition that sends the caller back to the search ladder."""


def _git(args, cwd):
    try:
        result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=30,
                                stdin=subprocess.DEVNULL, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise CodeMapError(f"git unavailable: {error}") from error
    if result.returncode != 0:
        raise CodeMapError(f"git {args[0]} failed: {result.stderr.strip()}")
    return result.stdout


def toplevel(cwd):
    return _git(["rev-parse", "--show-toplevel"], cwd).strip()


def head(root):
    try:
        return _git(["rev-parse", "--verify", "-q", "HEAD"], root).strip()
    except CodeMapError:
        return None


def enabled(root):
    try:
        return team_conf.get(root, "code_map") is True
    except team_conf.ConfError as error:
        raise CodeMapError(f"invalid fsa-team.conf: {error}") from error


def store_dir(root):
    base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return base / "fullstack-agents" / "code-map" / hashlib.sha1(root.encode()).hexdigest()


def eligible(path):
    name = path.rsplit("/", 1)[-1]
    return Path(name).suffix in EXTENSIONS or name.startswith(".env")


def list_paths(root):
    out = _git(["ls-files", "-z", "-co", "--exclude-standard"], root)
    return sorted({p for p in out.split("\0") if p and eligible(p)})


def _load(store, version):
    try:
        index = json.loads((store / "index.json").read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(index, dict) or index.get("format") != FORMAT or index.get("extractor") != version:
        return None
    return index if index.get("complete") is True and isinstance(index.get("files"), dict) else None


def _save(store, index):
    tmp = store / f"index.json.{os.getpid()}.tmp"
    tmp.write_text(json.dumps(index, separators=(",", ":")))
    os.replace(tmp, store / "index.json")


@contextlib.contextmanager
def _lock(store):
    store.mkdir(parents=True, exist_ok=True)
    with open(store / "lock", "w") as handle:
        deadline = time.monotonic() + LOCK_TIMEOUT_S
        while True:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise CodeMapError("code-map lock busy") from None
                time.sleep(0.05)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _read(full):
    data = full.read_bytes()
    if len(data) > MAX_BYTES or b"\0" in data[:8192]:
        return data, None
    return data, data.decode("utf-8", errors="replace")


def _entry(root, path, old, written_at, extractor, stats):
    full = Path(root) / path
    st = full.stat()
    racy = old is None or st.st_mtime_ns / 1e9 >= written_at - RACY_S
    if old and not racy and old["size"] == st.st_size and old["mtime_ns"] == st.st_mtime_ns:
        stats["reused"] += 1
        return old
    data, text = _read(full)
    digest = hashlib.sha256(data).hexdigest()
    if old and old["sha256"] == digest:
        stats["rehashed"] += 1
        return {**old, "size": st.st_size, "mtime_ns": st.st_mtime_ns}
    stats["scanned"] += 1
    facts = extractor.extract(path, text) if text is not None else []
    return {"size": st.st_size, "mtime_ns": st.st_mtime_ns, "sha256": digest, "facts": facts}


def refresh(root, extractor):
    """Bring the store up to date with the working tree (tracked + untracked), rescanning only changed files."""
    store = store_dir(root)
    with _lock(store):
        old = _load(store, extractor.VERSION)
        old_files = old["files"] if old else {}
        written_at = old["written_at"] if old else 0.0
        stats = {"scanned": 0, "rehashed": 0, "reused": 0, "dropped": 0, "rebuilt": old is None}
        started = time.time()
        files = {}
        for path in list_paths(root):
            if (Path(root) / path).is_symlink():
                continue
            try:
                files[path] = _entry(root, path, old_files.get(path), written_at, extractor, stats)
            except OSError:
                continue
        stats["dropped"] = len(set(old_files) - set(files))
        index = {"format": FORMAT, "extractor": extractor.VERSION, "head": head(root), "written_at": started,
                 "complete": True, "files": files}
        _save(store, index)
    return index, stats


def _compatible(consumer, provider):
    return ANY in (consumer["verb"], provider["verb"]) or consumer["verb"] == provider["verb"]


def _pairs(group):
    providers = [f for f in group if f["role"] == PROVIDER]
    consumers = [f for f in group if f["role"] != PROVIDER]
    if not consumers:
        return [(None, provider) for provider in providers]
    joined, unjoined = [], []
    for consumer in consumers:
        matched = [p for p in providers if _compatible(consumer, p)]
        joined.extend((consumer, p) for p in matched)
        unjoined.extend([] if matched else [(consumer, None)])
    return joined + unjoined


def _strip(key, prefixes):
    stripped = True
    while stripped:
        stripped = False
        for prefix in prefixes:
            if key.startswith(prefix + "/"):
                key, stripped = key[len(prefix):], True
                break
    return key


def _groups(index):
    facts = [(path, *fact) for path, entry in sorted(index["files"].items()) for fact in entry["facts"]]
    prefixes = sorted({f[2] for f in facts if f[1] == PREFIX and f[2] != "/"}, key=len, reverse=True)
    groups = {}
    for path, kind, key, line, role, pattern, *verb in facts:
        if kind == PREFIX:
            continue
        join = _strip(key, prefixes) if kind == ROUTE else key
        groups.setdefault((kind, join), []).append(
            {"path": path, "line": line, "role": role, "pattern": pattern, "verb": verb[0] if verb else ANY, "raw": key})
    return groups


def _loc(fact):
    return f"{fact['path']}:{fact['line']}" if fact else ""


def _row(kind, key, consumer, provider):
    verb = (consumer or provider)["verb"]
    relation = consumer["role"] if consumer else "defined"
    return {"kind": kind, "key": key, "from": _loc(consumer), "to": _loc(provider),
            "relation": relation if verb == ANY else f"{relation} {verb}",
            "provenance": "+".join(sorted({f["pattern"] for f in (consumer, provider) if f})), "fresh": "yes"}


def match(index, seeds, budget=DEFAULT_BUDGET):
    """Rows for every group whose key contains a seed, each group capped so one broad key cannot starve the rest."""
    groups = {gk: g for gk, g in _groups(index).items()
              if any(seed in gk[1] or any(seed in f["raw"] for f in g) for seed in seeds)}
    cap = max(4, budget // max(len(groups), 1))
    first, rest = [], []
    for (kind, key), group in sorted(groups.items()):
        pairs = [(kind, key, consumer, provider) for consumer, provider in _pairs(group)]
        first, rest = first + pairs[:cap], rest + pairs[cap:]
    ordered = first + rest
    return [_row(*item) for item in ordered[:budget]], len(ordered) > budget


def _default_extractor():
    import code_map_joins
    return code_map_joins


def query(cwd, seeds, budget=DEFAULT_BUDGET, extractor=None):
    """Status `off` (key not on; nothing touched), `ok`, or `fallback` with a reason: use the search ladder."""
    try:
        root = toplevel(cwd)
        if not enabled(root):
            return {"status": "off", "rows": []}
        index, stats = refresh(root, extractor or _default_extractor())
        rows, truncated = match(index, seeds, budget)
    except Exception as error:  # noqa: BLE001 - the map must never block; every failure means use the ladder
        return {"status": "fallback", "reason": f"{type(error).__name__}: {error}", "rows": []}
    if not any(row["from"] and row["to"] for row in rows):
        return {"status": "fallback", "reason": f"no joined row among {len(rows)}", "rows": rows, "stats": stats}
    return {"status": "ok", "rows": rows, "stats": stats, "truncated": truncated}


def _cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def _print_table(result):
    fields = ("kind", "key", "from", "to", "relation", "provenance", "fresh")
    print("| " + " | ".join(fields) + " |")
    print("|" + "---|" * len(fields))
    for row in result["rows"]:
        print("| " + " | ".join(_cell(row[f]) for f in fields) + " |")


def main(argv):
    parser = argparse.ArgumentParser(prog="code_map")
    parser.add_argument("--cwd", default=".")
    parser.add_argument("--seed", action="append", required=True)
    parser.add_argument("--budget", type=int, default=DEFAULT_BUDGET)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = query(args.cwd, args.seed, args.budget)
    if args.json:
        print(json.dumps(result, indent=2))
    elif result["status"] == "off":
        print("code_map is off (set code_map=on in .claude/fsa-team.conf)")
    else:
        if result["status"] == "fallback":
            print(f"FALLBACK: {result['reason']} — use rg / bounded-extractor", file=sys.stderr)
        _print_table(result)
    return 3 if result["status"] == "fallback" else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
