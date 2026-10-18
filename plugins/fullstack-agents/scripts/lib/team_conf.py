"""One parser for <repo>/.claude/fsa-team.conf: key=value lines, never evaluated as shell."""
import os
import re
import sys
from pathlib import Path


class ConfError(Exception):
    """An invalid value for a known key; str(exc) is '<key>: <reason>'."""

    def __init__(self, key, reason):
        self.key = key
        self.reason = reason
        super().__init__(f"{key}: {reason}")


def _expand_home(value):
    if value == "~":
        return os.environ.get("HOME", "~")
    if value.startswith("~/"):
        return os.environ.get("HOME", "~") + "/" + value[2:]
    return value


def _path(key, value):
    return _expand_home(value)


def _path_list(key, value):
    return [_expand_home(item) for item in value.split(":") if item != ""]


def _posint(key, value):
    try:
        number = int(value)
    except ValueError:
        number = 0
    if number <= 0:
        raise ConfError(key, "must be a positive integer")
    return number


def _list(key, value):
    return value.split()


def _onoff(key, value):
    if value not in ("on", "off"):
        raise ConfError(key, "must be 'on' or 'off'")
    return value == "on"


def _slug(key, value):
    if not re.fullmatch(r"[a-z0-9-]+", value):
        raise ConfError(key, "must match [a-z0-9-]+")
    return value


def _nonempty(key, value):
    if value == "":
        raise ConfError(key, "must not be empty")
    return value


# Known keys and the typed value each converts to; unknown keys are warned about, not fatal.
SCHEMA = {
    "runs_dir": _path,
    "legacy_runs_dirs": _path_list,
    "codex_add_dirs": _path_list,
    "edit_budget": _posint,
    "read_range_max": _posint,
    "gated_extensions": _list,
    "carve_outs": _list,
    "scan_gate": _onoff,
    "policy_profile": _slug,
    "monitor_model": _nonempty,
    "deploy_regex": _nonempty,
}


def _read_raw(repo):
    """Last `key=value` line per key, verbatim value, comments and blank lines dropped."""
    try:
        lines = (Path(repo) / ".claude" / "fsa-team.conf").read_text().splitlines()
    except OSError:
        return {}
    raw = {}
    for line in lines:
        if line.strip() == "" or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if not sep:
            continue
        raw[key] = value
    return raw


def _parse(repo):
    raw = _read_raw(repo)
    for key in raw:
        if key not in SCHEMA:
            print(f"warning: unknown fsa-team.conf key: {key}", file=sys.stderr)
    return raw


def load(repo):
    """Typed values for every known key present in the conf; raises ConfError on the first invalid one."""
    raw = _parse(repo)
    return {key: SCHEMA[key](key, value) for key, value in raw.items() if key in SCHEMA}


def get(repo, key):
    """The typed value of `key`, or None if absent; raises ConfError if its value is invalid."""
    raw = _parse(repo)
    if key not in raw or key not in SCHEMA:
        return None
    return SCHEMA[key](key, raw[key])


def _print_value(value):
    if isinstance(value, list):
        for item in value:
            print(item)
    elif isinstance(value, bool):
        print("on" if value else "off")
    else:
        print(value)


def _cmd_get(repo, key):
    try:
        value = get(repo, key)
    except ConfError as exc:
        print(f"invalid fsa-team.conf: {exc}", file=sys.stderr)
        return 3
    if value is not None:
        _print_value(value)
    return 0


def _cmd_check(repo):
    problems = []
    for key, value in _parse(repo).items():
        if key not in SCHEMA:
            continue
        try:
            SCHEMA[key](key, value)
        except ConfError as exc:
            problems.append(str(exc))
    for problem in problems:
        print(f"invalid fsa-team.conf: {problem}")
    return 3 if problems else 0


def _cmd_get_many(repo, keys):
    """One parse for several keys (hooks call this once instead of once per key). Output, per key in order:
    "ok" or "invalid", NUL, the value (list items on their own lines), NUL. The file is re-read on every call."""
    raw = _parse(repo)
    for key in keys:
        status, text = "ok", ""
        if key in raw and key in SCHEMA:
            try:
                value = SCHEMA[key](key, raw[key])
                text = "\n".join(value) if isinstance(value, list) else \
                    ("on" if value else "off") if isinstance(value, bool) else str(value)
            except ConfError as exc:
                status = "invalid"
                print(f"invalid fsa-team.conf: {exc}", file=sys.stderr)
        sys.stdout.write(f"{status}\0{text}\0")
    return 0


def main(argv):
    if len(argv) == 3 and argv[0] == "get":
        return _cmd_get(argv[1], argv[2])
    if len(argv) >= 3 and argv[0] == "get-many":
        return _cmd_get_many(argv[1], argv[2:])
    if len(argv) == 2 and argv[0] == "check":
        return _cmd_check(argv[1])
    print("usage: team_conf.py get <repo> <key> | get-many <repo> <key>... | check <repo>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
