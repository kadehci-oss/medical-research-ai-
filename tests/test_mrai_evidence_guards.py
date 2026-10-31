"""B6 and B9 tests."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import evidence_guards as eg  # noqa: E402


class DateRange(unittest.TestCase):
    def test_none(self):
        self.assertIsNone(eg.fill_date_range(None, None))

    def test_start_only_gets_current_year_as_end(self):
        self.assertEqual(eg.fill_date_range(2020, None, today_year=2026), ("2020", "2026"))

    def test_end_only_gets_early_start(self):
        self.assertEqual(eg.fill_date_range(None, 2015), (str(eg.EARLIEST_YEAR), "2015"))

    def test_both(self):
        self.assertEqual(eg.fill_date_range(2018, 2022), ("2018", "2022"))

    def test_reversed_raises(self):
        with self.assertRaises(ValueError):
            eg.fill_date_range(2024, 2020)


class Retraction(unittest.TestCase):
    def test_statuses(self):
        self.assertEqual(eg.retraction_status({"publication_types": ["Journal Article", "Retracted Publication"]}),
                         "retracted")
        self.assertEqual(eg.retraction_status({"publication_types": ["Retraction of Publication"]}),
                         "retraction_notice")
        self.assertEqual(eg.retraction_status({"publication_types": ["Randomized Controlled Trial"]}), "none")
        self.assertEqual(eg.retraction_status({}), "none")
        self.assertEqual(eg.retraction_status(None), "none")

    def test_case_insensitive(self):
        self.assertEqual(eg.retraction_status({"publication_types": ["retracted publication"]}), "retracted")


if __name__ == "__main__":
    unittest.main()
