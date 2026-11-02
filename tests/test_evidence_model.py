"""Category 1 — software unit and integration tests for the structured evidence model.

No network. Synthetic abstracts isolate one rule each; integration tests use the
recorded real PubMed records under validation/.
"""
import json
import os
import unittest
from unittest.mock import patch

import evidence_model as em
import report_generator as rg
import report_verification as rv

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _art(pmid, abstract, title="Test title", pub_types=("Journal Article",), journal="J Test", year="2024", doi=""):
    return {
        "pmid": pmid, "title": title, "abstract": abstract, "publication_types": list(pub_types),
        "authors": ["Ada Lovelace"], "journal": journal, "pub_year": year, "doi": doi,
        "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
    }


def _records():
    with open(os.path.join(_ROOT, "validation", "pubmed_records_multispecialty.json"), encoding="utf-8") as handle:
        return {r["pmid"]: r for r in json.load(handle)}


RCT_ABSTRACT = (
    "In this double-blind trial, we randomly assigned 1200 patients with heart failure to receive drugzumab or placebo, "
    "in addition to usual therapy. The primary outcome was a composite of cardiovascular death or hospitalization for "
    "heart failure. A primary outcome event occurred in 100 of 600 patients (16.7%) in the drugzumab group and in 140 of "
    "600 patients (23.3%) in the placebo group (hazard ratio, 0.70; 95% confidence interval [CI], 0.54 to 0.90; P=0.006)."
)


class TestCountsAreSeparated(unittest.TestCase):
    def setUp(self):
        em.clear_cache()

    def test_event_numerators_and_arm_sizes_are_not_sample_size(self):
        study = em.build_study(_art("1", RCT_ABSTRACT, pub_types=["Randomized Controlled Trial"]))
        self.assertEqual(study.population.n_total, 1200)
        events = {(e.events, e.total) for e in study.event_counts}
        self.assertIn((100, 600), events)
        self.assertNotIn(study.population.n_total, {e.events for e in study.event_counts})

    def test_arm_counts_sum_is_labelled_as_derived(self):
        abstract = ("A total of 400 participants were assigned to the alphamab group, and 410 to the placebo group. "
                    "Overall survival was longer with alphamab (hazard ratio 0.80; 95% CI 0.66 to 0.97).")
        study = em.build_study(_art("2", abstract, pub_types=["Randomized Controlled Trial"]))
        self.assertEqual([a.n for a in study.arms], [400, 410])
        self.assertEqual(study.population.n_total, 810)
        self.assertEqual(study.population.n_kind, "arm_sum")
        self.assertEqual(study.population.source.verification_status, em.SOURCE_DERIVED)
        rendered = "\n".join(em.render_study_card_lines(study))
        self.assertIn("(kol n değerlerinin toplamı; türetilmiş)", rendered)
        self.assertIn("- alphamab: n = 400 — Kaynak cümle:", rendered)
        self.assertIn("- placebo: n = 410 — Kaynak cümle:", rendered)
        self.assertIn("**Müdahale:** alphamab — Kaynak cümle:", rendered)
        self.assertIn("**Karşılaştırıcı:** placebo — Kaynak cümle:", rendered)

    def test_article_cache_key_is_stable_sha256(self):
        article = _art("5", "A cohort of 50 patients was enrolled.")
        first = em._article_key(article)
        self.assertEqual(first, em._article_key(article))
        self.assertEqual(len(first), 64)

    def test_protocol_planned_sample_is_not_reported_as_enrolled(self):
        abstract = "This prospective observational study will include 800 patients with suspected stroke."
        study = em.build_study(_art("3", abstract, title="A protocol for a multicenter study"))
        self.assertIsNone(study.population.n_total)
        self.assertEqual(study.population.n_planned, 800)
        self.assertFalse(study.results_reported)
        self.assertEqual(study.estimates, [])

    def test_case_control_cases_are_not_total(self):
        abstract = ("A total of 3,043 newly diagnosed breast cancer cases and age-matched controls from the general "
                    "population were recruited.")
        study = em.build_study(_art("4", abstract, title="A large case-control study"))
        self.assertEqual(study.design_key, "case_control")
        self.assertIsNone(study.population.n_total)
        self.assertEqual(study.population.n_cases, 3043)


