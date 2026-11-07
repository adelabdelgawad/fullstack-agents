"""Framework join facts for code_map: HTTP routes, route prefixes, env keys, SQL tables and Celery tasks, via stdlib re."""
import bisect
import hashlib
import re
from pathlib import Path

VERSION = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:12]
PROVIDER = "provider"
TESTS = "tests"
VERBS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS")
SQL_WORDS = {"SET", "LATERAL", "SELECT", "VALUES", "WHERE", "AS", "ON", "IN", "NOT", "NULL", "AND", "OR", "TABLE"}
TS_EXT = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}

_EXPR = re.compile(r"\$\{[^}]*\}")
_PARAM = re.compile(r"^(?:\x00+|\{[^}]*\}|:\w+|\[{1,2}(?:\.\.\.)?\w+\]{1,2}|<[^>]*>)$")
_COMMENT = ("//", "#", "--", "*", "/*")
_TEST_PATH = re.compile(r"(?:^|/)(?:tests?|__tests__)/|(?:^|/)(?:test_[^/]*\.py|conftest\.py|[^/]*_test\.\w+|"
                        r"[^/]*\.(?:test|spec)\.[jt]sx?)$")

_AXUM_ROUTE = re.compile(r"\.route\(\s*\"([^\"]*)\"")
_AXUM_NEST = re.compile(r"\.nest\(\s*\"([^\"]*)\"")
_AXUM_VERB = re.compile(r"(?<![\w])(get|post|put|patch|delete|head|options|any)\s*\(")
_FASTAPI_ROUTE = re.compile(r"@\w+\.(get|post|put|patch|delete|head|options|api_route)\(\s*[rf]?[\"']([^\"']*)[\"']")
_PY_PREFIX = re.compile(r"(?:APIRouter|include_router)\([^)]*?\bprefix\s*=\s*[\"']([^\"']+)[\"']", re.DOTALL)
_PY_CLIENT = re.compile(r"\.(get|post|put|patch|delete)\(\s*f?[\"'](/[^\"'\n]*)[\"']")
_TS_CLIENT = re.compile(r"\b\w+\.(get|post|put|patch|delete)\s*(?:<[^()\n]*?>)?\s*\(\s*([\"'`])([^\"'`\n]*)\2")
_TS_FETCH = re.compile(r"\bfetch\(\s*([\"'`])([^\"'`\n]*)\1([^)]{0,400})")
_TS_METHOD = re.compile(r"\bmethod\s*:\s*[\"'](\w+)[\"']")
_TS_RESOURCE = re.compile(r"\bcreateResourceApi\b[^(]*\(\s*[\"'`]([^\"'`\n]+)[\"'`]")
_TS_PATHVAR = re.compile(r"\b\w*[Pp]ath\s*[:=]\s*[\"'`](/[^\"'`\n]*)[\"'`]")
_TS_PREFIX = re.compile(r"\b(?:BASE_URL|baseURL|baseUrl|API_BASE(?:_URL)?)\s*[:=][^\"'`\n]*[\"'`](/[^\"'`\n]*)[\"'`]")
_NEXT_HANDLER = re.compile(r"export\s+(?:async\s+function|function|const)\s+(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b")
_RUST_ENV = re.compile(r"(?:\benv::var(?:_os)?\(|\bdotenvy::var\(|\b(?:option_)?env!\()\s*\"(\w+)\"")
_PY_ENV = re.compile(r"\bos\.(?:environ(?:\.get)?\s*[\[(]|getenv\()\s*[\"'](\w+)[\"']")
_TS_ENV = re.compile(r"\b(?:process|import\.meta)\.env(?:\.([A-Za-z_]\w*)|\[\s*[\"'](\w+)[\"']\s*\])")
_ENV_LINE = re.compile(r"^\s*(?:export\s+)?([A-Z_][A-Z0-9_]*)\s*=", re.MULTILINE)
_COMPOSE_LINE = re.compile(r"^\s*(?:-\s*)?([A-Z_][A-Z0-9_]*)\s*[:=]", re.MULTILINE)
_SQL_CREATE = re.compile(r"\b(CREATE\s+(?:UNLOGGED\s+)?TABLE|ALTER\s+TABLE)\s+(?:IF\s+(?:NOT\s+)?EXISTS\s+)?(?:ONLY\s+)?"
                         r"(?:\"?\w+\"?\.)?\"?(\w+)\"?", re.IGNORECASE)
