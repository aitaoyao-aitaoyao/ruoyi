"""
V2 风险分析仪表盘 — 债务燃烧率、生存线、债务自由预测、现金流破裂预警、利息消耗率

所有指标基于现有数据实时计算，不修改数据库。
"""
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db import get_db
from app.auth import get_current_user
from app.models import User
from app.models import Loan, RepaymentPlan, PosSwipe, CardInstallment, Mortgage, Income, Expense, CashRecord
from app.finance.snapshot_service import compute_snapshot

router = APIRouter(prefix="/finance", tags=["finance-v2-dashboard"])


def _risk(result, thresholds):
    """根据阈值判定风险等级。
    thresholds: (safe_below, warn_below, danger_above) — 越小越好的指标
    或使用 reverse=True 表示越大越好。
    """
    safe, warn = thresholds
    if result is None:
        return {"risk_level": "unknown", "risk_color": "#888", "risk_label": "无数据"}
    if result <= safe:
        return {"risk_level": "safe", "risk_color": "#00d2a0", "risk_label": "健康"}
    elif result <= warn:
        return {"risk_level": "warning", "risk_color": "#f9ca24", "risk_label": "关注"}
    else:
        return {"risk_level": "danger", "risk_color": "#e94560", "risk_label": "高危"}


def _risk_reverse(result, thresholds):
    """反向风险判定：值越小越危险。
    thresholds: (danger_below, warn_below, safe_above)
    """
    danger, warn = thresholds
    if result is None:
        return {"risk_level": "unknown", "risk_color": "#888", "risk_label": "无数据"}
    if result < danger:
        return {"risk_level": "danger", "risk_color": "#e94560", "risk_label": "高危"}
    elif result < warn:
        return {"risk_level": "warning", "risk_color": "#f9ca24", "risk_label": "关注"}
    else:
        return {"risk_level": "safe", "risk_color": "#00d2a0", "risk_label": "健康"}


