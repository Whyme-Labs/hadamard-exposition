"""Checks for the claims Part II of the v3 article computes."""
import unittest
import numpy as np
import known_orders as k


def circulant(row):
    row = np.asarray(row)
    return np.array([np.roll(row, i) for i in range(len(row))])


def williamson(a, b, c, d):
    return np.block([[a, b, c, d], [-b, a, -d, c], [-c, d, a, -b], [-d, -c, b, a]])


class ClassicalOrders(unittest.TestCase):
    def test_prime_powers(self):
        self.assertEqual([q for q in range(1, 30) if k.prime_power(q)],
                         [2, 3, 4, 5, 7, 8, 9, 11, 13, 16, 17, 19, 23, 25, 27, 29])

    def test_missing_orders_up_to_200(self):
        r = k.report(200)
        self.assertEqual(r['missing'], [92, 116, 156, 172, 184, 188])
        self.assertEqual((r['reached'], r['multiples_of_four']), (44, 50))

    def test_up_to_1000(self):
        r = k.report(1000)
        self.assertEqual((r['reached'], r['multiples_of_four']), (195, 250))
        self.assertIn(668, r['missing'])

    def test_paley_obstructions(self):
        for n, q1, q2 in [(92, 91, 45), (668, 667, 333)]:
            o = k.paley_obstruction(n)
            self.assertEqual((o['paley_i_q'], o['paley_ii_q']), (q1, q2))
            self.assertFalse(o['paley_i_q_is_prime_power'] or o['paley_ii_q_is_prime_power'])
        self.assertEqual((667, 333), (23 * 29, 9 * 37))


class WilliamsonArray(unittest.TestCase):
    def test_order_twelve_example(self):
        a = np.ones((3, 3), dtype=int)
        b = 2 * np.eye(3, dtype=int) - a
        self.assertTrue(np.array_equal(a @ a + 3 * b @ b, 12 * np.eye(3, dtype=int)))
        h = williamson(a, b, b, b)
        self.assertTrue(set(np.unique(h)) <= {-1, 1})
        self.assertTrue(np.array_equal(h @ h.T, 12 * np.eye(12, dtype=int)))

    def test_array_with_distinct_blocks(self):
        # Williamson matrices with m = 5, found by exhaustive search over symmetric first rows.
        a, b, c = (circulant(r) for r in ([1, 1, -1, -1, 1], [1, -1, 1, 1, -1], [1, -1, -1, -1, -1]))
        self.assertTrue(np.array_equal(a @ a + b @ b + 2 * c @ c, 20 * np.eye(5, dtype=int)))
        h = williamson(a, b, c, c)
        self.assertTrue(np.array_equal(h @ h.T, 20 * np.eye(20, dtype=int)))

    def test_corrupted_entry_rejected(self):
        a = np.ones((3, 3), dtype=int); b = 2 * np.eye(3, dtype=int) - a
        h = williamson(a, b, b, b); h[0, 5] *= -1
        self.assertFalse(np.array_equal(h @ h.T, 12 * np.eye(12, dtype=int)))


if __name__ == '__main__':
    unittest.main()
