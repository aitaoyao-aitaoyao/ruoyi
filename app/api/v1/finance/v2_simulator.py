"""
债务模拟器 + 风险评级 — 情景模拟、收入测算、提前还款分析
"""
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db import get_db
from app.auth import get_current_user
from app.models import User
from app.models import Loan, RepaymentPlan, PosSwipe, CardInstallment, Mortgage, Income, Expense, CashRecord
from app.finance.snapshot_service import compute_snapshot

router = APIRouter(prefix="/finance/v2", tags=["finance-v2-simulator"])


def _rate(value, thresholds):
    """通用风险评级，thresholds 为 [B阈值, C阈值, D阈值, E阈值]"""
    if value is None:
        return 5  # E
    for i, t in enumerate(thresholds):
        if value <= t:
            return i + 1  # A=1, B=2, ...
    return 5


def _rate_reverse(value, thresholds):
    """反向评级（越小越危险）"""
    if value is None:
        return 5
    for i, t in enumerate(thresholds):
        if value >= t:
            return i + 1
    return 5


def _grade_label(score):
    labels = {1: "A·安全", 2: "B·轻度风险", 3: "C·中度风险", 4: "D·高风险", 5: "E·极高风险"}
    colors = {1: "#00d2a0", 2: "#4facfe", 3: "#f9ca24", 4: "#e94560", 5: "#e94560"}
    return {"grade": chr(64 + score), "label": labels.get(score, "?"), "color": colors.get(score, "#888")}