class TestEffectEstimates(unittest.TestCase):
    def setUp(self):
        em.clear_cache()

    def test_hr_is_bound_to_primary_outcome_with_its_own_ci(self):
        study = em.build_study(_art("10", RCT_ABSTRACT, pub_types=["Randomized Controlled Trial"]))
        est = study.estimates[0]
        self.assertEqual((est.measure, est.value, est.ci_low, est.ci_high, est.ci_level), ("HR", 0.70, 0.54, 0.90, 95))
        self.assertIn("cardiovascular death", est.outcome_name)
        self.assertIn("birincil sonlanım tanımı", est.outcome_basis)
        self.assertEqual(est.source.verification_status, em.SOURCE_VERIFIED)

    def test_missing_point_estimate_is_not_imputed(self):
        abstract = ("The adjusted odds ratio and 95% confidence interval (0.62-1.12) were < 1 and included 1, "
                    "respectively.")
        study = em.build_study(_art("11", abstract, title="A retrospective cohort study"))
        est = study.estimates[0]
        self.assertIsNone(est.value)
        self.assertEqual((est.ci_low, est.ci_high), (0.62, 1.12))
        self.assertEqual(est.validation, "eksik")
        self.assertIn("nokta tahmini özette bildirilmedi", em.format_estimate_tr(est))

    def test_ci_that_excludes_point_estimate_is_rejected(self):
        abstract = "Mortality was lower with the drug (hazard ratio 0.50; 95% CI 0.60 to 0.90)."
        study = em.build_study(_art("12", abstract, pub_types=["Randomized Controlled Trial"]))
        est = study.estimates[0]
        self.assertEqual(est.validation, "tutarsiz")
        self.assertFalse(est.usable)
        lines = "\n".join(em.render_study_card_lines(study))
        self.assertIn("Reddedilen eşleştirmeler", lines)

    def test_ci_level_label_is_not_read_as_value(self):
        abstract = "SGLT-2is reduced events (HR [95% CI]: 0.75 [0.68, 0.82])."
        study = em.build_study(_art("13", abstract, pub_types=["Meta-Analysis"]))
        est = study.estimates[0]
        self.assertEqual((est.value, est.ci_low, est.ci_high), (0.75, 0.68, 0.82))

    def test_coordinated_diagnostic_list_pairs_in_order(self):
        abstract = ("DOR, pooled sensitivity, and pooled specificity for ICH were 5.28 (95% CI: 4.11-6.46), "
                    "0.88 (95% CI: 0.79-0.97), and 0.99 (95% CI: 0.98-1.0).")
        study = em.build_study(_art("14", abstract, pub_types=["Meta-Analysis", "Systematic Review"]))
        got = [(e.measure, e.value, e.ci_low, e.ci_high) for e in study.estimates]
        self.assertEqual(got, [("DOR", 5.28, 4.11, 6.46), ("sensitivity", 0.88, 0.79, 0.97), ("specificity", 0.99, 0.98, 1.0)])
        self.assertTrue(all(e.outcome_name == "ICH" for e in study.estimates))

    def test_ninety_percent_ci_level_is_kept(self):
        abstract = "Treatment failure occurred in 34% versus 7% of patients (difference 26.7%, 90% CI 22.4-30.9)."
        study = em.build_study(_art("15", abstract, pub_types=["Randomized Controlled Trial"]))
        self.assertEqual(study.estimates[0].ci_level, 90)
        self.assertIn("%90 GA", em.format_estimate_tr(study.estimates[0]))

    def test_diagnostic_values_need_explicit_percentage_units(self):
        for measure in ("AUC", "Sensitivity", "Specificity"):
            with self.subTest(measure=measure):
                study = em.build_study(_art("12345678", f"{measure} was 1.2 (95% CI 1.1-1.3)."))
                self.assertFalse(study.estimates[0].usable)
                percent = em.build_study(_art("12345678", f"{measure} was 92% (95% CI 88-96)."))
                self.assertTrue(percent.estimates[0].usable)

    def test_diagnostic_confidence_bounds_must_match_reported_scale(self):
        for abstract in ("Sensitivity was 0.9 (95% CI -0.1-0.95).",
                         "Sensitivity was 0.9 (95% CI 0.8-1.2).",
                         "Sensitivity was 92% (95% CI 88-106)."):
            with self.subTest(abstract=abstract):
                study = em.build_study(_art("12345678", abstract))
                self.assertFalse(study.estimates[0].usable)

    def test_lowercase_or_is_not_an_odds_ratio(self):
        abstract = "Patients with diabetes or hypertension (n = 50) were included; no ratio was computed."
        study = em.build_study(_art("16", abstract))
        self.assertEqual(study.estimates, [])

    def test_exposure_in_parenthesis_is_not_the_outcome(self):
        abstract = ("Higher counts (monocyte counts, hazard ratio [HR]=1.093, 95 % confidence interval [CI] 1.052-1.136, "
                    "P<0.001) were associated with an increased risk of epilepsy.")
        study = em.build_study(_art("17", abstract, title="A prospective cohort"))
        self.assertEqual(study.estimates[0].outcome_name, "epilepsy")

    def test_explicit_follow_up_timepoint_is_structured_and_source_grounded(self):
        abstract = ("During a median follow-up of 18 months, all-cause mortality was lower "
                    "(hazard ratio, 0.75; 95% CI, 0.60 to 0.92).")
        study = em.build_study(_art("18", abstract, pub_types=["Randomized Controlled Trial"]))
        timepoint = study.estimates[0].follow_up_timepoint
        self.assertIsNotNone(timepoint)
        self.assertEqual((timepoint.value, timepoint.unit, timepoint.qualifier), (18.0, "month", "median"))
        self.assertEqual(timepoint.source.sentence, study.estimates[0].source.sentence)
        self.assertEqual(timepoint.source.verification_status, em.SOURCE_VERIFIED)
        self.assertIn("medyan takip: 18 ay", em.format_estimate_tr(study.estimates[0]))

    def test_follow_up_timepoint_stays_unknown_when_not_explicit(self):
        abstract = "All-cause mortality was lower (hazard ratio, 0.75; 95% CI, 0.60 to 0.92)."
        study = em.build_study(_art("19", abstract, pub_types=["Randomized Controlled Trial"]))
        self.assertIsNone(study.estimates[0].follow_up_timepoint)

    def test_distinct_follow_up_and_outcome_times_are_not_collapsed(self):
        sentence = ("Median follow-up was 18 months and overall survival at 24 months was 80% "
                    "(hazard ratio, 0.75; 95% CI, 0.60 to 0.92).")
        source = em._source(_art("191", sentence), sentence)
        self.assertIsNone(em.extract_follow_up_timepoint(sentence, source))

    def test_ambiguous_thousands_separator_is_not_misread_as_decimal(self):
        sentence = "Median follow-up was 1,200 days (hazard ratio, 0.75; 95% CI, 0.60 to 0.92)."
        source = em._source(_art("192", sentence), sentence)
        self.assertIsNone(em.extract_follow_up_timepoint(sentence, source))


