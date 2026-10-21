"""Exact educational checks, not a proof of the general Hadamard conjecture."""
from fractions import Fraction
from math import isqrt


def is_prime(q: int) -> bool:
    return type(q) is int and q >= 2 and all(q % d for d in range(2, isqrt(q) + 1))


def character(a: int, q: int) -> int:
    value = pow(a % q, (q - 1) // 2, q)
    return -1 if value == q - 1 else value


def paley_prime(q: int) -> list[list[int]]:
    """Paley I over a prime field only; q must be prime and 3 modulo 4."""
    if not is_prime(q) or q % 4 != 3:
        raise ValueError("q must be a prime congruent to 3 modulo 4")
    return [[1] * (q + 1)] + [
        [1] + [character(j - i, q) - int(i == j) for j in range(q)]
        for i in range(q)
    ]


def is_hadamard(h: list[list[int]]) -> bool:
    n = len(h)
    if not n or any(len(r) != n for r in h):
        return False
    if any(type(x) is not int or x not in (-1, 1) for r in h for x in r):
        return False
    return all(sum(a * b for a, b in zip(h[i], h[j])) == (n if i == j else 0)
               for i in range(n) for j in range(n))


def determinant(a: list[list[int]]) -> int:
    """Fraction-free Bareiss elimination with exact division and row pivots."""
    n = len(a)
    if not n or any(len(r) != n for r in a):
        raise ValueError("nonempty square integer matrix required")
    if any(type(x) is not int for r in a for x in r):
        raise ValueError("integer entries required")
    b = [r[:] for r in a]
    sign, previous = 1, 1
    for k in range(n - 1):
        if b[k][k] == 0:
            pivot = next((i for i in range(k + 1, n) if b[i][k]), None)
            if pivot is None:
                return 0
            b[k], b[pivot] = b[pivot], b[k]
            sign = -sign
        current = b[k][k]
        for i in range(k + 1, n):
            for j in range(k + 1, n):
                numerator = b[i][j] * current - b[i][k] * b[k][j]
                if numerator % previous:
                    raise ArithmeticError("Bareiss division was not exact")
                b[i][j] = numerator // previous
        for i in range(k + 1, n):
            b[i][k] = 0
        previous = current
    return sign * b[-1][-1]


def counterexample() -> dict:
    x = list(map(Fraction, (7, 1, 1, 0)))
    h = [[1,1,1,1], [1,-1,1,-1], [1,1,-1,-1], [1,-1,-1,1]]
    z = [sum(x[i] * h[i][j] for i in range(4)) / 2 for j in range(4)]
    scale = max(map(abs, z)) / 7
    rounded = [round(t / scale) * scale for t in z]
    error = sum((a-b)**2 for a,b in zip(z, rounded)) / sum(t*t for t in x)
    if error != Fraction(11, 3332):
        raise ArithmeticError("counterexample failed")
    return {"input": [str(t) for t in x], "transformed": [str(t) for t in z],
            "dequantized": [str(t) for t in rounded], "relative_squared_error": str(error),
            "original_peak": "7", "transformed_peak": "9/2"}


def verify(primes: list[int]) -> dict:
    records = []
    for q in primes:
        h = paley_prime(q)
        if not is_hadamard(h):
            raise ArithmeticError("integer Gram identity failed")
        det = determinant(h)
        n = q + 1
        if abs(det) != n ** (n // 2):
            raise ArithmeticError("determinant equality failed")
        for a in range(q):
            for b in range(q):
                observed = sum(character(x-a, q)*character(x-b, q) for x in range(q))
                if observed != (q-1 if a == b else -1):
                    raise ArithmeticError("quadratic-character identity failed")
        broken = [r[:] for r in h]
        broken[-1][-1] *= -1
        if is_hadamard(broken):
            raise ArithmeticError("corruption was not detected")
        records.append({"q": q, "order": n, "integer_gram_pass": True,
                        "determinant": det, "absolute_determinant_bound": n ** (n // 2),
                        "character_correlations_checked": q*q, "corruption_rejected": True})
    for q in (0, 1, 2, 5, 9, 15, True):
        try:
            paley_prime(q)
        except ValueError:
            pass
        else:
            raise ArithmeticError("invalid Paley input accepted")
    return {"scope": "Exact finite constructions and arithmetic checks, not a universal existence proof.",
            "paley": records, "order_12_matrix": paley_prime(11),
            "rational_counterexample": counterexample(), "invalid_inputs_rejected": True}
