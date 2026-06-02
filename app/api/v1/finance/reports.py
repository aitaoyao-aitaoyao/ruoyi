from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from app.db import get_db
from app.auth import get_current_user, require_role
from app.models import User
from app.models import Loan, LoanPlatform, PosSwipe, Income, Expense, RepaymentPlan, DebtSnapshot, CardInstallment, Mortgage, CreditCard
from app import crud, schemas

router = APIRouter(prefix="/finance/reports", tags=["finance-reports"])


def _month_prefixes_in_range(date_from: str, date_to: str) -> list[str]:
    """生成 date_from ~ date_to 范围内所有 YYYY-MM 前缀。"""
    df = date.fromisoformat(date_from).replace(day=1)
    dt = date.fromisoformat(date_to).replace(day=1)
    prefixes = []
    cursor = df
    while cursor <= dt:
        prefixes.append(cursor.strftime("%Y-%m"))
        cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
    return prefixes


def _period_filter(column, prefixes: list[str]):
    """为 period_value 列构建 OR LIKE 过滤条件。"""
    if not prefixes:
        return True
    return or_(*[column.like(f"{p}%") for p in prefixes])


@router.get("/summary")
def report_summary(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    total_loans = db.query(func.coalesce(func.sum(Loan.amount), 0)).filter(Loan.status == "active").scalar() or 0
    total_pos_fee = db.query(func.coalesce(func.sum(PosSwipe.fee), 0)).scalar() or 0
    return {"total_active_loans": total_loans, "total_pos_fees": total_pos_fee}


@router.get("/by-platform")
def report_by_platform(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """各平台贷款剩余待还款金额（按平台汇总）。"""
    from collections import defaultdict
    platform_totals = defaultdict(float)

    active_loans = db.query(Loan).filter(Loan.status == "active").all()
    for loan in active_loans:
        # 计算该贷款剩余待还款本金
        pending = db.query(func.coalesce(func.sum(RepaymentPlan.principal), 0)).filter(
            RepaymentPlan.loan_id == loan.id,
            RepaymentPlan.status == "pending",
        ).scalar() or 0
        remaining = pending if pending > 0 else loan.amount

        platform_name = loan.platform.name if loan.platform else "未知平台"
        platform_totals[platform_name] += remaining

    return [{"platform": k, "total_amount": round(v, 2)} for k, v in platform_totals.items()]


@router.get("/by-month")
def report_by_month(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    results = db.query(
        func.strftime("%Y-%m", PosSwipe.swipe_date), func.coalesce(func.sum(PosSwipe.fee), 0)
    ).group_by(func.strftime("%Y-%m", PosSwipe.swipe_date)).order_by(
        func.strftime("%Y-%m", PosSwipe.swipe_date)
    ).all()
    return [{"month": r[0], "pos_fee": r[1]} for r in results]


@router.get("/gap-analysis")
def gap_analysis(date_from: str = Query(None), date_to: str = Query(None),
                 year: int = Query(None), month: int = Query(None),
                 db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """收支缺口分析，支持年份/月份或日期区间查询。"""
    if date_from and date_to:
        period_prefix = None
        period_label = f"{date_from} ~ {date_to}"
        prefixes = _month_prefixes_in_range(date_from, date_to)
    elif year:
        period_prefix = f"{year}-{month:02d}" if month else f"{year}-"
        period_label = period_prefix
        prefixes = None
    else:
        year = date.today().year
        period_prefix = f"{year}-"
        period_label = period_prefix
        month = None
        prefixes = None

    if period_prefix or prefixes:
        if prefixes:
            income_filter = _period_filter(Income.period_value, prefixes)
            expense_filter = _period_filter(Expense.period_value, prefixes)
        else:
            income_filter = Income.period_value.like(f"{period_prefix}%")
            expense_filter = Expense.period_value.like(f"{period_prefix}%")

        income_total = db.query(func.coalesce(func.sum(Income.amount), 0)).filter(
            income_filter
        ).scalar() or 0

        expense_total = db.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
            expense_filter
        ).scalar() or 0

        # 待还款：仅统计所选时间范围内到期的还款计划
        if prefixes:
            debt_filter = or_(*[func.strftime("%Y-%m", RepaymentPlan.due_date) == p for p in prefixes])
            debt_payment = db.query(func.coalesce(func.sum(RepaymentPlan.total_amount), 0)).filter(
                RepaymentPlan.status == "pending", debt_filter
            ).scalar() or 0
        elif month:
            debt_payment = db.query(func.coalesce(func.sum(RepaymentPlan.total_amount), 0)).filter(
                RepaymentPlan.status == "pending",
                func.strftime("%Y-%m", RepaymentPlan.due_date) == period_prefix,
            ).scalar() or 0
        else:
            debt_payment = db.query(func.coalesce(func.sum(RepaymentPlan.total_amount), 0)).filter(
                RepaymentPlan.status == "pending",
                func.strftime("%Y-%m", RepaymentPlan.due_date).like(f"{period_prefix}%"),
            ).scalar() or 0
    else:
        income_total = expense_total = debt_payment = 0

    total_expense = expense_total + debt_payment
    gap = income_total - total_expense

    # 支出分类明细
    expense_by_cat = db.query(
        Expense.category, func.coalesce(func.sum(Expense.amount), 0)
    )
    if prefixes:
        expense_by_cat = expense_by_cat.filter(_period_filter(Expense.period_value, prefixes))
    elif period_prefix:
        expense_by_cat = expense_by_cat.filter(Expense.period_value.like(f"{period_prefix}%"))
    expense_by_cat = expense_by_cat.group_by(Expense.category).order_by(func.sum(Expense.amount).desc()).all()

    # 收入来源明细
    income_sources = db.query(
        Income.source, func.coalesce(func.sum(Income.amount), 0)
    )
    if prefixes:
        income_sources = income_sources.filter(_period_filter(Income.period_value, prefixes))
    elif period_prefix:
        income_sources = income_sources.filter(Income.period_value.like(f"{period_prefix}%"))
    income_sources = income_sources.group_by(Income.source).all()

    return {
        "period": period_label,
        "total_income": round(income_total, 2),
        "daily_expense": round(expense_total, 2),
        "debt_payment": round(debt_payment, 2),
        "total_expense": round(total_expense, 2),
        "gap": round(gap, 2),
        "expense_breakdown": [{"category": r[0], "amount": round(r[1], 2)} for r in expense_by_cat],
        "income_sources": [{"source": r[0], "amount": round(r[1], 2)} for r in income_sources],
    }


@router.get("/gap-analysis-detail")
def gap_analysis_detail(
    date_from: str = Query(None), date_to: str = Query(None),
    year: int = Query(None), month: int = Query(None),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    """数据驱动的收支缺口分析，生成个性化洞察和改进建议。"""
    today = date.today()

    # --- 确定查询周期 ---
    if date_from and date_to:
        period_prefix = None
        period_label = f"{date_from} ~ {date_to}"
        prefixes = _month_prefixes_in_range(date_from, date_to)
        df_date = date.fromisoformat(date_from)
        target_year = df_date.year
        target_month = df_date.month
    elif year:
        period_prefix = f"{year}-{month:02d}" if month else f"{year}-"
        period_label = period_prefix
        prefixes = None
        target_year = year
        target_month = month
    else:
        target_year = today.year
        target_month = today.month
        period_prefix = f"{target_year}-{target_month:02d}"
        period_label = period_prefix
        prefixes = None

    # --- 1. 当期收支缺口 ---
    if period_prefix or prefixes:
        if prefixes:
            income_filter = _period_filter(Income.period_value, prefixes)
            expense_filter = _period_filter(Expense.period_value, prefixes)
        else:
            income_filter = Income.period_value.like(f"{period_prefix}%")
            expense_filter = Expense.period_value.like(f"{period_prefix}%")

        income_total = db.query(func.coalesce(func.sum(Income.amount), 0)).filter(
            income_filter
        ).scalar() or 0

        expense_total = db.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
            expense_filter
        ).scalar() or 0

        if prefixes:
            debt_filter = or_(*[func.strftime("%Y-%m", RepaymentPlan.due_date) == p for p in prefixes])
            debt_payment = db.query(func.coalesce(func.sum(RepaymentPlan.total_amount), 0)).filter(
                RepaymentPlan.status == "pending", debt_filter
            ).scalar() or 0
        elif month:
            debt_payment = db.query(func.coalesce(func.sum(RepaymentPlan.total_amount), 0)).filter(
                RepaymentPlan.status == "pending",
                func.strftime("%Y-%m", RepaymentPlan.due_date) == period_prefix,
            ).scalar() or 0
        else:
            debt_payment = db.query(func.coalesce(func.sum(RepaymentPlan.total_amount), 0)).filter(
                RepaymentPlan.status == "pending",
                func.strftime("%Y-%m", RepaymentPlan.due_date).like(f"{period_prefix}%"),
            ).scalar() or 0
    else:
        income_total = expense_total = debt_payment = 0

    total_expense = expense_total + debt_payment
    gap = income_total - total_expense
    savings_rate = round((gap / income_total) * 100, 1) if income_total > 0 else 0
    debt_to_income = round((debt_payment / income_total) * 100, 1) if income_total > 0 else (100 if debt_payment > 0 else 0)

    # 支出分类
    expense_by_cat_q = db.query(
        Expense.category, func.coalesce(func.sum(Expense.amount), 0)
    )
    if prefixes:
        expense_by_cat_q = expense_by_cat_q.filter(_period_filter(Expense.period_value, prefixes))
    elif period_prefix:
        expense_by_cat_q = expense_by_cat_q.filter(Expense.period_value.like(f"{period_prefix}%"))
    expense_by_cat = expense_by_cat_q.group_by(Expense.category).order_by(func.sum(Expense.amount).desc()).all()

    # 收入来源
    income_sources_q = db.query(
        Income.source, func.coalesce(func.sum(Income.amount), 0)
    )
    if prefixes:
        income_sources_q = income_sources_q.filter(_period_filter(Income.period_value, prefixes))
    elif period_prefix:
        income_sources_q = income_sources_q.filter(Income.period_value.like(f"{period_prefix}%"))
    income_sources = income_sources_q.group_by(Income.source).all()

    # --- 2. 近6个月缺口趋势 ---
    gap_trend = []
    for i in range(5, -1, -1):
        m = today.replace(day=1) - relativedelta(months=i)
        m_prefix = f"{m.year}-{m.month:02d}"
        m_income = db.query(func.coalesce(func.sum(Income.amount), 0)).filter(
            Income.period_value.like(f"{m_prefix}%")
        ).scalar() or 0
        m_expense = db.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
            Expense.period_value.like(f"{m_prefix}%")
        ).scalar() or 0
        m_debt = db.query(func.coalesce(func.sum(RepaymentPlan.total_amount), 0)).filter(
            RepaymentPlan.status == "pending",
            func.strftime("%Y-%m", RepaymentPlan.due_date) == m_prefix,
        ).scalar() or 0
        m_gap = m_income - m_expense - m_debt
        m_savings = round((m_gap / m_income) * 100, 1) if m_income > 0 else 0
        gap_trend.append({
            "month": m_prefix,
            "income": round(m_income, 2),
            "expense": round(m_expense + m_debt, 2),
            "gap": round(m_gap, 2),
            "savings_rate": m_savings,
        })

    # --- 3. 债务结构 ---
    cards = db.query(CreditCard).filter(CreditCard.status == "active", CreditCard.current_balance > 0).all()
    card_debt_total = sum(c.current_balance for c in cards)
    # 信用卡加权平均利率
    if card_debt_total > 0:
        card_rate = sum(c.current_balance * (c.interest_rate or 0.1825) for c in cards) / card_debt_total
    else:
        card_rate = 0
    card_monthly_interest = sum(c.current_balance * (c.interest_rate or 0.1825) / 12 for c in cards)

    active_loans = db.query(Loan).filter(Loan.status == "active").all()
    loan_debt_total = 0
    loan_rates = []
    for loan in active_loans:
        pending = db.query(func.coalesce(func.sum(RepaymentPlan.principal), 0)).filter(
            RepaymentPlan.loan_id == loan.id, RepaymentPlan.status == "pending"
        ).scalar() or 0
        if pending <= 0:
            pending = loan.amount
        loan_debt_total += pending
        if loan.rate_type == "annual":
            annual = loan.rate
        else:
            annual = loan.rate * 12
        loan_rates.append({
            "name": f"{loan.platform.name if loan.platform else '贷款'} #{loan.id}",
            "person_name": loan.person.name if loan.person else "",
            "balance": round(pending, 2),
            "annual_rate": round(annual, 4),
            "rate_label": f"{round(annual * 100, 2)}%",
        })

    mortgages = db.query(Mortgage).filter(Mortgage.status == "active", Mortgage.remaining_principal > 0).all()
    mtg_debt_total = sum(m.remaining_principal for m in mortgages)
    mtg_monthly_interest = sum(m.remaining_principal * m.rate / 12 for m in mortgages)

    installments = db.query(CardInstallment).all()
    inst_debt_total = 0
    for inst in installments:
        remaining = inst.amount - inst.period_principal * min(inst.paid_periods, inst.periods)
        if remaining > 0:
            inst_debt_total += remaining

    debt_total = card_debt_total + loan_debt_total + inst_debt_total + mtg_debt_total

    # --- 4. 分类趋势（近3个月） ---
    category_trend = {}
    for i in range(2, -1, -1):
        m = today.replace(day=1) - relativedelta(months=i)
        m_prefix = f"{m.year}-{m.month:02d}"
        cat_rows = db.query(
            Expense.category, func.coalesce(func.sum(Expense.amount), 0)
        ).filter(Expense.period_value.like(f"{m_prefix}%")).group_by(Expense.category).all()
        for cat, amt in cat_rows:
            if cat not in category_trend:
                category_trend[cat] = []
            category_trend[cat].append({"month": m_prefix, "amount": round(amt, 2)})

    # --- 5. 生成洞察 ---
    observations = []

    # 储蓄率评估
    consecutive_negative = 0
    for g in gap_trend:
        if g["savings_rate"] < 0:
            consecutive_negative += 1
        else:
            consecutive_negative = 0
    if consecutive_negative >= 2:
        prev_sr = gap_trend[-2]["savings_rate"] if len(gap_trend) >= 2 else 0
        if savings_rate < prev_sr:
            observations.append({
                "severity": "critical",
                "category": "savings_rate",
                "text": f"本月储蓄率 {savings_rate}%，连续 {consecutive_negative} 个月为负，较上月 {prev_sr}% 进一步恶化",
            })
        else:
            observations.append({
                "severity": "warning",
                "category": "savings_rate",
                "text": f"本月储蓄率 {savings_rate}%，连续 {consecutive_negative} 个月为负，但较上月有所改善",
            })
    elif savings_rate < 0:
        observations.append({
            "severity": "warning",
            "category": "savings_rate",
            "text": f"本月储蓄率 {savings_rate}%，入不敷出，需关注资金平衡",
        })
    elif savings_rate < 10:
        observations.append({
            "severity": "neutral",
            "category": "savings_rate",
            "text": f"本月储蓄率 {savings_rate}%，虽然为正但低于建议的 10% 底线",
        })
    elif savings_rate >= 20:
        observations.append({
            "severity": "positive",
            "category": "savings_rate",
            "text": f"本月储蓄率 {savings_rate}%，财务状况健康，建议将结余合理投资",
        })

    # 收入为0
    if income_total == 0:
        observations.append({
            "severity": "critical",
            "category": "income",
            "text": "当前无收入数据，无法进行完整财务分析，建议尽快录入收入信息",
        })

    # 负债率
    if debt_to_income > 50:
        observations.append({
            "severity": "warning",
            "category": "debt_ratio",
            "text": f"待还债务占收入比 {debt_to_income}%，超过 50% 警戒线，偿债压力较大",
        })
    elif debt_to_income > 30:
        observations.append({
            "severity": "neutral",
            "category": "debt_ratio",
            "text": f"待还债务占收入比 {debt_to_income}%，处于中等水平，需持续关注",
        })

    # 债务总额
    if debt_total > 0 and income_total > 0:
        debt_months = round(debt_total / income_total, 1) if income_total > 0 else 0
        if debt_months > 12:
            observations.append({
                "severity": "warning",
                "category": "debt_total",
                "text": f"总负债 ¥{int(debt_total):,} 相当于 {debt_months} 个月收入，远超健康水平",
            })

    # 高息债务（信用卡 vs 贷款）
    if card_debt_total > 0:
        avg_loan_rate = sum(r["annual_rate"] for r in loan_rates) / len(loan_rates) if loan_rates else 0
        if card_rate > avg_loan_rate + 0.05:
            observations.append({
                "severity": "warning",
                "category": "high_interest",
                "text": f"信用卡债务年化利率 {card_rate*100:.2f}%，远高于平均贷款利率 {avg_loan_rate*100:.2f}%，应优先偿还信用卡",
            })

    # 收入来源集中度
    if len(income_sources) == 1 and income_total > 0:
        observations.append({
            "severity": "neutral",
            "category": "income_diversity",
            "text": f"收入来源单一（仅「{income_sources[0][0]}」），建议拓展多元化收入渠道以降低风险",
        })

    # 支出集中度
    if expense_by_cat and expense_total > 0:
        top_cat = expense_by_cat[0]
        top_pct = round(top_cat[1] / expense_total * 100, 1) if expense_total > 0 else 0
        if top_pct > 40:
            observations.append({
                "severity": "neutral",
                "category": "spending_concentration",
                "text": f"「{top_cat[0]}」支出占日常消费的 {top_pct}%，集中度较高",
            })

    # 支出类别增长趋势
    if len(gap_trend) >= 2 and expense_by_cat:
        top_cat_name = expense_by_cat[0][0]
        cat_trend_data = category_trend.get(top_cat_name, [])
        if len(cat_trend_data) >= 3:
            increasing = all(
                cat_trend_data[i]["amount"] < cat_trend_data[i + 1]["amount"]
                for i in range(len(cat_trend_data) - 1)
            )
            if increasing:
                growth = cat_trend_data[-1]["amount"] - cat_trend_data[0]["amount"]
                observations.append({
                    "severity": "warning",
                    "category": "spending_growth",
                    "text": f"「{top_cat_name}」支出连续 3 个月增长，累计增加 ¥{int(growth):,}，建议审视消费习惯",
                })

    # 缺口趋势改善
    if len(gap_trend) >= 3:
        recent = [g["gap"] for g in gap_trend[-3:]]
        if recent[0] < recent[1] < recent[2]:
            observations.append({
                "severity": "positive",
                "category": "gap_trend",
                "text": "近 3 个月收支缺口持续收窄，财务状况正在改善",
            })

    # --- 6. 生成建议 ---
    recommendations = []
    priority = 0

    # 高息债务优先
    if card_debt_total > 0:
        priority += 1
        card_list = [f"{c.bank}({c.card_number_last4})" for c in cards]
        months_to_payoff = round(card_debt_total / (income_total * 0.2), 1) if income_total > 0 and savings_rate < 20 else 0
        rec = {
            "priority": priority,
            "category": "debt",
            "impact": "high",
            "text": f"优先偿还信用卡债务（年化 {card_rate*100:.2f}%）：{'、'.join(card_list)}，合计 ¥{int(card_debt_total):,}，月利息约 ¥{int(card_monthly_interest):,}",
        }
        if months_to_payoff > 0 and months_to_payoff < 60:
            rec["action"] = f"若将月收入 20% 用于还款，预计 {months_to_payoff} 个月可还清，节省利息约 ¥{int(card_debt_total * card_rate * months_to_payoff / 12):,}"
        recommendations.append(rec)

    # 多笔贷款利率对比
    if len(loan_rates) >= 2:
        loan_rates_sorted = sorted(loan_rates, key=lambda x: x["annual_rate"], reverse=True)
        if loan_rates_sorted[0]["annual_rate"] > loan_rates_sorted[-1]["annual_rate"] + 0.02:
            priority += 1
            recommendations.append({
                "priority": priority,
                "category": "debt",
                "impact": "medium",
                "text": f"采用雪崩法还贷：优先偿还利率最高的 {loan_rates_sorted[0]['name']}（{loan_rates_sorted[0]['rate_label']}），依次向下",
                "action": f"最高利率 {loan_rates_sorted[0]['rate_label']} vs 最低 {loan_rates_sorted[-1]['rate_label']}，优先还高息贷款可最大程度减少利息支出",
            })

    # 储蓄率低
    if savings_rate < 10 and income_total > 0:
        priority += 1
        target_savings = income_total * 0.2
        rec = {
            "priority": priority,
            "category": "savings",
            "impact": "high",
            "text": f"储蓄率仅 {savings_rate}%，建议目标储蓄率 20%，即每月至少储蓄 ¥{int(target_savings):,}",
        }
        if expense_by_cat:
            non_essential = [c for c in expense_by_cat if c[0] in ("购物", "娱乐", "餐饮", "其他")]
            if non_essential:
                total_non = sum(c[1] for c in non_essential)
                rec["action"] = f"可削减的非必要支出约 ¥{int(total_non):,}（{'/'.join(c[0] for c in non_essential[:3])}），减少一半即可达标"
        recommendations.append(rec)

    # 应急金
    if expense_total > 0 and savings_rate >= 0:
        monthly_needed = expense_total  # 月基本开支
        emergency_target = monthly_needed * 3
        if savings_rate > 0:
            monthly_saving = gap
            if monthly_saving > 0:
                months_to_emergency = round(emergency_target / monthly_saving, 1)
                if months_to_emergency > 6:
                    priority += 1
                    recommendations.append({
                        "priority": priority,
                        "category": "emergency_fund",
                        "impact": "medium",
                        "text": f"建立 3 个月应急储备金需 ¥{int(emergency_target):,}，按当前储蓄速度需 {months_to_emergency} 个月",
                        "action": f"建议先储蓄 ¥{int(monthly_needed):,}（1 个月基本开支）作为起点",
                    })

    # 收入多元化
    if len(income_sources) <= 1 and income_total > 0:
        priority += 1
        recommendations.append({
            "priority": priority,
            "category": "income",
            "impact": "medium",
            "text": "收入来源单一，建议拓展副业、投资理财或技能变现等第二收入渠道",
            "action": "即使每月增加 ¥500-1,000 的额外收入，也能显著提升财务稳定性",
        })

    # 如果没有任何问题
    if len(observations) == 0 and savings_rate >= 10:
        observations.append({
            "severity": "positive",
            "category": "overall",
            "text": "整体财务状况良好，保持当前的收支节奏，可考虑将结余用于投资增值",
        })

    sorted_recs = sorted(recommendations, key=lambda x: x["priority"])

    return {
        "period": period_label,
        "summary": {
            "gap": round(gap, 2),
            "total_income": round(income_total, 2),
            "total_expense": round(total_expense, 2),
            "daily_expense": round(expense_total, 2),
            "debt_payment": round(debt_payment, 2),
            "savings_rate": savings_rate,
            "debt_to_income_ratio": debt_to_income,
        },
        "observations": observations,
        "recommendations": sorted_recs,
        "trends": {
            "gap_6m": gap_trend,
        },
        "benchmarks": {
            "china_inflation_rate": "约 0.3%（2026年4月 CPI）",
            "recommended_savings_rate": "20-30%",
            "healthy_debt_to_income": "< 40%",
            "source": "基于中国人民银行及国家统计局公开数据",
        },
    }


@router.get("/interest-stats")
def interest_stats(
    stat_type: str = Query("monthly", description="monthly / yearly / range"),
    year: int = Query(None),
    month: int = Query(None),
    date_from: str = Query(None),
    date_to: str = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """按类型统计利息/手续费：贷款利息、POS手续费、分期手续费、房贷利息。"""
    if stat_type == "range" and date_from and date_to:
        date_filter_loan = (RepaymentPlan.paid_date >= date_from) & (RepaymentPlan.paid_date <= date_to)
        date_filter_pos = (PosSwipe.swipe_date >= date_from) & (PosSwipe.swipe_date <= date_to)
        period_label = f"{date_from} ~ {date_to}"
    elif stat_type == "monthly" and year and month:
        period_str = f"{year}-{month:02d}"
        date_filter_loan = func.strftime("%Y-%m", RepaymentPlan.paid_date) == period_str
        date_filter_pos = func.strftime("%Y-%m", PosSwipe.swipe_date) == period_str
        period_label = period_str
    elif stat_type == "yearly" and year:
        period_str = f"{year}-"
        date_filter_loan = func.strftime("%Y-%m", RepaymentPlan.paid_date).like(f"{period_str}%")
        date_filter_pos = func.strftime("%Y-%m", PosSwipe.swipe_date).like(f"{period_str}%")
        period_label = f"{year}年"
    else:
        # 默认当年
        year = date.today().year
        month = None
        period_str = f"{year}-"
        date_filter_loan = func.strftime("%Y-%m", RepaymentPlan.paid_date).like(f"{period_str}%")
        date_filter_pos = func.strftime("%Y-%m", PosSwipe.swipe_date).like(f"{period_str}%")
        period_label = f"{year}年"

    # 已还贷款利息
    loan_interest = db.query(func.coalesce(func.sum(RepaymentPlan.interest), 0)).filter(
        RepaymentPlan.status == "paid", date_filter_loan
    ).scalar() or 0

    # POS 手续费
    pos_fee = db.query(func.coalesce(func.sum(PosSwipe.fee), 0)).filter(
        date_filter_pos
    ).scalar() or 0

    # 分期手续费（按已还期数比例计算，根据时间范围过滤）
    installments = db.query(CardInstallment).all()
    installment_fee = 0
    for inst in installments:
        if inst.paid_periods <= 0:
            continue
        fee_per_period = inst.total_fee / inst.periods
        if stat_type == "monthly" and year and month:
            # 统计特定月份的已还期数
            count = 0
            for n in range(1, inst.paid_periods + 1):
                pd = inst.start_date + relativedelta(months=n - 1)
                if pd.year == year and pd.month == month:
                    count += 1
            installment_fee += fee_per_period * count
        elif stat_type == "yearly" or (not month and year):
            # 统计特定年份的已还期数
            count = 0
            for n in range(1, inst.paid_periods + 1):
                pd = inst.start_date + relativedelta(months=n - 1)
                if pd.year == year:
                    count += 1
            installment_fee += fee_per_period * count
        elif stat_type == "range" and date_from and date_to:
            df = date.fromisoformat(date_from)
            dt = date.fromisoformat(date_to)
            count = 0
            for n in range(1, inst.paid_periods + 1):
                pd = inst.start_date + relativedelta(months=n - 1)
                if df <= pd <= dt:
                    count += 1
            installment_fee += fee_per_period * count
        else:
            installment_fee += inst.total_fee * inst.paid_periods / inst.periods

    # 房贷利息（月供 - 本金部分，近似计算）
    mortgages = db.query(Mortgage).filter(Mortgage.status == "active").all()
    mortgage_interest = 0
    # 确定实际统计类型
    effective_type = stat_type
    if effective_type == "monthly" and not (year and month):
        # 走默认路径时 stat_type 仍为 monthly，实际是 yearly
        effective_type = "yearly"
    for m in mortgages:
        monthly_interest = m.remaining_principal * m.rate / 12
        if effective_type == "monthly":
            mortgage_interest += monthly_interest
        elif effective_type == "yearly":
            mortgage_interest += monthly_interest * 12
        elif effective_type == "range" and date_from and date_to:
            df = date.fromisoformat(date_from)
            dt = date.fromisoformat(date_to)
            months = (dt.year - df.year) * 12 + (dt.month - df.month) + 1
            mortgage_interest += monthly_interest * min(months, 12)

    total_interest = round(loan_interest + pos_fee + installment_fee + mortgage_interest, 2)

    return {
        "period": period_label,
        "total_interest": total_interest,
        "loan_interest": round(loan_interest, 2),
        "pos_fee": round(pos_fee, 2),
        "installment_fee": round(installment_fee, 2),
        "mortgage_interest": round(mortgage_interest, 2),
    }


@router.get("/repay-priority")
def repay_priority(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """生成优先还款方案，按年化利率从高到低排列（雪崩法）。"""
    items = []

    # 信用卡（按每张卡的实际利率）
    cards = db.query(CreditCard).filter(CreditCard.status == "active", CreditCard.current_balance > 0).all()
    for c in cards:
        annual_rate = c.interest_rate or 0.1825
        items.append({
            "debt_type": "信用卡",
            "name": f"{c.bank} 尾号{c.card_number_last4}",
            "person_name": c.person.name if c.person else "",
            "balance": round(c.current_balance, 2),
            "annual_rate": round(annual_rate, 4),
            "rate_label": f"{(annual_rate * 100):.2f}%",
            "note": f"透支利率 {(annual_rate*100):.2f}%",
        })

    # 分期
    installments = db.query(CardInstallment).all()
    for inst in installments:
        remaining = inst.amount - inst.period_principal * min(inst.paid_periods, inst.periods)
        if remaining <= 0:
            continue
        annual_rate = inst.annual_rate or 0
        card_name = inst.card.bank if inst.card else ""
        items.append({
            "debt_type": "分期",
            "name": f"{card_name} 分期#{inst.id}",
            "person_name": inst.person.name if inst.person else "",
            "balance": round(remaining, 2),
            "annual_rate": round(annual_rate, 4),
            "rate_label": f"{(annual_rate * 100):.2f}%",
            "note": f"剩余{inst.periods - inst.paid_periods}期，每期¥{round(inst.period_total, 2)}",
        })

    # 贷款
    loans = db.query(Loan).filter(Loan.status == "active").all()
    for loan in loans:
        pending_principal = db.query(func.coalesce(func.sum(RepaymentPlan.principal), 0)).filter(
            RepaymentPlan.loan_id == loan.id,
            RepaymentPlan.status == "pending",
        ).scalar() or 0
        if pending_principal <= 0:
            pending_principal = loan.amount
        if loan.rate_type == "annual":
            annual_rate = loan.rate
        else:
            annual_rate = loan.rate * 12  # monthly to annual
        items.append({
            "debt_type": "贷款",
            "name": f"{loan.platform.name if loan.platform else ''} #{loan.id}",
            "person_name": loan.person.name if loan.person else "",
            "balance": round(pending_principal, 2),
            "annual_rate": round(annual_rate, 4),
            "rate_label": f"{(annual_rate * 100):.2f}%",
            "note": loan.repay_method if loan.repay_method else "",
        })

    # 房贷
    mortgages = db.query(Mortgage).filter(Mortgage.status == "active", Mortgage.remaining_principal > 0).all()
    for m in mortgages:
        items.append({
            "debt_type": "房贷",
            "name": f"{m.bank} {m.house_name}",
            "person_name": m.person.name if m.person else "",
            "balance": round(m.remaining_principal, 2),
            "annual_rate": round(m.rate, 4),
            "rate_label": f"{(m.rate * 100):.2f}%",
            "note": f"月供¥{round(m.monthly_payment, 2)}",
        })

    # 按年化利率降序排列（雪崩法）
    items.sort(key=lambda x: x["annual_rate"], reverse=True)

    total_debt = sum(it["balance"] for it in items)
    total_monthly_interest = sum(it["balance"] * it["annual_rate"] / 12 for it in items)

    return {
        "items": items,
        "total_debt": round(total_debt, 2),
        "total_monthly_interest": round(total_monthly_interest, 2),
        "method": "雪崩法（优先偿还利率最高的债务，总利息支出最小）",
    }


@router.get("/debt-forecast")
def debt_forecast(
    months: int = Query(12, ge=1, le=36, description="预测月数"),
    include_mortgage: bool = Query(True, description="是否包含房贷"),
    monthly_surplus: float = Query(None, description="月均结余（用于加速还债），不传则自动从近6月收支缺口计算"),
    monthly_new_borrowing: float = Query(0, ge=0, description="预估月均新增借款"),
    db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """基于还款计划、收支缺口、信用卡复利推演负债变化。

    每月逻辑：
    1. 信用卡产生循环利息（按每张卡设定的年化利率），有余额则每月计息
    2. 按还款计划扣除贷款/分期/房贷本金
    3. 月结余优先偿还最高利率债务（雪崩法：信用卡 > 高息贷款 > 低息贷款）
    4. 新增借款加入贷款负债
    """
    today = date.today()

    # ---- 当前负债基准 ----
    from app.finance.snapshot_service import compute_snapshot
    snap = compute_snapshot(db, today)
    base = {
        "loan_debt": snap["loan_debt"],
        "card_debt": snap["card_debt"],
        "installment_debt": snap["installment_debt"],
        "mortgage_debt": snap["mortgage_debt"],
        "total_debt": snap["total_debt"],
    }
    base["total_debt_ex_mortgage"] = round(base["total_debt"] - base["mortgage_debt"], 2)

    # ---- 自动计算月均结余（近6月收支缺口均值） ----
    auto_surplus = 0.0
    gap_months = 0
    for i in range(1, 7):
        m = today.replace(day=1) - relativedelta(months=i)
        m_prefix = f"{m.year}-{m.month:02d}"
        m_income = db.query(func.coalesce(func.sum(Income.amount), 0)).filter(
            Income.period_value.like(f"{m_prefix}%")
        ).scalar() or 0
        m_expense = db.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
            Expense.period_value.like(f"{m_prefix}%")
        ).scalar() or 0
        m_debt = db.query(func.coalesce(func.sum(RepaymentPlan.total_amount), 0)).filter(
            RepaymentPlan.status == "pending",
            func.strftime("%Y-%m", RepaymentPlan.due_date) == m_prefix,
        ).scalar() or 0
        if m_income > 0:
            gap_months += 1
            auto_surplus += m_income - m_expense - m_debt
    if gap_months > 0:
        auto_surplus = round(auto_surplus / gap_months, 2)

    # 用户手动指定的结余优先，否则用自动计算值
    effective_surplus = monthly_surplus if monthly_surplus is not None else auto_surplus

    # ---- 每月还本金额（来自还款计划） ----
    pending_rps = db.query(RepaymentPlan).filter(RepaymentPlan.status == "pending").all()
    monthly_principals = {}
    for rp in pending_rps:
        key = rp.due_date.strftime("%Y-%m") if rp.due_date else ""
        monthly_principals[key] = monthly_principals.get(key, 0) + rp.principal
    if monthly_principals:
        loan_monthly_principal = sum(monthly_principals.values()) / len(monthly_principals)
    else:
        loan_monthly_principal = 0.0

    # 分期每月本金
    installments = db.query(CardInstallment).all()
    inst_monthly_principal = 0.0
    for inst in installments:
        remaining = inst.periods - inst.paid_periods
        if remaining > 0:
            inst_monthly_principal += inst.period_principal

    # 房贷每月本金（月供 - 利息）
    mtg_monthly_principal = 0.0
    if include_mortgage:
        mortgages = db.query(Mortgage).filter(Mortgage.status == "active").all()
        for m in mortgages:
            monthly_int = m.remaining_principal * m.rate / 12
            mtg_monthly_principal += m.monthly_payment - monthly_int

    # ---- 逐月推演 ----
    # 信用卡加权平均利率
    cards = db.query(CreditCard).filter(CreditCard.status == "active", CreditCard.current_balance > 0).all()
    card_total = sum(c.current_balance for c in cards)
    if card_total > 0:
        card_rate_avg = sum(c.current_balance * (c.interest_rate or 0.1825) for c in cards) / card_total
    else:
        card_rate_avg = 0.1825
    f_loan = base["loan_debt"]
    f_card = base["card_debt"]
    f_inst = base["installment_debt"]
    f_mtg = base["mortgage_debt"] if include_mortgage else 0

    forecasts = []
    cum_card_interest = 0.0  # 累计信用卡利息

    for i in range(1, months + 1):
        forecast_date = today + relativedelta(months=i)
        month_label = f"{forecast_date.year}-{forecast_date.month:02d}"

        # 1. 信用卡产生循环利息（有余额时）
        card_interest_this_month = 0.0
        if f_card > 0:
            card_interest_this_month = f_card * card_rate_avg / 12
            f_card += card_interest_this_month
            cum_card_interest += card_interest_this_month

        # 2. 按还款计划扣除贷款本金
        f_loan = max(0, f_loan - loan_monthly_principal)

        # 3. 分期本金减少
        f_inst = max(0, f_inst - inst_monthly_principal)

        # 4. 房贷本金减少
        if include_mortgage:
            f_mtg = max(0, f_mtg - mtg_monthly_principal)

        # 5. 新增借款
        if monthly_new_borrowing > 0:
            f_loan += monthly_new_borrowing

        # 6. 月结余优先偿还高息债务（雪崩法：信用卡 > 贷款）
        surplus = effective_surplus
        if surplus > 0:
            # 先还信用卡（利率最高）
            if f_card > 0:
                pay_card = min(surplus, f_card)
                f_card = max(0, f_card - pay_card)
                surplus -= pay_card
            # 再还贷款
            if surplus > 0 and f_loan > 0:
                f_loan = max(0, f_loan - surplus)

        f_ex_mtg = f_loan + f_card + f_inst
        f_total = f_ex_mtg + (f_mtg if include_mortgage else 0)

        forecasts.append({
            "month": month_label,
            "loan_debt": round(f_loan, 2),
            "card_debt": round(f_card, 2),
            "installment_debt": round(f_inst, 2),
            "mortgage_debt": round(f_mtg, 2),
            "total_debt": round(f_total, 2),
            "total_debt_ex_mortgage": round(f_ex_mtg, 2),
            "card_interest_month": round(card_interest_this_month, 2),
            "is_current": False,
        })

    # ---- 趋势描述 ----
    parts = []
    if abs(effective_surplus) > 100:
        if effective_surplus > 0:
            parts.append(f"月均结余 ¥{int(effective_surplus):,} 用于加速还款")
        else:
            parts.append(f"月均缺口 ¥{int(abs(effective_surplus)):,}，无额外还款能力")
    if monthly_new_borrowing > 0:
        parts.append(f"月均新增借款 ¥{int(monthly_new_borrowing):,}")
    if cum_card_interest > 100:
        parts.append(f"{months}个月累计信用卡利息约 ¥{int(cum_card_interest):,}")
    trend_desc = "；".join(parts) if parts else ""

    trends = {
        "loan_trend": round(-loan_monthly_principal + monthly_new_borrowing, 2),
        "card_trend": round(0, 2),
        "installment_trend": round(-inst_monthly_principal, 2),
        "card_interest_monthly": round(base["card_debt"] * card_rate_avg / 12, 2) if base["card_debt"] > 0 else 0,
        "auto_monthly_surplus": auto_surplus,
        "effective_monthly_surplus": effective_surplus,
    }
    if include_mortgage:
        trends["mortgage_trend"] = round(-mtg_monthly_principal, 2)

    return {
        "base": base,
        "include_mortgage": include_mortgage,
        "monthly_surplus": effective_surplus,
        "monthly_new_borrowing": monthly_new_borrowing,
        "trends": trends,
        "trend_desc": trend_desc,
        "forecasts": forecasts,
    }


@router.get("/pos-count")
def pos_count(
    stat_type: str = Query("monthly", description="monthly / yearly / range"),
    year: int = Query(None),
    month: int = Query(None),
    date_from: str = Query(None),
    date_to: str = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """按时间统计 POS 刷卡次数。"""
    if stat_type == "range" and date_from and date_to:
        date_filter = (PosSwipe.swipe_date >= date_from) & (PosSwipe.swipe_date <= date_to)
        group_col = func.strftime("%Y-%m", PosSwipe.swipe_date)
        period_label = f"{date_from} ~ {date_to}"
    elif stat_type == "monthly" and year and month:
        period_str = f"{year}-{month:02d}"
        date_filter = func.strftime("%Y-%m", PosSwipe.swipe_date) == period_str
        group_col = func.strftime("%Y-%m-%d", PosSwipe.swipe_date)
        period_label = period_str
    elif stat_type == "yearly" and year:
        period_str = f"{year}-"
        date_filter = func.strftime("%Y-%m", PosSwipe.swipe_date).like(f"{period_str}%")
        group_col = func.strftime("%Y-%m", PosSwipe.swipe_date)
        period_label = f"{year}年"
    else:
        year = date.today().year
        period_str = f"{year}-"
        date_filter = func.strftime("%Y-%m", PosSwipe.swipe_date).like(f"{period_str}%")
        group_col = func.strftime("%Y-%m", PosSwipe.swipe_date)
        period_label = f"{year}年"

    results = db.query(
        group_col.label("period"),
        func.count(PosSwipe.id).label("count"),
    ).filter(date_filter).group_by(group_col).order_by(group_col).all()

    total_count = sum(r.count for r in results)

    return {
        "period": period_label,
        "stat_type": stat_type,
        "total_count": total_count,
        "items": [{"period": r.period, "count": r.count} for r in results],
    }


@router.get("/snapshots", response_model=list[schemas.DebtSnapshotRead])
def get_snapshots(months: int = Query(12, ge=1, le=60), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return crud.get_snapshots(db, months)
