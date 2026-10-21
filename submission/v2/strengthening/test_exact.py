import itertools
import unittest
from exact_checks import counterexample, determinant, is_hadamard, paley_prime, verify


def leibniz(a):
    total = 0
    for p in itertools.permutations(range(len(a))):
        inversions = sum(p[i] > p[j] for i in range(len(p)) for j in range(i+1, len(p)))
        value = (-1)**inversions
        for i,j in enumerate(p):
            value *= a[i][j]
        total += value
    return total


class ExactTests(unittest.TestCase):
    def test_paley_worked_example(self):
        self.assertTrue(is_hadamard(paley_prime(11)))
        self.assertEqual(abs(determinant(paley_prime(11))), 2985984)

    def test_bad_inputs(self):
        for q in (0,1,2,5,9,15,True,11.0):
            with self.subTest(q=q), self.assertRaises(ValueError):
                paley_prime(q)

    def test_bad_matrices(self):
        for h in ([], [[1,1]], [[True]], [[2]], [[1,1],[1,1]]):
            self.assertFalse(is_hadamard(h))

    def test_rational_example(self):
        self.assertEqual(counterexample()['relative_squared_error'], '11/3332')

    def test_determinant_against_independent_permutation_sum(self):
        for values in itertools.product((-1,0,1), repeat=4):
            a = [list(values[:2]),list(values[2:])]
            self.assertEqual(determinant(a), leibniz(a))
        for a in ([[0,1,2],[3,4,5],[6,7,8]], [[2,3,4],[5,-6,7],[8,9,10]], paley_prime(3)):
            self.assertEqual(determinant(a), leibniz(a))

    def test_all_registered_constructions(self):
        report = verify([3,7,11,19,23,31,43])
        self.assertEqual(len(report['paley']),7)


if __name__ == '__main__':
    unittest.main()
