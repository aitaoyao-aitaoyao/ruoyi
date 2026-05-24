"""Tests for finance data models."""
from datetime import date
from app.models import Person, LoanPlatform, Loan, RepaymentPlan, PosSwipe, CreditCard
from app.models import CreditCardTransaction, CardInstallment, Mortgage, Income, Expense, FeeConfig, DebtSnapshot


class TestPerson:
    def test_create_person(self, db_session):
        p = Person(name="张三", relation="本人")
        db_session.add(p)
        db_session.commit()
        assert p.id is not None
        assert p.name == "张三"
        assert p.relation == "本人"


class TestLoanPlatform:
    def test_create_platform(self, db_session):
        lp = LoanPlatform(name="借呗", icon="💰", description="支付宝借呗")
        db_session.add(lp)
        db_session.commit()
        assert lp.name == "借呗"


class TestLoan:
    def test_create_loan(self, db_session):
        p = Person(name="测试", relation="本人")
        lp = LoanPlatform(name="微粒贷")
        db_session.add_all([p, lp])
        db_session.commit()

        loan = Loan(
            person_id=p.id, platform_id=lp.id, amount=10000, rate=0.01,
            rate_type="monthly", repay_method="equal_installment",
            start_date=date(2025, 1, 1), end_date=date(2025, 12, 1), periods=12,
        )
        db_session.add(loan)
        db_session.commit()
        assert loan.status == "active"
        assert loan.platform.name == "微粒贷"
        assert loan.person.name == "测试"


class TestRepaymentPlan:
    def test_repayment_linked_to_loan(self, db_session):
        p = Person(name="测试")
        lp = LoanPlatform(name="银行")
        db_session.add_all([p, lp])
        db_session.commit()
        loan = Loan(person_id=p.id, platform_id=lp.id, amount=5000, rate=0.01,
                    rate_type="monthly", repay_method="equal_installment",
                    start_date=date(2025, 1, 1), end_date=date(2025, 6, 1), periods=6)
        db_session.add(loan)
        db_session.commit()

        rp = RepaymentPlan(loan_id=loan.id, person_id=p.id, period_no=1,
                           due_date=date(2025, 2, 1), principal=800, interest=50, total_amount=850)
        db_session.add(rp)
        db_session.commit()

        assert len(loan.repayments) == 1
        assert loan.repayments[0].period_no == 1