@router.get("/simulator")
def simulator(
    salary: float = Query(None, description="模拟月薪资"),
    side_income: float = Query(0, description="模拟副业月收入"),
    extra_payment: float = Query(0, description="额外月还款额"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """债务模拟器：根据输入的薪资/副业/额外还款计算各项指标变化。"""
    today = date.today()
    month_prefix = today.strftime("%Y-%m")

    # 基础数据
    monthly_interest = _get_monthly_interest(db, today)
    monthly_pos_fee = db.query(func.coalesce(func.sum(PosSwipe.fee), 0)).filter(
        func.strftime("%Y-%m", PosSwipe.swipe_date) == month_prefix
    ).scalar() or 0

    # 当月实际收入和支出
    actual_income = db.query(func.coalesce(func.sum(Income.amount), 0)).filter(
        Income.period_value.like(f"{month_prefix}%")
    ).scalar() or 0
    actual_expense = db.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
        Expense.period_value.like(f"{month_prefix}%")
    ).scalar() or 0

    # 模拟收入
    sim_income = salary or actual_income
    total_income = sim_income + side_income

    snap = compute_snapshot(db, today)
    total_debt = snap["total_debt"]

    # 手头现金
    latest_cash = db.query(CashRecord).order_by(CashRecord.recorded_at.desc(), CashRecord.id.desc()).first()
    cash = latest_cash.amount if latest_cash else 0

    # 计算各项指标
    survival_line = round(total_income - actual_expense - monthly_interest, 2)
    interest_rate = round((monthly_interest / total_income) * 100, 1) if total_income > 0 else 0
    debt_freedom = round(total_debt / survival_line, 1) if survival_line > 0 and total_debt > 0 else (None if survival_line <= 0 else 0)

    cash_gap = total_income - actual_expense - monthly_interest
    rupture = round(cash / abs(cash_gap), 1) if cash_gap < 0 and cash > 0 else None

    # 年度净还债
    annual_repay = round(survival_line * 12, 2)

    # 额外还款效果
    extra_survival = round(survival_line + extra_payment, 2)
    extra_freedom = round(total_debt / extra_survival, 1) if extra_survival > 0 and total_debt > 0 else None
    extra_save = round(extra_payment * 12, 2) if extra_payment > 0 else 0

    return {
        "inputs": {"salary": total_income, "side_income": side_income, "extra_payment": extra_payment, "actual_income": actual_income, "actual_expense": actual_expense, "monthly_interest": monthly_interest, "cash_on_hand": round(cash, 2), "total_debt": round(total_debt, 2)},
        "current": {"survival_line": round(actual_income - actual_expense - monthly_interest, 2), "interest_consumption": round((monthly_interest / actual_income) * 100, 1) if actual_income > 0 else 0, "debt_freedom": None, "rupture": None},
        "simulated": {"survival_line": survival_line, "interest_consumption": interest_rate, "debt_freedom_months": debt_freedom, "cash_flow_rupture": rupture, "annual_net_repay": annual_repay},
        "extra_payment_effect": {"new_survival_line": extra_survival, "new_debt_freedom": extra_freedom, "annual_interest_saved": extra_save},
    }


@router.get("/presets")
def simulator_presets(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """返回预设薪资/副业档位对应的各项指标。"""
    today = date.today()
    month_prefix = today.strftime("%Y-%m")

    actual_income = db.query(func.coalesce(func.sum(Income.amount), 0)).filter(
        Income.period_value.like(f"{month_prefix}%")
    ).scalar() or 0
    actual_expense = db.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
        Expense.period_value.like(f"{month_prefix}%")
    ).scalar() or 0
    monthly_interest = _get_monthly_interest(db, today)
    snap = compute_snapshot(db, today)
    total_debt = snap["total_debt"]

    salary_presets = [actual_income or 12000, 15000, 18000, 22000, 30000]
    side_presets = [1000, 3000, 5000, 10000]
    extra_presets = [1000, 5000, 10000]

    results = {"current": _compute_row(actual_income, 0, actual_expense, monthly_interest, total_debt, "💼 当前")}

    for s in salary_presets:
        if s == actual_income and actual_income > 0: continue
        results[f"salary_{s}"] = _compute_row(s, 0, actual_expense, monthly_interest, total_debt, "💼 跳槽")

    for s in side_presets:
        if actual_income > 0:
            results[f"side_{s}"] = _compute_row(actual_income, s, actual_expense, monthly_interest, total_debt, "💰 副业")

    for s in side_presets:
        if actual_income > 0:
            results[f"combo_{s}"] = _compute_row(actual_income + s, 0, actual_expense, monthly_interest, total_debt, "💼+💰 组合")

    for e in extra_presets:
        sl = actual_income - actual_expense - monthly_interest + e
        df = round(total_debt / sl, 1) if sl > 0 and total_debt > 0 else None
        results[f"extra_{e}"] = {"type": "💰 提前还款", "monthly_income": f"+¥{e:,}", "survival_line": round(sl, 2), "interest_rate": round((monthly_interest / actual_income * 100), 1) if actual_income > 0 else 0, "debt_freedom": df, "annual_repay": round(sl * 12, 2)}

    return results


def _compute_row(income, side, expense, interest, debt, type_label):
    total = income + side
    sl = round(total - expense - interest, 2)
    ir = round((interest / total) * 100, 1) if total > 0 else 0
    df = round(debt / sl, 1) if sl > 0 and debt > 0 else None
    return {"type": type_label, "monthly_income": f"¥{total:,}", "survival_line": sl, "interest_rate": ir, "debt_freedom": df, "annual_repay": round(sl * 12, 2)}


def _get_monthly_interest(db, today):
    """获取当月总利息（复用 dashboard 逻辑）。"""
    month_start = today.replace(day=1)
    loan_interest = db.query(func.coalesce(func.sum(RepaymentPlan.interest), 0)).filter(
        RepaymentPlan.status == "pending",
        RepaymentPlan.due_date >= month_start,
        RepaymentPlan.due_date <= today.replace(day=28) + timedelta(days=7),
    ).scalar() or 0

    installments = db.query(CardInstallment).all()
    inst_fee = 0.0
    for inst in installments:
        if inst.total_fee <= 0: continue
        fee_per = inst.total_fee / inst.periods
        for n in range(1, inst.periods + 1):
            pd = inst.start_date + relativedelta(months=n - 1)
            if pd.year == today.year and pd.month == today.month:
                inst_fee += fee_per

    mortgages = db.query(Mortgage).filter(Mortgage.status == "active").all()
    mtg_interest = sum(m.remaining_principal * m.rate / 12 for m in mortgages)
    return round(loan_interest + inst_fee + mtg_interest, 2)


@router.get("/risk-assessment")
def risk_assessment(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """综合风险评级 A-E，含 5 个维度的拆解。"""
    today = date.today()
    month_prefix = today.strftime("%Y-%m")

    income = db.query(func.coalesce(func.sum(Income.amount), 0)).filter(Income.period_value.like(f"{month_prefix}%")).scalar() or 0
    expense = db.query(func.coalesce(func.sum(Expense.amount), 0)).filter(Expense.period_value.like(f"{month_prefix}%")).scalar() or 0
    interest = _get_monthly_interest(db, today)
    snap = compute_snapshot(db, today)

    latest_cash = db.query(CashRecord).order_by(CashRecord.recorded_at.desc(), CashRecord.id.desc()).first()
    cash = latest_cash.amount if latest_cash else 0

    survival_line = round(income - expense - interest, 2)
    interest_pct = round((interest / income) * 100, 1) if income > 0 else 0
    debt_ratio = round((snap["total_debt"] / income) * 100, 1) if income > 0 else (100 if snap["total_debt"] > 0 else 0)
    cash_gap = income - expense - interest
    rupture = round(cash / abs(cash_gap), 1) if cash_gap < 0 and cash > 0 else None
    cash_months = round(cash / expense, 1) if expense > 0 and cash > 0 else (0 if cash <= 0 else None)

    # 生存线评级: >月收入10%=A, 0~10%=B, -10%~0=C, -30%~-10%=D, <-30%=E
    sl_threshold = income * 0.1 if income > 0 else 1
    sl_score = 1 if survival_line > sl_threshold else (2 if survival_line > 0 else (3 if survival_line > -income * 0.1 else (4 if survival_line > -income * 0.3 else 5)))

    # 利息吞噬率: <15%=A, 15-25%=B, 25-40%=C, 40-60%=D, >60%=E
    ir_score = _rate(interest_pct, [15, 25, 40, 60])

    # 资产负债率: <30%=A, 30-50%=B, 50-80%=C, 80-100%=D, >100%=E
    dr_score = _rate(debt_ratio, [30, 50, 80, 100])

    # 现金流破裂: 无风险=A, >12月=B, 6-12月=C, 3-6月=D, <3月=E
    if cash_gap >= 0: cf_score = 1
    elif rupture is None: cf_score = 5
    else: cf_score = _rate_reverse(rupture, [12, 6, 3])

    # 手头现金: >6月开支=A, 3-6月=B, 1-3月=C, <1月=D, 0=E
    if cash_months is None or cash <= 0: ch_score = 5
    else: ch_score = _rate_reverse(cash_months, [6, 3, 1])

    dimensions = {
        "survival_line": {"name": "生存线", "score": sl_score, "value": survival_line, "weight": 0.25, **_grade_label(sl_score)},
        "interest_consumption": {"name": "利息吞噬率", "score": ir_score, "value": interest_pct, "weight": 0.25, **_grade_label(ir_score)},
        "debt_ratio": {"name": "资产负债率", "score": dr_score, "value": debt_ratio, "weight": 0.20, **_grade_label(dr_score)},
        "cash_flow": {"name": "现金流破裂", "score": cf_score, "value": rupture, "weight": 0.15, **_grade_label(cf_score)},
        "cash_on_hand": {"name": "手头现金", "score": ch_score, "value": cash, "weight": 0.15, **_grade_label(ch_score)},
    }

    total_score = sum(d["score"] * d["weight"] for d in dimensions.values())
    # 1.0-1.5→A, 1.5-2.5→B, 2.5-3.5→C, 3.5-4.5→D, 4.5-5.0→E
    overall = 1 if total_score < 1.5 else (2 if total_score < 2.5 else (3 if total_score < 3.5 else (4 if total_score < 4.5 else 5)))

    return {
        "period": month_prefix,
        "overall": {"score": round(total_score, 2), **_grade_label(overall)},
        "dimensions": dimensions,
        "inputs": {"monthly_income": round(income, 2), "monthly_expense": round(expense, 2), "monthly_interest": interest, "total_debt": round(snap["total_debt"], 2), "cash_on_hand": round(cash, 2)},
    }
