"""Token usage, cost, redaction, totals and activity feed read from synthetic transcripts."""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins/fullstack-agents/scripts/lib"))
import activity
import context_handoff
import plan_usage
import usage

NOW = "2026-10-17T09:00:00.000Z"


def assistant(mid, model="claude-opus-5-5", inp=10, out=100, write=1000, read=50_000, side=False, ts=NOW):
    return {"type": "assistant", "timestamp": ts, "isSidechain": side, "message": {
        "id": mid, "model": model, "usage": {"input_tokens": inp, "output_tokens": out,
                                             "cache_creation_input_tokens": write, "cache_read_input_tokens": read,
                                             "cache_creation": {"ephemeral_1h_input_tokens": 0}}}}


def write_lines(path, rows):
    with open(path, "a") as f:
        f.writelines(json.dumps(r) + "\n" for r in rows)


class UsageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        usage._CACHE.clear()

    def tearDown(self):
        self.tmp.cleanup()

    def test_repeated_message_blocks_count_once(self):
        path = self.dir / "s.jsonl"
        write_lines(path, [assistant("m1"), assistant("m1"), assistant("m2")])
        u = usage.transcript_usage(path)
        self.assertEqual(u["tokens"], 2 * (10 + 100 + 1000 + 50_000))
        self.assertEqual(u["context"], 10 + 1000 + 50_000)
        self.assertAlmostEqual(u["cost"], 2 * (10 * 4 + 100 * 20 + 1000 * 5 + 50_000 * 0.2) / 1e6)

    def test_incremental_scan_reads_only_appended_lines(self):
        path = self.dir / "s.jsonl"
        write_lines(path, [assistant("m1")])
        first = usage.transcript_usage(path)["tokens"]
        write_lines(path, [assistant("m2")])
        self.assertEqual(usage.transcript_usage(path)["tokens"], 2 * first)

    def test_compaction_sets_blowout_and_post_context(self):
        path = self.dir / "s.jsonl"
        write_lines(path, [assistant("m1", read=900_000), {"type": "system", "subtype": "compact_boundary",
                     "compactMetadata": {"preTokens": 901_010, "postTokens": 26_000}}])
        u = usage.transcript_usage(path)
        self.assertEqual((u["compactions"], u["context"], u["compact_pre"]), (1, 26_000, 901_010))
        self.assertTrue(u["blowout"])

    def test_fill_threshold_marks_blowout_without_compaction(self):
        path = self.dir / "s.jsonl"
        write_lines(path, [assistant("m1", model="claude-haiku-4-5", read=185_000)])
        u = usage.transcript_usage(path)
        self.assertEqual(u["window"], 200_000)
        self.assertTrue(u["blowout"])

    def test_handoff_uses_token_cap_not_the_million_window(self):
        path = self.dir / "s.jsonl"
        write_lines(path, [assistant("m1", read=210_000)])
        u = usage.transcript_usage(path)
        self.assertEqual((u["window"], u["handoff_at"]), (1_000_000, 200_000))
        self.assertTrue(u["handoff"])

    def test_handoff_drops_below_the_smallest_compaction(self):
        path = self.dir / "s.jsonl"
        write_lines(path, [{"type": "system", "subtype": "compact_boundary", "compactMetadata": {"preTokens": 150_000, "postTokens": 30_000}},
                           {"type": "system", "subtype": "compact_boundary", "compactMetadata": {"preTokens": 400_000, "postTokens": 30_000}},
                           assistant("m1", read=130_000)])
        u = usage.transcript_usage(path)
        self.assertEqual(u["handoff_at"], 127_500)
        self.assertTrue(u["handoff"])

    def test_handoff_cap_reads_the_environment(self):
        os.environ["FSA_HANDOFF_TOKENS"] = "100000"
        self.addCleanup(os.environ.pop, "FSA_HANDOFF_TOKENS")
        self.assertEqual(usage.handoff_at(1_000_000), 100_000)
        self.assertEqual(usage.handoff_at(100_000), 85_000)

    def test_sidechain_does_not_move_lead_context(self):
        path = self.dir / "s.jsonl"
        write_lines(path, [assistant("m1", read=10_000), assistant("m2", read=500_000, side=True)])
        self.assertEqual(usage.transcript_usage(path)["context"], 10 + 1000 + 10_000)

    def test_session_usage_rolls_up_subagents(self):
        path = self.dir / "lead.jsonl"
        write_lines(path, [assistant("m1")])
        (self.dir / "lead" / "subagents").mkdir(parents=True)
        write_lines(self.dir / "lead" / "subagents" / "agent-abc.jsonl", [assistant("a1", model="claude-sonnet-5-5", side=True)])
        (self.dir / "lead" / "subagents" / "agent-abc.meta.json").write_text(json.dumps({"agentType": "fsa:reviewer", "description": "Audit diff"}))
        u = usage.session_usage(path)
        self.assertEqual(u["agents"]["abc"]["model"], "claude-sonnet-5-5")
        self.assertGreater(u["agents"]["abc"]["fill"], 0)
        self.assertEqual(u["agents"]["abc"]["label"], "reviewer · Audit diff")
        self.assertAlmostEqual(u["total_cost"], u["cost"] + u["agent_cost"])

    def test_unknown_model_has_tokens_but_no_cost(self):
        path = self.dir / "s.jsonl"
        write_lines(path, [assistant("m1", model="mystery-1")])
        u = usage.transcript_usage(path)
        self.assertGreater(u["tokens"], 0)
        self.assertIsNone(u["cost"])

    def test_price_file_overrides_defaults(self):
        prices = self.dir / "prices.json"
        prices.write_text(json.dumps({"mystery-1": {"input": 1, "output": 1, "cache_read": 1, "window": 100_000}}))
        old = usage.PRICE_FILE
        usage.PRICE_FILE, usage._PRICES["mtime"] = prices, -1
        try:
            path = self.dir / "s.jsonl"
            write_lines(path, [assistant("m1", model="mystery-1", inp=1_000_000, out=0, write=0, read=0)])
            self.assertAlmostEqual(usage.transcript_usage(path)["cost"], 1.0)
        finally:
            usage.PRICE_FILE, usage._PRICES["mtime"] = old, -1

    def test_codex_totals_become_deltas(self):
        path = self.dir / "rollout.jsonl"

        def count(total, last):
            return {"timestamp": NOW, "type": "event_msg", "payload": {"type": "token_count", "info": {
                "total_token_usage": {"input_tokens": total, "cached_input_tokens": 0, "output_tokens": 0, "total_tokens": total},
                "last_token_usage": {"input_tokens": last}, "model_context_window": 258_400}}}
        write_lines(path, [{"type": "turn_context", "timestamp": NOW, "payload": {"model": "gpt-5.6-sol"}}, count(1000, 1000), count(3000, 2000)])
        u = usage.transcript_usage(path, "codex")
        self.assertEqual((u["tokens"], u["context"], u["window"], u["model"]), (3000, 2000, 258_400, "gpt-5.6-sol"))

    def test_redaction_keeps_json_valid(self):
        body = json.dumps({"a": "Authorization: Bearer abcdefghijklmnop123", "b": "postgres://u:hunter22@db/x",
                           "c": "key sk-ant-api03-zzzzzzzzzz", "d": "DB_PASSWORD=supersecret", "e": "plain text"}).encode()
        out = json.loads(usage.redact(body))
        self.assertEqual(out["a"], "Authorization: Bearer [redacted]")
        self.assertEqual(out["b"], "postgres://u:[redacted]@db/x")
        self.assertEqual(out["c"], "key [redacted]")
        self.assertEqual(out["d"], "DB_PASSWORD=[redacted]")
        self.assertEqual(out["e"], "plain text")

    def test_redaction_covers_key_bodies_empty_users_and_quoted_keys(self):
        key = "-----BEGIN RSA PRIVATE KEY-----\nMIIEsecretbody\n-----END RSA PRIVATE KEY-----"
        inner = json.dumps({"password": "hunter22x", "tokens": 12})
        body = json.dumps({"k": f"before {key} after", "r": "redis://:s3cretpw@cache:6379", "said": inner}).encode()
        out = json.loads(usage.redact(body))
        self.assertEqual(out["k"], "before [redacted] after")
        self.assertEqual(out["r"], "redis://:[redacted]@cache:6379")
        self.assertEqual(json.loads(out["said"]), {"password": "[redacted]", "tokens": 12})
        self.assertNotIn(b"hunter22x", usage.redact(json.dumps({"password": "hunter22x"}).encode()))


