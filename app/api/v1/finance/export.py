"""数据导出 — CSV格式（Excel可直接打开）"""
import csv
import io
from datetime import date
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.db import get_db
from app.auth import get_current_user
from app.models import User, Loan, PosSwipe, CreditCard, CardInstallment, Mortgage, Income, Expense, CreditCardBill, CashRecord, RepaymentPlan

router = APIRouter(prefix="/finance/export", tags=["finance-export"])


@router.get("/all")
def export_all(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    output = io.StringIO()
    w = csv.writer(output)
    today = date.today().isoformat()

    # 贷款
    w.writerow(["=== 贷款 ==="])
    w.writerow(["ID", "人员", "平台", "金额", "利率", "利率类型", "还款方式", "总期数", "已还期数", "剩余期数", "状态", "开始日期", "备注"])
    for r in db.query(Loan).all():
        w.writerow([r.id, r.person.name if r.person else "", r.platform.name if r.platform else "", r.amount, r.rate, r.rate_type, r.repay_method, r.periods, r.paid_periods, r.remaining_periods, r.status, str(r.start_date) if r.start_date else "", r.note])

    # 还款计划
    w.writerow([])
    w.writerow(["=== 还款计划（已还）==="])
    w.writerow(["ID", "贷款ID", "期数", "本金", "利息", "总还款", "到期日", "还款日", "状态"])
    for r in db.query(RepaymentPlan).filter(RepaymentPlan.status == "paid").all():
        w.writerow([r.id, r.loan_id, r.period_no, r.principal, r.interest, r.total_amount, str(r.due_date) if r.due_date else "", str(r.paid_date) if r.paid_date else "", r.status])

    # POS刷卡
    w.writerow([])
    w.writerow(["=== POS刷卡 ==="])
    w.writerow(["ID", "人员", "金额", "费率", "手续费", "刷卡日期", "备注"])
    for r in db.query(PosSwipe).all():
        w.writerow([r.id, r.person.name if r.person else "", r.amount, r.fee_rate, r.fee, str(r.swipe_date) if r.swipe_date else "", r.note])

    # 信用卡
    w.writerow([])
    w.writerow(["=== 信用卡 ==="])
    w.writerow(["ID", "人员", "银行", "尾号", "额度", "余额", "年利率", "账单日", "还款日", "状态"])
    for r in db.query(CreditCard).all():
        w.writerow([r.id, r.person.name if r.person else "", r.bank, r.card_number_last4, r.credit_limit, r.current_balance, r.interest_rate, r.bill_day, r.due_day, r.status])

    # 信用卡账单
    w.writerow([])
    w.writerow(["=== 信用卡账单 ==="])
    w.writerow(["ID", "卡ID", "月份", "账单周期", "还款日", "账单金额", "已还", "利息", "手续费", "状态"])
    for r in db.query(CreditCardBill).all():
        w.writerow([r.id, r.card_id, r.bill_month, f"{r.bill_start}~{r.bill_end}", str(r.due_date), r.bill_amount, r.paid_amount, r.interest, r.fee, r.status])

    # 分期
    w.writerow([])
    w.writerow(["=== 分期 ==="])
    w.writerow(["ID", "人员", "信用卡", "金额", "期数", "每期本金", "每期还款", "已还", "开始日期", "总手续费"])
    for r in db.query(CardInstallment).all():
        card_name = r.card.bank if r.card else ""
        w.writerow([r.id, r.person.name if r.person else "", card_name, r.amount, r.periods, r.period_principal, r.period_total, r.paid_periods, str(r.start_date) if r.start_date else "", r.total_fee])

    # 房贷
    w.writerow([])
    w.writerow(["=== 房贷 ==="])
    w.writerow(["ID", "人员", "银行", "房产", "贷款总额", "剩余本金", "年利率", "月供", "状态"])
    for r in db.query(Mortgage).all():
        w.writerow([r.id, r.person.name if r.person else "", r.bank, r.house_name, r.total_amount, r.remaining_principal, r.rate, r.monthly_payment, r.status])

    # 收入
    w.writerow([])
    w.writerow(["=== 收入 ==="])
    w.writerow(["ID", "人员", "金额", "来源", "类型", "周期", "备注"])
    for r in db.query(Income).all():
        w.writerow([r.id, r.person.name if r.person else "", r.amount, r.source, r.period_type, r.period_value, r.note])

    # 支出
    w.writerow([])
    w.writerow(["=== 支出 ==="])
    w.writerow(["ID", "人员", "金额", "分类", "周期", "日期", "备注"])
    for r in db.query(Expense).all():
        w.writerow([r.id, r.person.name if r.person else "", r.amount, r.category, r.period_value, str(r.expense_date) if r.expense_date else "", r.note])

    # 现金
    w.writerow([])
    w.writerow(["=== 手头现金 ==="])
    w.writerow(["ID", "金额", "日期", "备注"])
    for r in db.query(CashRecord).all():
        w.writerow([r.id, r.amount, str(r.recorded_at), r.note])

    output.seek(0)
    filename = f"caizhiguanjia_export_{today}.csv"
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv; charset=utf-8-sig",
                             headers={"Content-Disposition": f"attachment; filename={filename}"})
