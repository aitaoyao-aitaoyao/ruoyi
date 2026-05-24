"""Unit tests for interest calculation engine."""
import pytest
from app.finance.calc_engine import (
    convert_to_monthly_rate,
    calc_equal_installment_plan,
    calc_interest_first_plan,
    calc_bullet_plan,
    calc_installment_annual_rate,
    calc_pos_fee,
)


class TestRateConversion:
    def test_monthly_rate_passthrough(self):
        assert convert_to_monthly_rate(rate=0.01, rate_type="monthly") == pytest.approx(0.01)

    def test_annual_rate_conversion(self):
        assert convert_to_monthly_rate(rate=0.12, rate_type="annual") == pytest.approx(0.01)

    def test_total_interest_rate_derivation_equal_installment(self):
        r = convert_to_monthly_rate(rate=661.85, rate_type="total_interest", amount=10000, periods=12, method="equal_installment")
        assert 0.009 < r < 0.011

    def test_unknown_rate_type_raises(self):
        with pytest.raises(ValueError):
            convert_to_monthly_rate(rate=0.01, rate_type="unknown")


class TestEqualInstallment:
    def test_12_periods_1pct_monthly(self):
        plan = calc_equal_installment_plan(amount=10000, monthly_rate=0.01, periods=12, start_date="2025-01-01")
        assert len(plan) == 12
        assert plan[0]["total_amount"] == pytest.approx(888.49, rel=0.01)
        assert plan[0]["interest"] == pytest.approx(100.00, rel=0.01)
        assert plan[0]["principal"] == pytest.approx(788.49, rel=0.01)
        total_paid = sum(p["total_amount"] for p in plan)
        assert total_paid == pytest.approx(10661.88, rel=0.01)

    def test_single_period(self):
        plan = calc_equal_installment_plan(amount=5000, monthly_rate=0.02, periods=1, start_date="2025-03-15")
        assert len(plan) == 1
        assert plan[0]["principal"] == pytest.approx(5000)
        assert plan[0]["interest"] == pytest.approx(100)

    def test_zero_interest(self):
        plan = calc_equal_installment_plan(amount=12000, monthly_rate=0, periods=12, start_date="2025-01-01")
        assert len(plan) == 12
        for p in plan:
            assert p["principal"] == 1000.0
            assert p["interest"] == 0.0
            assert p["total_amount"] == 1000.0


class TestInterestFirst:
    def test_12_periods(self):
        plan = calc_interest_first_plan(amount=10000, monthly_rate=0.01, periods=12, start_date="2025-01-01")
        assert len(plan) == 12
        for i in range(11):
            assert plan[i]["interest"] == pytest.approx(100.00, rel=0.01)
            assert plan[i]["principal"] == 0
            assert plan[i]["total_amount"] == pytest.approx(100.00, rel=0.01)
        assert plan[11]["interest"] == pytest.approx(100.00, rel=0.01)
        assert plan[11]["principal"] == pytest.approx(10000)
        assert plan[11]["total_amount"] == pytest.approx(10100, rel=0.01)


class TestBullet:
    def test_6_periods(self):
        plan = calc_bullet_plan(amount=20000, monthly_rate=0.015, periods=6, start_date="2025-06-01")
        assert len(plan) == 1
        assert plan[0]["principal"] == pytest.approx(20000)
        assert plan[0]["interest"] == pytest.approx(1800.00, rel=0.01)
        assert plan[0]["total_amount"] == pytest.approx(21800.00, rel=0.01)


class TestInstallmentAnnualRate:
    def test_12_periods_0_6_pct(self):
        r = calc_installment_annual_rate(period_rate=0.006, periods=12)
        assert 0.13 < r < 0.14

    def test_24_periods(self):
        r = calc_installment_annual_rate(period_rate=0.005, periods=24)
        expected = 0.005 * 24 * 24 / 25
        assert r == pytest.approx(expected)


class TestPosFee:
    def test_default_rate(self):
        assert calc_pos_fee(amount=10000, fee_rate=0.006) == 60.0

    def test_custom_rate(self):
        assert calc_pos_fee(amount=5000, fee_rate=0.005) == 25.0
