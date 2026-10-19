"""Synthetic acceptance-boundary controls; no real trace or matrix evaluation."""

from copy import deepcopy
import unittest

from run_audit import CASE_IDS, classify_candidate


def complete_cases():
    return [{"id": name, "candidate": [
        {"rows": rows, "checked_final_values": width, "completed": True,
         "fp32_vs_exact": {"bit_mismatches": 0}} for rows in (1, 513)
    ]} for name, width in zip(CASE_IDS, (1536, 2048, 1536, 2048), strict=True)]


class CandidateClassificationTests(unittest.TestCase):
    def test_complete_population_is_exactly_14336_primary_values(self):
        result = classify_candidate(complete_cases())
        self.assertEqual(result["checked_final_values"], 14336)
        self.assertEqual(result["status"], "qualified_for_tested_final_positions")
        self.assertFalse(result["campaign_ready"])
        self.assertFalse(result["general_correct_rounding_guarantee"])

    def test_one_bit_miss_rejects_candidate_without_invalidating_completion(self):
        cases = complete_cases()
        cases[2]["candidate"][1]["fp32_vs_exact"]["bit_mismatches"] = 1
        result = classify_candidate(cases)
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["bit_mismatches"], 1)
        self.assertEqual(result["checked_final_values"], 14336)

    def test_missing_duplicate_reordered_and_extra_cases_are_invalid(self):
        cases = complete_cases()
        for malformed in (cases[:-1], [cases[0], cases[0], *cases[2:]],
                          list(reversed(cases)), cases + [cases[0]]):
            with self.subTest(ids=[c["id"] for c in malformed]), self.assertRaises(ValueError):
                classify_candidate(malformed)

    def test_incomplete_wrong_shape_or_wrong_value_count_cannot_qualify(self):
        for field, value in (("completed", False), ("rows", 512),
                             ("checked_final_values", 1535), ("checked_final_values", True)):
            cases = complete_cases()
            cases[0]["candidate"][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                classify_candidate(cases)
        cases = complete_cases()
        cases[0]["candidate"].pop()
        with self.assertRaises(ValueError):
            classify_candidate(cases)

    def test_impossible_mismatch_counts_are_rejected(self):
        for value in (-1, 1537, True, 0.0, None):
            cases = deepcopy(complete_cases())
            cases[0]["candidate"][0]["fp32_vs_exact"]["bit_mismatches"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                classify_candidate(cases)


if __name__ == "__main__":
    unittest.main()