class TestInterventionsAndCoTreatments(unittest.TestCase):
    def setUp(self):
        em.clear_cache()

    def test_background_therapy_is_not_the_intervention(self):
        abstract = ("Participants were randomly assigned to neoadjuvant pembrolizumab or placebo, each of which was given "
                    "with cisplatin-based chemotherapy for 4 cycles. A total of 397 participants were assigned to the "
                    "pembrolizumab group, and 400 to the placebo group. Event-free survival was longer (hazard ratio, "
                    "0.58; 95% CI, 0.46 to 0.72).")
        study = em.build_study(_art("20", abstract, pub_types=["Randomized Controlled Trial"]))
        self.assertEqual([i.name for i in study.interventions], ["pembrolizumab"])
        self.assertEqual([c.name for c in study.comparators], ["placebo"])
        self.assertIn("cisplatin-based chemotherapy", [c.name for c in study.co_treatments])

    def test_observational_exposure_is_labelled_as_exposure(self):
        study = em.build_study(_records()["41208045"])
        self.assertEqual(study.claim_type, "association")
        for intervention in study.interventions:
            self.assertEqual(intervention.role_label, "Maruziyet")


class TestClaimTypes(unittest.TestCase):
    def setUp(self):
        em.clear_cache()

    def test_only_randomized_designs_allow_causal_language(self):
        records = _records()
        expectations = {
            "34449189": True,   # RCT
            "36041474": True,   # meta-analysis of RCTs
            "41208045": False,  # cohort
            "40542785": False,  # case-control
            "41403500": False,  # case series
            "41360588": False,  # diagnostic accuracy
            "40169492": False,  # diagnostic meta-analysis
        }
        for pmid, allowed in expectations.items():
            self.assertEqual(em.build_study(records[pmid]).causal_inference_allowed, allowed, pmid)

    def test_rendered_claims_for_non_randomized_studies_have_no_causal_verbs(self):
        records = _records()
        for pmid in ("41208045", "40542785", "39433008", "31589251", "41613714", "41300987"):
            study = em.build_study(records[pmid])
            text = "\n".join(em.render_study_card_lines(study))
            self.assertEqual(em.find_causal_language(text), [], pmid)

    def test_rob_and_grade_are_never_rated(self):
        for record in _records().values():
            study = em.build_study(record)
            self.assertEqual(study.risk_of_bias.status, "not_assessed")
            self.assertIsNone(study.risk_of_bias.overall_rating)
            self.assertEqual(study.certainty.status, "not_assessed")
            self.assertIsNone(study.certainty.rating)


