"""Exact affine arithmetic for finite IEEE-754 binary32 inputs.

Every finite binary32 value is an integer multiple of 2**-149. Products
therefore share the scale 2**-298; Python integers retain the complete dot
product, including the bias. No floating-point operation is used in this
module, including when rounding the exact result directly to binary32.

Weight orientation is explicit: weight_rows[o][k] is the weight multiplying
input_rows[r][k] for output feature o. The streaming helper visits output
features first so a weight row can be discarded after all input rows use it.
"""

from itertools import zip_longest
from operator import index


F32_SIGN = 1 << 31
F32_FRACTION = (1 << 23) - 1
F32_INFINITY = 0x7F800000
ACCUMULATOR_EXPONENT = -298


def _bits(value):
    """Accept an integer bit pattern, including a NumPy uint32 scalar."""
    value = index(value)
    if not 0 <= value < (1 << 32):
        raise ValueError("a binary32 bit pattern must be in [0, 2**32)")
    if (value >> 23) & 0xFF == 0xFF:
        raise ValueError("exact affine arithmetic requires finite binary32 inputs")
    return value


def f32_bits_to_scaled_int(bits):
    """Return I such that the finite binary32 bit pattern equals I * 2**-149.

    Both zero signs map to integer zero. For a normal value with stored
    exponent e and fraction f, I = (+/-)((2**23 + f) << (e - 1)); for a
    subnormal I = (+/-)f. NaNs, infinities and non-integer inputs are rejected.
    """
    bits = _bits(bits)
    exponent = (bits >> 23) & 0xFF
    fraction = bits & F32_FRACTION
    magnitude = ((1 << 23) | fraction) << (exponent - 1) if exponent else fraction
    return -magnitude if bits & F32_SIGN else magnitude


def _round_right_ties_even(magnitude, shift):
    """Round a nonnegative integer divided by 2**shift without using floats."""
    if shift <= 0:
        return magnitude << -shift
    quotient = magnitude >> shift
    remainder = magnitude - (quotient << shift)
    halfway = 1 << (shift - 1)
    return quotient + (remainder > halfway or (remainder == halfway and quotient & 1))


def round_accumulator_to_f32_bits(accumulator):
    """Round S * 2**-298 directly to binary32, nearest with ties to even.

    Exact integer zero returns +0, including exact affine cancellation. A
    negative nonzero value that rounds to zero returns -0. Subnormal results,
    carries into the next exponent and round-to-nearest overflow to infinity
    are handled explicitly. The returned value is an unsigned 32-bit pattern.
    """
    accumulator = index(accumulator)
    if accumulator == 0:
        return 0
    sign = F32_SIGN if accumulator < 0 else 0
    magnitude = abs(accumulator)
    exponent = magnitude.bit_length() - 1 + ACCUMULATOR_EXPONENT

    if exponent < -126:
        # One binary32 subnormal step is 2**-149 = 2**149 accumulator units.
        # A carry to 2**23 is already the encoding of the smallest normal.
        return sign | _round_right_ties_even(magnitude, 149)

    significand = _round_right_ties_even(magnitude, magnitude.bit_length() - 24)
    if significand == 1 << 24:
        significand >>= 1
        exponent += 1
    if exponent > 127:
        return sign | F32_INFINITY
    return sign | ((exponent + 127) << 23) | (significand - (1 << 23))


def exact_affine_accumulator(input_bits, weight_row_bits, bias_bits=0):
    """Return exact S = sum_k Ix[k]*Iw[k] + (Ib << 149).

    Input and weight vectors must have equal length. The result represents
    one output value at scale 2**-298. Zero-length vectors are permitted and
    return the bias. Finite bit-pattern validation is performed on every
    consumed value; no floating-point conversion or reduction is used.
    """
    missing = object()
    total = f32_bits_to_scaled_int(bias_bits) << 149
    for x, w in zip_longest(input_bits, weight_row_bits, fillvalue=missing):
        if x is missing or w is missing:
            raise ValueError("input and weight vectors must have equal length")
        total += f32_bits_to_scaled_int(x) * f32_bits_to_scaled_int(w)
    return total


def iter_exact_affine_rows(input_rows, weight_rows, bias_bits=None):
    """Yield exact output accumulators, streaming one weight row at a time.

    For each output feature o, yield a tuple containing S[r, o] for every
    input row r, where y[r, o] = sum_k x[r, k]*weight[o, k] + bias[o]. Thus
    the iterator is output-major, not input-major. It accepts ordinary
    integer sequences and two-dimensional uint32 arrays without requiring
    NumPy. Input rows must be nonempty as a collection and have equal width.

    Inputs are decoded once. Only one decoded weight row is retained at a
    time; every weight is reused across all input rows. If supplied, the
    bias iterable must contain exactly one value per weight row. Full shape
    and bias-length validation completes when the iterator is exhausted.
    """
    inputs = [tuple(f32_bits_to_scaled_int(value) for value in row) for row in input_rows]
    if not inputs:
        raise ValueError("at least one input row is required")
    width = len(inputs[0])
    if any(len(row) != width for row in inputs):
        raise ValueError("input rows must have equal width")

    missing = object()
    rows = ((row, 0) for row in weight_rows) if bias_bits is None else zip_longest(
        weight_rows, bias_bits, fillvalue=missing
    )
    for raw_weights, raw_bias in rows:
        if raw_weights is missing or raw_bias is missing:
            raise ValueError("one bias value is required for each weight row")
        weights = tuple(f32_bits_to_scaled_int(value) for value in raw_weights)
        if len(weights) != width:
            raise ValueError("a weight row must match the input width")
        bias = f32_bits_to_scaled_int(raw_bias) << 149
        yield tuple(bias + sum(x * w for x, w in zip(row, weights)) for row in inputs)


def absolute_error_numerator(result_bits, accumulator):
    """Return exact |binary32(result_bits) - S*2**-298| in 2**-298 units.

    The result bit pattern must be finite. Zero signs have zero numerical
    error relative to exact zero; compare raw bit patterns when their sign
    distinction matters. This integer permits exact error comparisons.
    """
    return abs((f32_bits_to_scaled_int(result_bits) << 149) - index(accumulator))


def ulp_distance(left_bits, right_bits):
    """Count representable binary32 steps between two finite values.

    Adjacent finite values have distance one. The two zero signs occupy the
    same numerical position, so +0 and -0 have distance zero; -minsubnormal
    and +minsubnormal have distance two. This is a representable-step
    distance, not absolute error divided by a single local spacing.
    """
    left_bits = _bits(left_bits)
    right_bits = _bits(right_bits)
    left_rank = -(left_bits & ~F32_SIGN) if left_bits & F32_SIGN else left_bits
    right_rank = -(right_bits & ~F32_SIGN) if right_bits & F32_SIGN else right_bits
    return abs(left_rank - right_rank)
