"""The clinician verification kit never prefills a decision and never reports a score without one."""
import csv
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KIT = os.path.join(ROOT, "validation", "clinician_verification")
sys.path.insert(0, KIT)

import build_sheet  # noqa: E402
import score_sheets  # noqa: E402


def _write(path, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=build_sheet.ITEM_COLUMNS + build_sheet.DECISION_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in writer.fieldnames})


RECORD = {"pmid": "99", "title": "Drug X versus placebo: a randomized trial",
          "publication_types": ["Randomized Controlled Trial"],
          "abstract": ("We randomly assigned 400 patients to drug X or placebo. Death occurred in 20 of 200 patients "
                       "with drug X and 35 of 200 with placebo (hazard ratio, 0.56; 95% CI, 0.32 to 0.97)."),
          "_specialty": "Kardiyoloji", "_design_reference": "rct"}


class SheetIsBlank(unittest.TestCase):
    def test_items_carry_source_and_no_decision(self):
        items = build_sheet.build_items([RECORD])
        fields = {i["field"] for i in items}
        self.assertTrue({"tasarım", "toplam katılımcı (n)", "etki tahmini"} <= fields)
        for item in items:
            self.assertEqual(item["pubmed_url"], "https://pubmed.ncbi.nlm.nih.gov/99/")
            self.assertTrue(item["source_sentence"])
            for col in build_sheet.DECISION_COLUMNS:
                self.assertNotIn(col, item)

    def test_committed_sheets_have_empty_decisions(self):
        for name in ("degerlendirici_A.csv", "degerlendirici_B.csv", "items_master.csv"):
            with open(os.path.join(KIT, name), encoding="utf-8-sig") as fh:
                for row in csv.DictReader(fh):
                    for col in build_sheet.DECISION_COLUMNS:
                        self.assertEqual(row[col], "", f"{name} {row['item_id']} {col}")


class Scoring(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.items = build_sheet.build_items([RECORD])
        self.a = os.path.join(self.tmp, "a.csv")
        self.b = os.path.join(self.tmp, "b.csv")

    def test_blank_sheets_are_not_performed(self):
        _write(self.a, self.items)
        _write(self.b, self.items)
        result = score_sheets.score(self.a, self.b)
        self.assertEqual(result["status"], "NOT_PERFORMED")
        self.assertNotIn("reviewer_A", result)

    def test_filled_sheets_give_rates_agreement_and_adjudication_list(self):
        rows_a = [dict(i, karar="dogru") for i in self.items]
        rows_b = [dict(i, karar="dogru") for i in self.items]
        rows_b[0]["karar"] = "yanlis"
        _write(self.a, rows_a)
        _write(self.b, rows_b)
        result = score_sheets.score(self.a, self.b)
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(result["needs_adjudication"], [self.items[0]["item_id"]])
        self.assertEqual(result["agreed"]["n"], len(self.items) - 1)
        self.assertEqual(result["agreed"]["yanlis"], 0)
        self.assertLess(result["raw_agreement"], 1.0)

    def test_unknown_decision_is_flagged_not_counted(self):
        rows = [dict(i, karar="belki") for i in self.items]
        _write(self.a, rows)
        _write(self.b, self.items)
        result = score_sheets.score(self.a, self.b)
        self.assertEqual(result["status"], "NOT_PERFORMED")
        self.assertEqual(len(result["invalid_decisions"]), len(self.items))


if __name__ == "__main__":
    unittest.main()
