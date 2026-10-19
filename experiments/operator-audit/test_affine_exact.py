"""Synthetic controls for exact affine arithmetic; no model or trace inputs."""

from fractions import Fraction
import math
import random
import struct
import unittest

from affine_exact import (
    absolute_error_numerator,
    exact_affine_accumulator,
    f32_bits_to_scaled_int,
    iter_exact_affine_rows,
    round_accumulator_to_f32_bits,
    ulp_distance,
)


def bits(value):
    return struct.unpack("<I", struct.pack("<f", value))[0]


def value(pattern):
    return struct.unpack("<f", struct.pack("<I", pattern))[0]


class ScaledIntegerTests(unittest.TestCase):
    def test_hand_decodings(self):
        cases = {
            0x00000000: 0,
            0x80000000: 0,
            0x00000001: 1,
            0x80000001: -1,
            0x007FFFFF: (1 << 23) - 1,
            0x00800000: 1 << 23,
            0x3F800000: 1 << 149,
            0xBF800000: -(1 << 149),
            0x7F7FFFFF: ((1 << 24) - 1) << 253,
            0xFF7FFFFF: -(((1 << 24) - 1) << 253),
        }
        for pattern, expected in cases.items():
            with self.subTest(pattern=hex(pattern)):
                self.assertEqual(f32_bits_to_scaled_int(pattern), expected)

    def test_decoding_against_exact_rationals(self):
        rng = random.Random(20261019)
        patterns = [rng.randrange(1 << 32) for _ in range(256)]
        for pattern in patterns:
            if (pattern >> 23) & 0xFF == 0xFF:
                continue
            with self.subTest(pattern=hex(pattern)):
                rational = Fraction.from_float(value(pattern))
                self.assertEqual(Fraction(f32_bits_to_scaled_int(pattern), 1 << 149), rational)

    def test_nonfinite_and_invalid_patterns_rejected(self):
        for pattern in [0x7F800000, 0xFF800000, 0x7FC00000, 0x7F800001, 0xFFC00000, -1, 1 << 32]:
            with self.subTest(pattern=pattern):
                with self.assertRaises(ValueError):
                    f32_bits_to_scaled_int(pattern)
        with self.assertRaises(TypeError):
            f32_bits_to_scaled_int(1.0)


