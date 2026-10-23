"""Exact reach of the Sylvester, Paley and Kronecker-product constructions.

The v3 article uses this to check which small orders those classical methods
cover. It proves nothing about orders they miss; other methods may cover them.
"""
from __future__ import annotations
import argparse
import json


def prime_power(q: int) -> bool:
    """Return True when q is p**k for a prime p and k >= 1."""
    if q < 2:
        return False
    p = 2
    while p * p <= q:
        if q % p == 0:
            while q % p == 0:
                q //= p
            return q == 1
        p += 1
    return True


def classical_orders(limit: int) -> set[int]:
    """Orders up to limit reached from 1 and 2 by Paley I, Paley II and products."""
    base = {1, 2}
    for q in range(2, limit + 1):
        if prime_power(q):
            if q % 4 == 3 and q + 1 <= limit:
                base.add(q + 1)
            if q % 4 == 1 and 2 * (q + 1) <= limit:
                base.add(2 * (q + 1))
    reached = set(base)
    changed = True
    while changed:
        changed = False
        for a in sorted(reached):
            for b in sorted(base):
                if a * b <= limit and a * b not in reached:
                    reached.add(a * b)
                    changed = True
    return reached


def paley_obstruction(n: int) -> dict:
    """Why neither Paley construction gives order n directly."""
    return {'order': n, 'paley_i_q': n - 1, 'paley_i_q_is_prime_power': prime_power(n - 1),
            'paley_ii_q': n // 2 - 1, 'paley_ii_q_is_prime_power': n % 2 == 0 and prime_power(n // 2 - 1)}


def report(limit: int) -> dict:
    reached = classical_orders(limit)
    missing = [n for n in range(4, limit + 1, 4) if n not in reached]
    return {'schema': 'hadamard-v3-classical-orders.v1', 'limit': limit,
            'scope': 'Sylvester doubling, prime-power Paley I and II, and Kronecker products only. '
                     'A missing order is not a nonexistence claim.',
            'multiples_of_four': limit // 4, 'reached': sum(1 for n in range(4, limit + 1, 4) if n in reached),
            'first_missing': missing[0] if missing else None, 'missing': missing,
            'order_668': paley_obstruction(668), 'order_2396': paley_obstruction(2396)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int, default=200)
    print(json.dumps(report(parser.parse_args().limit), indent=2))