@router.get("/v2/dashboard")
def get_v2_dashboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    today = date.today()
    month_prefix = today.strftime("%Y-%m")
    month_start = today.replace(day=1)
    month_end = (today.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)

    # =============================================
    # 共用基础数据查询
    # =============================================

    # 当月收入
    monthly_income = db.query(func.coalesce(func.sum(Income.amount), 0)).filter(
        Income.period_value.like(f"{month_prefix}%")
    ).scalar() or 0

    # 当月家庭支出
    monthly_expense = db.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
        Expense.period_value.like(f"{month_prefix}%")
    ).scalar() or 0

    # 当月贷款利息（待还还款计划，due_date 在本月窗口内）
    loan_interest = db.query(func.coalesce(func.sum(RepaymentPlan.interest), 0)).filter(
        RepaymentPlan.status == "pending",
        RepaymentPlan.due_date >= month_start,
        RepaymentPlan.due_date <= month_end,
    ).scalar() or 0

    # 当月分期手续费（全部分期中落在本月的期数，无论是否已还）
    installments = db.query(CardInstallment).all()
    inst_fee = 0.0
    inst_principal_paid = 0.0  # 实际已还的当月分期本金
    for inst in installments:
        fee_per_period = inst.total_fee / inst.periods if inst.total_fee > 0 else 0
        for n in range(1, inst.periods + 1):
            pd = inst.start_date + relativedelta(months=n - 1)
            if pd.year == today.year and pd.month == today.month:
                if inst.total_fee > 0:
                    inst_fee += fee_per_period
                # 只有当该期已还时才计入本金减少
                if n <= inst.paid_periods and inst.period_principal > 0:
                    inst_principal_paid += inst.period_principal

    # 当月房贷利息
    mortgages = db.query(Mortgage).filter(Mortgage.status == "active").all()
    mtg_interest = sum(m.remaining_principal * m.rate / 12 for m in mortgages)
    # 房贷本月还本金 = 月供 - 月利息
    mtg_principal = sum(
        m.monthly_payment - (m.remaining_principal * m.rate / 12)
        for m in mortgages
    )

    # 当月 POS 手续费
    monthly_pos_fee = db.query(func.coalesce(func.sum(PosSwipe.fee), 0)).filter(
        func.strftime("%Y-%m", PosSwipe.swipe_date) == month_prefix
    ).scalar() or 0

    # 当月已还贷款本金（从还款计划中统计本月 paid 的）
    paid_loan_principal = db.query(func.coalesce(func.sum(RepaymentPlan.principal), 0)).filter(
        RepaymentPlan.status == "paid",
        func.strftime("%Y-%m", RepaymentPlan.paid_date) == month_prefix,
    ).scalar() or 0

    # 手头现金（最近一次录入）
    latest_cash = db.query(CashRecord).order_by(CashRecord.recorded_at.desc(), CashRecord.id.desc()).first()
    cash_on_hand = latest_cash.amount if latest_cash else 0

    # 总负债（从快照服务获取）
    snap = compute_snapshot(db, today)

    # 月度汇总
    monthly_interest = round(loan_interest + inst_fee + mtg_interest, 2)
    monthly_principal_paid = round(paid_loan_principal + inst_principal_paid + mtg_principal, 2)

    # =============================================
    # 指标 1: 债务燃烧率
    # =============================================
    debt_burn_rate = round(monthly_interest + monthly_pos_fee - monthly_principal_paid, 2)
    burn_risk = _risk(debt_burn_rate, (0, 1000))  # ≤0 健康, ≤1000 关注, >1000 高危
    if debt_burn_rate < 0:
        burn_desc = f"债务每月净减少 ¥{abs(debt_burn_rate):,.0f}"
    elif debt_burn_rate == 0:
        burn_desc = "债务规模持平"
    else:
        burn_desc = f"债务每月净增长 ¥{debt_burn_rate:,.0f}"

    # =============================================
    # 指标 2: 生存线
    # =============================================
    survival_line = round(monthly_income - monthly_expense - monthly_interest - monthly_pos_fee, 2)
    survival_risk = _risk_reverse(survival_line, (0, monthly_income * 0.1))
    if survival_line < 0:
        survival_desc = f"每月现金流缺口 ¥{abs(survival_line):,.0f}"
    elif survival_line == 0:
        survival_desc = "收支刚好平衡"
    else:
        survival_desc = f"月结余 ¥{survival_line:,.0f} 可用于偿债"

    # =============================================
    # 指标 3: 债务自由预期（月）
    # =============================================
    if survival_line > 0 and snap["total_debt"] > 0:
        debt_freedom_months = round(snap["total_debt"] / survival_line, 1)
        if debt_freedom_months > 1200:
            debt_freedom_formatted = ">100 年（不切实际）"
        elif debt_freedom_months >= 12:
            debt_freedom_formatted = f"{debt_freedom_months / 12:.1f} 年"
        else:
            debt_freedom_formatted = f"{debt_freedom_months:.0f} 个月"
        freedom_risk = _risk(debt_freedom_months, (24, 60))
        freedom_desc = f"预计 {debt_freedom_formatted} 还清全部债务"
    elif snap["total_debt"] <= 0:
        debt_freedom_months = 0
        debt_freedom_formatted = "已无债务"
        freedom_risk = {"risk_level": "safe", "risk_color": "#00d2a0", "risk_label": "健康"}
        freedom_desc = "当前无债务"
    else:
        debt_freedom_months = None
        debt_freedom_formatted = "无法还清"
        freedom_risk = {"risk_level": "danger", "risk_color": "#e94560", "risk_label": "高危"}
        freedom_desc = "生存线为负，债务永续增长"

    # =============================================
    # 指标 4: 现金流破裂预警（月）
    # =============================================
    cash_gap = round(monthly_income - monthly_expense - monthly_interest - monthly_pos_fee, 2)  # 与生存线保持一致
    if cash_gap < 0 and cash_on_hand > 0:
        cash_flow_rupture = round(cash_on_hand / abs(cash_gap), 1)
        rupture_formatted = f"{cash_flow_rupture:.0f} 个月"
        rupture_risk = _risk_reverse(cash_flow_rupture, (3, 6))
        rupture_desc = f"手头现金 ¥{cash_on_hand:,.0f} 可支撑 {cash_flow_rupture:.0f} 个月"
    elif cash_gap >= 0:
        cash_flow_rupture = None
        rupture_formatted = "无破裂风险"
        rupture_risk = {"risk_level": "safe", "risk_color": "#00d2a0", "risk_label": "健康"}
        rupture_desc = "当月现金流为正"
    else:
        cash_flow_rupture = None
        rupture_formatted = "无现金储备"
        rupture_risk = {"risk_level": "danger", "risk_color": "#e94560", "risk_label": "高危"}
        rupture_desc = "手头现金为0，无应急缓冲"

    # =============================================
    # 指标 5: 利息消耗率
    # =============================================
    if monthly_income > 0:
        interest_consumption_rate = round((monthly_interest / monthly_income) * 100, 1)
        consumption_risk = _risk(interest_consumption_rate, (15, 30))
        consumption_desc = f"利息消耗占月收入 {interest_consumption_rate}%"
    else:
        interest_consumption_rate = 0
        consumption_risk = {"risk_level": "unknown", "risk_color": "#888", "risk_label": "无收入"}
        consumption_desc = "当月无收入数据"

    # =============================================
    # 组装响应
    # =============================================
    return {
        "period": month_prefix,
        "inputs": {
            "monthly_income": round(monthly_income, 2),
            "monthly_expense": round(monthly_expense, 2),
            "monthly_interest": monthly_interest,
            "monthly_pos_fee": round(monthly_pos_fee, 2),
            "monthly_principal_paid": monthly_principal_paid,
            "cash_on_hand": round(cash_on_hand, 2),
            "total_debt": round(snap["total_debt"], 2),
        },
        "metrics": {
            "debt_burn_rate": {
                "value": debt_burn_rate,
                "formatted": f"¥{debt_burn_rate:+,.0f}",
                **burn_risk,
                "description": burn_desc,
            },
            "survival_line": {
                "value": survival_line,
                "formatted": f"¥{survival_line:+,.0f}",
                **survival_risk,
                "description": survival_desc,
            },
            "debt_freedom_months": {
                "value": debt_freedom_months,
                "formatted": debt_freedom_formatted,
                **freedom_risk,
                "description": freedom_desc,
            },
            "cash_flow_rupture": {
                "value": cash_flow_rupture,
                "formatted": rupture_formatted,
                **rupture_risk,
                "description": rupture_desc,
            },
            "interest_consumption_rate": {
                "value": interest_consumption_rate,
                "formatted": f"{interest_consumption_rate}%",
                **consumption_risk,
                "description": consumption_desc,
            },
        },
    }
