"""Tests for finance Pydantic schemas."""
import pytest
from datetime import date, datetime
from app.schemas import (
    LoanCreate, CreditCardCreate, PosSwipeCreate, CardInstallmentCreate,
    IncomeCreate, ExpenseCreate, MortgageCreate,
)


class TestLoanCreate:
    def test_valid_loan(self):
        lc = LoanCreate(person_id=1, platform_id=1, amount=10000, rate=0.01,
                        rate_type="monthly", repay_method="equal_installment",
                        start_date=date(2025, 1, 1), end_date=date(2025, 12, 1), periods=12)
        assert lc.amount == 10000

    def test_invalid_rate_type(self):
        with pytest.raises(ValueError):
            LoanCreate(person_id=1, platform_id=1, amount=10000, rate=0.01,
                       rate_type="invalid", repay_method="equal_installment",
                       start_date=date(2025, 1, 1), end_date=date(2025, 12, 1), periods=12)

    def test_invalid_repay_method(self):
        with pytest.raises(ValueError):
            LoanCreate(person_id=1, platform_id=1, amount=10000, rate=0.01,
                       rate_type="monthly", repay_method="invalid",
                       start_date=date(2025, 1, 1), end_date=date(2025, 12, 1), periods=12)


class TestCreditCardCreate:
    def test_invalid_bill_day(self):
        with pytest.raises(ValueError):
            CreditCardCreate(person_id=1, bank="招行", card_number_last4="8823",
                             credit_limit=50000, bill_day=30, due_day=25)

    def test_valid_card(self):
        cc = CreditCardCreate(person_id=1, bank="招行", card_number_last4="8823",
                              credit_limit=50000, bill_day=5, due_day=25)
        assert cc.bank == "招行"