class DirectRoundingTests(unittest.TestCase):
    def test_exact_representable_values_round_trip(self):
        patterns = [0, 1, 2, 0x007FFFFF, 0x00800000, 0x3EAAAAAB, 0x3F800000, 0x7F7FFFFF]
        for pattern in patterns:
            for signed in [pattern, pattern | 0x80000000]:
                with self.subTest(pattern=hex(signed)):
                    scaled = f32_bits_to_scaled_int(signed) << 149
                    expected = 0 if not pattern else signed
                    self.assertEqual(round_accumulator_to_f32_bits(scaled), expected)

    def test_subnormal_midpoints_and_signed_tiny_zero(self):
        half_step = 1 << 148
        cases = [
            (1, 0x00000000),
            (-1, 0x80000000),
            (half_step, 0x00000000),
            (-half_step, 0x80000000),
            (half_step + 1, 0x00000001),
            (-half_step - 1, 0x80000001),
            (3 * half_step, 0x00000002),
            (5 * half_step, 0x00000002),
            (5 * half_step + 1, 0x00000003),
        ]
        for accumulator, expected in cases:
            with self.subTest(accumulator=accumulator):
                self.assertEqual(round_accumulator_to_f32_bits(accumulator), expected)

    def test_carry_from_subnormal_to_normal(self):
        midpoint = ((1 << 24) - 1) << 148
        self.assertEqual(round_accumulator_to_f32_bits(midpoint - 1), 0x007FFFFF)
        self.assertEqual(round_accumulator_to_f32_bits(midpoint), 0x00800000)
        self.assertEqual(round_accumulator_to_f32_bits(midpoint + 1), 0x00800000)
        self.assertEqual(round_accumulator_to_f32_bits(-midpoint), 0x80800000)

    def test_normal_midpoints_and_exponent_carry(self):
        one = 1 << 298
        half_ulp = 1 << 274
        self.assertEqual(round_accumulator_to_f32_bits(one + half_ulp - 1), 0x3F800000)
        self.assertEqual(round_accumulator_to_f32_bits(one + half_ulp), 0x3F800000)
        self.assertEqual(round_accumulator_to_f32_bits(one + half_ulp + 1), 0x3F800001)
        self.assertEqual(round_accumulator_to_f32_bits(one + 3 * half_ulp), 0x3F800002)
        self.assertEqual(round_accumulator_to_f32_bits(-one - half_ulp), 0xBF800000)
        below_two_midpoint = (1 << 299) - half_ulp
        self.assertEqual(round_accumulator_to_f32_bits(below_two_midpoint - 1), 0x3FFFFFFF)
        self.assertEqual(round_accumulator_to_f32_bits(below_two_midpoint), 0x40000000)

    def test_overflow_threshold(self):
        # max_finite + half of its ULP = (2**25 - 1) * 2**103.
        midpoint = ((1 << 25) - 1) << (103 + 298)
        self.assertEqual(round_accumulator_to_f32_bits(midpoint - 1), 0x7F7FFFFF)
        self.assertEqual(round_accumulator_to_f32_bits(midpoint), 0x7F800000)
        self.assertEqual(round_accumulator_to_f32_bits(midpoint + 1), 0x7F800000)
        self.assertEqual(round_accumulator_to_f32_bits(-midpoint), 0xFF800000)

    def test_float64_double_rounding_counterexample(self):
        # 1 + 2**-24 is a binary32 midpoint. The positive 2**-80 perturbation
        # is lost by an intermediate binary64 rounding, reversing the answer.
        accumulator = (1 << 298) + (1 << 274) + (1 << 218)
        direct = round_accumulator_to_f32_bits(accumulator)
        via_float64 = bits(float(Fraction(accumulator, 1 << 298)))
        self.assertEqual(direct, 0x3F800001)
        self.assertEqual(via_float64, 0x3F800000)

    def test_independent_midpoint_neighborhood_oracle(self):
        # Use exact rational distances to independently choose each neighbor;
        # the fixtures straddle zero, subnormal/normal and exponent boundaries.
        for lower in [0, 1, 2, 0x007FFFFF, 0x00800000, 0x3F7FFFFF, 0x3F800000, 0x3FFFFFFF, 0x7F7FFFFE]:
            upper = lower + 1
            a = Fraction.from_float(value(lower))
            b = Fraction.from_float(value(upper))
            midpoint_scaled = ((a + b) / 2) * (1 << 298)
            self.assertEqual(midpoint_scaled.denominator, 1)
            for offset in [-1, 0, 1]:
                s = midpoint_scaled.numerator + offset
                exact = Fraction(s, 1 << 298)
                distances = [(abs(exact - a), lower & 1, lower), (abs(exact - b), upper & 1, upper)]
                expected = min(distances)[2]
                with self.subTest(lower=hex(lower), offset=offset):
                    self.assertEqual(round_accumulator_to_f32_bits(s), expected)
                    expected_negative = expected | 0x80000000 if s else 0
                    self.assertEqual(round_accumulator_to_f32_bits(-s), expected_negative)


