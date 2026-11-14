"""Unit tests for scripts/gates.py.

Every bet below is a SYNTHETIC fixture written to exercise the decision rules. None is a result,
price or strategy from this repository, and none may be published as a finding.
"""
import math
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import gates  # noqa: E402


def make_bets(n, bet_price, close_price, win_rate, stake=1.0, seed=7):
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        if rng.random() < win_rate:
            out.append(gates.Bet(bet_price, close_price, stake, stake * 100 / 110, "W"))
        else:
            out.append(gates.Bet(bet_price, close_price, stake, -stake, "L"))
    return out


class ImpliedProbTests(unittest.TestCase):
    def test_american_to_probability(self):
        self.assertAlmostEqual(gates.implied_prob(-110), 110 / 210)
        self.assertAlmostEqual(gates.implied_prob(150), 100 / 250)

    def test_clv_sign(self):
        # Bet at -105 vs close at -115: bet was priced better than the close, so CLV > 0.
        self.assertGreater(gates.clv(-105, -115), 0)
        self.assertLess(gates.clv(-115, -105), 0)

    def test_zero_odds_rejected(self):
        with self.assertRaises(ValueError):
            gates.implied_prob(0)


class DemotionTests(unittest.TestCase):
    def test_small_sample_holds_even_when_clv_is_bad(self):
        bets = make_bets(50, -115, -105, 0.5)  # negative CLV, but n < N_MIN
        res = gates.evaluate(bets)
        self.assertEqual(res["decision"], gates.DECISION_HOLD)

    def test_large_negative_clv_demotes(self):
        bets = make_bets(400, -115, -105, 0.5)  # consistently priced worse than the close
        res = gates.evaluate(bets)
        self.assertLess(res["signal"]["upper_95_one_sided"], 0)
        self.assertEqual(res["decision"], gates.DECISION_DEMOTE)

    def test_lucky_staking_run_cannot_mask_bad_signal(self):
        # Same bad signal, but every bet wins: ROI is strongly positive yet the decision is DEMOTE.
        bets = [gates.Bet(-115, -105, 1.0, 100 / 115, "W") for _ in range(400)]
        res = gates.evaluate(bets)
        self.assertGreater(res["staking"]["roi"], 0)
        self.assertEqual(res["decision"], gates.DECISION_DEMOTE)
        self.assertFalse(res["staking"]["drives_decision"])

    def test_bad_staking_run_cannot_demote_good_signal(self):
        # Positive CLV (bet -105 vs close -115), but every bet loses: ROI negative, signal good.
        bets = [gates.Bet(-105, -115, 1.0, -1.0, "L") for _ in range(400)]
        res = gates.evaluate(bets)
        self.assertLess(res["staking"]["roi"], 0)
        self.assertEqual(res["decision"], gates.DECISION_KEEP_LIVE)

    def test_pushes_excluded_from_roi_but_counted_in_clv(self):
        bets = [gates.Bet(-110, -110, 1.0, 0.0, "P") for _ in range(10)]
        res = gates.evaluate(bets)
        self.assertEqual(res["n_bets"], 10)
        self.assertEqual(res["staking"]["staked_bets"], 0)
        self.assertTrue(math.isnan(res["staking"]["roi"]))

    def test_only_live_strategies_are_evaluated(self):
        with self.assertRaises(ValueError):
            gates.evaluate([], current_state="paper")


if __name__ == "__main__":
    unittest.main()
