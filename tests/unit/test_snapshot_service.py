"""Tests for debt snapshot service."""
from datetime import date
from app.finance.snapshot_service import compute_snapshot


class TestComputeSnapshot:
    def test_empty_db_returns_zeros(self, db_session):
        snap = compute_snapshot(db_session, date.today())
        assert snap["total_debt"] == 0
        assert snap["loan_debt"] == 0
        assert snap["card_debt"] == 0

    def test_sums_active_loans(self, db_session):
        from app.models import Person, LoanPlatform, Loan
        p = Person(name="T", relation="本人")
        lp = LoanPlatform(name="Bank")
        db_session.add_all([p, lp])
        db_session.commit()
        db_session.add(Loan(person_id=p.id, platform_id=lp.id, amount=10000, rate=0.01,
                            rate_type="monthly", repay_method="equal_installment",
                            start_date=date(2025, 1, 1), end_date=date(2025, 12, 1),
                            periods=12, status="active"))
        db_session.add(Loan(person_id=p.id, platform_id=lp.id, amount=5000, rate=0.01,
                            rate_type="monthly", repay_method="equal_installment",
                            start_date=date(2025, 1, 1), end_date=date(2025, 6, 1),
                            periods=6, status="closed"))
        db_session.commit()

        snap = compute_snapshot(db_session, date.today())
        assert snap["loan_debt"] == 10000
        assert snap["total_debt"] == 10000