_SQL_USE = r"\b(?:FROM|INTO|UPDATE|JOIN)\s+(?:ONLY\s+)?(?:\"?\w+\"?\.)?\"?(\w+)\b\"?(?!\()"
_SQL_USE_ANY = re.compile(_SQL_USE, re.IGNORECASE)
_SQL_USE_UPPER = re.compile(_SQL_USE)
_TABLENAME = re.compile(r"\b__tablename__\s*=\s*[\"'](\w+)[\"']")
_CELERY_TASK = re.compile(r"@(?:\w+\.)?(?:task|shared_task)\b([^\n]*)\n(?:\s*@[^\n]*\n)*\s*(?:async\s+)?def\s+(\w+)")
_CELERY_NAME = re.compile(r"\bname\s*=\s*[\"']([\w.]+)[\"']")
_CELERY_CALL = re.compile(r"\b(\w+)\.(delay|apply_async)\(")
_CELERY_SEND = re.compile(r"\bsend_task\(\s*[\"']([\w.]+)[\"']")


def norm_path(raw):
    """URL path with params as {}, a leading base expression dropped; None when no literal segment survives."""
    path = _EXPR.sub("\x00", re.sub(r"^[a-z]+://[^/]+", "", raw.strip()))
    path = re.split(r"[?#]", path.lstrip("\x00"), maxsplit=1)[0]
    if not path.startswith("/"):
        return None
    segments = []
    for segment in filter(None, path.split("/")):
        if _PARAM.match(segment):
            segments.append("{}")
            continue
        segment = segment.rstrip("\x00")
        segments.append("{}" if "\x00" in segment or "{" in segment else segment)
    if all(s == "{}" for s in segments):
        return None
    return "/" + "/".join(segments)


def is_test(path):
    return bool(_TEST_PATH.search(path))


class _Text:
    """Source text with offset-to-line lookup and a comment-line test."""

    def __init__(self, text):
        self.text = text
        self.starts = [0] + [m.end() for m in re.finditer("\n", text)]

    def line(self, offset):
        return bisect.bisect_right(self.starts, offset)

    def commented(self, offset):
        start = self.starts[self.line(offset) - 1]
        return self.text[start:offset].lstrip().startswith(_COMMENT)


def _fact(kind, key, line, role, pattern, verb=None):
    return [kind, key, line, role, pattern] + ([verb] if verb else [])


def _route(src, raw, offset, role, pattern, verb=None):
    key = norm_path(raw)
    return [_fact("route", key, src.line(offset), role, pattern, verb)] if key else []


def _prefix(src, raw, offset, pattern):
    key = norm_path(raw)
    return [_fact("prefix", key, src.line(offset), "defines", pattern)] if key else []


def _call_args(text, start):
    depth, index = 0, start
    while index < len(text):
        char = text[index]
        depth += (char == "(") - (char == ")")
        if depth == 0:
            return text[start:index]
        index += 1
    return text[start:]


def _axum(src):
    facts = []
    for match in _AXUM_ROUTE.finditer(src.text):
        args = _call_args(src.text, match.start() + len(".route"))[len(match.group(0)) - len(".route"):]
        verbs = sorted({v.upper() for v in _AXUM_VERB.findall(args)} - {"ANY"}) or [None]
        for verb in verbs:
            facts += _route(src, match.group(1), match.start(), PROVIDER, "axum-route", verb)
    for match in _AXUM_NEST.finditer(src.text):
        facts += _prefix(src, match.group(1), match.start(), "axum-nest")
    return facts


def _fastapi(src):
    facts, decorators = [], []
    for match in _FASTAPI_ROUTE.finditer(src.text):
        decorators.append(match.span())
        verb = None if match.group(1) == "api_route" else match.group(1).upper()
        facts += _route(src, match.group(2), match.start(), PROVIDER, "fastapi-route", verb)
    for match in _PY_PREFIX.finditer(src.text):
        facts += _prefix(src, match.group(1), match.start(), "fastapi-prefix")
    for match in _PY_CLIENT.finditer(src.text):
        if any(start <= match.start() < end for start, end in decorators):
            continue
        facts += _route(src, match.group(2), match.start(), "calls", "py-client", match.group(1).upper())
    return facts


