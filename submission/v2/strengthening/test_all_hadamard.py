import unittest
from fractions import Fraction
from all_hadamard_checks import witness, verify_all
from exact_checks import paley_prime


class AllHadamardTests(unittest.TestCase):
    def test_non_power_of_two_example(self):
        result=witness(paley_prime(11),4)
        self.assertEqual(result['order'],12)
        self.assertEqual(result['reconstruction_error'],'11/3332')
        self.assertEqual(result['linear_output_error'],'1/784')
        self.assertEqual(Fraction(result['peak_ratio_squared']),Fraction(27,196))

    def test_all_constructions_and_equivalences(self):
        self.assertEqual(verify_all()['cases'],1280)

    def test_corruption_rejected(self):
        h=paley_prime(11); h[2][4]*=-1
        with self.assertRaises(ValueError): witness(h,4)

    def test_support_and_width_rejected(self):
        h=paley_prime(3)
        for bits,support in ((2,(0,1,2)),(True,(0,1,2)),(4,(0,0,1)),(4,(0,1,4))):
            with self.assertRaises(ValueError): witness(h,bits,support)

    def test_non_sign_rejected(self):
        with self.assertRaises(ValueError): witness(paley_prime(3),4,signs=(1,1,0))


if __name__=='__main__': unittest.main()
