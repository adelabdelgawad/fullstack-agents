"""Rung-0 baseline: score fixed-string rg over each task's frozen seeds against its hand-written answer key."""
import argparse
import json
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

RUNS = 3


def rg_hits(rg, corpus, seeds):
    hits = set()
    for seed in seeds:
        out = subprocess.run([rg, "--sort", "path", "-n", "-F", "--no-heading", "-e", seed, "."], cwd=corpus,
                             stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False).stdout
        for line in out.splitlines():
            path, lineno, _ = line.split(":", 2)
            hits.add((path.removeprefix("./"), int(lineno)))
    return hits


def timed(rg, corpus, seeds):
    samples, hits = [], set()
    for _ in range(RUNS):
        start = time.perf_counter()
        hits = rg_hits(rg, corpus, seeds)
        samples.append(time.perf_counter() - start)
    return hits, statistics.median(samples)


def covered(entry, hits):
    start, end = entry["lines"]
    return any(path == entry["path"] and start <= line <= end for path, line in hits)


def score(task, hits):
    must = [k for k in task["key"] if k["level"] == "must"]
    key_files = {k["path"] for k in task["key"]}
    hit_files = {path for path, _ in hits}
    must_files = {k["path"] for k in must}
    line_hits = [k for k in must if covered(k, hits)]
    return {
        "must_sites": len(must),
        "site_recall": round(len(line_hits) / len(must), 3),
        "file_recall": round(len(must_files & hit_files) / len(must_files), 3),
        "missed": [f"{k['path']}:{k['lines'][0]}-{k['lines'][1]}" for k in must if not covered(k, hits)],
        "hits": len(hits),
        "hit_files": len(hit_files),
        "file_precision": round(len(hit_files & key_files) / len(hit_files), 3) if hit_files else 0.0,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus")
    parser.add_argument("--rg", default=shutil.which("rg") or "rg")
    parser.add_argument("--tasks", default=str(Path(__file__).with_name("tasks.json")))
    args = parser.parse_args()
    spec = json.loads(Path(args.tasks).read_text())
    version = subprocess.run([args.rg, "--version"], capture_output=True, text=True, check=True).stdout.splitlines()[0]
    tree = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=args.corpus, capture_output=True, text=True,
                          check=True).stdout.strip()
    if tree != spec["corpus"]["tree"]:
        sys.exit(f"corpus tree {tree} != frozen {spec['corpus']['tree']}")
    results = []
    for task in spec["tasks"]:
        hits, median_s = timed(args.rg, args.corpus, task["seeds"])
        results.append({"id": task["id"], "median_s": round(median_s, 3), **score(task, hits)})
    print(json.dumps({"rung": 0, "rg": version, "tree": tree, "runs": RUNS, "results": results}, indent=2))


if __name__ == "__main__":
    main()
