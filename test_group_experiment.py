"""Focused independent fixtures; this suite does not execute the group sweep."""

import unittest

import numpy as np

from group_experiment import (
    CASES,
    GROUP_SIZES,
    OUTPUT_KEYS,
    SEEDS,
    bootstrap_indices,
    expected_scale_counts,
    percentile_interval,
    quantize_groups,
    summarize_setting,
    validate_sweep,
)


def scalar_group_oracle(a, group_size, feature_axis, bits=4):
    """A direct scalar-loop specification, independent of reshape and NumPy rounding."""
    a = np.asarray(a, dtype=float)
    output = np.empty(a.shape)
    feature_count = a.shape[feature_axis]
    outer_count = a.shape[1 - feature_axis]
    scales = np.empty((outer_count, feature_count // group_size))
    limit = 2 ** (bits - 1) - 1
    for outer in range(outer_count):
        for start in range(0, feature_count, group_size):
            coordinates = [(outer, j) if feature_axis == 1 else (j, outer) for j in range(start, start + group_size)]
            maximum = max(abs(float(a[c])) for c in coordinates)
            scale = maximum / limit if maximum else 1.0
            scales[outer, start // group_size] = scale
            for coordinate in coordinates:
                code = max(-limit, min(limit, round(float(a[coordinate]) / scale)))
                output[coordinate] = code * scale
    return output, scales


def row(seed, original, rotated, case="persistent_outlier", group_size=32, **extras):
    return {"seed": seed, "case": case, "group_size": group_size,
            OUTPUT_KEYS[0]: original, OUTPUT_KEYS[1]: rotated, **extras}


class GroupQuantizerTests(unittest.TestCase):
    def test_activation_groups_match_hand_values_and_scalar_oracle(self):
        a = np.array([[7, .5, 14, 3], [21, 4.5, 28, 10]], dtype=float)
        actual = quantize_groups(a, 2, feature_axis=1)
        np.testing.assert_array_equal(actual.values, [[7, 0, 14, 4], [21, 6, 28, 8]])
        np.testing.assert_array_equal(actual.scales, [[1, 2], [3, 4]])
        expected, scales = scalar_group_oracle(a, 2, 1)
        np.testing.assert_array_equal(actual.values, expected)
        np.testing.assert_array_equal(actual.scales, scales)

    def test_weights_group_down_feature_rows_not_output_columns(self):
        a = np.array([[7, 21, 35], [.5, 4.5, 12.5], [14, 28, 42], [3, 10, 21]], dtype=float)
        actual = quantize_groups(a, 2, feature_axis=0)
        np.testing.assert_array_equal(actual.values, [[7, 21, 35], [0, 6, 10], [14, 28, 42], [4, 8, 24]])
        np.testing.assert_array_equal(actual.scales, [[1, 2], [3, 4], [5, 6]])
        expected, scales = scalar_group_oracle(a, 2, 0)
        np.testing.assert_array_equal(actual.values, expected)
        np.testing.assert_array_equal(actual.scales, scales)
        transposed = quantize_groups(a.T, 2, feature_axis=1)
        np.testing.assert_array_equal(actual.values, transposed.values.T)

    def test_noncontiguous_input_and_axis_orientation_match_scalar_oracle(self):
        a = np.arange(-24, 24, dtype=float).reshape(4, 12)[:, ::2] / 3
        original = a.copy()
        for values, axis in ((a, 1), (a.T, 0)):
            actual = quantize_groups(values, 3, feature_axis=axis)
            expected, scales = scalar_group_oracle(values, 3, axis)
            np.testing.assert_allclose(actual.values, expected, rtol=0, atol=2e-15)
            np.testing.assert_allclose(actual.scales, scales, rtol=0, atol=2e-15)
        np.testing.assert_array_equal(a, original)

    def test_signed_halfway_values_use_ties_to_even(self):
        a = np.array([[-7, -2.5, -1.5, -.5, .5, 1.5, 2.5, 7]])
        expected = [[-7, -2, -2, 0, 0, 2, 2, 7]]
        np.testing.assert_array_equal(quantize_groups(a, 8, 1).values, expected)
        np.testing.assert_array_equal(quantize_groups(a.T, 8, 0).values, np.array(expected).T)

    def test_zero_groups_keep_scales_without_polluting_exact_neighbor(self):
        a = np.array([[0, 0, 7, 1], [0, 0, -7, -1]], dtype=float)
        actual = quantize_groups(a, 2, 1)
        np.testing.assert_array_equal(actual.values, a)
        np.testing.assert_array_equal(actual.scales, np.ones((2, 2)))
        self.assertEqual(actual.scales.size, 4)
        self.assertTrue(np.isfinite(actual.values).all())

    def test_frozen_scale_counts_include_all_zero_groups(self):
        activations = np.zeros((512, 128))
        weights = np.zeros((128, 64))
        for group, activation_count, weight_count in [(128, 512, 64), (64, 1024, 128), (32, 2048, 256), (16, 4096, 512)]:
            with self.subTest(group=group):
                self.assertEqual(quantize_groups(activations, group, 1).scales.size, activation_count)
                self.assertEqual(quantize_groups(weights, group, 0).scales.size, weight_count)
                self.assertEqual(expected_scale_counts(group), {"activation_per_arm": activation_count,
                    "weight_per_arm": weight_count, "total_per_arm": activation_count + weight_count})

    def test_rejects_invalid_group_boundaries_and_nonfinite_values(self):
        for a, group, axis in [(np.ones((2, 5)), 2, 1), (np.ones((2, 4)), 0, 1),
                               (np.ones((2, 4)), 2, 2), (np.array([[1, np.nan]]), 2, 1)]:
            with self.subTest(group=group, axis=axis), self.assertRaises(ValueError):
                quantize_groups(a, group, axis)


class PairedSummaryTests(unittest.TestCase):
    def test_constant_paired_difference_has_zero_bootstrap_width(self):
        rows = [row(0, 1, 2), row(1, 10, 11), row(2, 100, 101)]
        indices = np.array([[0, 0, 0], [1, 1, 1], [2, 2, 2], [0, 1, 2]])
        summary = summarize_setting(rows, indices, (0, 1, 2))
        self.assertEqual(summary["output"]["paired_difference_mean"], 1)
        self.assertEqual(summary["output"]["bootstrap_95"]["paired_difference_mean"], [1, 1])
        self.assertEqual(summary["output"]["bootstrap_95"]["paired_difference_percentage_points"], [100, 100])
        self.assertEqual(summary["output"]["rotation_win_count"], 0)

    def test_reduction_is_ratio_of_means_not_mean_seed_reduction(self):
        rows = [row(0, 1, .5), row(1, 100, 20)]
        indices = np.array([[0, 0], [0, 1], [1, 0], [1, 1]])
        output = summarize_setting(rows, indices, (0, 1))["output"]
        self.assertAlmostEqual(output["relative_reduction_in_mean_error"], 80.5 / 101, places=15)
        self.assertNotAlmostEqual(output["relative_reduction_in_mean_error"], .65, places=12)
        expected_draws = [.5, 80.5 / 101, 80.5 / 101, .8]
        ordered = sorted(expected_draws)
        expected_low = ordered[0] + .075 * (ordered[1] - ordered[0])
        expected_high = ordered[2] + .925 * (ordered[3] - ordered[2])
        np.testing.assert_allclose(output["bootstrap_95"]["relative_reduction_in_mean_error"], [expected_low, expected_high], rtol=0, atol=2e-15)

    def test_means_seed_ratios_without_pooling_reference_norms(self):
        rows = [row(0, 1, .5, reference_norm=1), row(1, 0, 0, reference_norm=9)]
        indices = np.array([[0, 1], [1, 0]])
        output = summarize_setting(rows, indices, (0, 1))["output"]
        self.assertEqual(output["original_mean"], .5)
        self.assertEqual(output["rotated_mean"], .25)

    def test_linear_percentiles_and_negative_rotation_sign(self):
        rows = [row(0, 1, 0), row(1, 3, 0)]
        indices = np.array([[0, 0], [0, 1], [1, 0], [1, 1]])
        output = summarize_setting(rows, indices, (0, 1))["output"]
        np.testing.assert_allclose(output["bootstrap_95"]["paired_difference_mean"], [-2.925, -1.075], rtol=0, atol=1e-15)
        self.assertEqual(output["paired_difference_mean"], -2)
        self.assertEqual(output["rotation_win_count"], 2)
        self.assertEqual(percentile_interval(np.array([4.])), [4, 4])

    def test_record_permutation_does_not_change_shared_seed_pairing(self):
        rows = [row(2, 7, 5), row(0, 2, 3), row(1, 10, 8)]
        indices = np.array([[0, 0, 2], [2, 1, 1], [0, 1, 2]])
        first = summarize_setting(rows, indices, (0, 1, 2))
        second = summarize_setting(list(reversed(rows)), indices, (0, 1, 2))
        self.assertEqual(first, second)
        self.assertEqual(first["seed_order"], [0, 1, 2])

    def test_zero_mean_and_undefined_resampled_reductions_stay_explicit(self):
        all_zero = summarize_setting([row(0, 0, 0)], np.array([[0], [0]]), (0,))["output"]
        self.assertIsNone(all_zero["relative_reduction_in_mean_error"])
        self.assertIsNone(all_zero["bootstrap_95"]["relative_reduction_in_mean_error"])
        self.assertEqual(all_zero["rotation_win_count"], 0)
        mixed = summarize_setting([row(0, 0, 0), row(1, 1, .5)], np.array([[0, 0], [0, 1], [1, 1]]), (0, 1))["output"]
        self.assertEqual(mixed["relative_reduction_in_mean_error"], .5)
        self.assertEqual(mixed["bootstrap_reduction_defined_draw_count"], 2)
        self.assertIsNone(mixed["bootstrap_95"]["relative_reduction_in_mean_error"])

    def test_duplicate_missing_mixed_or_invalid_resampling_rows_are_rejected(self):
        good = [row(0, 1, .5), row(1, 2, 1)]
        invalid = [
            ([good[0], good[0]], np.array([[0, 1]])),
            ([good[0]], np.array([[0, 1]])),
            ([good[0], row(1, 2, 1, case="isotropic_gaussian")], np.array([[0, 1]])),
            (good, np.array([[0., 1.]])), (good, np.array([[0, 2]])),
            (good, np.array([[0]])), ([row(0, np.nan, 1), good[1]], np.array([[0, 1]])),
        ]
        for rows, indices in invalid:
            with self.subTest(rows=rows, indices=indices), self.assertRaises(ValueError):
                summarize_setting(rows, indices, (0, 1))

    def test_bootstrap_indices_are_seeded_whole_record_positions(self):
        indices = bootstrap_indices(3, draws=10)
        np.testing.assert_array_equal(indices, bootstrap_indices(3, draws=10))
        self.assertEqual(indices.shape, (10, 3))
        self.assertTrue(np.issubdtype(indices.dtype, np.integer))
        self.assertTrue(((indices >= 0) & (indices < 3)).all())
        with self.assertRaises(ValueError):
            bootstrap_indices(0)

    def test_reference_identity_guard_rejects_duplicate_or_unexpected_rows(self):
        # Identity-only fixtures stop before numerical checks. No sweep is run.
        cells = [{"case": case, "seed": seed, "group_size": group}
                 for case in CASES for seed in SEEDS for group in GROUP_SIZES]
        retained = [{"case": case, "seed": seed} for case in CASES for seed in SEEDS]
        for invalid in (retained + [retained[0]], retained[1:] + [{"case": CASES[0], "seed": 999}]):
            with self.assertRaisesRegex(ValueError, "retained reference identities"):
                validate_sweep(cells, {"records": invalid})


if __name__ == "__main__":
    unittest.main()
