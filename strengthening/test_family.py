import unittest
import itertools
from fractions import Fraction
from counterexample_family import exact_family, sylvester_integer


class FamilyTests(unittest.TestCase):
    def test_four_bit_reference(self):
        self.assertEqual(exact_family(4,4)['relative_squared_error'], '11/3332')

    def test_three_bit(self):
        self.assertEqual(exact_family(3,4)['relative_squared_error'], '1/66')

    def test_all_registered_examples_and_closed_form(self):
        for bits in range(3,17):
            for n in (4,8,16,32,64,128):
                result=exact_family(bits,n)
                q=2**(bits-1)-1
                value=Fraction(result['relative_squared_error'])
                self.assertGreater(value,0)
                self.assertTrue(result['peak_strictly_lower'])
                self.assertEqual(value,Fraction(exact_family(bits,4)['relative_squared_error']))
                if bits>=5:
                    self.assertEqual(value,Fraction(24,q*q*(q*q+2)))

    def test_all_supported_signs(self):
        for bits in range(3,17):
            for n in (4,8,16,32,64,128):
                expected=exact_family(bits,n)["relative_squared_error"]
                for signs in itertools.product((-1,1),repeat=3):
                    self.assertEqual(exact_family(bits,n,signs)["relative_squared_error"],expected)

    def test_linear_layer_corollary(self):
        for bits in range(3,17):
            k=2**(bits-1)-1
            expected=Fraction(1,81) if bits==3 else Fraction(1,784) if bits==4 else Fraction(16,k**4)
            for n in (4,8,16,32,64,128):
                for signs in itertools.product((-1,1),repeat=3):
                    result=exact_family(bits,n,signs)
                    self.assertEqual(Fraction(result['linear_output_relative_squared_error']),expected)
                    self.assertEqual(result['linear_target'],k)
                    self.assertTrue(result['rotated_weight_exactly_representable'])

    def test_orthogonality(self):
        h=sylvester_integer(8)
        for i in range(8):
            for j in range(8):
                self.assertEqual(sum(h[i][k]*h[j][k] for k in range(8)),8 if i==j else 0)

    def test_invalid(self):
        for b,n in ((1,4),(2,4),(3,2),(4,12),(True,4),(4,True)):
            with self.assertRaises(ValueError): exact_family(b,n)


if __name__=='__main__': unittest.main()
