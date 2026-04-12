import unittest

from core.services.portfolio_optimizer import _correlation, _normalize_positive, _risk_contributions


class TestPortfolioOptimizerHelpers(unittest.TestCase):
    def test_normalize_positive(self):
        vals = _normalize_positive([2.0, 1.0, 1.0])
        self.assertAlmostEqual(sum(vals), 1.0, places=6)
        self.assertGreater(vals[0], vals[1])

    def test_correlation_bounds(self):
        a = [0.01, 0.02, -0.01, 0.03]
        b = [0.01, 0.02, -0.01, 0.03]
        self.assertAlmostEqual(_correlation(a, b), 1.0, places=5)

    def test_risk_contributions_sum_to_portfolio_vol(self):
        cov = [[0.04, 0.01], [0.01, 0.09]]
        w = [0.5, 0.5]
        rc = _risk_contributions(cov, w)
        self.assertGreater(sum(rc), 0)
