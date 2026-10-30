"""Claude runs only through the user's `cc` shell alias; scripts never see aliases, so it is resolved explicitly."""
import os
import re
import shlex
import shutil
import subprocess
import sys

ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")

HINT = ("Claude is launched through the `cc` alias, which is not defined. Ask the user to add it to ~/.bashrc "
        "and open a new shell:  alias cc='claude --dangerously-skip-permissions'")


class MissingAlias(OSError):
    """Like a missing executable, an absent alias is an environment failure callers already handle."""


def argv():
    """The alias expansion as argv; `/usr/bin/cc` is the C compiler and is never a fallback."""
    try:
        shown = subprocess.run(["bash", "-ic", "alias cc"], check=False, stdin=subprocess.DEVNULL,
                               capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.TimeoutExpired) as error:
        raise MissingAlias(f"{HINT} ({error})") from error
    match = re.fullmatch(r"alias cc='(.*)'", shown, re.DOTALL)
    try:
        words = shlex.split(match[1].replace("'\\''", "'")) if match else []
    except ValueError:
        words = []
    assignments = []
    while words and ASSIGNMENT.match(words[0]):
        name, value = words.pop(0).split("=", 1)
        assignments.append(f"{name}={os.path.expanduser(value)}")
    if not words or shutil.which(words[0]) is None:
        raise MissingAlias(HINT)
    return ["env", *assignments, *words] if assignments else words


if __name__ == "__main__":
    try:
        print(shlex.join(argv()))
    except MissingAlias as error:
        print(error, file=sys.stderr)
        raise SystemExit(2)