def _ts_routes(src):
    facts = []
    for match in _TS_CLIENT.finditer(src.text):
        facts += _route(src, match.group(3), match.start(), "calls", "ts-client-verb", match.group(1).upper())
    for match in _TS_FETCH.finditer(src.text):
        method = _TS_METHOD.search(match.group(3))
        facts += _route(src, match.group(2), match.start(), "calls", "ts-fetch", method.group(1).upper() if method else "GET")
    for match in _TS_RESOURCE.finditer(src.text):
        for suffix in ("", "/{id}"):
            facts += _route(src, match.group(1) + suffix, match.start(), "calls", "ts-resource-factory")
    for match in _TS_PATHVAR.finditer(src.text):
        facts += _route(src, match.group(1), match.start(), "calls", "ts-path-literal")
    for match in _TS_PREFIX.finditer(src.text):
        facts += _prefix(src, match.group(1), match.start(), "ts-base-url")
    return facts


def _next_route(path, src):
    parts = path.split("/")
    if parts[-1].rsplit(".", 1)[0] != "route" or "app" not in parts[:-1]:
        return []
    start = len(parts) - 1 - parts[-2::-1].index("app")
    segments = [p for p in parts[start:-1] if not (p.startswith("(") and p.endswith(")")) and not p.startswith("@")]
    facts = []
    for match in _NEXT_HANDLER.finditer(src.text):
        facts += _route(src, "/" + "/".join(segments), match.start(), PROVIDER, "next-route-handler", match.group(1))
    return facts


def _matches(src, regex, kind, role, pattern, key=lambda m: m.group(1)):
    return [_fact(kind, key(m), src.line(m.start()), role, pattern) for m in regex.finditer(src.text)
            if not src.commented(m.start()) and key(m)]


def _env_readers(src, suffix):
    if suffix == ".rs":
        return _matches(src, _RUST_ENV, "env", "reads", "rust-env")
    if suffix == ".py":
        return _matches(src, _PY_ENV, "env", "reads", "py-env")
    return _matches(src, _TS_ENV, "env", "reads", "ts-env", key=lambda m: m.group(1) or m.group(2))


def _env_providers(name, src):
    if name.startswith((".env", "env.")) or name.endswith((".env", ".example")):
        return _matches(src, _ENV_LINE, "env", PROVIDER, "env-file")
    if re.match(r"(?:docker-)?compose[\w.-]*\.ya?ml$", name):
        return _matches(src, _COMPOSE_LINE, "env", PROVIDER, "compose-env")
    return []


def _tables(src, suffix):
    facts = _matches(src, _SQL_CREATE, "table", PROVIDER, "sql-ddl", key=lambda m: m.group(2))
    uses = _SQL_USE_ANY if suffix == ".sql" else _SQL_USE_UPPER
    facts += [f for f in _matches(src, uses, "table", "queries", "sql-use") if f[1].upper() not in SQL_WORDS]
    if suffix == ".py":
        facts += _matches(src, _TABLENAME, "table", PROVIDER, "sqlalchemy-tablename")
    return facts


def _celery(src):
    facts = []
    for match in _CELERY_TASK.finditer(src.text):
        named = _CELERY_NAME.search(match.group(1))
        keys = {match.group(2), named.group(1).rsplit(".", 1)[-1] if named else match.group(2)}
        facts += [_fact("task", key, src.line(match.start()), PROVIDER, "celery-task") for key in sorted(keys)]
    facts += _matches(src, _CELERY_CALL, "task", "enqueues", "celery-call")
    facts += _matches(src, _CELERY_SEND, "task", "enqueues", "celery-send-task", key=lambda m: m.group(1).rsplit(".", 1)[-1])
    return facts


def _by_language(path, name, suffix, src):
    if suffix == ".rs":
        return _axum(src) + _env_readers(src, suffix) + _tables(src, suffix)
    if suffix == ".py":
        return _fastapi(src) + _env_readers(src, suffix) + _tables(src, suffix) + _celery(src)
    if suffix in TS_EXT:
        return _ts_routes(src) + _next_route(path, src) + _env_readers(src, suffix) + _tables(src, suffix)
    if suffix == ".sql":
        return _tables(src, suffix)
    return _env_providers(name, src)


def _as_test(facts):
    return [fact[:3] + [TESTS] + fact[4:] for fact in facts if fact[0] != "prefix"]


def extract(path, text):
    """Facts `[kind, key, line, role, pattern, verb?]` for one file; facts in a test file become `tests` consumers."""
    name = path.rsplit("/", 1)[-1]
    facts = _by_language(path, name, Path(name).suffix, _Text(text))
    return _as_test(facts) if is_test(path) else facts
