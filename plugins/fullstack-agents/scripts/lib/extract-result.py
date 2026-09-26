#!/usr/bin/env python3
"""Write the last fenced JSON result of an implementer transcript to the run's result file."""
import json
import re
import sys

REQUIRED = {"summary": str, "files": list, "tests": list, "open_risks": list}
LIMITS = {"summary": 12000, "files": 40, "tests": 10, "open_risks": 5}
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
FENCE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)


def main(log_path: str, out_path: str) -> int:
    with open(log_path, encoding="utf-8", errors="replace") as handle:
        text = ANSI.sub("", handle.read())
    for candidate in reversed(FENCE.findall(text)):
        try:
            result = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if not isinstance(result, dict) or not all(isinstance(result.get(k), t) for k, t in REQUIRED.items()):
            continue
        result = {k: result[k][: LIMITS[k]] for k in REQUIRED}
        with open(out_path, "w", encoding="utf-8") as handle:
            json.dump(result, handle, ensure_ascii=False)
        return 0
    print("no fenced JSON result matching the result schema in the transcript", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
