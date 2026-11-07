import sys
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "plugins/fullstack-agents"
sys.path.insert(0, str(PLUGIN / "scripts/lib"))

import code_map
import code_map_joins as joins


def facts(path, text, kind=None):
    return [f for f in joins.extract(path, text) if kind is None or f[0] == kind]


def keys(path, text, kind):
    return sorted({f[1] for f in facts(path, text, kind)})


class NormPathTests(unittest.TestCase):
    def test_params_normalise_to_braces(self):
        for raw in ("/items/${id}", "/items/{item_id}", "/items/:id", "/items/[id]", "/items/<int:id>", "/items/[[...slug]]"):
            self.assertEqual(joins.norm_path(raw), "/items/{}", raw)

    def test_leading_base_expression_is_dropped(self):
        self.assertEqual(joins.norm_path("${BASE_URL}/auth/refresh"), "/auth/refresh")

    def test_no_literal_segment_means_no_key(self):
        for raw in ("${BASE_URL}${path}", "${basePath}/${id}", "/", "relative/path", ""):
            self.assertIsNone(joins.norm_path(raw), raw)

    def test_glued_expression_query_host_and_trailing_slash(self):
        self.assertEqual(joins.norm_path("/leads${query}"), "/leads")
        self.assertEqual(joins.norm_path("https://api.example.com/x/y/?page=1"), "/x/y")
        self.assertEqual(joins.norm_path("/a/${x}-${y}/b"), "/a/{}/b")


class AxumTests(unittest.TestCase):
    SRC = ('Router::new()\n'
           '    .route("/items", get(list).post(create))\n'
           '    .route(\n'
           '        "/items/{id}",\n'
           '        patch(routes::items::update),\n'
           '    )\n'
           '    .route("/any", any(h))\n'
           '    .nest("/api/v1", api())\n'
           '    .nest(PREFIX, other())\n')

    def test_chained_verbs_and_multiline_route_start_line(self):
        routes = [f[1:3] + f[5:] for f in facts("router.rs", self.SRC, "route")]
        self.assertIn(["/items", 2, "GET"], routes)
        self.assertIn(["/items", 2, "POST"], routes)
        self.assertIn(["/items/{}", 3, "PATCH"], routes)

    def test_any_router_has_no_verb(self):
        self.assertIn(["route", "/any", 7, "provider", "axum-route"], facts("router.rs", self.SRC, "route"))

    def test_nest_counts_only_a_string_literal(self):
        self.assertEqual(facts("router.rs", self.SRC, "prefix"), [["prefix", "/api/v1", 8, "defines", "axum-nest"]])


class FastApiTests(unittest.TestCase):
    SRC = ('router = APIRouter(\n    prefix="/tts", tags=["t"])\n'
           '@router.get("/items/{item_id}")\ndef get_item(item_id): ...\n'
           '@router.api_route("/raw", methods=["GET"])\ndef raw(): ...\n'
           'app.include_router(other, prefix="/v1")\n')

    def test_routes_and_prefixes(self):
        self.assertIn(["route", "/items/{}", 3, "provider", "fastapi-route", "GET"], facts("api.py", self.SRC))
        self.assertIn(["route", "/raw", 5, "provider", "fastapi-route"], facts("api.py", self.SRC))
        self.assertEqual(keys("api.py", self.SRC, "prefix"), ["/tts", "/v1"])

    def test_a_route_decorator_is_not_also_a_client_call(self):
        src = '@router.get("/list")\ndef list_items(): ...\nhttpx.get("/other")\n'
        self.assertEqual([f[2:5] for f in facts("api.py", src, "route")],
                         [[1, "provider", "fastapi-route"], [3, "calls", "py-client"]])


class TypeScriptTests(unittest.TestCase):
    SRC = ('const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "/api/v1";\n'
           'api.get<{ items: Item[]; total: number }>(`/items/${id}`);\n'
           'fetch("/api/upload", {\n  method: "POST",\n});\n'
           'const r = createResourceApi<A, B>("/call-groups");\n'
           'const bulkPath = "/call-groups/bulk";\n'
           'api.get(url);\n'
           'fetch(`${BASE_URL}${path}`);\n')

    def test_consumers(self):
        routes = [f[1:4] + f[5:] for f in facts("lib/api/items.ts", self.SRC, "route")]
        self.assertIn(["/items/{}", 2, "calls", "GET"], routes)
        self.assertIn(["/api/upload", 3, "calls", "POST"], routes)
        self.assertIn(["/call-groups", 6, "calls"], routes)
        self.assertIn(["/call-groups/{}", 6, "calls"], routes)
        self.assertIn(["/call-groups/bulk", 7, "calls"], routes)

    def test_documented_miss_variable_urls_emit_nothing(self):
        lines = {f[2] for f in facts("lib/api/items.ts", self.SRC, "route")}
        self.assertFalse(lines & {8, 9})

    def test_base_url_prefix_and_env_reader(self):
        self.assertEqual(facts("client.ts", self.SRC, "prefix"), [["prefix", "/api/v1", 1, "defines", "ts-base-url"]])
        self.assertEqual(keys("client.ts", self.SRC, "env"), ["NEXT_PUBLIC_API_URL"])

    def test_next_route_handler_ignores_route_groups(self):
        src = "export async function GET() {}\nexport const POST = handler;\n"
        got = facts("src/app/(admin)/api/items/[id]/route.ts", src, "route")
        self.assertEqual([f[1:3] + f[5:] for f in got], [["/api/items/{}", 1, "GET"], ["/api/items/{}", 2, "POST"]])
        self.assertEqual(facts("src/app/api/items/page.ts", src, "route"), [])


