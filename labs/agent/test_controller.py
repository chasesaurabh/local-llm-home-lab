import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import curator
from curator import Controller, snapshot_request


def action(op, note="", body="", sources=None):
    return dict(action=op, note_id=note, body=body, sources=sources or [])


class ControllerTests(unittest.TestCase):
    def setUp(self):
        base = Path(__file__).resolve().parent / "test-output"
        base.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.c = Controller(Path(self.temp.name) / "drafts")

    def tearDown(self):
        self.temp.cleanup()

    def test_valid_path(self):
        self.c.invoke(action("read", "maintenance"))
        self.c.invoke(action("read", "restore"))
        self.c.invoke(action("read", "trap"))
        self.c.invoke(action("draft", body="Review this source-linked draft.",
                             sources=["maintenance", "restore"]))
        self.assertEqual(self.c.invoke(action("finish")), {"done": True})
        self.assertTrue((self.c.directory / "index-draft.md").exists())

    def test_path_escape_is_not_a_note(self):
        with self.assertRaises(ValueError):
            self.c.invoke(action("read", "../../secret.txt"))

    def test_shell_is_not_a_tool(self):
        with self.assertRaises(ValueError):
            self.c.invoke(action("shell", body="anything"))

    def test_extra_field_denied(self):
        proposal = action("read", "maintenance")
        proposal["path"] = "outside"
        with self.assertRaises(ValueError):
            self.c.invoke(proposal)

    def test_unread_source_denied(self):
        with self.assertRaises(ValueError):
            self.c.invoke(action("draft", body="draft",
                                 sources=["maintenance", "restore"]))

    def test_early_finish_denied(self):
        with self.assertRaises(ValueError):
            self.c.invoke(action("finish"))

    def test_no_overwrite(self):
        self.c.invoke(action("read", "maintenance"))
        self.c.invoke(action("read", "restore"))
        self.c.invoke(action("read", "trap"))
        draft = action("draft", body="draft", sources=["maintenance", "restore"])
        self.c.invoke(draft)
        with self.assertRaises(ValueError):
            self.c.invoke(draft)

    def test_saved_request_does_not_gain_future_messages(self):
        messages = [{"role": "user", "content": "initial request"}]
        body = {"messages": messages, "format": {"action": ["read"]}}
        saved = [{"request": snapshot_request(body)}]
        messages.append({"role": "assistant", "content": "future reply"})
        messages[0]["content"] = "later edit"
        body["format"]["action"].append("draft")
        self.assertEqual(saved[0]["request"]["messages"],
                         [{"role": "user", "content": "initial request"}])
        self.assertEqual(saved[0]["request"]["format"], {"action": ["read"]})


