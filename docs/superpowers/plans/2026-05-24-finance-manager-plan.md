# Finance Manager Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a personal finance management platform integrated into LightPress CMS, covering loans, POS swipes, credit cards, installments, mortgage, income/expenses with interest calculation engine and dark-themed dashboard.

**Architecture:** New `app/finance/` package for calc engine and snapshot service, new `app/api/v1/finance/` package for API routes, new models/schemas/crud added to existing files, new `app/static/finance.html` + `app/static/finance-app.js` for the dark financial-themed frontend with ECharts.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 + SQLite + Pydantic v2 + Vue 3 (CDN) + ECharts (CDN)

---

## Phase 1: Core Infrastructure

### Task 1: Interest Calculation Engine

**Files:**
- Create: `app/finance/__init__.py`
- Create: `app/finance/calc_engine.py`
- Create: `tests/unit/test_calc_engine.py`

- [ ] **Step 1: Write the failing test**

```python
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
        # amount=10000, 12 periods, total_interest=661.85 -> monthly rate ~0.01 (1%)
        r = convert_to_monthly_rate(rate=661.85, rate_type="total_interest", amount=10000, periods=12, method="equal_installment")
        # Should be approximately 0.01
        assert 0.009 < r < 0.011

    def test_unknown_rate_type_raises(self):
        with pytest.raises(ValueError):
            convert_to_monthly_rate(rate=0.01, rate_type="unknown")


class TestEqualInstallment:
    def test_12_periods_1pct_monthly(self):
        plan = calc_equal_installment_plan(amount=10000, monthly_rate=0.01, periods=12, start_date="2025-01-01")
        assert len(plan) == 12
        # Each payment: 10000 * 0.01 * (1.01^12) / ((1.01^12) - 1) ≈ 888.49
        assert plan[0]["total_amount"] == pytest.approx(888.49, rel=0.01)
        assert plan[0]["interest"] == pytest.approx(100.00, rel=0.01)
        assert plan[0]["principal"] == pytest.approx(788.49, rel=0.01)
        # Total of all payments should equal amount + total interest
        total_paid = sum(p["total_amount"] for p in plan)
        assert total_paid == pytest.approx(10661.88, rel=0.01)

    def test_single_period(self):
        plan = calc_equal_installment_plan(amount=5000, monthly_rate=0.02, periods=1, start_date="2025-03-15")
        assert len(plan) == 1
        assert plan[0]["principal"] == pytest.approx(5000)
        assert plan[0]["interest"] == pytest.approx(100)


class TestInterestFirst:
    def test_12_periods(self):
        plan = calc_interest_first_plan(amount=10000, monthly_rate=0.01, periods=12, start_date="2025-01-01")
        assert len(plan) == 12
        # First 11 periods: interest only
        for i in range(11):
            assert plan[i]["interest"] == pytest.approx(100.00, rel=0.01)
            assert plan[i]["principal"] == 0
            assert plan[i]["total_amount"] == pytest.approx(100.00, rel=0.01)
        # Last period: interest + full principal
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
        # 0.006 * 12 * 24 / 13 ≈ 0.1329 (13.29%)
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/unit/test_calc_engine.py -v
```
Expected: FAIL with "No module named 'app.finance.calc_engine'"

- [ ] **Step 3: Write the calc engine implementation**

Create `app/finance/__init__.py`:
```python
```

Create `app/finance/calc_engine.py`:
```python
"""Interest calculation engine — pure functions, no database dependency."""
import math
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta


def convert_to_monthly_rate(rate: float, rate_type: str, amount: float = 0, periods: int = 0, method: str = "") -> float:
    """Convert various rate types to monthly rate."""
    if rate_type == "monthly":
        return rate
    if rate_type == "annual":
        return rate / 12.0
    if rate_type == "total_interest":
        return _derive_monthly_rate_from_total(rate, amount, periods, method)
    raise ValueError(f"Unknown rate_type: {rate_type}")


def _derive_monthly_rate_from_total(total_interest: float, amount: float, periods: int, method: str) -> float:
    """Derive monthly rate from total interest using binary search."""
    lo, hi = 0.0, 0.5  # 0% to 50% monthly
    for _ in range(60):
        mid = (lo + hi) / 2
        if method == "equal_installment":
            plan = calc_equal_installment_plan(amount, mid, periods, "2000-01-01")
        elif method == "interest_first":
            plan = calc_interest_first_plan(amount, mid, periods, "2000-01-01")
        elif method == "bullet":
            plan = calc_bullet_plan(amount, mid, periods, "2000-01-01")
        else:
            raise ValueError(f"Unknown method: {method}")
        calc_total = sum(p["interest"] for p in plan)
        if calc_total > total_interest:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def calc_equal_installment_plan(amount: float, monthly_rate: float, periods: int, start_date: str) -> list[dict]:
    """Calculate equal installment repayment plan. Returns list of period dicts."""
    if monthly_rate == 0:
        period_amount = amount / periods
        plans = []
        d = date.fromisoformat(start_date)
        for i in range(periods):
            plans.append({
                "period_no": i + 1,
                "due_date": str(d + relativedelta(months=i)),
                "principal": round(period_amount, 2),
                "interest": 0.0,
                "total_amount": round(period_amount, 2),
            })
        return plans

    period_payment = amount * monthly_rate * (1 + monthly_rate) ** periods / ((1 + monthly_rate) ** periods - 1)
    remaining = amount
    plans = []
    d = date.fromisoformat(start_date)
    for i in range(periods):
        interest = round(remaining * monthly_rate, 2)
        principal = round(period_payment - interest, 2)
        remaining -= principal
        plans.append({
            "period_no": i + 1,
            "due_date": str(d + relativedelta(months=i)),
            "principal": principal,
            "interest": interest,
            "total_amount": round(principal + interest, 2),
        })
    return plans


def calc_interest_first_plan(amount: float, monthly_rate: float, periods: int, start_date: str) -> list[dict]:
    """Interest-first: pay interest each period, principal at the end."""
    period_interest = round(amount * monthly_rate, 2)
    plans = []
    d = date.fromisoformat(start_date)
    for i in range(periods - 1):
        plans.append({
            "period_no": i + 1,
            "due_date": str(d + relativedelta(months=i)),
            "principal": 0,
            "interest": period_interest,
            "total_amount": period_interest,
        })
    # Last period: interest + full principal
    plans.append({
        "period_no": periods,
        "due_date": str(d + relativedelta(months=periods - 1)),
        "principal": amount,
        "interest": period_interest,
        "total_amount": round(amount + period_interest, 2),
    })
    return plans


def calc_bullet_plan(amount: float, monthly_rate: float, periods: int, start_date: str) -> list[dict]:
    """Bullet repayment: single payment at the end with all principal + accumulated interest."""
    total_interest = round(amount * monthly_rate * periods, 2)
    d = date.fromisoformat(start_date)
    return [{
        "period_no": 1,
        "due_date": str(d + relativedelta(months=periods - 1)),
        "principal": amount,
        "interest": total_interest,
        "total_amount": round(amount + total_interest, 2),
    }]


def calc_installment_annual_rate(period_rate: float, periods: int) -> float:
    """Calculate actual annual rate for credit card installments.
    Formula: period_rate * periods * 24 / (periods + 1)"""
    return period_rate * periods * 24.0 / (periods + 1)


def calc_pos_fee(amount: float, fee_rate: float) -> float:
    """Calculate POS swipe fee."""
    return round(amount * fee_rate, 2)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pip install python-dateutil -q
python -m pytest tests/unit/test_calc_engine.py -v
```
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add app/finance/ tests/unit/test_calc_engine.py
git commit -m "feat: add interest calculation engine with full test coverage"
```

---

### Task 2: Add Finance Models to models.py

**Files:**
- Modify: `app/models.py` — append finance models at the end
- Create: `tests/unit/test_finance_models.py`

- [ ] **Step 1: Add finance models**

Append to `app/models.py` after the existing Permission model:

```python
# ========== 财务管理模块模型 ==========

class Person(Base):
    __tablename__ = "persons"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    relation = Column(String(20), default="本人")
    created_at = Column(DateTime, default=datetime.utcnow)


class LoanPlatform(Base):
    __tablename__ = "loan_platforms"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    icon = Column(String(10), default="")
    description = Column(String(200), default="")