class ActivityTests(unittest.TestCase):
    def state(self, sstate="working", compactions=0, runs=(), events=()):
        return {"events": list(events), "cards": [{"key": "k", "title": "Card", "runs": list(runs),
                "sessions": [{"id": "s1", "usage": {"compactions": compactions, "fill": 0.5}}],
                "now": [{"id": "s1", "name": "lead", "state": sstate, "agents": []}]}]}

    def test_feed_reports_changes_not_the_first_snapshot(self):
        feed = activity.ActivityFeed()
        self.assertEqual(feed.update(self.state()), [])
        events = feed.update(self.state("waiting", compactions=1))
        self.assertEqual([e["text"] for e in events], ["context compacted (1×)", "waiting on you"])

    def test_failed_run_carries_its_cause(self):
        feed = activity.ActivityFeed()
        run = {"id": "implement-1", "mode": "implement", "unit": "u1", "state": "running"}
        feed.update(self.state(runs=[run]))
        events = feed.update(self.state(runs=[{**run, "state": "failed", "cause": "error[E0382]: borrow"}]))
        self.assertEqual(events[0]["text"], "implement u1 failed: error[E0382]: borrow")
        self.assertEqual(events[0]["tone"], "bad")

    def test_board_events_are_seeded_once(self):
        feed = activity.ActivityFeed()
        ev = {"at": "2026-10-17T08:44:07Z", "session": "x", "name": "peer", "text": "deployed"}
        feed.update(self.state(events=[ev]))
        self.assertEqual(len(feed.update(self.state(events=[ev]))), 1)

    def test_run_cause_prefers_last_error_line(self):
        with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False) as f:
            f.write("compiling\nerror: first\nwarning: x\nerror: last one\ndone\n")
        try:
            self.assertEqual(activity.run_cause(f.name, None), "error: last one")
        finally:
            os.unlink(f.name)

    def test_totals_count_shown_but_spend_every_session(self):
        now = time.time()
        u = {"blowout": True, "today": {"cost": 2.0, "tokens": 10}, "tpm": 5}
        shown = [{"state": "waiting", "updated": now, "usage": u, "agents": [{"state": "running"}]}]
        every = shown + [{"state": "idle", "updated": now - 90_000, "usage": {**u, "blowout": False}}]
        t = activity.totals(shown, every, [{"state": "failed"}], now)
        self.assertEqual((t["live"], t["waiting"], t["workers"], t["failed"], t["blowouts"]), (1, 1, 1, 1, 1))
        self.assertEqual((t["cost_today"], t["tokens_today"]), (4.0, 20))


class PlanUsageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.old = plan_usage.BASES, plan_usage.CODEX_HOME, plan_usage.CACHE_FILE, plan_usage._fetch_claude
        plan_usage.CACHE_FILE = self.dir / "cache" / "claude-plan.json"
        plan_usage._CACHE.update(at=0.0, value=None, busy=False)

    def tearDown(self):
        plan_usage.BASES, plan_usage.CODEX_HOME, plan_usage.CACHE_FILE, plan_usage._fetch_claude = self.old
        self.tmp.cleanup()

    def test_codex_windows_come_from_the_newest_rollout(self):
        day = self.dir / "sessions" / "2026" / "10" / "17"
        day.mkdir(parents=True)
        limits = {"plan_type": "plus", "primary": {"used_percent": 12.5, "window_minutes": 300, "resets_at": 1792238809},
                  "secondary": {"used_percent": 100.0, "window_minutes": 10080, "resets_at": 1792649557},
                  "credits": {"has_credits": True, "unlimited": False, "balance": "59210.46"}}
        write_lines(day / "rollout-a.jsonl", [{"type": "event_msg", "payload": {"type": "token_count", "rate_limits": limits}}])
        plan_usage.CODEX_HOME = self.dir
        p = plan_usage.codex_plan()
        self.assertEqual(p["plan"], "plus")
        self.assertEqual([(w["name"], w["pct"]) for w in p["windows"]], [("5 h", 12.5), ("week", 100.0)])
        self.assertTrue(p["windows"][0]["resets_at"].endswith("Z"))
        self.assertEqual(p["credits"], {"balance": 59210.46, "unlimited": False})

    def test_claude_code_copy_is_used_when_newer_and_expired_windows_blank(self):
        plan_usage.BASES = (str(self.dir),)
        cached = {"fetchedAtMs": (time.time() - 60) * 1000, "utilization": {
            "five_hour": {"utilization": 13, "resets_at": "2000-01-01T00:00:00+00:00"},
            "seven_day": {"utilization": 59, "resets_at": "2999-01-01T00:00:00+00:00"}}}
        (self.dir / ".claude.json").write_text(json.dumps({"cachedUsageUtilization": cached}))
        p = plan_usage._present({"error": "usage endpoint unavailable (429)"})
        self.assertEqual([(w["name"], w["pct"]) for w in p["windows"]], [("5 h", None), ("week", 59.0)])
        self.assertIn("429", p["stale"])
        self.assertFalse(plan_usage._due({}, time.time()), "a fresh Claude Code copy must spare the endpoint call")

    def test_grok_spend_sums_xai_messages_by_window(self):
        import sqlite3
        path = self.dir / "opencode.db"
        db = sqlite3.connect(path)
        db.execute("create table message (id text, session_id text, time_created integer, time_updated integer, data text)")
        now = time.time()
        rows = [(now - 60, "xai", 1.5, 1000), (now - 3 * 86400, "xai", 2.0, 4000), (now - 60, "openai", 9.0, 9)]
        for i, (at, provider, cost, tokens) in enumerate(rows):
            db.execute("insert into message values (?, 's', ?, ?, ?)", (str(i), int(at * 1000), int(at * 1000),
                       json.dumps({"providerID": provider, "cost": cost, "tokens": {"total": tokens}})))
        db.commit()
        db.close()
        old = plan_usage.OPENCODE_DB
        plan_usage.OPENCODE_DB = path
        try:
            g = plan_usage._grok_query(now)
        finally:
            plan_usage.OPENCODE_DB = old
        self.assertEqual([(x["name"], x["cost"], x["tokens"]) for x in g["spend"]], [("today", 1.5, 1000), ("7 days", 3.5, 5000)])

    def test_missing_or_expired_login_reports_instead_of_calling(self):
        plan_usage.BASES = (str(self.dir),)
        self.assertEqual(plan_usage.claude_plan(wait=True), {"error": "no Claude login found"})
        (self.dir / ".credentials.json").write_text(json.dumps({"claudeAiOauth": {"accessToken": "x", "expiresAt": 1000}}))
        plan_usage._CACHE.update(at=0.0, value=None, busy=False)
        plan_usage.CACHE_FILE.unlink()
        self.assertIn("expired", plan_usage.claude_plan(wait=True)["error"])

    def test_rate_limit_keeps_last_good_value_and_backs_off(self):
        calls = []
        good = {"plan": "team", "windows": [{"name": "5 h", "pct": 15.0, "resets_at": ""}]}
        plan_usage._fetch_claude = lambda: calls.append(1) or good
        self.assertEqual(plan_usage.claude_plan(wait=True), good)
        shared = json.loads(plan_usage.CACHE_FILE.read_text())
        shared["at"] = 0
        plan_usage.CACHE_FILE.write_text(json.dumps(shared))
        plan_usage._fetch_claude = lambda: calls.append(1) or {"error": "usage endpoint unavailable (429)", "retry_after": 600}
        plan_usage._CACHE.update(at=0.0, value=None, busy=False)
        stale = plan_usage.claude_plan(wait=True)
        self.assertEqual(stale["windows"], good["windows"])
        self.assertIn("429", stale["stale"])
        plan_usage._CACHE.update(at=0.0, value=None, busy=False)
        plan_usage.claude_plan(wait=True)
        self.assertEqual(len(calls), 2, "a second process inside the backoff window must not call the endpoint")


class ContextHandoffHookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.path = self.dir / "s.jsonl"
        self.hook = {"session_id": "s1", "transcript_path": str(self.path)}
        usage._CACHE.clear()

    def tearDown(self):
        self.tmp.cleanup()

    def notice(self, **extra):
        return context_handoff.notice({**self.hook, **extra}, self.dir)

    def test_fires_once_per_compaction_cycle(self):
        write_lines(self.path, [assistant("m1", read=150_000)])
        self.assertIsNone(self.notice())
        write_lines(self.path, [assistant("m2", read=210_000)])
        self.assertIn("HANDOFF: context is at 211,010 tokens", self.notice())
        write_lines(self.path, [assistant("m3", read=250_000)])
        self.assertIsNone(self.notice())
        write_lines(self.path, [{"type": "system", "subtype": "compact_boundary",
                                 "compactMetadata": {"preTokens": 260_000, "postTokens": 30_000}}])
        self.assertIsNone(self.notice())
        write_lines(self.path, [assistant("m4", read=230_000)])
        self.assertIn("checkpoint size 200,000", self.notice())

    def test_resumes_from_saved_offset_without_rescanning(self):
        write_lines(self.path, [assistant("m1", read=10_000)])
        self.notice()
        saved = json.loads((self.dir / "handoff-s1.json").read_text())
        self.assertEqual(saved["offset"], self.path.stat().st_size)
        usage._CACHE.clear()
        write_lines(self.path, [assistant("m2", read=205_000)])
        self.assertIsNotNone(self.notice())

    def test_subagent_and_missing_transcript_stay_silent(self):
        write_lines(self.path, [assistant("m1", read=500_000)])
        self.assertIsNone(self.notice(agent_id="a1"))
        self.assertIsNone(context_handoff.notice({"session_id": "s2", "transcript_path": str(self.dir / "none.jsonl")}, self.dir))


if __name__ == "__main__":
    unittest.main()