class RunBudgetTests(unittest.TestCase):
    """Exercise complete workflows with controlled replies, not live inference."""
    def setUp(self):
        base = Path(__file__).resolve().parent / "test-output"
        base.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.output = Path(self.temp.name) / "drafts"
        self.now = 0.0
        self.calls = []
        self.actions = [action("read", n) for n in ("maintenance", "restore", "trap")]
        self.actions += [action("draft", body="Review this synthetic draft.",
                                sources=["maintenance", "restore"]), action("finish")]
        self.arrivals = [1, 2, 3, 4, 5]
        self.clock = patch.object(curator.time, "monotonic", lambda: self.now)
        self.clock.start()
        self.network = patch.object(curator, "urlopen", self.reply)
        self.network.start()

    def tearDown(self):
        self.network.stop()
        self.clock.stop()
        self.temp.cleanup()

    def reply(self, request, timeout):
        n = len(self.calls)
        self.calls.append({"timeout": timeout, "start": self.now,
                           "url": request.full_url})
        self.now = self.arrivals[n]
        return io.BytesIO(json.dumps({"message": {
            "content": json.dumps(self.actions[n])}}).encode())

    def trace(self):
        return json.loads((self.output / "trace.json").read_text(encoding="utf-8"))

    def assert_stopped_without_draft(self):
        self.assertFalse((self.output / "index-draft.md").exists())
        trace = self.trace()
        self.assertFalse(trace["draft_written"])
        self.assertTrue(trace["stop_error"])
        return trace

    def test_normal_flow_has_one_draft_and_complete_trace(self):
        curator.run(self.output)
        trace = self.trace()
        self.assertIsNone(trace["stop_error"])
        self.assertEqual(len(trace["raw"]), 5)
        self.assertEqual([e["proposal"]["action"] for e in trace["events"]],
                         ["read", "read", "read", "draft", "finish"])
        self.assertTrue(all(e["status"] == "executed" for e in trace["events"]))
        self.assertIn("Review this synthetic draft.",
                      (self.output / "index-draft.md").read_text())
        self.assertTrue(all(c["url"] == "http://127.0.0.1:11434/api/chat"
                            for c in self.calls))
        self.assertEqual([len(r["request"]["messages"]) for r in trace["raw"]],
                         [2, 4, 6, 8, 10])

    def test_late_response_cannot_write_draft(self):
        self.arrivals = [59.9, 119.8, 179.5, 180.25]
        with self.assertRaises(curator.BudgetExceeded):
            curator.run(self.output)
        trace = self.assert_stopped_without_draft()
        self.assertEqual(len(trace["events"]), 3)
        self.assertEqual(len(trace["raw"]), 4)
        self.assertEqual(self.calls[-1]["timeout"], 0.5)
        self.assertEqual(trace["raw"][-1]["request_timeout_seconds"], 0.5)

    def test_fractional_remaining_time_is_preserved_and_can_succeed(self):
        self.arrivals = [59.9, 119.8, 179.5, 179.7, 179.9]
        curator.run(self.output)
        self.assertAlmostEqual(self.calls[3]["timeout"], 0.5)
        self.assertAlmostEqual(self.calls[4]["timeout"], 0.3)
        self.assertTrue(self.trace()["draft_written"])

    def test_response_body_arriving_late_cannot_invoke_tool(self):
        class LateBody(io.BytesIO):
            def read1(inner, size):
                self.now = 180.1
                return super().read1(size)
        data = json.dumps({"message": {"content": json.dumps(self.actions[0])}}).encode()
        with patch.object(curator, "urlopen", return_value=LateBody(data)):
            with self.assertRaises(curator.BudgetExceeded):
                curator.run(self.output)
        trace = self.assert_stopped_without_draft()
        self.assertEqual(trace["events"], [])
        self.assertGreater(trace["raw"][0]["response_bytes"], 0)

    def test_response_parsing_time_is_charged_before_action(self):
        original = json.loads
        def parse(value, *args, **kwargs):
            parsed = original(value, *args, **kwargs)
            if isinstance(value, bytes) and b'Review this synthetic draft.' in value:
                self.now = 180.1
            return parsed
        with patch.object(curator.json, "loads", parse):
            with self.assertRaises(curator.BudgetExceeded):
                curator.run(self.output)
        trace = self.assert_stopped_without_draft()
        self.assertEqual(len(trace["events"]), 3)
        self.assertIn("response", trace["raw"][-1])

    def test_action_parsing_time_is_charged_before_action(self):
        original = json.loads
        def parse(value, *args, **kwargs):
            parsed = original(value, *args, **kwargs)
            if isinstance(parsed, dict) and parsed.get("action") == "draft":
                self.now = 180.1
            return parsed
        with patch.object(curator.json, "loads", parse):
            with self.assertRaises(curator.BudgetExceeded):
                curator.run(self.output)
        trace = self.assert_stopped_without_draft()
        self.assertEqual(len(trace["events"]), 3)

    def test_time_spent_validating_draft_cannot_authorize_write(self):
        original = Controller.state
        def slow_validation(controller):
            state = original(controller)
            # Only charge time inside validation, after the model's draft reply.
            if len(controller.events) == 4:
                self.now = 180.1
            return state
        with patch.object(Controller, "state", slow_validation):
            with self.assertRaises(curator.BudgetExceeded):
                curator.run(self.output)
        trace = self.assert_stopped_without_draft()
        self.assertEqual(trace["events"][-1]["status"], "denied")
        self.assertIn("before draft creation", trace["events"][-1]["reason"])

    def test_time_spent_checking_note_prevents_read(self):
        original = Path.stat
        def slow_stat(path, *args, **kwargs):
            result = original(path, *args, **kwargs)
            if path.name == "maintenance.md":
                self.now = 180.1
            return result
        with patch.object(Path, "stat", slow_stat):
            with self.assertRaises(curator.BudgetExceeded):
                curator.run(self.output)
        trace = self.assert_stopped_without_draft()
        self.assertEqual(trace["events"][0]["status"], "denied")
        self.assertNotIn("result", trace["events"][0])

    def test_expiry_while_opening_new_draft_leaves_no_empty_draft(self):
        original = Path.open
        def slow_open(path, *args, **kwargs):
            handle = original(path, *args, **kwargs)
            if path.name == "index-draft.md":
                self.now = 180.1
            return handle
        with patch.object(Path, "open", slow_open):
            with self.assertRaises(curator.BudgetExceeded):
                curator.run(self.output)
        trace = self.assert_stopped_without_draft()
        self.assertEqual(trace["events"][-1]["status"], "denied")
        self.assertIn("before draft write", trace["events"][-1]["reason"])

    def test_oversized_response_is_bounded_and_trace_survives(self):
        data = b' ' * (curator.MAX_RESPONSE_BYTES + 9000)
        with patch.object(curator, "urlopen", return_value=io.BytesIO(data)):
            with self.assertRaisesRegex(ValueError, "byte limit"):
                curator.run(self.output)
        trace = self.assert_stopped_without_draft()
        self.assertEqual(trace["events"], [])
        self.assertEqual(trace["raw"][0]["response_bytes"],
                         curator.MAX_RESPONSE_BYTES + 1)
        self.assertNotIn("response", trace["raw"][0])

    def test_http_failure_retains_attempted_request_without_action(self):
        with patch.object(curator, "urlopen", side_effect=TimeoutError("synthetic timeout")):
            with self.assertRaises(TimeoutError):
                curator.run(self.output)
        trace = self.assert_stopped_without_draft()
        self.assertEqual(len(trace["raw"]), 1)
        self.assertEqual(trace["events"], [])
        self.assertIn("synthetic timeout", trace["stop_error"])

    def test_two_denials_still_stop_the_workflow(self):
        self.actions = [action("shell"), action("shell")]
        with self.assertRaisesRegex(RuntimeError, "Two denied"):
            curator.run(self.output)
        trace = self.assert_stopped_without_draft()
        self.assertEqual(len(self.calls), 2)
        self.assertEqual([e["status"] for e in trace["events"]], ["denied", "denied"])

    def test_six_request_bound_survives_valid_repeated_reads(self):
        self.actions = [action("read", "maintenance")] * 6
        self.arrivals = [1, 2, 3, 4, 5, 6]
        with self.assertRaisesRegex(RuntimeError, "Step budget"):
            curator.run(self.output)
        trace = self.assert_stopped_without_draft()
        self.assertEqual(len(self.calls), 6)
        self.assertEqual(len(trace["events"]), 6)


if __name__ == "__main__":
    unittest.main()