class Loan(Base):
    __tablename__ = "loans"
    id = Column(Integer, primary_key=True, index=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    platform_id = Column(Integer, ForeignKey("loan_platforms.id"), nullable=False)
    amount = Column(Float, nullable=False)
    rate = Column(Float, nullable=False)
    rate_type = Column(String(10), nullable=False)
    total_interest = Column(Float, nullable=True)
    repay_method = Column(String(20), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    periods = Column(Integer, nullable=False)
    status = Column(String(20), default="active")
    note = Column(String(200), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    person = relationship("Person")
    platform = relationship("LoanPlatform")
    repayments = relationship("RepaymentPlan", back_populates="loan", cascade="all, delete-orphan")


class RepaymentPlan(Base):
    __tablename__ = "repayment_plans"
    id = Column(Integer, primary_key=True, index=True)
    loan_id = Column(Integer, ForeignKey("loans.id"), nullable=False)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    period_no = Column(Integer, nullable=False)
    due_date = Column(Date, nullable=False)
    principal = Column(Float, nullable=False)
    interest = Column(Float, nullable=False)
    total_amount = Column(Float, nullable=False)
    status = Column(String(20), default="pending")
    paid_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    loan = relationship("Loan", back_populates="repayments")
    person = relationship("Person")


class PosSwipe(Base):
    __tablename__ = "pos_swipes"
    id = Column(Integer, primary_key=True, index=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    amount = Column(Float, nullable=False)
    fee_rate = Column(Float, nullable=False)
    fee = Column(Float, nullable=False)
    bank_card = Column(String(50), default="")
    pos_machine = Column(String(50), default="")
    swipe_date = Column(DateTime, nullable=False)
    note = Column(String(200), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    person = relationship("Person")


class CreditCard(Base):
    __tablename__ = "credit_cards"
    id = Column(Integer, primary_key=True, index=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    bank = Column(String(50), nullable=False)
    card_number_last4 = Column(String(4), nullable=False)
    credit_limit = Column(Float, nullable=False)
    current_balance = Column(Float, default=0)
    bill_day = Column(Integer, nullable=False)
    due_day = Column(Integer, nullable=False)
    status = Column(String(20), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)

    person = relationship("Person")
    installments = relationship("CardInstallment", back_populates="card", cascade="all, delete-orphan")
    transactions = relationship("CreditCardTransaction", back_populates="card", cascade="all, delete-orphan")


class CreditCardTransaction(Base):
    __tablename__ = "credit_card_transactions"
    id = Column(Integer, primary_key=True, index=True)
    card_id = Column(Integer, ForeignKey("credit_cards.id"), nullable=False)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    amount = Column(Float, nullable=False)
    description = Column(String(200), default="")
    trans_date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    person = relationship("Person")
    card = relationship("CreditCard", back_populates="transactions")


class CardInstallment(Base):
    __tablename__ = "card_installments"
    id = Column(Integer, primary_key=True, index=True)
    card_id = Column(Integer, ForeignKey("credit_cards.id"), nullable=False)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    amount = Column(Float, nullable=False)
    periods = Column(Integer, nullable=False)
    period_rate = Column(Float, nullable=False)
    annual_rate = Column(Float, nullable=True)
    total_fee = Column(Float, nullable=False)
    period_principal = Column(Float, nullable=False)
    period_fee = Column(Float, nullable=False)
    period_total = Column(Float, nullable=False)
    paid_periods = Column(Integer, default=0)
    start_date = Column(Date, nullable=False)
    note = Column(String(200), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    person = relationship("Person")
    card = relationship("CreditCard", back_populates="installments")


class Mortgage(Base):
    __tablename__ = "mortgages"
    id = Column(Integer, primary_key=True, index=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    bank = Column(String(50), nullable=False)
    house_name = Column(String(100), default="")
    total_amount = Column(Float, nullable=False)
    remaining_principal = Column(Float, nullable=False)
    rate = Column(Float, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    total_periods = Column(Integer, nullable=False)
    monthly_payment = Column(Float, nullable=False)
    repay_method = Column(String(20), default="equal_installment")
    status = Column(String(20), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)

    person = relationship("Person")


class Income(Base):
    __tablename__ = "incomes"
    id = Column(Integer, primary_key=True, index=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    amount = Column(Float, nullable=False)
    source = Column(String(50), nullable=False)
    period_type = Column(String(10), nullable=False)
    period_value = Column(String(7), nullable=False)
    note = Column(String(200), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    person = relationship("Person")


class Expense(Base):
    __tablename__ = "expenses"
    id = Column(Integer, primary_key=True, index=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String(30), nullable=False)
    period_value = Column(String(7), nullable=False)
    expense_date = Column(Date, nullable=False)
    note = Column(String(200), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    person = relationship("Person")


class FeeConfig(Base):
    __tablename__ = "fee_configs"
    id = Column(Integer, primary_key=True, index=True)
    fee_type = Column(String(30), nullable=False)
    rate = Column(Float, nullable=False)
    description = Column(String(100), default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class DebtSnapshot(Base):
    __tablename__ = "debt_snapshots"
    id = Column(Integer, primary_key=True, index=True)
    snapshot_date = Column(Date, nullable=False, index=True)
    total_debt = Column(Float, default=0)
    loan_debt = Column(Float, default=0)
    card_debt = Column(Float, default=0)
    installment_debt = Column(Float, default=0)
    mortgage_debt = Column(Float, default=0)
    pos_fee_total = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
```

- [ ] **Step 2: Write model tests**

```python
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
```

- [ ] **Step 3: Run model tests**

```bash
python -m pytest tests/unit/test_finance_models.py -v
```
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add app/models.py tests/unit/test_finance_models.py
git commit -m "feat: add 13 finance data models with unit tests"
```

---

### Task 3: Add Finance Pydantic Schemas

**Files:**
- Modify: `app/schemas.py` — append finance schemas
- Create: `tests/unit/test_finance_schemas.py`

- [ ] **Step 1: Append finance schemas**

Append to `app/schemas.py`:

```python
# ========== 财务管理模块 Schemas ==========
from datetime import date


class PersonCreate(BaseModel):
    name: str
    relation: str = "本人"


class PersonRead(BaseModel):
    id: int
    name: str
    relation: str
    created_at: datetime
    model_config = {"from_attributes": True}


class LoanPlatformCreate(BaseModel):
    name: str
    icon: str = ""
    description: str = ""


class LoanPlatformRead(BaseModel):
    id: int
    name: str
    icon: str
    description: str
    model_config = {"from_attributes": True}


class LoanCreate(BaseModel):
    person_id: int
    platform_id: int
    amount: float
    rate: float
    rate_type: str  # monthly / annual / total_interest
    total_interest: Optional[float] = None
    repay_method: str  # equal_installment / interest_first / bullet
    start_date: date
    end_date: date
    periods: int
    note: str = ""

    @field_validator("rate_type")
    @classmethod
    def validate_rate_type(cls, v):
        if v not in ("monthly", "annual", "total_interest"):
            raise ValueError("rate_type must be monthly, annual, or total_interest")
        return v

    @field_validator("repay_method")
    @classmethod
    def validate_repay_method(cls, v):
        if v not in ("equal_installment", "interest_first", "bullet"):
            raise ValueError("repay_method must be equal_installment, interest_first, or bullet")
        return v


class LoanRead(BaseModel):
    id: int
    person_id: int
    platform_id: int
    amount: float
    rate: float
    rate_type: str
    total_interest: Optional[float] = None
    repay_method: str
    start_date: date
    end_date: date
    periods: int
    status: str
    note: str
    created_at: datetime
    person: Optional[PersonRead] = None
    platform: Optional[LoanPlatformRead] = None
    model_config = {"from_attributes": True}


class RepaymentPlanRead(BaseModel):
    id: int
    loan_id: int
    person_id: int
    period_no: int
    due_date: date
    principal: float
    interest: float
    total_amount: float
    status: str
    paid_date: Optional[datetime] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class PosSwipeCreate(BaseModel):
    person_id: int
    amount: float
    fee_rate: Optional[float] = None  # if None, uses default from FeeConfig
    bank_card: str = ""
    pos_machine: str = ""
    swipe_date: datetime
    note: str = ""


class PosSwipeRead(BaseModel):
    id: int
    person_id: int
    amount: float
    fee_rate: float
    fee: float
    bank_card: str
    pos_machine: str
    swipe_date: datetime
    note: str
    created_at: datetime
    person: Optional[PersonRead] = None
    model_config = {"from_attributes": True}


class CreditCardCreate(BaseModel):
    person_id: int
    bank: str
    card_number_last4: str
    credit_limit: float
    current_balance: float = 0
    bill_day: int
    due_day: int

    @field_validator("bill_day")
    @classmethod
    def validate_bill_day(cls, v):
        if v < 1 or v > 28:
            raise ValueError("bill_day must be 1-28")
        return v

    @field_validator("due_day")
    @classmethod
    def validate_due_day(cls, v):
        if v < 1 or v > 28:
            raise ValueError("due_day must be 1-28")
        return v


class CreditCardRead(BaseModel):
    id: int
    person_id: int
    bank: str
    card_number_last4: str
    credit_limit: float
    current_balance: float
    bill_day: int
    due_day: int
    status: str
    created_at: datetime
    person: Optional[PersonRead] = None
    model_config = {"from_attributes": True}


class CreditCardUpdate(BaseModel):
    credit_limit: Optional[float] = None
    current_balance: Optional[float] = None
    bill_day: Optional[int] = None
    due_day: Optional[int] = None
    status: Optional[str] = None


class CreditCardTransactionCreate(BaseModel):
    card_id: int
    person_id: int
    amount: float
    description: str = ""
    trans_date: datetime


class CreditCardTransactionRead(BaseModel):
    id: int
    card_id: int
    person_id: int
    amount: float
    description: str
    trans_date: datetime
    created_at: datetime
    person: Optional[PersonRead] = None
    model_config = {"from_attributes": True}


class CardInstallmentCreate(BaseModel):
    card_id: int
    person_id: int
    amount: float
    periods: int
    period_rate: float
    start_date: date
    note: str = ""


class CardInstallmentRead(BaseModel):
    id: int
    card_id: int
    person_id: int
    amount: float
    periods: int
    period_rate: float
    annual_rate: Optional[float] = None
    total_fee: float
    period_principal: float
    period_fee: float
    period_total: float
    paid_periods: int
    start_date: date
    note: str
    created_at: datetime
    person: Optional[PersonRead] = None
    model_config = {"from_attributes": True}


class MortgageCreate(BaseModel):
    person_id: int
    bank: str
    house_name: str = ""
    total_amount: float
    remaining_principal: float
    rate: float
    start_date: date
    end_date: date
    total_periods: int
    monthly_payment: float
    repay_method: str = "equal_installment"


class MortgageRead(BaseModel):
    id: int
    person_id: int
    bank: str
    house_name: str
    total_amount: float
    remaining_principal: float
    rate: float
    start_date: date
    end_date: date
    total_periods: int
    monthly_payment: float
    repay_method: str
    status: str
    created_at: datetime
    person: Optional[PersonRead] = None
    model_config = {"from_attributes": True}


class IncomeCreate(BaseModel):
    person_id: int
    amount: float
    source: str
    period_type: str  # monthly / yearly / once
    period_value: str  # 2025-05
    note: str = ""


class IncomeRead(BaseModel):
    id: int
    person_id: int
    amount: float
    source: str
    period_type: str
    period_value: str
    note: str
    created_at: datetime
    person: Optional[PersonRead] = None
    model_config = {"from_attributes": True}


class ExpenseCreate(BaseModel):
    person_id: int
    amount: float
    category: str
    period_value: str  # 2025-05
    expense_date: date
    note: str = ""


class ExpenseRead(BaseModel):
    id: int
    person_id: int
    amount: float
    category: str
    period_value: str
    expense_date: date
    note: str
    created_at: datetime
    person: Optional[PersonRead] = None
    model_config = {"from_attributes": True}


class FeeConfigCreate(BaseModel):
    fee_type: str
    rate: float
    description: str = ""


class FeeConfigRead(BaseModel):
    id: int
    fee_type: str
    rate: float
    description: str
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class DebtSnapshotRead(BaseModel):
    id: int
    snapshot_date: date
    total_debt: float
    loan_debt: float
    card_debt: float
    installment_debt: float
    mortgage_debt: float
    pos_fee_total: float
    created_at: datetime
    model_config = {"from_attributes": True}


# ========== 查询参数 ==========

class TransactionQuery(BaseModel):
    type: Optional[str] = None
    person_id: Optional[int] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    page: int = 1
    page_size: int = 20


# ========== 仪表盘 ==========

class DashboardSummary(BaseModel):
    total_debt: float
    total_assets: float
    monthly_interest: float
    monthly_pos_fee: float
    total_loan_debt: float
    total_card_debt: float
    total_installment_debt: float
    total_mortgage_debt: float


class RepayReminderItem(BaseModel):
    type: str  # loan / card / installment
    name: str
    person_name: str
    card_last4: str
    due_date: date
    amount: float
    days_left: int


class GapAnalysis(BaseModel):
    period_value: str
    total_income: float
    daily_expense: float
    debt_payment: float
    total_expense: float
    gap: float
```

- [ ] **Step 2: Write schema validation tests**

```python
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
```

- [ ] **Step 3: Run schema tests**

```bash
python -m pytest tests/unit/test_finance_schemas.py -v
```
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add app/schemas.py tests/unit/test_finance_schemas.py
git commit -m "feat: add finance Pydantic schemas with validation tests"
```

---

## Phase 2: Basic CRUD & Core APIs

### Task 4: Finance CRUD Operations

**Files:**
- Modify: `app/crud.py` — append finance CRUD functions

- [ ] **Step 1: Add finance CRUD functions**

Append to `app/crud.py`:

```python
# ======================== 财务管理 CRUD ========================
from app.models import Person, LoanPlatform, Loan, RepaymentPlan, PosSwipe, CreditCard
from app.models import CreditCardTransaction, CardInstallment, Mortgage, Income, Expense, FeeConfig, DebtSnapshot


# --- Person ---
def create_person(db: Session, data: schemas.PersonCreate) -> Person:
    person = Person(**data.model_dump())
    db.add(person)
    db.commit()
    db.refresh(person)
    return person

def get_persons(db: Session) -> list[Person]:
    return db.query(Person).all()

def get_person(db: Session, person_id: int) -> Optional[Person]:
    return db.query(Person).filter(Person.id == person_id).first()

def delete_person(db: Session, person_id: int) -> bool:
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        return False
    db.delete(person)
    db.commit()
    return True


# --- LoanPlatform ---
def create_platform(db: Session, data: schemas.LoanPlatformCreate) -> LoanPlatform:
    platform = LoanPlatform(**data.model_dump())
    db.add(platform)
    db.commit()
    db.refresh(platform)
    return platform

def get_platforms(db: Session) -> list[LoanPlatform]:
    return db.query(LoanPlatform).all()

def get_platform(db: Session, platform_id: int) -> Optional[LoanPlatform]:
    return db.query(LoanPlatform).filter(LoanPlatform.id == platform_id).first()

def delete_platform(db: Session, platform_id: int) -> bool:
    platform = db.query(LoanPlatform).filter(LoanPlatform.id == platform_id).first()
    if not platform:
        return False
    db.delete(platform)
    db.commit()
    return True


# --- Loan ---
def create_loan(db: Session, data: schemas.LoanCreate, repayments: list[dict]) -> Loan:
    loan = Loan(**data.model_dump())
    db.add(loan)
    db.flush()
    for rp in repayments:
        plan = RepaymentPlan(loan_id=loan.id, person_id=data.person_id, **rp)
        db.add(plan)
    db.commit()
    db.refresh(loan)
    return loan

def get_loans(db: Session, person_id: Optional[int] = None) -> list[Loan]:
    q = db.query(Loan)
    if person_id:
        q = q.filter(Loan.person_id == person_id)
    return q.order_by(Loan.created_at.desc()).all()

def get_loan(db: Session, loan_id: int) -> Optional[Loan]:
    return db.query(Loan).filter(Loan.id == loan_id).first()

def update_loan_status(db: Session, loan_id: int, status: str) -> Optional[Loan]:
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if loan:
        loan.status = status
        db.commit()
        db.refresh(loan)
    return loan

def delete_loan(db: Session, loan_id: int) -> bool:
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        return False
    db.delete(loan)
    db.commit()
    return True


# --- RepaymentPlan ---
def get_repayments(db: Session, loan_id: int) -> list[RepaymentPlan]:
    return db.query(RepaymentPlan).filter(RepaymentPlan.loan_id == loan_id).order_by(RepaymentPlan.period_no).all()

def pay_repayment(db: Session, repayment_id: int) -> Optional[RepaymentPlan]:
    rp = db.query(RepaymentPlan).filter(RepaymentPlan.id == repayment_id).first()
    if rp:
        rp.status = "paid"
        rp.paid_date = datetime.utcnow()
        db.commit()
        db.refresh(rp)
    return rp


# --- PosSwipe ---
def create_pos_swipe(db: Session, data: schemas.PosSwipeCreate, fee: float = 0) -> PosSwipe:
    swipe = PosSwipe(**data.model_dump(), fee=fee)
    db.add(swipe)
    db.commit()
    db.refresh(swipe)
    return swipe

def get_pos_swipes(db: Session, person_id: Optional[int] = None) -> list[PosSwipe]:
    q = db.query(PosSwipe)
    if person_id:
        q = q.filter(PosSwipe.person_id == person_id)
    return q.order_by(PosSwipe.swipe_date.desc()).all()

def get_pos_swipe(db: Session, swipe_id: int) -> Optional[PosSwipe]:
    return db.query(PosSwipe).filter(PosSwipe.id == swipe_id).first()

def delete_pos_swipe(db: Session, swipe_id: int) -> bool:
    swipe = db.query(PosSwipe).filter(PosSwipe.id == swipe_id).first()
    if not swipe:
        return False
    db.delete(swipe)
    db.commit()
    return True


# --- CreditCard ---
def create_credit_card(db: Session, data: schemas.CreditCardCreate) -> CreditCard:
    card = CreditCard(**data.model_dump())
    db.add(card)
    db.commit()
    db.refresh(card)
    return card

def get_credit_cards(db: Session, person_id: Optional[int] = None) -> list[CreditCard]:
    q = db.query(CreditCard)
    if person_id:
        q = q.filter(CreditCard.person_id == person_id)
    return q.all()

def get_credit_card(db: Session, card_id: int) -> Optional[CreditCard]:
    return db.query(CreditCard).filter(CreditCard.id == card_id).first()

def update_credit_card(db: Session, card_id: int, data: schemas.CreditCardUpdate) -> Optional[CreditCard]:
    card = db.query(CreditCard).filter(CreditCard.id == card_id).first()
    if card:
        for key, val in data.model_dump(exclude_unset=True).items():
            setattr(card, key, val)
        db.commit()
        db.refresh(card)
    return card

def delete_credit_card(db: Session, card_id: int) -> bool:
    card = db.query(CreditCard).filter(CreditCard.id == card_id).first()
    if not card:
        return False
    db.delete(card)
    db.commit()
    return True


# --- CreditCardTransaction ---
def create_card_transaction(db: Session, data: schemas.CreditCardTransactionCreate) -> CreditCardTransaction:
    txn = CreditCardTransaction(**data.model_dump())
    db.add(txn)
    # Update card balance
    card = db.query(CreditCard).filter(CreditCard.id == data.card_id).first()
    if card:
        card.current_balance += data.amount
    db.commit()
    db.refresh(txn)
    return txn

def get_card_transactions(db: Session, card_id: Optional[int] = None,
                          person_id: Optional[int] = None) -> list[CreditCardTransaction]:
    q = db.query(CreditCardTransaction)
    if card_id:
        q = q.filter(CreditCardTransaction.card_id == card_id)
    if person_id:
        q = q.filter(CreditCardTransaction.person_id == person_id)
    return q.order_by(CreditCardTransaction.trans_date.desc()).all()

def delete_card_transaction(db: Session, txn_id: int) -> bool:
    txn = db.query(CreditCardTransaction).filter(CreditCardTransaction.id == txn_id).first()
    if not txn:
        return False
    db.delete(txn)
    db.commit()
    return True


# --- CardInstallment ---
def create_card_installment(db: Session, data: schemas.CardInstallmentCreate,
                            calc_fields: dict) -> CardInstallment:
    inst = CardInstallment(**data.model_dump(), **calc_fields)
    db.add(inst)
    db.commit()
    db.refresh(inst)
    return inst

def get_card_installments(db: Session, card_id: Optional[int] = None,
                          person_id: Optional[int] = None) -> list[CardInstallment]:
    q = db.query(CardInstallment)
    if card_id:
        q = q.filter(CardInstallment.card_id == card_id)
    if person_id:
        q = q.filter(CardInstallment.person_id == person_id)
    return q.order_by(CardInstallment.created_at.desc()).all()

def get_card_installment(db: Session, inst_id: int) -> Optional[CardInstallment]:
    return db.query(CardInstallment).filter(CardInstallment.id == inst_id).first()

def pay_installment_period(db: Session, inst_id: int) -> Optional[CardInstallment]:
    inst = db.query(CardInstallment).filter(CardInstallment.id == inst_id).first()
    if inst and inst.paid_periods < inst.periods:
        inst.paid_periods += 1
        db.commit()
        db.refresh(inst)
    return inst

def delete_card_installment(db: Session, inst_id: int) -> bool:
    inst = db.query(CardInstallment).filter(CardInstallment.id == inst_id).first()
    if not inst:
        return False
    db.delete(inst)
    db.commit()
    return True


# --- Mortgage ---
def create_mortgage(db: Session, data: schemas.MortgageCreate) -> Mortgage:
    m = Mortgage(**data.model_dump())
    db.add(m)
    db.commit()
    db.refresh(m)
    return m

def get_mortgages(db: Session, person_id: Optional[int] = None) -> list[Mortgage]:
    q = db.query(Mortgage)
    if person_id:
        q = q.filter(Mortgage.person_id == person_id)
    return q.all()

def get_mortgage(db: Session, mortgage_id: int) -> Optional[Mortgage]:
    return db.query(Mortgage).filter(Mortgage.id == mortgage_id).first()

def update_mortgage_principal(db: Session, mortgage_id: int, remaining_principal: float) -> Optional[Mortgage]:
    m = db.query(Mortgage).filter(Mortgage.id == mortgage_id).first()
    if m:
        m.remaining_principal = remaining_principal
        db.commit()
        db.refresh(m)
    return m

def delete_mortgage(db: Session, mortgage_id: int) -> bool:
    m = db.query(Mortgage).filter(Mortgage.id == mortgage_id).first()
    if not m:
        return False
    db.delete(m)
    db.commit()
    return True


# --- Income ---
def create_income(db: Session, data: schemas.IncomeCreate) -> Income:
    inc = Income(**data.model_dump())
    db.add(inc)
    db.commit()
    db.refresh(inc)
    return inc

def get_incomes(db: Session, person_id: Optional[int] = None,
                period_value: Optional[str] = None) -> list[Income]:
    q = db.query(Income)
    if person_id:
        q = q.filter(Income.person_id == person_id)
    if period_value:
        q = q.filter(Income.period_value == period_value)
    return q.order_by(Income.created_at.desc()).all()

def delete_income(db: Session, income_id: int) -> bool:
    inc = db.query(Income).filter(Income.id == income_id).first()
    if not inc:
        return False
    db.delete(inc)
    db.commit()
    return True


# --- Expense ---
def create_expense(db: Session, data: schemas.ExpenseCreate) -> Expense:
    exp = Expense(**data.model_dump())
    db.add(exp)
    db.commit()
    db.refresh(exp)
    return exp

def get_expenses(db: Session, person_id: Optional[int] = None,
                 period_value: Optional[str] = None,
                 category: Optional[str] = None) -> list[Expense]:
    q = db.query(Expense)
    if person_id:
        q = q.filter(Expense.person_id == person_id)
    if period_value:
        q = q.filter(Expense.period_value == period_value)
    if category:
        q = q.filter(Expense.category == category)
    return q.order_by(Expense.expense_date.desc()).all()

def delete_expense(db: Session, expense_id: int) -> bool:
    exp = db.query(Expense).filter(Expense.id == expense_id).first()
    if not exp:
        return False
    db.delete(exp)
    db.commit()
    return True


# --- FeeConfig ---
def create_fee_config(db: Session, data: schemas.FeeConfigCreate) -> FeeConfig:
    fc = FeeConfig(**data.model_dump())
    db.add(fc)
    db.commit()
    db.refresh(fc)
    return fc

def get_fee_configs(db: Session) -> list[FeeConfig]:
    return db.query(FeeConfig).all()

def get_active_fee_config(db: Session, fee_type: str) -> Optional[FeeConfig]:
    return db.query(FeeConfig).filter(
        FeeConfig.fee_type == fee_type, FeeConfig.is_active == True
    ).first()

def delete_fee_config(db: Session, config_id: int) -> bool:
    fc = db.query(FeeConfig).filter(FeeConfig.id == config_id).first()
    if not fc:
        return False
    db.delete(fc)
    db.commit()
    return True


# --- DebtSnapshot ---
def get_latest_snapshot(db: Session) -> Optional[DebtSnapshot]:
    return db.query(DebtSnapshot).order_by(DebtSnapshot.snapshot_date.desc()).first()

def get_today_snapshot(db: Session, today: date) -> Optional[DebtSnapshot]:
    return db.query(DebtSnapshot).filter(DebtSnapshot.snapshot_date == today).first()

def create_snapshot(db: Session, data: dict) -> DebtSnapshot:
    snap = DebtSnapshot(**data)
    db.add(snap)
    db.commit()
    db.refresh(snap)
    return snap

def get_snapshots(db: Session, months: int = 12) -> list[DebtSnapshot]:
    from datetime import timedelta
    cutoff = datetime.utcnow().date() - timedelta(days=months * 30)
    return db.query(DebtSnapshot).filter(
        DebtSnapshot.snapshot_date >= cutoff
    ).order_by(DebtSnapshot.snapshot_date).all()
```

- [ ] **Step 2: Commit**

```bash
git add app/crud.py
git commit -m "feat: add finance CRUD operations for all 13 entities"
```

---

### Task 5: Snapshot Service

**Files:**
- Create: `app/finance/snapshot_service.py`
- Create: `tests/unit/test_snapshot_service.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/unit/test_snapshot_service.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement snapshot service**

Create `app/finance/snapshot_service.py`:

```python
"""Debt snapshot computation service."""
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import Loan, CreditCard, CardInstallment, Mortgage, PosSwipe


def compute_snapshot(db: Session, snapshot_date: date) -> dict:
    """Compute all debt metrics for a given date. Returns a dict ready for DebtSnapshot."""
    loan_debt = db.query(func.coalesce(func.sum(Loan.amount), 0)).filter(
        Loan.status == "active"
    ).scalar() or 0.0

    card_debt = db.query(func.coalesce(func.sum(CreditCard.current_balance), 0)).filter(
        CreditCard.status == "active"
    ).scalar() or 0.0

    installment_debt = db.query(
        func.coalesce(func.sum(CardInstallment.amount - CardInstallment.period_principal * CardInstallment.paid_periods), 0)
    ).scalar() or 0.0

    mortgage_debt = db.query(func.coalesce(func.sum(Mortgage.remaining_principal), 0)).filter(
        Mortgage.status == "active"
    ).scalar() or 0.0

    total_debt = loan_debt + card_debt + installment_debt + mortgage_debt

    pos_fee_total = db.query(func.coalesce(func.sum(PosSwipe.fee), 0)).scalar() or 0.0

    return {
        "snapshot_date": snapshot_date,
        "total_debt": round(total_debt, 2),
        "loan_debt": round(loan_debt, 2),
        "card_debt": round(card_debt, 2),
        "installment_debt": round(installment_debt, 2),
        "mortgage_debt": round(mortgage_debt, 2),
        "pos_fee_total": round(pos_fee_total, 2),
    }
```

- [ ] **Step 4: Run test to verify pass**

```bash
python -m pytest tests/unit/test_snapshot_service.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/finance/snapshot_service.py tests/unit/test_snapshot_service.py
git commit -m "feat: add debt snapshot computation service"
```

---

### Task 6: Person, Platform, Loan, and POS APIs

**Files:**
- Create: `app/api/v1/finance/__init__.py`
- Create: `app/api/v1/finance/persons.py`
- Create: `app/api/v1/finance/platforms.py`
- Create: `app/api/v1/finance/loans.py`
- Create: `app/api/v1/finance/pos_swipes.py`
- Create: `tests/api/test_finance_persons.py`
- Create: `tests/api/test_finance_loans.py`
- Create: `tests/api/test_finance_pos.py`

- [ ] **Step 1: Create the persons API**

Create `app/api/v1/finance/__init__.py`:
```python
```

Create `app/api/v1/finance/persons.py`:
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app import crud, schemas

router = APIRouter(prefix="/finance/persons", tags=["finance-persons"])


@router.post("/", response_model=schemas.PersonRead, status_code=201)
def create_person(data: schemas.PersonCreate, db: Session = Depends(get_db)):
    return crud.create_person(db, data)


@router.get("/", response_model=list[schemas.PersonRead])
def list_persons(db: Session = Depends(get_db)):
    return crud.get_persons(db)


@router.get("/{person_id}", response_model=schemas.PersonRead)
def get_person(person_id: int, db: Session = Depends(get_db)):
    person = crud.get_person(db, person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    return person


@router.delete("/{person_id}", status_code=204)
def delete_person(person_id: int, db: Session = Depends(get_db)):
    if not crud.delete_person(db, person_id):
        raise HTTPException(status_code=404, detail="Person not found")
```

- [ ] **Step 2: Create platforms API**

Create `app/api/v1/finance/platforms.py`:
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app import crud, schemas

router = APIRouter(prefix="/finance/platforms", tags=["finance-platforms"])


@router.post("/", response_model=schemas.LoanPlatformRead, status_code=201)
def create_platform(data: schemas.LoanPlatformCreate, db: Session = Depends(get_db)):
    return crud.create_platform(db, data)


@router.get("/", response_model=list[schemas.LoanPlatformRead])
def list_platforms(db: Session = Depends(get_db)):
    return crud.get_platforms(db)


@router.delete("/{platform_id}", status_code=204)
def delete_platform(platform_id: int, db: Session = Depends(get_db)):
    if not crud.delete_platform(db, platform_id):
        raise HTTPException(status_code=404, detail="Platform not found")
```

- [ ] **Step 3: Create loans API with auto repayment plan generation**

Create `app/api/v1/finance/loans.py`:
```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db import get_db
from app import crud, schemas
from app.finance.calc_engine import convert_to_monthly_rate, calc_equal_installment_plan, calc_interest_first_plan, calc_bullet_plan

router = APIRouter(prefix="/finance/loans", tags=["finance-loans"])


@router.post("/", response_model=schemas.LoanRead, status_code=201)
def create_loan(data: schemas.LoanCreate, db: Session = Depends(get_db)):
    monthly_rate = convert_to_monthly_rate(
        rate=data.rate, rate_type=data.rate_type,
        amount=data.amount, periods=data.periods, method=data.repay_method,
    )
    if data.repay_method == "equal_installment":
        plan = calc_equal_installment_plan(data.amount, monthly_rate, data.periods, str(data.start_date))
    elif data.repay_method == "interest_first":
        plan = calc_interest_first_plan(data.amount, monthly_rate, data.periods, str(data.start_date))
    else:
        plan = calc_bullet_plan(data.amount, monthly_rate, data.periods, str(data.start_date))

    return crud.create_loan(db, data, plan)


@router.get("/", response_model=list[schemas.LoanRead])
def list_loans(person_id: int = Query(None), db: Session = Depends(get_db)):
    return crud.get_loans(db, person_id)


@router.get("/{loan_id}", response_model=schemas.LoanRead)
def get_loan(loan_id: int, db: Session = Depends(get_db)):
    loan = crud.get_loan(db, loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    return loan


@router.get("/{loan_id}/repayments", response_model=list[schemas.RepaymentPlanRead])
def get_loan_repayments(loan_id: int, db: Session = Depends(get_db)):
    return crud.get_repayments(db, loan_id)


@router.patch("/repayments/{repayment_id}/pay", response_model=schemas.RepaymentPlanRead)
def pay_repayment(repayment_id: int, db: Session = Depends(get_db)):
    rp = crud.pay_repayment(db, repayment_id)
    if not rp:
        raise HTTPException(status_code=404, detail="Repayment not found")
    return rp


@router.delete("/{loan_id}", status_code=204)
def delete_loan(loan_id: int, db: Session = Depends(get_db)):
    if not crud.delete_loan(db, loan_id):
        raise HTTPException(status_code=404, detail="Loan not found")
```

- [ ] **Step 4: Create POS swipes API**

Create `app/api/v1/finance/pos_swipes.py`:
```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db import get_db
from app import crud, schemas
from app.finance.calc_engine import calc_pos_fee

router = APIRouter(prefix="/finance/pos-swipes", tags=["finance-pos"])


@router.post("/", response_model=schemas.PosSwipeRead, status_code=201)
def create_pos_swipe(data: schemas.PosSwipeCreate, db: Session = Depends(get_db)):
    if data.fee_rate is None:
        config = crud.get_active_fee_config(db, "pos_swipe")
        fee_rate = config.rate if config else 0.006
    else:
        fee_rate = data.fee_rate
    fee = calc_pos_fee(data.amount, fee_rate)
    data.fee_rate = fee_rate
    return crud.create_pos_swipe(db, data, fee)


@router.get("/", response_model=list[schemas.PosSwipeRead])
def list_pos_swipes(person_id: int = Query(None), db: Session = Depends(get_db)):
    return crud.get_pos_swipes(db, person_id)


@router.delete("/{swipe_id}", status_code=204)
def delete_pos_swipe(swipe_id: int, db: Session = Depends(get_db)):
    if not crud.delete_pos_swipe(db, swipe_id):
        raise HTTPException(status_code=404, detail="POS swipe not found")
```

- [ ] **Step 5: Write API tests for persons**

```python
"""API tests for finance persons."""
class TestPersonAPI:
    def test_create_person(self, client):
        resp = client.post("/api/v1/finance/persons/", json={"name": "张三", "relation": "本人"})
        assert resp.status_code == 201
        assert resp.json()["name"] == "张三"

    def test_list_persons(self, client):
        client.post("/api/v1/finance/persons/", json={"name": "张三", "relation": "本人"})
        resp = client.get("/api/v1/finance/persons/")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_get_person_not_found(self, client):
        resp = client.get("/api/v1/finance/persons/9999")
        assert resp.status_code == 404

    def test_delete_person(self, client):
        resp = client.post("/api/v1/finance/persons/", json={"name": "李四", "relation": "配偶"})
        pid = resp.json()["id"]
        resp = client.delete(f"/api/v1/finance/persons/{pid}")
        assert resp.status_code == 204
```

- [ ] **Step 6: Write API tests for loans**

```python
"""API tests for finance loans."""
class TestLoanAPI:
    def test_create_loan_generates_repayments(self, client):
        p = client.post("/api/v1/finance/persons/", json={"name": "测试", "relation": "本人"})
        pid = p.json()["id"]
        lp = client.post("/api/v1/finance/platforms/", json={"name": "借呗"})
        lpid = lp.json()["id"]

        resp = client.post("/api/v1/finance/loans/", json={
            "person_id": pid, "platform_id": lpid, "amount": 10000,
            "rate": 0.01, "rate_type": "monthly", "repay_method": "equal_installment",
            "start_date": "2025-01-01", "end_date": "2025-12-01", "periods": 12,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "active"
        assert data["periods"] == 12

        # Check repayments were generated
        loan_id = data["id"]
        rp_resp = client.get(f"/api/v1/finance/loans/{loan_id}/repayments")
        assert rp_resp.status_code == 200
        assert len(rp_resp.json()) == 12

    def test_pay_repayment(self, client):
        p = client.post("/api/v1/finance/persons/", json={"name": "测试"})
        pid = p.json()["id"]
        lp = client.post("/api/v1/finance/platforms/", json={"name": "测试平台"})
        lpid = lp.json()["id"]
        loan = client.post("/api/v1/finance/loans/", json={
            "person_id": pid, "platform_id": lpid, "amount": 5000,
            "rate": 0.01, "rate_type": "monthly", "repay_method": "bullet",
            "start_date": "2025-01-01", "end_date": "2025-06-01", "periods": 6,
        })
        loan_id = loan.json()["id"]
        rps = client.get(f"/api/v1/finance/loans/{loan_id}/repayments")
        rp_id = rps.json()[0]["id"]

        resp = client.patch(f"/api/v1/finance/loans/repayments/{rp_id}/pay")
        assert resp.status_code == 200
        assert resp.json()["status"] == "paid"
```

- [ ] **Step 7: Write API tests for POS**

```python
"""API tests for finance POS swipes."""
class TestPosAPI:
    def test_create_pos_swipe_default_fee(self, client):
        p = client.post("/api/v1/finance/persons/", json={"name": "测试"})
        pid = p.json()["id"]

        resp = client.post("/api/v1/finance/pos-swipes/", json={
            "person_id": pid, "amount": 10000,
            "bank_card": "招行储蓄卡", "pos_machine": "拉卡拉",
            "swipe_date": "2025-05-24T14:30:00",
        })
        assert resp.status_code == 201
        assert resp.json()["fee"] == 60.0

    def test_create_pos_swipe_custom_fee(self, client):
        p = client.post("/api/v1/finance/persons/", json={"name": "测试"})
        pid = p.json()["id"]

        resp = client.post("/api/v1/finance/pos-swipes/", json={
            "person_id": pid, "amount": 10000, "fee_rate": 0.005,
            "swipe_date": "2025-05-24T14:30:00",
        })
        assert resp.status_code == 201
        assert resp.json()["fee"] == 50.0
```

- [ ] **Step 8: Run all API tests**

```bash
python -m pytest tests/api/test_finance_persons.py tests/api/test_finance_loans.py tests/api/test_finance_pos.py -v
```
Expected: ALL PASS

- [ ] **Step 9: Register routes and commit**

First, update `app/main.py` to register the new routes. After the existing `include_router` lines, add:

```python
from app.api.v1.finance import persons, platforms, loans, pos_swipes
app.include_router(persons.router, prefix="/api/v1")
app.include_router(platforms.router, prefix="/api/v1")
app.include_router(loans.router, prefix="/api/v1")
app.include_router(pos_swipes.router, prefix="/api/v1")
```

```bash
git add app/api/v1/finance/ app/main.py tests/api/test_finance_persons.py tests/api/test_finance_loans.py tests/api/test_finance_pos.py
git commit -m "feat: add person, platform, loan, and POS API routes with tests"
```

---

### Task 7: Credit Card & Installment APIs

**Files:**
- Create: `app/api/v1/finance/credit_cards.py`
- Create: `app/api/v1/finance/card_transactions.py`
- Create: `app/api/v1/finance/card_installments.py`
- Create: `tests/api/test_finance_cards.py`

- [ ] **Step 1: Create credit cards API**

Create `app/api/v1/finance/credit_cards.py`:
```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db import get_db
from app import crud, schemas

router = APIRouter(prefix="/finance/credit-cards", tags=["finance-cards"])


@router.post("/", response_model=schemas.CreditCardRead, status_code=201)
def create_card(data: schemas.CreditCardCreate, db: Session = Depends(get_db)):
    return crud.create_credit_card(db, data)


@router.get("/", response_model=list[schemas.CreditCardRead])
def list_cards(person_id: int = Query(None), db: Session = Depends(get_db)):
    return crud.get_credit_cards(db, person_id)


@router.get("/{card_id}", response_model=schemas.CreditCardRead)
def get_card(card_id: int, db: Session = Depends(get_db)):
    card = crud.get_credit_card(db, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Credit card not found")
    return card


@router.patch("/{card_id}", response_model=schemas.CreditCardRead)
def update_card(card_id: int, data: schemas.CreditCardUpdate, db: Session = Depends(get_db)):
    card = crud.update_credit_card(db, card_id, data)
    if not card:
        raise HTTPException(status_code=404, detail="Credit card not found")
    return card


@router.delete("/{card_id}", status_code=204)
def delete_card(card_id: int, db: Session = Depends(get_db)):
    if not crud.delete_credit_card(db, card_id):
        raise HTTPException(status_code=404, detail="Credit card not found")
```

- [ ] **Step 2: Create card transactions API**

Create `app/api/v1/finance/card_transactions.py`:
```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db import get_db
from app import crud, schemas

router = APIRouter(prefix="/finance/card-transactions", tags=["finance-card-txns"])


@router.post("/", response_model=schemas.CreditCardTransactionRead, status_code=201)
def create_transaction(data: schemas.CreditCardTransactionCreate, db: Session = Depends(get_db)):
    return crud.create_card_transaction(db, data)


@router.get("/", response_model=list[schemas.CreditCardTransactionRead])
def list_transactions(card_id: int = Query(None), person_id: int = Query(None),
                      db: Session = Depends(get_db)):
    return crud.get_card_transactions(db, card_id, person_id)


@router.delete("/{txn_id}", status_code=204)
def delete_transaction(txn_id: int, db: Session = Depends(get_db)):
    if not crud.delete_card_transaction(db, txn_id):
        raise HTTPException(status_code=404, detail="Transaction not found")
```

- [ ] **Step 3: Create card installments API**

Create `app/api/v1/finance/card_installments.py`:
```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db import get_db
from app import crud, schemas
from app.finance.calc_engine import calc_installment_annual_rate

router = APIRouter(prefix="/finance/card-installments", tags=["finance-installments"])


@router.post("/", response_model=schemas.CardInstallmentRead, status_code=201)
def create_installment(data: schemas.CardInstallmentCreate, db: Session = Depends(get_db)):
    annual_rate = calc_installment_annual_rate(data.period_rate, data.periods)
    total_fee = round(data.amount * data.period_rate * data.periods, 2)
    period_principal = round(data.amount / data.periods, 2)
    period_fee = round(data.amount * data.period_rate, 2)
    calc_fields = {
        "annual_rate": round(annual_rate, 4),
        "total_fee": total_fee,
        "period_principal": period_principal,
        "period_fee": period_fee,
        "period_total": round(period_principal + period_fee, 2),
    }
    return crud.create_card_installment(db, data, calc_fields)


@router.get("/", response_model=list[schemas.CardInstallmentRead])
def list_installments(card_id: int = Query(None), person_id: int = Query(None),
                      db: Session = Depends(get_db)):
    return crud.get_card_installments(db, card_id, person_id)


@router.patch("/{inst_id}/pay-period", response_model=schemas.CardInstallmentRead)
def pay_period(inst_id: int, db: Session = Depends(get_db)):
    inst = crud.pay_installment_period(db, inst_id)
    if not inst:
        raise HTTPException(status_code=404, detail="Installment not found")
    return inst


@router.delete("/{inst_id}", status_code=204)
def delete_installment(inst_id: int, db: Session = Depends(get_db)):
    if not crud.delete_card_installment(db, inst_id):
        raise HTTPException(status_code=404, detail="Installment not found")
```

- [ ] **Step 4: Write API tests**

```python
"""API tests for credit cards and installments."""
class TestCreditCardAPI:
    def test_create_and_list(self, client):
        p = client.post("/api/v1/finance/persons/", json={"name": "测试"})
        pid = p.json()["id"]

        resp = client.post("/api/v1/finance/credit-cards/", json={
            "person_id": pid, "bank": "招商银行", "card_number_last4": "8823",
            "credit_limit": 50000, "bill_day": 5, "due_day": 25,
        })
        assert resp.status_code == 201
        assert resp.json()["bank"] == "招商银行"

    def test_card_update(self, client):
        p = client.post("/api/v1/finance/persons/", json={"name": "测试"})
        pid = p.json()["id"]
        card = client.post("/api/v1/finance/credit-cards/", json={
            "person_id": pid, "bank": "招行", "card_number_last4": "8823",
            "credit_limit": 50000, "bill_day": 5, "due_day": 25,
        })
        cid = card.json()["id"]
        resp = client.patch(f"/api/v1/finance/credit-cards/{cid}", json={"current_balance": 8500})
        assert resp.status_code == 200
        assert resp.json()["current_balance"] == 8500


class TestInstallmentAPI:
    def test_create_installment(self, client):
        p = client.post("/api/v1/finance/persons/", json={"name": "测试"})
        pid = p.json()["id"]
        card = client.post("/api/v1/finance/credit-cards/", json={
            "person_id": pid, "bank": "招行", "card_number_last4": "8823",
            "credit_limit": 50000, "bill_day": 5, "due_day": 25,
        })
        cid = card.json()["id"]

        resp = client.post("/api/v1/finance/card-installments/", json={
            "card_id": cid, "person_id": pid, "amount": 12000,
            "periods": 12, "period_rate": 0.006, "start_date": "2025-05-01",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["total_fee"] == 864.0
        assert data["period_principal"] == 1000.0
        assert data["period_fee"] == 72.0
        assert 0.13 < data["annual_rate"] < 0.14
```

- [ ] **Step 5: Run tests and commit**

```bash
python -m pytest tests/api/test_finance_cards.py -v
```

Update `app/main.py`:
```python
from app.api.v1.finance import credit_cards, card_transactions, card_installments
app.include_router(credit_cards.router, prefix="/api/v1")
app.include_router(card_transactions.router, prefix="/api/v1")
app.include_router(card_installments.router, prefix="/api/v1")
```

```bash
git add app/api/v1/finance/credit_cards.py app/api/v1/finance/card_transactions.py app/api/v1/finance/card_installments.py tests/api/test_finance_cards.py app/main.py
git commit -m "feat: add credit card, transaction, and installment APIs with tests"
```

---

## Phase 3: Remaining APIs

### Task 8: Mortgage, Income, Expense, Fee Config APIs

**Files:**
- Create: `app/api/v1/finance/mortgages.py`
- Create: `app/api/v1/finance/incomes.py`
- Create: `app/api/v1/finance/expenses.py`
- Create: `app/api/v1/finance/fee_configs.py`
- Create: `tests/api/test_finance_rest.py`

- [ ] **Step 1: Create mortgages API**

```python
# app/api/v1/finance/mortgages.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db import get_db
from app import crud, schemas

router = APIRouter(prefix="/finance/mortgages", tags=["finance-mortgages"])


@router.post("/", response_model=schemas.MortgageRead, status_code=201)
def create_mortgage(data: schemas.MortgageCreate, db: Session = Depends(get_db)):
    return crud.create_mortgage(db, data)


@router.get("/", response_model=list[schemas.MortgageRead])
def list_mortgages(person_id: int = Query(None), db: Session = Depends(get_db)):
    return crud.get_mortgages(db, person_id)


@router.patch("/{mortgage_id}", response_model=schemas.MortgageRead)
def update_principal(mortgage_id: int, remaining_principal: float, db: Session = Depends(get_db)):
    m = crud.update_mortgage_principal(db, mortgage_id, remaining_principal)
    if not m:
        raise HTTPException(status_code=404, detail="Mortgage not found")
    return m


@router.delete("/{mortgage_id}", status_code=204)
def delete_mortgage(mortgage_id: int, db: Session = Depends(get_db)):
    if not crud.delete_mortgage(db, mortgage_id):
        raise HTTPException(status_code=404, detail="Mortgage not found")
```

- [ ] **Step 2: Create incomes API**

```python
# app/api/v1/finance/incomes.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db import get_db
from app import crud, schemas

router = APIRouter(prefix="/finance/incomes", tags=["finance-incomes"])


@router.post("/", response_model=schemas.IncomeRead, status_code=201)
def create_income(data: schemas.IncomeCreate, db: Session = Depends(get_db)):
    return crud.create_income(db, data)


@router.get("/", response_model=list[schemas.IncomeRead])
def list_incomes(person_id: int = Query(None), period_value: str = Query(None),
                 db: Session = Depends(get_db)):
    return crud.get_incomes(db, person_id, period_value)


@router.delete("/{income_id}", status_code=204)
def delete_income(income_id: int, db: Session = Depends(get_db)):
    if not crud.delete_income(db, income_id):
        raise HTTPException(status_code=404, detail="Income not found")
```

- [ ] **Step 3: Create expenses API**

```python
# app/api/v1/finance/expenses.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db import get_db
from app import crud, schemas

router = APIRouter(prefix="/finance/expenses", tags=["finance-expenses"])


@router.post("/", response_model=schemas.ExpenseRead, status_code=201)
def create_expense(data: schemas.ExpenseCreate, db: Session = Depends(get_db)):
    return crud.create_expense(db, data)


@router.get("/", response_model=list[schemas.ExpenseRead])
def list_expenses(person_id: int = Query(None), period_value: str = Query(None),
                  category: str = Query(None), db: Session = Depends(get_db)):
    return crud.get_expenses(db, person_id, period_value, category)


@router.delete("/{expense_id}", status_code=204)
def delete_expense(expense_id: int, db: Session = Depends(get_db)):
    if not crud.delete_expense(db, expense_id):
        raise HTTPException(status_code=404, detail="Expense not found")
```

- [ ] **Step 4: Create fee configs API**

```python
# app/api/v1/finance/fee_configs.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app import crud, schemas

router = APIRouter(prefix="/finance/fee-configs", tags=["finance-fee-configs"])


@router.post("/", response_model=schemas.FeeConfigRead, status_code=201)
def create_fee_config(data: schemas.FeeConfigCreate, db: Session = Depends(get_db)):
    return crud.create_fee_config(db, data)


@router.get("/", response_model=list[schemas.FeeConfigRead])
def list_fee_configs(db: Session = Depends(get_db)):
    return crud.get_fee_configs(db)


@router.delete("/{config_id}", status_code=204)
def delete_fee_config(config_id: int, db: Session = Depends(get_db)):
    if not crud.delete_fee_config(db, config_id):
        raise HTTPException(status_code=404, detail="Fee config not found")
```

- [ ] **Step 5: Write tests and register routes**

Write a single test file `tests/api/test_finance_rest.py` covering mortgage, income, expense, and fee config APIs.

Update `app/main.py`:
```python
from app.api.v1.finance import mortgages, incomes, expenses, fee_configs
app.include_router(mortgages.router, prefix="/api/v1")
app.include_router(incomes.router, prefix="/api/v1")
app.include_router(expenses.router, prefix="/api/v1")
app.include_router(fee_configs.router, prefix="/api/v1")
```

```bash
git add app/api/v1/finance/mortgages.py app/api/v1/finance/incomes.py app/api/v1/finance/expenses.py app/api/v1/finance/fee_configs.py tests/api/test_finance_rest.py app/main.py
git commit -m "feat: add mortgage, income, expense, and fee config APIs"
```

---

### Task 9: Dashboard, Calculator, Transactions, and Reports APIs

**Files:**
- Create: `app/api/v1/finance/dashboard.py`
- Create: `app/api/v1/finance/calc.py`
- Create: `app/api/v1/finance/transactions.py`
- Create: `app/api/v1/finance/reports.py`
- Create: `tests/api/test_finance_dashboard.py`

- [ ] **Step 1: Create dashboard API**

```python
# app/api/v1/finance/dashboard.py
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db import get_db
from app import crud, schemas
from app.models import Loan, RepaymentPlan, PosSwipe, CreditCard, CardInstallment, Mortgage, Income, Expense
from app.finance.snapshot_service import compute_snapshot

router = APIRouter(prefix="/finance", tags=["finance-dashboard"])


@router.get("/dashboard", response_model=schemas.DashboardSummary)
def get_dashboard(db: Session = Depends(get_db)):
    today = date.today()
    # Get or create today's snapshot
    snap = crud.get_today_snapshot(db, today)
    if not snap:
        data = compute_snapshot(db, today)
        snap = crud.create_snapshot(db, data)

    # Sum wealth (incomes and deposits)
    total_income = db.query(func.coalesce(func.sum(Income.amount), 0)).scalar() or 0

    # Monthly interest from active repayment plans
    month_start = today.replace(day=1)
    monthly_interest = db.query(func.coalesce(func.sum(RepaymentPlan.interest), 0)).filter(
        RepaymentPlan.status == "pending",
        RepaymentPlan.due_date >= month_start,
        RepaymentPlan.due_date <= today.replace(day=28) + timedelta(days=7),
    ).scalar() or 0

    month_pos_fee = db.query(func.coalesce(func.sum(PosSwipe.fee), 0)).filter(
        func.strftime("%Y-%m", PosSwipe.swipe_date) == today.strftime("%Y-%m")
    ).scalar() or 0

    return {
        "total_debt": snap.total_debt,
        "total_assets": round(total_income, 2),
        "monthly_interest": round(monthly_interest, 2),
        "monthly_pos_fee": round(month_pos_fee, 2),
        "total_loan_debt": snap.loan_debt,
        "total_card_debt": snap.card_debt,
        "total_installment_debt": snap.installment_debt,
        "total_mortgage_debt": snap.mortgage_debt,
    }


@router.get("/repay-reminders", response_model=list[schemas.RepayReminderItem])
def get_repay_reminders(db: Session = Depends(get_db)):
    today = date.today()
    cutoff = today + timedelta(days=7)
    reminders = []

    # Loan repayments
    rps = db.query(RepaymentPlan).filter(
        RepaymentPlan.status == "pending",
        RepaymentPlan.due_date >= today,
        RepaymentPlan.due_date <= cutoff,
    ).all()
    for rp in rps:
        reminders.append(schemas.RepayReminderItem(
            type="loan",
            name=f"贷款 #{rp.loan_id}",
            person_name=rp.person.name if rp.person else "",
            card_last4="",
            due_date=rp.due_date,
            amount=rp.total_amount,
            days_left=(rp.due_date - today).days,
        ))

    # Credit card bills based on due_day
    cards = db.query(CreditCard).filter(CreditCard.status == "active").all()
    for card in cards:
        due_this_month = date(today.year, today.month, min(card.due_day, 28))
        if today <= due_this_month <= cutoff and card.current_balance > 0:
            reminders.append(schemas.RepayReminderItem(
                type="card",
                name=card.bank,
                person_name=card.person.name if card.person else "",
                card_last4=card.card_number_last4,
                due_date=due_this_month,
                amount=card.current_balance,
                days_left=(due_this_month - today).days,
            ))

    # Installments
    installments = db.query(CardInstallment).filter(
        CardInstallment.paid_periods < CardInstallment.periods,
    ).all()
    for inst in installments:
        due_date_inst = date(today.year, today.month, min(inst.card.due_day if inst.card else 1, 28))
        if today <= due_date_inst <= cutoff:
            reminders.append(schemas.RepayReminderItem(
                type="installment",
                name=f"{inst.card.bank if inst.card else ''} 分期",
                person_name=inst.person.name if inst.person else "",
                card_last4=inst.card.card_number_last4 if inst.card else "",
                due_date=due_date_inst,
                amount=inst.period_total,
                days_left=(due_date_inst - today).days,
            ))

    reminders.sort(key=lambda r: r.days_left)
    return reminders
```

- [ ] **Step 2: Create calculator API**

```python
# app/api/v1/finance/calc.py
from fastapi import APIRouter
from pydantic import BaseModel
from app.finance.calc_engine import (
    calc_equal_installment_plan, calc_interest_first_plan, calc_bullet_plan,
    calc_installment_annual_rate, convert_to_monthly_rate,
)

router = APIRouter(prefix="/finance/calc", tags=["finance-calc"])


class InterestCalcRequest(BaseModel):
    amount: float
    rate: float
    rate_type: str  # monthly / annual
    periods: int
    method: str  # equal_installment / interest_first / bullet
    start_date: str = "2000-01-01"


@router.post("/interest")
def calc_interest(data: InterestCalcRequest):
    monthly_rate = convert_to_monthly_rate(data.rate, data.rate_type)
    if data.method == "equal_installment":
        plan = calc_equal_installment_plan(data.amount, monthly_rate, data.periods, data.start_date)
    elif data.method == "interest_first":
        plan = calc_interest_first_plan(data.amount, monthly_rate, data.periods, data.start_date)
    else:
        plan = calc_bullet_plan(data.amount, monthly_rate, data.periods, data.start_date)
    total_interest = sum(p["interest"] for p in plan)
    return {"monthly_rate": monthly_rate, "plan": plan, "total_interest": total_interest}


class AnnualRateRequest(BaseModel):
    period_rate: float
    periods: int


@router.post("/annual-rate")
def calc_annual_rate(data: AnnualRateRequest):
    return {"annual_rate": calc_installment_annual_rate(data.period_rate, data.periods)}
```

- [ ] **Step 3: Create transactions API**

```python
# app/api/v1/finance/transactions.py
from datetime import date, datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db import get_db

router = APIRouter(prefix="/finance/transactions", tags=["finance-transactions"])


@router.get("/")
def list_transactions(
    type: str = Query(None),
    person_id: int = Query(None),
    date_from: date = Query(None),
    date_to: date = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    queries = []
    params = {}

    if not type or type == "loan":
        q = "SELECT id, 'loan' as type, person_id, amount, created_at FROM loans WHERE 1=1"
        if person_id:
            q += " AND person_id = :person_id"
            params["person_id"] = person_id
        if date_from:
            q += " AND created_at >= :date_from"
            params["date_from"] = date_from
        if date_to:
            q += " AND created_at <= :date_to"
            params["date_to"] = date_to
        queries.append(q)

    if not type or type == "pos":
        q = "SELECT id, 'pos' as type, person_id, amount, created_at FROM pos_swipes WHERE 1=1"
        if person_id:
            q += " AND person_id = :person_id"
        if date_from:
            q += " AND created_at >= :date_from"
        if date_to:
            q += " AND created_at <= :date_to"
        queries.append(q)

    if not type or type == "installment":
        q = "SELECT id, 'installment' as type, person_id, amount, created_at FROM card_installments WHERE 1=1"
        if person_id:
            q += " AND person_id = :person_id"
        if date_from:
            q += " AND created_at >= :date_from"
        if date_to:
            q += " AND created_at <= :date_to"
        queries.append(q)

    if not type or type == "card_trans":
        q = "SELECT id, 'card_trans' as type, person_id, amount, created_at FROM credit_card_transactions WHERE 1=1"
        if person_id:
            q += " AND person_id = :person_id"
        if date_from:
            q += " AND created_at >= :date_from"
        if date_to:
            q += " AND created_at <= :date_to"
        queries.append(q)

    if not type or type == "income":
        q = "SELECT id, 'income' as type, person_id, amount, created_at FROM incomes WHERE 1=1"
        if person_id:
            q += " AND person_id = :person_id"
        if date_from:
            q += " AND created_at >= :date_from"
        if date_to:
            q += " AND created_at <= :date_to"
        queries.append(q)

    if not type or type == "expense":
        q = "SELECT id, 'expense' as type, person_id, amount, created_at FROM expenses WHERE 1=1"
        if person_id:
            q += " AND person_id = :person_id"
        if date_from:
            q += " AND created_at >= :date_from"
        if date_to:
            q += " AND created_at <= :date_to"
        queries.append(q)

    if not queries:
        return {"items": [], "total": 0}

    union_sql = " UNION ALL ".join(queries)
    count_sql = f"SELECT COUNT(*) FROM ({union_sql})"
    total = db.execute(text(count_sql), params).scalar()

    offset = (page - 1) * page_size
    items = db.execute(
        text(f"{union_sql} ORDER BY created_at DESC LIMIT :limit OFFSET :offset"),
        {**params, "limit": page_size, "offset": offset},
    ).fetchall()

    return {
        "items": [{"id": r[0], "type": r[1], "person_id": r[2], "amount": r[3], "created_at": str(r[4])} for r in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
```

- [ ] **Step 4: Create reports API**

```python
# app/api/v1/finance/reports.py
from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db import get_db
from app.models import Loan, PosSwipe, Income, Expense, DebtSnapshot

router = APIRouter(prefix="/finance/reports", tags=["finance-reports"])


@router.get("/summary")
def report_summary(db: Session = Depends(get_db)):
    total_loans = db.query(func.coalesce(func.sum(Loan.amount), 0)).filter(Loan.status == "active").scalar() or 0
    total_pos_fee = db.query(func.coalesce(func.sum(PosSwipe.fee), 0)).scalar() or 0
    return {"total_active_loans": total_loans, "total_pos_fees": total_pos_fee}


@router.get("/by-platform")
def report_by_platform(db: Session = Depends(get_db)):
    results = db.query(
        LoanPlatform.name, func.coalesce(func.sum(Loan.amount), 0)
    ).join(Loan).filter(Loan.status == "active").group_by(LoanPlatform.name).all()
    return [{"platform": r[0], "total_amount": r[1]} for r in results]


@router.get("/by-month")
def report_by_month(db: Session = Depends(get_db)):
    results = db.query(
        func.strftime("%Y-%m", PosSwipe.swipe_date), func.coalesce(func.sum(PosSwipe.fee), 0)
    ).group_by(func.strftime("%Y-%m", PosSwipe.swipe_date)).order_by(
        func.strftime("%Y-%m", PosSwipe.swipe_date)
    ).all()
    return [{"month": r[0], "pos_fee": r[1]} for r in results]


@router.get("/gap-analysis")
def gap_analysis(year: int = Query(None), month: int = Query(None), db: Session = Depends(get_db)):
    if not year:
        year = date.today().year
    period_prefix = f"{year}-{month:02d}" if month else f"{year}-"

    income_total = db.query(func.coalesce(func.sum(Income.amount), 0)).filter(
        Income.period_value.like(f"{period_prefix}%")
    ).scalar() or 0

    expense_total = db.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
        Expense.period_value.like(f"{period_prefix}%")
    ).scalar() or 0

    # Debt payments summary
    from app.models import RepaymentPlan
    debt_payment = db.query(func.coalesce(func.sum(RepaymentPlan.total_amount), 0)).filter(
        RepaymentPlan.status == "pending"
    ).scalar() or 0

    total_expense = expense_total + debt_payment
    gap = income_total - total_expense

    return {
        "period": period_prefix.strip("%"),
        "total_income": income_total,
        "daily_expense": expense_total,
        "debt_payment": debt_payment,
        "total_expense": total_expense,
        "gap": gap,
    }
```

- [ ] **Step 5: Register routes and commit**

Update `app/main.py`:
```python
from app.api.v1.finance import dashboard, calc, transactions, reports
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(calc.router, prefix="/api/v1")
app.include_router(transactions.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
```

```bash
git add app/api/v1/finance/dashboard.py app/api/v1/finance/calc.py app/api/v1/finance/transactions.py app/api/v1/finance/reports.py tests/api/test_finance_dashboard.py app/main.py
git commit -m "feat: add dashboard, calculator, transactions, and reports APIs"
```

---

## Phase 4: Frontend

### Task 10: Finance Management Frontend (HTML + Vue 3 + ECharts)

**Files:**
- Create: `app/static/finance.html`
- Create: `app/static/finance-app.js`

- [ ] **Step 1: Create finance.html entry point**

Create `app/static/finance.html` with the dark financial theme, sidebar navigation, and Vue 3 + ECharts CDN references. The HTML includes:
- Dark theme CSS with colors from the spec (#0d0d1a background, #e94560/#00d2a0/#f9ca24/#4facfe accents)
- Left sidebar (200px) with all 10 navigation items
- Main content area with Vue router outlet
- ECharts CDN script tag

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FinManager - 个人财务管理</title>
    <script src="https://unpkg.com/vue@3/dist/vue.global.prod.js"></script>
    <script src="https://unpkg.com/vue-router@4/dist/vue-router.global.prod.js"></script>
    <script src="https://unpkg.com/echarts@5/dist/echarts.min.js"></script>
    <style>
        :root {
            --bg-primary: #0d0d1a;
            --bg-secondary: #13132b;
            --card-bg: rgba(26,26,46,0.8);
            --red: #e94560;
            --green: #00d2a0;
            --yellow: #f9ca24;
            --blue: #4facfe;
            --text: #ffffff;
            --text-secondary: #888888;
            --border: rgba(255,255,255,0.06);
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg-primary); color: var(--text); display: flex; min-height: 100vh; }
        .sidebar { width: 200px; background: var(--bg-secondary); border-right: 1px solid var(--border); padding: 20px 0; position: fixed; top: 0; left: 0; bottom: 0; overflow-y: auto; }
        .sidebar .logo { padding: 0 20px 24px; font-size: 18px; font-weight: bold; color: var(--red); }
        .sidebar .nav-item { padding: 10px 20px; color: var(--text-secondary); font-size: 13px; cursor: pointer; transition: all 0.2s; border-left: 3px solid transparent; }
        .sidebar .nav-item:hover, .sidebar .nav-item.active { color: var(--text); background: rgba(233,69,96,0.08); border-left-color: var(--red); }
        .main { margin-left: 200px; flex: 1; padding: 24px; }
        .stat-cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 20px; }
        .stat-card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 20px; backdrop-filter: blur(10px); }
        .stat-card .label { font-size: 11px; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 1px; }
        .stat-card .value { font-size: 26px; font-weight: bold; margin-top: 4px; }
        .stat-card .value.red { color: var(--red); }
        .stat-card .value.green { color: var(--green); }
        .stat-card .value.yellow { color: var(--yellow); }
        .stat-card .value.blue { color: var(--blue); }
        .chart-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px; }
        .chart-box { background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 16px; }
        .chart-box .title { font-size: 13px; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px; border-bottom: 1px solid var(--border); padding-bottom: 8px; }
        .remind-item { display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; border-radius: 8px; margin-bottom: 6px; font-size: 13px; }
        .remind-item.urgent { background: rgba(233,69,96,0.1); border-left: 3px solid var(--red); }
        .remind-item.warning { background: rgba(249,202,36,0.08); border-left: 3px solid var(--yellow); }
        .remind-item.normal { background: rgba(79,172,254,0.06); border-left: 3px solid var(--blue); }
        .badge { padding: 2px 10px; border-radius: 10px; font-size: 10px; font-weight: bold; }
        .badge.red { background: var(--red); color: white; }
        .badge.yellow { background: var(--yellow); color: black; }
        .badge.blue { background: var(--blue); color: white; }
        .form-group { margin-bottom: 12px; }
        .form-group label { display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 4px; }
        .form-group input, .form-group select { width: 100%; padding: 8px 12px; background: rgba(255,255,255,0.05); border: 1px solid var(--border); border-radius: 6px; color: var(--text); font-size: 13px; }
        .form-group input:focus, .form-group select:focus { outline: none; border-color: var(--red); }
        .btn { padding: 8px 16px; border: none; border-radius: 6px; font-size: 13px; cursor: pointer; transition: all 0.2s; }
        .btn-primary { background: var(--red); color: white; }
        .btn-primary:hover { background: #d03a50; }
        .btn-danger { background: transparent; border: 1px solid var(--red); color: var(--red); }
        .btn-sm { padding: 4px 10px; font-size: 11px; }
        table.data-table { width: 100%; border-collapse: collapse; font-size: 12px; }
        table.data-table th { background: var(--bg-secondary); padding: 10px; border: 1px solid var(--border); text-align: left; font-size: 11px; color: var(--text-secondary); text-transform: uppercase; }
        table.data-table td { padding: 8px 10px; border: 1px solid rgba(255,255,255,0.04); }
        table.data-table tr:hover { background: rgba(255,255,255,0.02); }
        .tag { padding: 2px 8px; border-radius: 4px; font-size: 10px; }
        .tag.red { background: rgba(233,69,96,0.2); color: var(--red); }
        .tag.blue { background: rgba(79,172,254,0.2); color: var(--blue); }
        .tag.yellow { background: rgba(249,202,36,0.2); color: var(--yellow); }
        .tag.green { background: rgba(0,210,160,0.2); color: var(--green); }
        .gap-box { padding: 20px; border-radius: 12px; text-align: center; margin-top: 16px; }
        .gap-box.negative { background: linear-gradient(135deg, rgba(233,69,96,0.12), rgba(233,69,96,0.04)); border: 1px solid rgba(233,69,96,0.3); }
        .gap-box.positive { background: linear-gradient(135deg, rgba(0,210,160,0.12), rgba(0,210,160,0.04)); border: 1px solid rgba(0,210,160,0.3); }
        .filter-bar { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; align-items: center; }
        .filter-chip { padding: 4px 12px; border-radius: 14px; font-size: 11px; border: 1px solid var(--border); background: transparent; color: var(--text-secondary); cursor: pointer; transition: all 0.2s; }
        .filter-chip.active { background: rgba(233,69,96,0.12); border-color: var(--red); color: var(--red); }
        .page-header { margin-bottom: 20px; }
        .page-header h2 { font-size: 20px; }
        .page-header p { font-size: 13px; color: var(--text-secondary); margin-top: 4px; }
    </style>
</head>
<body>
    <div id="app">
        <nav class="sidebar">
            <div class="logo">FinManager</div>
            <div v-for="item in navItems" :key="item.path" class="nav-item" :class="{ active: currentPath === item.path }"
                 @click="navigate(item.path)">{{ item.icon }} {{ item.label }}</div>
        </nav>
        <main class="main">
            <router-view></router-view>
        </main>
    </div>
    <script src="/static/finance-app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Create finance-app.js with Vue Router and all component pages**

The JS file should include:
1. Vue Router configuration with all 10 routes
2. API helper function
3. Dashboard component with ECharts integration (stat cards, interest trend chart, platform pie chart, 7-day reminders, gap analysis)
4. Loans component with create form, list table, repayment detail
5. POS component with create form, list, fee auto-calculation
6. Credit Cards component with create/edit form, list
7. Installments component with create form, list
8. Mortgage component with create form, list
9. Income/Expense components with create forms and lists
10. Transactions component with unified log view and type filters
11. Reports component with stat charts
12. Settings component with fee config and person management

Due to the length of this file (~800+ lines), the full JavaScript will be written in the implementation step.

- [ ] **Step 3: Test the frontend**

```bash
python -m uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000/static/finance.html in a browser and manually verify:
- Dashboard loads with stat cards and charts
- Each CRUD form creates records successfully
- Repayments and reminders display correctly

- [ ] **Step 4: Commit**

```bash
git add app/static/finance.html app/static/finance-app.js
git commit -m "feat: add dark-themed finance management frontend with ECharts"
```

---

### Task 11: Seed Data for Finance Module

**Files:**
- Modify: `seed_data.py` — append finance seed data
- Create: `seed_finance_data.py`

- [ ] **Step 1: Create finance-specific seed script**

Create `seed_finance_data.py` with sample data: 2 persons, 3 loan platforms, 2 loans with repayments, 3 POS swipes, 2 credit cards with transactions, 1 installment, 1 mortgage, sample incomes and expenses.

- [ ] **Step 2: Run seed and verify**

```bash
python seed_finance_data.py
python -m uvicorn app.main:app --reload
# Visit http://127.0.0.1:8000/static/finance.html to verify seed data shows up
```

- [ ] **Step 3: Commit**

```bash
git add seed_finance_data.py
git commit -m "feat: add seed data script for finance module"
```

---

### Task 12: Integration, Final Testing, and requirements.txt Update

**Files:**
- Modify: `requirements.txt`
- Run: Full test suite

- [ ] **Step 1: Update requirements.txt**

Check if `python-dateutil` is in requirements.txt. If not, add it.

- [ ] **Step 2: Run full test suite**

```bash
python -m pytest tests/ -v --ignore=tests/selenium
```
Expected: ALL PASS (existing + new finance tests)

- [ ] **Step 3: Verify app starts cleanly**

```bash
python -m uvicorn app.main:app --reload &
sleep 2
curl -s http://127.0.0.1:8000/ | python -m json.tool
curl -s http://127.0.0.1:8000/api/v1/finance/dashboard | python -m json.tool
```

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "chore: add python-dateutil dependency and finalize finance module"
```

---

## Verification

After all tasks complete, verify:
1. `python -m pytest tests/ -v --ignore=tests/selenium` — all tests pass
2. `python -m uvicorn app.main:app` — app starts without errors
3. Open `http://127.0.0.1:8000/static/finance.html` — dark-themed dashboard renders
4. Create a loan → repayment plan auto-generated correctly
5. Create a POS swipe → fee auto-calculated
6. Create a credit card installment → annual rate computed
7. Dashboard shows correct totals, reminders, and gap analysis
8. Unified transactions endpoint returns filtered results