class TestStudyRelations(unittest.TestCase):
    def setUp(self):
        em.clear_cache()

    def test_secondary_and_updated_reports_link_to_parent_and_are_not_double_counted(self):
        records = _records()
        articles = [records[p] for p in ("34449189", "36129693", "37272513", "39288781", "36041474", "33017106", "34694761")]
        studies, summary = em.build_studies(articles)
        by = {s.pmid: s for s in studies}
        self.assertEqual(by["36129693"].report_role, "secondary_analysis")
        # EMPEROR-Pooled combines multiple cohorts; the shared EMPEROR-Preserved
        # name alone does not make it the same participant cohort as PMID 34449189.
        self.assertNotIn("34449189", {r.related_pmid for r in by["36129693"].relations})
        self.assertEqual(by["39288781"].report_role, "updated_analysis")
        self.assertIn("37272513", {r.related_pmid for r in by["39288781"].relations})
        self.assertEqual(by["34694761"].report_role, "undetermined")
        # PubMed lists both Letter and RCT, but no abstract is available to establish its role.
        self.assertEqual(by["34694761"].relations, [])
        self.assertFalse(by["34694761"].causal_inference_allowed)
        for derived in ("36129693", "39288781", "34694761", "36041474"):
            self.assertFalse(by[derived].counts_as_independent, derived)
        for primary in ("34449189", "37272513", "33017106"):
            self.assertTrue(by[primary].counts_as_independent, primary)
        self.assertEqual(summary["independent_primary_units"], 3)
        self.assertEqual(summary["independent_participants"], 5988 + 797 + 1552)
        self.assertTrue(any("36041474" in note and "34449189" in note for note in summary["overlap_notes"]))

    def test_synthesis_background_mention_is_not_reported_as_included_trial(self):
        primary = _art(
            "70011", "A randomized trial enrolled adults. ClinicalTrials.gov identifier NCT01234567.",
            title="A randomized trial", pub_types=["Randomized Controlled Trial"],
        )
        synthesis = _art(
            "70012",
            "Background: NCT01234567 was an important previous study. "
            "Methods: We reviewed eligible randomized trials of the intervention.",
            title="Systematic review and meta-analysis of the intervention",
            pub_types=["Meta-Analysis"],
        )

        studies, summary = em.build_studies([primary, synthesis])
        synthesis_study = next(study for study in studies if study.pmid == "70012")
        self.assertEqual(synthesis_study.report_role, "evidence_synthesis")
        self.assertEqual(synthesis_study.relations, [])
        self.assertEqual(summary["overlap_notes"], [])

    def test_synthesis_explicit_inclusion_statement_links_trial(self):
        primary = _art(
            "70021", "A randomized trial enrolled adults. ClinicalTrials.gov identifier NCT01234567.",
            title="A randomized trial", pub_types=["Randomized Controlled Trial"],
        )
        synthesis = _art(
            "70022",
            "Methods: Six eligible trials, including NCT01234567, were included in the meta-analysis.",
            title="Systematic review and meta-analysis of the intervention",
            pub_types=["Meta-Analysis"],
        )

        studies, summary = em.build_studies([primary, synthesis])
        synthesis_study = next(study for study in studies if study.pmid == "70022")
        self.assertEqual(
            [(relation.relation_type, relation.related_pmid, relation.confidence)
             for relation in synthesis_study.relations],
            [("includes_trial", "70021", "kesin")],
        )
        self.assertTrue(any("70022" in note and "70021" in note for note in summary["overlap_notes"]))

    def test_synthesis_excluded_or_uncertain_trial_does_not_create_overlap(self):
        primary = _art(
            "70031", "A randomized trial enrolled adults. ClinicalTrials.gov identifier NCT01234567.",
            title="A randomized trial", pub_types=["Randomized Controlled Trial"],
        )
        abstracts = (
            "Methods: NCT01234567 was excluded from the meta-analysis.",
            "Methods: NCT01234567 may have been included in the pooled analysis.",
            "Methods: The review cited NCT01234567 as background; inclusion was uncertain.",
        )

        for index, abstract in enumerate(abstracts, start=1):
            with self.subTest(abstract=abstract):
                synthesis = _art(
                    f"7003{index + 1}", abstract,
                    title="Systematic review and meta-analysis of the intervention",
                    pub_types=["Meta-Analysis"],
                )
                studies, summary = em.build_studies([primary, synthesis])
                synthesis_study = next(study for study in studies if study.report_role == "evidence_synthesis")
                self.assertFalse(synthesis_study.relations)
                self.assertFalse(summary["overlap_notes"])

    def test_shared_registry_number_is_found(self):
        study = em.build_study(_records()["39288781"])
        self.assertIn("NCT03425643", study.registry_ids)
        self.assertIn("KEYNOTE-671", study.trial_acronyms)

    def test_shared_registry_or_acronym_alone_does_not_merge_primary_cohorts(self):
        registry_articles = [
            _art("70001", "A prospective cohort enrolled 100 adults. ClinicalTrials.gov number, NCT01234567.", title="Cohort A"),
            _art("70002", "A prospective cohort enrolled 200 children. ClinicalTrials.gov number, NCT01234567.", title="Cohort B"),
        ]
        registry_studies, registry_summary = em.build_studies(registry_articles)
        self.assertNotEqual(registry_studies[0].evidence_cluster, registry_studies[1].evidence_cluster)
        self.assertEqual(registry_summary["independent_primary_units"], 2)
        self.assertTrue(all(study.counts_as_independent for study in registry_studies))

        acronym_articles = [
            _art("70003", "A prospective cohort enrolled 100 adults.", title="Adults in a prospective cohort (SHARED-TRIAL)"),
            _art("70004", "A prospective cohort enrolled 200 children.", title="Children in a prospective cohort (SHARED-TRIAL)"),
        ]
        acronym_studies, acronym_summary = em.build_studies(acronym_articles)
        self.assertNotEqual(acronym_studies[0].evidence_cluster, acronym_studies[1].evidence_cluster)
        self.assertEqual(acronym_summary["independent_primary_units"], 2)
        self.assertTrue(all(study.counts_as_independent for study in acronym_studies))

    def test_derived_report_with_two_candidate_parents_is_not_linked(self):
        articles = [
            _art("71001", "A prospective randomized trial enrolled 100 adults. NCT01234568.", title="Trial A"),
            _art("71002", "A prospective randomized trial enrolled 200 adults. NCT01234568.", title="Trial B"),
            _art("71003", "This secondary analysis of NCT01234568 reports an outcome.",
                 title="Secondary analysis of NCT01234568"),
        ]
        studies, summary = em.build_studies(articles)
        by = {study.pmid: study for study in studies}
        self.assertEqual(by["71003"].report_role, "secondary_analysis")
        self.assertEqual(by["71003"].relations, [])
        self.assertEqual(len({study.evidence_cluster for study in studies}), 3)
        self.assertFalse(by["71003"].counts_as_independent)
        self.assertEqual(summary["independent_primary_units"], 2)