class AffineTests(unittest.TestCase):
    def test_non_square_orientation_and_bias(self):
        inputs = [[bits(x) for x in row] for row in [[1.25, -2.0, 0.5], [0.0, 1.0, -2.0]]]
        weights = [[bits(x) for x in row] for row in [[2.0, -3.0, 4.0], [-1.0, 0.25, 8.0]]]
        biases = [bits(0.25), bits(-0.5)]
        output_columns = list(iter_exact_affine_rows(inputs, weights, biases))
        expected_columns = [(10.75, -10.75), (1.75, -16.25)]
        for accumulators, expected in zip(output_columns, expected_columns):
            for accumulator, wanted in zip(accumulators, expected):
                self.assertEqual(Fraction(accumulator, 1 << 298), Fraction(wanted))
                self.assertEqual(round_accumulator_to_f32_bits(accumulator), bits(wanted))
        self.assertEqual(exact_affine_accumulator(inputs[0], weights[0], biases[0]), output_columns[0][0])
        with self.assertRaisesRegex(ValueError, "input width"):
            list(iter_exact_affine_rows(inputs, zip(*weights), [0, 0, 0]))

    def test_exact_affine_against_independent_fraction_products(self):
        # Includes severe cancellation, subnormal products, large exponents,
        # and a nonzero bias. Binary32 -> Python float conversion is exact.
        x = [0x3F800001, 0xBF800000, 0x00000001, 0x7F000000, 0x80000001]
        w = [0x3F800001, 0x3F800002, 0x00000003, 0x00800000, 0x007FFFFF]
        bias = 0xB3000000
        exact = sum(Fraction.from_float(value(a)) * Fraction.from_float(value(b)) for a, b in zip(x, w))
        exact += Fraction.from_float(value(bias))
        accumulator = exact_affine_accumulator(x, w, bias)
        self.assertEqual(Fraction(accumulator, 1 << 298), exact)

    def test_affine_legal_fp32_double_rounding_fixture(self):
        # All operands are representable binary32 values. Their exact affine
        # result is 1 + 2**-24 + 2**-54, just above a binary32 midpoint.
        x = [bits(math.ldexp(1.0, -12)), bits(math.ldexp(1.0, -27))]
        accumulator = exact_affine_accumulator(x, x, bits(1.0))
        self.assertEqual(accumulator, (1 << 298) + (1 << 274) + (1 << 244))
        self.assertEqual(round_accumulator_to_f32_bits(accumulator), 0x3F800001)
        self.assertEqual(bits(float(Fraction(accumulator, 1 << 298))), 0x3F800000)

    def test_exact_zero_cancellation_and_negative_underflow(self):
        cancelled = exact_affine_accumulator([bits(1.0), bits(-1.0)], [bits(1.0), bits(1.0)], 0x80000000)
        self.assertEqual(cancelled, 0)
        self.assertEqual(round_accumulator_to_f32_bits(cancelled), 0)
        tiny_negative = exact_affine_accumulator([0x80000001], [0x00000001])
        self.assertEqual(tiny_negative, -1)
        self.assertEqual(round_accumulator_to_f32_bits(tiny_negative), 0x80000000)

    def test_shape_bias_length_and_nonfinite_guards(self):
        for inputs, weights, biases in [
            ([], [[0]], [0]),
            ([[0], [0, 0]], [[0]], [0]),
            ([[0]], [[0, 0]], [0]),
            ([[0]], [[0]], []),
            ([[0]], [[0]], [0, 0]),
        ]:
            with self.subTest(inputs=inputs, weights=weights, biases=biases):
                with self.assertRaises(ValueError):
                    list(iter_exact_affine_rows(inputs, weights, biases))
        with self.assertRaises(ValueError):
            exact_affine_accumulator([0], [0, 0])
        with self.assertRaises(ValueError):
            exact_affine_accumulator([0x7F800000], [0])
        with self.assertRaises(ValueError):
            list(iter_exact_affine_rows([[0]], [[0]], [0x7FC00000]))
        self.assertEqual(exact_affine_accumulator([], [], bits(1.0)), 1 << 298)
        self.assertEqual(list(iter_exact_affine_rows([[0]], [[0]])), [(0,)])

    def test_streams_weight_rows_without_lookahead(self):
        def weights():
            yield [bits(2.0)]
            raise RuntimeError("second row was requested")

        stream = iter_exact_affine_rows([[bits(3.0)], [bits(4.0)]], weights())
        self.assertEqual(next(stream), (6 << 298, 8 << 298))
        with self.assertRaisesRegex(RuntimeError, "second row"):
            next(stream)


class ErrorHelperTests(unittest.TestCase):
    def test_exact_error_and_zero_sign_distinction(self):
        self.assertEqual(absolute_error_numerator(0x80000000, 0), 0)
        self.assertEqual(absolute_error_numerator(0x3F800001, 1 << 298), 1 << 275)
        self.assertEqual(ulp_distance(0x00000000, 0x80000000), 0)
        self.assertNotEqual(0x00000000, 0x80000000)
        self.assertEqual(ulp_distance(0x80000001, 0x00000001), 2)
        self.assertEqual(ulp_distance(0x3F7FFFFF, 0x3F800000), 1)
        self.assertEqual(ulp_distance(0xBF800001, 0xBF800000), 1)
        with self.assertRaises(ValueError):
            absolute_error_numerator(0x7F800000, 0)
        with self.assertRaises(ValueError):
            ulp_distance(0, 0x7F800000)


if __name__ == "__main__":
    unittest.main()