class EnvTests(unittest.TestCase):
    def test_readers_per_language(self):
        rust = 'let a = std::env::var("A_DIR");\nlet b = env::var_os("B");\nlet c = env!("C");\n// env::var("DOC")\n'
        self.assertEqual(keys("main.rs", rust, "env"), ["A_DIR", "B", "C"])
        py = 'x = os.environ["X"]\ny = os.environ.get("Y")\nz = os.getenv("Z")\n# os.getenv("DOC")\n'
        self.assertEqual(keys("cfg.py", py, "env"), ["X", "Y", "Z"])

    def test_providers(self):
        self.assertEqual(facts(".env.example", "# OLD=1\nA_DIR=/data\nexport B=1\n"),
                         [["env", "A_DIR", 2, "provider", "env-file"], ["env", "B", 3, "provider", "env-file"]])
        self.assertEqual(keys("deploy/x.env.example", "C=1\n", "env"), ["C"])
        self.assertEqual(keys("docker-compose.yml", "environment:\n  - A_DIR=/d\n  B: 1\n", "env"), ["A_DIR", "B"])
        self.assertEqual(facts("config.yaml", "A_DIR: 1\n"), [])


class TableTests(unittest.TestCase):
    def test_ddl_and_uses(self):
        sql = ("CREATE TABLE IF NOT EXISTS public.items (id int);\nALTER TABLE items ADD c int;\n"
               "select * from items i join tags t on true;\n")
        self.assertEqual([f[1:4] for f in facts("m.sql", sql, "table")],
                         [["items", 1, "provider"], ["items", 2, "provider"], ["items", 3, "queries"], ["tags", 3, "queries"]])

    def test_code_uses_are_uppercase_only_and_skip_functions_and_keywords(self):
        rust = ('sqlx::query("SELECT a FROM items WHERE id = $1");\n"INSERT INTO items (a) VALUES ($1) '
                'ON CONFLICT (a) DO UPDATE SET a = 1";\n"FROM unnest($1)";\n"JOIN LATERAL x";\n'
                '// FROM docs_table\n')
        self.assertEqual([f[1:3] for f in facts("repo.rs", rust, "table")], [["items", 1], ["items", 2]])
        self.assertEqual(keys("svc.py", "from items import x\nrows = db.execute('select * from items')\n", "table"), [])

    def test_sqlalchemy_tablename(self):
        self.assertEqual(keys("models.py", 'class Item(Base):\n    __tablename__ = "items"\n', "table"), ["items"])


class CeleryTests(unittest.TestCase):
    def test_tasks_and_enqueues(self):
        src = ('@shared_task\ndef send_mail(x): ...\n'
               '@celery_app.task(name="ucm.run_source", bind=True)\ndef run_source_task(self): ...\n'
               'send_mail.delay(1)\nrun_source_task.apply_async(args=[1])\n'
               'app.send_task("ucm.run_source")\nsend_mail.s(1)\n')
        got = [f[1:4] for f in facts("tasks.py", src, "task")]
        self.assertIn(["send_mail", 1, "provider"], got)
        self.assertIn(["run_source", 3, "provider"], got)
        self.assertIn(["run_source_task", 3, "provider"], got)
        self.assertIn(["send_mail", 5, "enqueues"], got)
        self.assertIn(["run_source_task", 6, "enqueues"], got)
        self.assertIn(["run_source", 7, "enqueues"], got)
        self.assertNotIn(8, {f[1] for f in got})


class TestFileTests(unittest.TestCase):
    def test_test_files_become_tests_consumers_and_drop_prefixes(self):
        src = 'client.get("/items/1")\nrouter = APIRouter(prefix="/t")\n'
        self.assertEqual(facts("tests/test_api.py", src), [["route", "/items/1", 1, "tests", "py-client", "GET"]])
        for path in ("web/items.test.tsx", "web/__tests__/a.ts", "src/x_test.py", "web/a.spec.ts", "conftest.py"):
            self.assertTrue(joins.is_test(path), path)
        self.assertFalse(joins.is_test("src/contest.py"))


ENVELOPE_FILES = {
    "api/router.rs": 'Router::new().nest("/api/v1", v1());\nfn v1() { Router::new()\n    .route("/items", get(list)) }\n',
    "web/client.ts": 'const BASE_URL = "/api/v1";\n',
    "web/items.ts": 'api.get("/items");\napi.delete("/items");\n',
    "web/items.test.ts": 'fetch("/api/v1/items");\n',
}


class EnvelopeTests(unittest.TestCase):
    def index(self):
        return {"files": {p: {"facts": joins.extract(p, t)} for p, t in ENVELOPE_FILES.items()}}

    def test_rows_match_section_7_envelope(self):
        rows, truncated = code_map.match(self.index(), ["items"])
        self.assertFalse(truncated)
        self.assertIn({"kind": "route", "key": "/items", "from": "web/items.ts:1", "to": "api/router.rs:3",
                       "relation": "calls GET", "provenance": "axum-route+ts-client-verb", "fresh": "yes"}, rows)
        self.assertIn({"kind": "route", "key": "/items", "from": "web/items.test.ts:1", "to": "api/router.rs:3",
                       "relation": "tests GET", "provenance": "axum-route+ts-fetch", "fresh": "yes"}, rows)

    def test_verb_mismatch_stays_unjoined(self):
        rows, _ = code_map.match(self.index(), ["items"])
        self.assertIn(("web/items.ts:2", ""), {(r["from"], r["to"]) for r in rows})


if __name__ == "__main__":
    unittest.main()