class TestSingleSourceOfTruth(unittest.TestCase):
    def setUp(self):
        em.clear_cache()

    def test_same_object_is_returned_for_cards_sections_and_export(self):
        record = _records()["34449189"]
        first = em.build_study(record)
        second = em.build_study(dict(record))
        self.assertIs(first, second)

    @patch("report_generator.verify_citation", return_value={"status": "unverified", "verified": False, "error": "offline"})
    def test_sections_5_and_6_and_export_show_model_values(self, _verify):
        records = _records()
        articles = [records["34449189"], records["41360588"]]
        report = rg.generate_rule_based_turkish_report("Empagliflozin versus placebo in heart failure", articles)
        section_5 = report.split("## 5. Bilimsel Kanıt Tablosu")[1].split("## 6.")[0]
        section_6 = report.split("## 6. Önemli Çalışmaların Karşılaştırılması")[1].split("## 7.")[0]
        studies, summary = em.build_studies(articles)
        for study in studies:
            self.assertIn(study.design_label, section_5)
            self.assertIn(study.design_label, section_6)
            self.assertIn(study.claim_type_tr, section_6)
        self.assertIn("Yapılandırılmış Kanıt Kayıtları", section_6)
        self.assertIn("n = 5988", section_6)
        self.assertIn("Tanı Doğruluğu Çalışması", section_5)  # refined design label from the model
        exported = json.loads(em.export_studies_json(studies, summary))
        self.assertEqual(exported["studies"][0]["population"]["n_total"], 5988)
        self.assertEqual(exported["evidence_model_version"], em.EVIDENCE_MODEL_VERSION)
        self.assertIn("Soru Türü ve Çerçeve", report)


