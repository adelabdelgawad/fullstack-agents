"""UserPromptSubmit: a slash command typed with the Arabic keyboard layout is stopped with the command it meant."""
import json
import sys

ARABIC_KEYS = dict(zip("ضصثقفغعهخحجدشسيبلاتنمكطئءؤرىةوزظذ", "qwertyuiop[]asdfghjkl;'zxcvnm,./`", strict=True))
COMMANDS = {"/copy", "/clear", "/compact", "/plugin", "/model", "/resume", "/exit", "/reload-plugins", "/status",
            "/usage", "/context", "/cost", "/help", "/config", "/agents", "/mcp", "/hooks", "/memory", "/init",
            "/rewind", "/export", "/doctor", "/reload-skills", "/login", "/logout", "/permissions"}


def decode(prompt):
    """The slash command an Arabic-layout prompt was typed as, or None."""
    token = prompt.strip()
    if not token or " " in token or not all(c in ARABIC_KEYS or c == "-" for c in token):
        return None
    latin = "".join(ARABIC_KEYS.get(c, c) for c in token)
    return latin if latin in COMMANDS else None


def main():
    try:
        hook = json.load(sys.stdin)
    except ValueError:
        return
    command = decode(hook.get("prompt") or "")
    if command:
        print(json.dumps({"decision": "block", "reason": f"Arabic keyboard layout: \"{hook['prompt'].strip()}\" is "
                                                          f"{command}. Switch the layout and send {command}."}))


if __name__ == "__main__":
    main()
