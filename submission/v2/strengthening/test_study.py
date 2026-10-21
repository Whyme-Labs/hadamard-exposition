import unittest
import numpy as np
from study import transforms, quantize_groups, error, summarize


class StudyTests(unittest.TestCase):
    def test_ties_and_zero(self):
        np.testing.assert_array_equal(quantize_groups(np.array([[7.,.5,1.5,2.5]]),4,1),[[7,0,2,2]])
        np.testing.assert_array_equal(quantize_groups(np.zeros((4,4)),2,0),np.zeros((4,4)))

    def test_group_orientation(self):
        a=np.array([[7.,1.,4.,1.],[.5,1.5,2.5,7.]])
        np.testing.assert_array_equal(quantize_groups(a,2,1).T,quantize_groups(a.T,2,0))

    def test_reject_bad_groups_and_values(self):
        for a,g,axis in [(np.ones((2,4)),3,1),(np.ones((2,4)),True,1),(np.ones((2,4)),0,1),
                         (np.ones((2,4)),2,2),(np.array([[float('nan'),1.]]),2,1)]:
            with self.assertRaises(ValueError): quantize_groups(a,g,axis)

    def test_all_transforms_orthogonal_and_compensated(self):
        x=np.arange(24.).reshape(3,8); w=np.arange(32.).reshape(8,4)
        for name,q in transforms(3,8).items():
            with self.subTest(name=name):
                np.testing.assert_allclose(q@q.T,np.eye(8),atol=2e-14)
                self.assertLess(error((x@q)@(q.T@w),x@w),1e-27)

    def test_signed_permutation_preserves_full_group_error(self):
        r=np.random.default_rng(3); x=r.normal(size=(5,8)); w=r.normal(size=(8,3))
        q=transforms(3,8)['signed_permutation']; y=x@w
        a=error(quantize_groups(x,8,1)@quantize_groups(w,8,0),y)
        b=error(quantize_groups(x@q,8,1)@quantize_groups(q.T@w,8,0),y)
        self.assertAlmostEqual(a,b,places=14)

    def test_non_power_of_two_rejected(self):
        with self.assertRaises(ValueError): transforms(1,12)

    def test_zero_reference_rejected(self):
        with self.assertRaises(ValueError): error(np.zeros(2),np.zeros(2))

    def test_summary_pairing_and_coverage(self):
        records=[dict(seed=s,case='gaussian_outlier',multiplier=32,group=32,arm=arm,error=e)
                 for s,e0 in [(1000,.04),(1001,.02)] for arm,e in [('original',e0),('randomized_hadamard',e0/2)]]
        result=summarize(records,['original','randomized_hadamard'],[1000,1001],100,1)
        self.assertAlmostEqual(result[0]['arms']['original']['mean_error'],.03)
        self.assertEqual(result[0]['arms']['randomized_hadamard']['wins_vs_original'],2)
        with self.assertRaises(ValueError): summarize(records+records[:1],['original','randomized_hadamard'],[1000,1001],100,1)
        with self.assertRaises(ValueError): summarize(records[:-1],['original','randomized_hadamard'],[1000,1001],100,1)


if __name__=='__main__': unittest.main()
