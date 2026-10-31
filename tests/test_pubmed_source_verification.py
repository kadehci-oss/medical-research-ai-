"""Category 2 — real PubMed source verification.

Offline checks run in CI: the recorded PubMed records are complete, well formed
and cover every reference row. The live check re-fetches each PMID from NCBI
E-utilities and compares title and DOI; it runs only with RUN_LIVE_PUBMED=1 so CI
never depends on the network.
"""
import json
import os
import re
import unittest

import pytest

_VALIDATION = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "validation")
SETS = [
    ("pubmed_records_multispecialty.json", "reference_dataset.json"),
    ("pubmed_records_holdout.json", "reference_dataset_holdout.json"),
    ("pubmed_records_holdout2.json", "reference_dataset_holdout2.json"),
]


REQUIRED_SPECIALTIES = {"Kardiyoloji", "Onkoloji", "Nöroloji", "Enfeksiyon", "Endokrinoloji",
                        "Pediatri", "Cerrahi", "Radyoloji"}


def _load(name):
    with open(os.path.join(_VALIDATION, name), encoding="utf-8") as handle:
        return json.load(handle)


class TestRecordedPubMedRecords(unittest.TestCase):
    def test_records_are_complete_and_well_formed(self):
        for records_name, _ref in SETS:
            for record in _load(records_name):
                self.assertRegex(record["pmid"], r"^\d{7,9}$")
                self.assertTrue(record["title"].strip(), record["pmid"])
                self.assertTrue(record["publication_types"], record["pmid"])
                self.assertEqual(record["pubmed_url"], f"https://pubmed.ncbi.nlm.nih.gov/{record['pmid']}/")
                if record["doi"]:
                    self.assertRegex(record["doi"], r"^10\.\d{4,9}/\S+$")
                    self.assertEqual(record["doi_url"], f"https://doi.org/{record['doi']}")

    def test_every_reference_row_has_a_recorded_pubmed_record(self):
        for records_name, ref_name in SETS:
            pmids = {r["pmid"] for r in _load(records_name)}
            for row in _load(ref_name)["studies"]:
                self.assertIn(row["pmid"], pmids, f"{ref_name}: {row['pmid']}")

    def test_no_pmid_is_shared_between_sets(self):
        sets = [{r["pmid"] for r in _load(name)} for name, _ref in SETS]
        for i in range(len(sets)):
            for j in range(i + 1, len(sets)):
                self.assertEqual(sets[i] & sets[j], set(), (SETS[i][0], SETS[j][0]))

    def test_eight_specialties_and_required_designs_are_covered(self):
        rows = [row for _name, ref in SETS for row in _load(ref)["studies"]]
        specialties = {r["specialty"] for r in rows}
        self.assertLessEqual(REQUIRED_SPECIALTIES, specialties)
        designs = {d for r in rows for d in r["design"][:1]}
        for required in ("rct", "cohort", "case_control", "diagnostic_accuracy", "case_series",
                         "systematic_review", "meta_analysis"):
            self.assertIn(required, designs | {d for r in rows for d in r["design"]}, required)
        for specialty in REQUIRED_SPECIALTIES:
            kinds = {r["design"][0] for r in rows if r["specialty"] == specialty}
            self.assertGreaterEqual(len(kinds), 2, specialty)

    def test_reference_source_sentences_exist_for_effects(self):
        """Every reference effect value appears in its PubMed abstract (guards against typos in the table)."""
        import evidence_model as em
        for records_name, ref_name in SETS:
            records = {r["pmid"]: r for r in _load(records_name)}
            for row in _load(ref_name)["studies"]:
                text = em.normalize_text(records[row["pmid"]]["abstract"])
                numbers = {abs(float(n)) for n in re.findall(r"\d+(?:\.\d+)?", text)}
                for effect in row["effects"]:
                    for value in [effect.get("value")] + list(effect.get("ci") or []):
                        if value is None:
                            continue
                        self.assertTrue(any(abs(abs(value) - n) < 1e-9 for n in numbers),
                                        f"{row['pmid']}: {value} not in abstract")


@pytest.mark.skipif(os.environ.get("RUN_LIVE_PUBMED") != "1", reason="set RUN_LIVE_PUBMED=1 to query NCBI E-utilities")
class TestLivePubMedRecords(unittest.TestCase):
    def test_live_title_and_doi_match_recorded_records(self):
        from pubmed_client import normalize_doi, normalize_title, verify_pmid
        mismatches = []
        for records_name, _ref in SETS:
            for record in _load(records_name):
                live = verify_pmid(record["pmid"])
                if not live.get("valid"):
                    mismatches.append(f"{record['pmid']}: not fetched ({live.get('error')})")
                    continue
                if normalize_title(live.get("title")) != normalize_title(record["title"]):
                    mismatches.append(f"{record['pmid']}: title differs")
                if record["doi"] and normalize_doi(live.get("doi")) != normalize_doi(record["doi"]):
                    mismatches.append(f"{record['pmid']}: DOI differs")
        self.assertEqual(mismatches, [])


if __name__ == "__main__":
    unittest.main()
