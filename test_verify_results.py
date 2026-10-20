"""Negative controls for the independent retained-result verifier."""

import copy
from pathlib import Path
import tempfile
import unittest

from scripts.verify_results import ROOT, compare_reproduction, load, verify_group, verify_reference


class RetainedResultControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference = load(ROOT / "results.json")
        cls.group = load(ROOT / "group-results.json")

    def test_reference_has_sixty_records_and_arithmetic_seed_summaries(self):
        result = verify_reference(self.reference, ROOT)
        self.assertEqual(result["records"], 60)
        altered = copy.deepcopy(self.reference)
        altered["summary"]["persistent_outlier"]["metrics"]["linear_output_relative_squared_error_original"]["mean"] *= 1.05
        with self.assertRaisesRegex(ValueError, "reference summary"):
            verify_reference(altered, ROOT)

    def test_all_grouped_cells_and_whole_seed_summaries_verify(self):
        result = verify_group(self.group, self.reference, ROOT)
        self.assertEqual(result["paired_cells"], 160)
        self.assertEqual(result["settings"], 8)
        self.assertEqual(result["bootstrap_draws_per_setting"], 10000)

    def test_rejects_duplicate_missing_and_nonfinite_cells(self):
        for corruption in ("duplicate", "missing", "nonfinite"):
            with self.subTest(corruption=corruption):
                altered = copy.deepcopy(self.group)
                if corruption == "duplicate":
                    altered["records"][-1] = copy.deepcopy(altered["records"][0])
                elif corruption == "missing":
                    altered["records"].pop()
                else:
                    altered["records"][0]["linear_output_relative_squared_error_original"] = float("nan")
                with self.assertRaises(ValueError):
                    verify_group(altered, self.reference, ROOT)

    def test_rejects_stale_protocol_identity_or_unmatched_scales(self):
        altered = copy.deepcopy(self.group)
        altered["provenance"]["sha256"]["protocol"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source/protocol/reference"):
            verify_group(altered, self.reference, ROOT)
        altered = copy.deepcopy(self.group)
        altered["records"][3]["scale_counts"]["activation_rotated"] += 1
        with self.assertRaisesRegex(ValueError, "matched scale counts"):
            verify_group(altered, self.reference, ROOT)

    def test_rejects_failed_or_incomplete_outer_process_observations(self):
        for corruption in ("failed", "missing", "over_budget"):
            with self.subTest(corruption=corruption):
                altered = copy.deepcopy(self.group)
                altered["timing"].update(outer_process_wall_seconds=2.0, outer_timeout_seconds=180, outer_process_exit_code=0)
                if corruption == "failed":
                    altered["timing"]["outer_process_exit_code"] = 1
                elif corruption == "missing":
                    del altered["timing"]["outer_process_wall_seconds"]
                else:
                    altered["timing"]["outer_process_wall_seconds"] = 181.0
                with self.assertRaisesRegex(ValueError, "outer"):
                    verify_group(altered, self.reference, ROOT)

    def test_rejects_wrong_mean_paired_difference_wins_or_reduction(self):
        for field in ("original_mean", "paired_difference_mean", "relative_reduction_in_mean_error", "rotation_win_count"):
            with self.subTest(field=field):
                altered = copy.deepcopy(self.group)
                altered["summaries"][0]["output"][field] += 1
                with self.assertRaisesRegex(ValueError, "summary"):
                    verify_group(altered, self.reference, ROOT)

    def test_rejects_broken_bootstrap_pairing_or_diagnostic_interval(self):
        altered = copy.deepcopy(self.group)
        output = altered["summaries"][0]["output"]
        # The sum of marginal uncertainties is not the interval for paired differences.
        original, rotated = output["bootstrap_95"]["original_mean"], output["bootstrap_95"]["rotated_mean"]
        output["bootstrap_95"]["paired_difference_mean"] = [rotated[0] - original[1], rotated[1] - original[0]]
        with self.assertRaisesRegex(ValueError, "bootstrap_95"):
            verify_group(altered, self.reference, ROOT)
        altered = copy.deepcopy(self.group)
        altered["summaries"][0]["diagnostics"]["weight_relative_squared_error_original"]["bootstrap_95"][1] += .01
        with self.assertRaisesRegex(ValueError, "bootstrap_95"):
            verify_group(altered, self.reference, ROOT)

    def test_reproduction_checks_all_deterministic_sections(self):
        reproduced = copy.deepcopy(self.group)
        reproduced["started_utc"] = "a different run"
        reproduced["timing"]["total_run_wall_seconds"] += 1
        self.assertEqual(compare_reproduction(self.group, reproduced)["status"], "passed")
        reproduced["configuration"]["bits"] = 8
        with self.assertRaisesRegex(ValueError, "reproduction.configuration"):
            compare_reproduction(self.group, reproduced)


class JsonControls(unittest.TestCase):
    def test_rejects_duplicate_json_keys_and_nonfinite_literals(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            for source in ('{"x": 1, "x": 2}', '{"x": NaN}', '{"x": Infinity}'):
                with self.subTest(source=source):
                    path.write_text(source)
                    with self.assertRaises(ValueError):
                        load(path)


if __name__ == "__main__":
    unittest.main()
