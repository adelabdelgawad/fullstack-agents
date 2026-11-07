"""Graphify probe (P4): build a code-only graph on a clone of the export and score affected/query output per task."""
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import rung0

TIMEOUT_S = 600
_AFFECTED = re.compile(r"\s(\S+\.\w+):L?(\d+)")
_QUERY = re.compile(r"\[src=(\S+) loc=L(\d+)")


def tree(clone):
    return subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=clone, capture_output=True, text=True,
                          check=True).stdout.strip()


def graphify(binary, env, clone, *args, timeout=120):
    start = time.perf_counter()
    run = subprocess.run([str(binary), *args], cwd=clone, env=env, capture_output=True, text=True, timeout=timeout,
                         stdin=subprocess.DEVNULL, check=False)
    return run, round(time.perf_counter() - start, 2)


def parse(text, clone):
    hits = set()
    for pattern in (_AFFECTED, _QUERY):
        for path, line in pattern.findall(text):
            rel = path[len(str(clone)) + 1:] if path.startswith(str(clone) + "/") else path
            hits.add((rel, int(line)))
    return hits


def missed_by(name):
    return {r["id"]: set(r["missed"]) for r in json.loads((HERE / name).read_text())["results"]}


def arm(task, binary, env, clone, rg, prior):
    hits, outputs = set(), []
    for seed in task["seeds"]:
        for args in (["affected", seed, "--depth", "2"], ["query", seed, "--budget", "2000"]):
            run, seconds = graphify(binary, env, clone, *args)
            outputs.append({"args": args, "rc": run.returncode, "seconds": seconds, "lines": len(run.stdout.splitlines())})
            hits |= parse(run.stdout, clone)
    alone = rung0.score(task, hits)
    union = rung0.score(task, hits | rung0.rg_hits(rg, clone, task["seeds"]))
    recovered = sorted(prior.get(task["id"], set()) - set(alone["missed"]))
    return {"id": task["id"], "graphify_only": alone, "with_rung0": union, "recovered": recovered, "runs": outputs}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("clone", help="a git clone of the export; Graphify never sees the export itself")
    parser.add_argument("--graphify", required=True)
    parser.add_argument("--rg", required=True)
    parser.add_argument("--home", required=True)
    parser.add_argument("--out", required=True, help="GRAPHIFY_OUT, outside the clone")
    args = parser.parse_args()
    spec = json.loads((HERE / "tasks.json").read_text())
    clone = Path(args.clone).resolve()
    if tree(clone) != spec["corpus"]["tree"]:
        sys.exit("clone tree differs from tasks.json")
    env = {"PATH": f"{Path(args.graphify).parent}:/usr/bin:/bin", "HOME": args.home, "GRAPHIFY_OUT": args.out}
    report = {"arm": "graphify", "tree": spec["corpus"]["tree"], "env_keys": sorted(env)}
    try:
        build, seconds = graphify(args.graphify, env, clone, "extract", ".", "--code-only", timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired:
        print(json.dumps({**report, "status": "skipped", "reason": f"build exceeded {TIMEOUT_S} s"}, indent=2))
        return
    report["build"] = {"rc": build.returncode, "seconds": seconds, "stderr_tail": build.stderr.splitlines()[-5:]}
    if build.returncode != 0:
        print(json.dumps({**report, "status": "skipped", "reason": "build failed"}, indent=2))
        return
    prior = {tid: missed_by("rung0-results.json")[tid] & ids for tid, ids in missed_by("map-arm-results.json").items()}
    report["results"] = [arm(task, args.graphify, env, clone, args.rg, prior) for task in spec["tasks"]]
    report["tree_after"] = tree(clone)
    report["status"] = "recovered" if any(r["recovered"] for r in report["results"][:3]) else "no_recovery"
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
