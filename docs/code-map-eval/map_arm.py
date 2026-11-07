"""Rung-0 + map arm: score rung-0 hits plus code-map row sites per task, and time index builds on a clone."""
import argparse
import json
import os
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "plugins/fullstack-agents/scripts/lib"))

import code_map
import code_map_joins
import rung0

BUDGET = 40


def sites(rows):
    out = set()
    for row in rows:
        for loc in (row["from"], row["to"]):
            if loc:
                path, line = loc.rsplit(":", 1)
                out.add((path, int(line)))
    return out


def arm(task, index, rg, corpus):
    rows, truncated = code_map.match(index, task["seeds"], BUDGET)
    joined = any(r["from"] and r["to"] for r in rows)
    map_sites = sites(rows) if joined else set()
    hits = rung0.rg_hits(rg, corpus, task["seeds"]) | map_sites
    return {"id": task["id"], "rows": len(rows), "joined": joined, "truncated": truncated,
            **rung0.score(task, hits), "map_only": rung0.score(task, map_sites) if map_sites else None}


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, stdin=subprocess.DEVNULL,
                   env={**os.environ, "GIT_AUTHOR_NAME": "e", "GIT_AUTHOR_EMAIL": "e@e", "GIT_COMMITTER_NAME": "e",
                        "GIT_COMMITTER_EMAIL": "e@e"})


def timed_refresh(root):
    start = time.perf_counter()
    _, stats = code_map.refresh(str(root), code_map_joins)
    return round(time.perf_counter() - start, 3), stats


def make_branch(clone):
    paths = code_map.list_paths(str(clone))
    for path in paths[:300]:
        with open(clone / path, "a") as handle:
            handle.write("\n")
    for path in paths[300:320]:
        (clone / path).unlink()
    for number in range(20):
        (clone / f"added_{number}.py").write_text(f'x = os.getenv("ADDED_{number}")\n')
    git(clone, "checkout", "-q", "-b", "eval-switch")
    git(clone, "add", "-A")
    git(clone, "commit", "-q", "-m", "switch")
    git(clone, "checkout", "-q", "-")


def timings(corpus, work):
    clone = work / "clone"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    git(work, "clone", "-q", str(corpus), str(clone))
    make_branch(clone)
    os.environ["XDG_CACHE_HOME"] = str(work / "cache")
    result = {"cold": timed_refresh(clone)}
    result["noop"] = statistics.median(timed_refresh(clone)[0] for _ in range(3))
    edit = []
    for _ in range(3):
        time.sleep(code_map.RACY_S + 0.1)
        with open(clone / "src/backend/apps/pbx-admin-api/src/router.rs", "a") as handle:
            handle.write("// edit\n")
        edit.append(timed_refresh(clone))
    result["one_edit"] = [statistics.median(e[0] for e in edit), edit[-1][1]]
    time.sleep(code_map.RACY_S + 0.1)
    git(clone, "checkout", "-q", "eval-switch")
    result["branch_switch"] = timed_refresh(clone)
    result["store_bytes"] = (Path(code_map.store_dir(str(clone))) / "index.json").stat().st_size
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus")
    parser.add_argument("--rg", required=True)
    parser.add_argument("--work", required=True, help="scratch directory for the cache and the timing clone")
    args = parser.parse_args()
    spec = json.loads((HERE / "tasks.json").read_text())
    corpus, work = Path(args.corpus).resolve(), Path(args.work).resolve()
    tree = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=corpus, capture_output=True, text=True, check=True)
    if tree.stdout.strip() != spec["corpus"]["tree"]:
        sys.exit("corpus tree differs from tasks.json")
    os.environ["XDG_CACHE_HOME"] = str(work / "score-cache")
    shutil.rmtree(work / "score-cache", ignore_errors=True)
    index, _ = code_map.refresh(str(corpus), code_map_joins)
    results = [arm(task, index, args.rg, corpus) for task in spec["tasks"]]
    print(json.dumps({"arm": "rung0+map", "extractor": code_map_joins.VERSION, "tree": spec["corpus"]["tree"],
                      "budget": BUDGET, "results": results, "timings": timings(corpus, work / "timing")}, indent=2))


if __name__ == "__main__":
    main()
