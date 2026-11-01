import unittest
from pricing import fair_decimal_no_push, expected_return, binary_dependence

class PricingTests(unittest.TestCase):
    # Entirely synthetic arithmetic tests; not NFL observations.
    def test_fair_price(self):
        self.assertEqual(fair_decimal_no_push(.5), 2)
        with self.assertRaises(ValueError): fair_decimal_no_push(0)
    def test_ev_push(self):
        self.assertAlmostEqual(expected_return(2, .4, .4), 0)
        self.assertAlmostEqual(expected_return(3, .4, .6), .2)
        with self.assertRaises(ValueError): expected_return(2, .6, .6)
    def test_correlation(self):
        self.assertAlmostEqual(binary_dependence(.5, .5, .25), 0)
        self.assertAlmostEqual(binary_dependence(.5, .5, .5), 1)
        self.assertAlmostEqual(binary_dependence(.5, .5, 0), -1)
        with self.assertRaises(ValueError): binary_dependence(.5, .5, .6)
        with self.assertRaises(ValueError): binary_dependence(0, .5, 0)
        with self.assertRaises(ValueError): binary_dependence(float('nan'), .5, 0)

if __name__ == '__main__': unittest.main()
