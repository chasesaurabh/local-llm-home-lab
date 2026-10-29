import unittest
from retention import expired_names


class RetentionTests(unittest.TestCase):
    def test_boundary_is_kept(self):
        rows = [("recent", 13), ("boundary", 14), ("expired", 15)]
        self.assertEqual(expired_names(rows, 14, True), ["expired"])

    def test_unverified_blocks_every_candidate(self):
        self.assertEqual(expired_names([("old", 99)], 14, False), [])

    def test_zero_keeps_today(self):
        rows = [("today", 0), ("yesterday", 1)]
        self.assertEqual(expired_names(rows, 0, True), ["yesterday"])

    def test_empty_input(self):
        self.assertEqual(expired_names([], 14, True), [])

    def test_invalid_retention(self):
        for value in [-1, True, 1.5, "14"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                expired_names([], value, True)


if __name__ == "__main__":
    unittest.main()