class TestCrossStudyComparisonUsesModel(unittest.TestCase):
    def setUp(self):
        em.clear_cache()

    def test_rct_and_cohort_are_not_called_consistent_and_same_trial_is_not_two_studies(self):
        from universal_evidence_engine import UniversalEvidenceEngine
        records = _records()
        articles = [records["34449189"], records["36129693"], records["41208045"]]
        cross = UniversalEvidenceEngine().compare_cross_article_findings(articles, "heart failure mortality")
        for item in cross["consistent_findings"] + cross["conflicting_findings"]:
            self.assertNotIn("41208045", item["articles"])
            self.assertFalse({"34449189", "36129693"} <= set(item["articles"]))
        reasons = " ".join(item["reason"] for item in cross["non_comparable_studies"])
        self.assertIn("tasarım ailesi uyuşmazlığı", reasons)
        self.assertIn("Popülasyon uyuşmazlığı", reasons)
        self.assertNotIn("aynı çalışmanın farklı yayınları", reasons)


class TestReportVerification(unittest.TestCase):
    def setUp(self):
        em.clear_cache()

    def _studies(self):
        records = _records()
        return em.build_studies([records["34449189"], records["41208045"]])[0]

    def test_clean_rendering_verifies(self):
        studies = self._studies()
        report = em.render_structured_evidence_section(studies, em.link_studies(studies))
        result = rv.verify_report(report, studies)
        self.assertEqual(result["status"], rv.STATUS_OK, result)
        self.assertGreater(result["quotes_checked"], 0)

    def test_fabricated_pmid_fails(self):
        result = rv.verify_report("Bulgu (PMID: 99999999).", self._studies())
        self.assertEqual(result["status"], rv.STATUS_FAIL)
        self.assertEqual(result["unknown_pmids"], ["99999999"])

    def test_altered_quote_fails(self):
        report = 'Kaynak cümle: "Empagliflozin doubled survival in every patient with heart failure." (PMID: 34449189)'
        result = rv.verify_report(report, self._studies())
        self.assertEqual(result["status"], rv.STATUS_FAIL)
        self.assertEqual(len(result["quotes_failed"]), 1)

    def test_unassessed_rob_or_grade_rating_fails(self):
        result = rv.verify_report("Yanlılık riski: düşük. GRADE kesinliği: yüksek (PMID: 34449189)", self._studies())
        self.assertEqual(result["status"], rv.STATUS_FAIL)
        self.assertTrue(result["rob_rating_claims"])
        self.assertTrue(result["grade_rating_claims"])

    def test_markdown_grade_rating_fails(self):
        for label in ("**GRADE:** **Yüksek**", "__GRADE:__ __Düşük__"):
            with self.subTest(label=label):
                result = rv.verify_report(label, self._studies())
                self.assertEqual(result["status"], rv.STATUS_FAIL)
                self.assertTrue(result["grade_rating_claims"])

    def test_bracketed_citation_and_curly_quotes_are_checked(self):
        quote = "Empagliflozin doubled survival in every patient with heart failure."
        for report in (f'Kaynak cümle: "{quote}" [PMID: 34449189]',
                       f'Kaynak cümle: “{quote}” [PMID: 34449189](https://pubmed.ncbi.nlm.nih.gov/34449189/)'):
            with self.subTest(report=report):
                result = rv.verify_report(report, self._studies())
                self.assertEqual(result["status"], rv.STATUS_FAIL)
                self.assertEqual(result["quotes_checked"], 1)
                self.assertEqual(len(result["quotes_failed"]), 1)

    def test_causal_wording_on_observational_line_warns(self):
        result = rv.verify_report("Metformin mortaliteyi azalttı (PMID: 41208045).", self._studies())
        self.assertEqual(result["status"], rv.STATUS_WARN)
        self.assertEqual(len(result["causal_language_hits"]), 1)

    def test_footer_shows_version_and_status(self):
        studies = self._studies()
        footer = rv.render_verification_footer(rv.verify_report("", studies), "v9.9.9")
        self.assertIn("v9.9.9", footer)
        self.assertIn("Rapor Doğrulama Durumu", footer)

    def test_derived_sources_are_reported_separately_from_literal_quotes(self):
        studies = self._studies()
        sources = [estimate.source for study in studies for estimate in study.estimates]
        sources += [study.population.source for study in studies if study.population.n_total]
        self.assertTrue(sources)
        for source in sources:
            source.verification_status = em.SOURCE_DERIVED

        result = rv.verify_report("", studies)
        footer = rv.render_verification_footer(result, "v9.9.9")

        self.assertEqual(result["structured_sources_verified"], 0)
        self.assertEqual(result["structured_sources_derived"], len(sources))
        self.assertEqual(result["structured_sources_unverified"], 0)
        self.assertIn("0 kaynak cümlesi birebir doğrulandı", footer)
        self.assertIn(f"{len(sources)} değer kaynaktan hesaplandı", footer)


if __name__ == "__main__":
    unittest.main()
