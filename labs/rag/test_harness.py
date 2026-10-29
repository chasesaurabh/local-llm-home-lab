"""Harness unit checks with deliberately synthetic responses, never model evidence."""
import json
import unittest
from unittest.mock import patch
import retrieval_baseline as lab


class HarnessChecks(unittest.TestCase):
    def test_manifest_removes_stale_revision(self):
        updated = lab.index("after-update")
        deleted = lab.index("after-delete")
        self.assertTrue(any(c["id"].startswith("maintenance-v3#") for c in updated))
        self.assertFalse(any(c["id"].startswith("maintenance-v2#") for c in updated))
        self.assertFalse(any(c["id"].startswith("maintenance-") for c in deleted))

    def test_injection_reaches_prompt(self):
        p = next(p for p in lab.prompts(4) if p["case_id"] == "B07")
        self.assertIn("CANDLE-PARADE-731", p["messages"][1]["content"])

    def test_source_hash_changes_with_revision(self):
        a = lab.index("baseline")[0]
        b = lab.index("after-update")[0]
        self.assertNotEqual(a["sha256"], b["sha256"])

    def test_missing_answers_are_not_passes(self):
        real_load = lab.load
        with patch.object(lab, "load", side_effect=lambda n: [] if n == "stub.json" else real_load(n)):
            result = lab.score_answers("stub.json", 4)
        self.assertEqual(len(result["cases"]), 20)
        self.assertTrue(all(r["status"] == "not_run" for r in result["cases"]))

    def test_false_fact_and_forged_source_fail(self):
        real_load = lab.load
        bad = [{"case_id": "B01", "answer": "Friday at 03:00 CANDLE-PARADE-731",
                "citations": ["invented#1"], "abstained": False}]
        with patch.object(lab, "load", side_effect=lambda n: bad if n == "stub.json" else real_load(n)):
            result = lab.score_answers("stub.json", 4)
        row = result["cases"][0]
        self.assertEqual(row["status"], "heuristic_fail")
        self.assertFalse(row["checks"]["facts"])
        self.assertFalse(row["checks"]["citations_available"])
        self.assertFalse(row["checks"]["canary_absent"])

    def test_empty_evidence_requirements_not_counted_as_success(self):
        result = lab.evaluate(4)
        self.assertEqual(result["scored"], 18)
        self.assertEqual(result["not_applicable"], 2)

    def test_traversal_input_rejected(self):
        with self.assertRaises(ValueError):
            lab.load("../not-permitted.json")


if __name__ == "__main__":
    unittest.main(verbosity=2)
