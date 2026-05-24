"""
Finance Manager 种子数据脚本。
生成示例财务数据，用于本地开发和测试。

用法:
    python seed_finance_data.py
"""
import sys
from datetime import date, datetime

from app.db import engine, SessionLocal, Base
from app.models import (
    Person, LoanPlatform, Loan, RepaymentPlan, PosSwipe,
    CreditCard, CreditCardTransaction, CardInstallment,
    Mortgage, Income, Expense, FeeConfig,
)
from app.finance.calc_engine import (
    convert_to_monthly_rate, calc_equal_installment_plan,
    calc_interest_first_plan, calc_installment_annual_rate,
    calc_pos_fee,
)


def seed():
    # 确保财务表存在
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 检查是否已有数据，避免重复插入
        if db.query(Person).count() > 0:
            print("种子数据已存在，跳过。如需重新生成请先清空财务表。")
            return

        # ===== 人员 =====
        p_self = Person(name="张三", relation="本人")
        p_spouse = Person(name="李四", relation="配偶")
        db.add_all([p_self, p_spouse])
        db.commit()

        # ===== 借贷平台 =====
        plat_jiebei = LoanPlatform(name="借呗", icon="🐜", description="支付宝借呗")
        plat_weilidai = LoanPlatform(name="微粒贷", icon="💬", description="微信微粒贷")
        plat_douyin = LoanPlatform(name="抖音月付", icon="🎵", description="抖音月付")
        db.add_all([plat_jiebei, plat_weilidai, plat_douyin])
        db.commit()

        # ===== 借款 + 还款计划 =====
        # 借呗：等额本息，10000元，12期，月利率1%
        monthly_rate = 0.01
        plan = calc_equal_installment_plan(amount=10000, monthly_rate=monthly_rate, periods=12, start_date="2025-01-15")
        loan1 = Loan(
            person_id=p_self.id, platform_id=plat_jiebei.id,
            amount=10000, rate=0.01, rate_type="monthly",
            repay_method="equal_installment",
            start_date=date(2025, 1, 15), end_date=date(2025, 12, 15),
            periods=12, status="active", note="借呗消费贷",
        )
        db.add(loan1)
        db.flush()
        for rp in plan:
            db.add(RepaymentPlan(
                loan_id=loan1.id, person_id=p_self.id,
                period_no=rp["period_no"], due_date=date.fromisoformat(rp["due_date"]),
                principal=rp["principal"], interest=rp["interest"],
                total_amount=rp["total_amount"], status="pending",
            ))
        # 标记前3期已还
        db.flush()
        rps = db.query(RepaymentPlan).filter(RepaymentPlan.loan_id == loan1.id).order_by(RepaymentPlan.period_no).all()
        for i in range(3):
            rps[i].status = "paid"
            rps[i].paid_date = datetime(2025, i + 2, 15)

        # 微粒贷：先息后本，5000元，6期，年利率12%
        annual_rate = 0.12
        monthly_rate2 = annual_rate / 12
        plan2 = calc_interest_first_plan(amount=5000, monthly_rate=monthly_rate2, periods=6, start_date="2025-03-01")
        loan2 = Loan(
            person_id=p_self.id, platform_id=plat_weilidai.id,
            amount=5000, rate=0.12, rate_type="annual",
            repay_method="interest_first",
            start_date=date(2025, 3, 1), end_date=date(2025, 8, 1),
            periods=6, status="active", note="微粒贷短期周转",
        )
        db.add(loan2)
        db.flush()
        for rp in plan2:
            db.add(RepaymentPlan(
                loan_id=loan2.id, person_id=p_self.id,
                period_no=rp["period_no"], due_date=date.fromisoformat(rp["due_date"]),
                principal=rp["principal"], interest=rp["interest"],
                total_amount=rp["total_amount"], status="pending",
            ))

        db.commit()

        # ===== POS 刷卡 =====
        now = datetime.now()
        pos_data = [
            PosSwipe(person_id=p_self.id, amount=20000, fee_rate=0.006, fee=120.0,
                     bank_card="招商银行储蓄卡", pos_machine="拉卡拉",
                     swipe_date=datetime(2025, 5, 10, 14, 30), note="资金周转"),
            PosSwipe(person_id=p_self.id, amount=15000, fee_rate=0.0058, fee=87.0,
                     bank_card="工商银行储蓄卡", pos_machine="随行付",
                     swipe_date=datetime(2025, 5, 18, 10, 15), note=""),
            PosSwipe(person_id=p_spouse.id, amount=8000, fee_rate=0.006, fee=48.0,
                     bank_card="建设银行储蓄卡", pos_machine="拉卡拉",
                     swipe_date=datetime(2025, 5, 22, 16, 45), note="家庭消费"),
        ]
        db.add_all(pos_data)
        db.commit()

        # ===== 信用卡 =====
        card1 = CreditCard(
            person_id=p_self.id, bank="招商银行", card_number_last4="8823",
            credit_limit=50000, current_balance=11200,
            bill_day=5, due_day=25, status="active",
        )
        card2 = CreditCard(
            person_id=p_self.id, bank="交通银行", card_number_last4="5671",
            credit_limit=30000, current_balance=8500,
            bill_day=10, due_day=28, status="active",
        )
        db.add_all([card1, card2])
        db.commit()

        # 信用卡消费
        txns = [
            CreditCardTransaction(card_id=card1.id, person_id=p_self.id,
                                  amount=3200, description="超市购物",
                                  trans_date=datetime(2025, 5, 3, 12, 0)),
            CreditCardTransaction(card_id=card1.id, person_id=p_self.id,
                                  amount=5000, description="网购电子产品",
                                  trans_date=datetime(2025, 5, 8, 20, 30)),
            CreditCardTransaction(card_id=card1.id, person_id=p_self.id,
                                  amount=3000, description="餐厅消费",
                                  trans_date=datetime(2025, 5, 15, 19, 0)),
            CreditCardTransaction(card_id=card2.id, person_id=p_self.id,
                                  amount=4500, description="加油+保养",
                                  trans_date=datetime(2025, 5, 12, 9, 0)),
            CreditCardTransaction(card_id=card2.id, person_id=p_self.id,
                                  amount=4000, description="服饰购物",
                                  trans_date=datetime(2025, 5, 20, 15, 0)),
        ]
        db.add_all(txns)
        db.commit()

        # ===== 信用卡分期 =====
        period_rate = 0.006  # 每期0.6%
        annual_rate = calc_installment_annual_rate(period_rate, 12)
        total_fee = round(12000 * period_rate * 12, 2)
        period_principal = round(12000 / 12, 2)
        period_fee = round(12000 * period_rate, 2)
        inst = CardInstallment(
            card_id=card1.id, person_id=p_self.id,
            amount=12000, periods=12, period_rate=period_rate,
            annual_rate=round(annual_rate, 4), total_fee=total_fee,
            period_principal=period_principal, period_fee=period_fee,
            period_total=round(period_principal + period_fee, 2),
            paid_periods=2, start_date=date(2025, 3, 1),
            note="招商银行消费分期",
        )
        db.add(inst)
        db.commit()

        # ===== 房贷 =====
        mortgage = Mortgage(
            person_id=p_self.id, bank="中国银行", house_name="阳光花园 3-1502",
            total_amount=1200000, remaining_principal=985000,
            rate=0.041, start_date=date(2022, 6, 1), end_date=date(2052, 5, 1),
            total_periods=360, monthly_payment=5798.35,
            repay_method="equal_installment", status="active",
        )
        db.add(mortgage)
        db.commit()

        # ===== 收入 =====
        incomes = [
            Income(person_id=p_self.id, amount=18000, source="工资",
                   period_type="monthly", period_value="2025-05", note="5月工资"),
            Income(person_id=p_spouse.id, amount=12000, source="工资",
                   period_type="monthly", period_value="2025-05", note="5月工资"),
            Income(person_id=p_self.id, amount=3500, source="兼职",
                   period_type="monthly", period_value="2025-05", note="周末私活"),
            Income(person_id=p_self.id, amount=20000, source="年终奖",
                   period_type="yearly", period_value="2025-01", note="2025年年终奖"),
        ]
        db.add_all(incomes)
        db.commit()

        # ===== 支出 =====
        expenses = [
            Expense(person_id=p_self.id, amount=2500, category="餐饮",
                    period_value="2025-05", expense_date=date(2025, 5, 1), note=""),
            Expense(person_id=p_self.id, amount=800, category="交通",
                    period_value="2025-05", expense_date=date(2025, 5, 3), note="加油"),
            Expense(person_id=p_self.id, amount=1500, category="购物",
                    period_value="2025-05", expense_date=date(2025, 5, 8), note="网购"),
            Expense(person_id=p_spouse.id, amount=3000, category="购物",
                    period_value="2025-05", expense_date=date(2025, 5, 12), note="服饰"),
            Expense(person_id=p_self.id, amount=1200, category="娱乐",
                    period_value="2025-05", expense_date=date(2025, 5, 15), note="电影+聚餐"),
            Expense(person_id=p_self.id, amount=500, category="医疗",
                    period_value="2025-05", expense_date=date(2025, 5, 18), note="门诊"),
            Expense(person_id=p_self.id, amount=6000, category="居住",
                    period_value="2025-05", expense_date=date(2025, 5, 1), note="物业+水电+暖气"),
            Expense(person_id=p_self.id, amount=1500, category="教育",
                    period_value="2025-05", expense_date=date(2025, 5, 10), note="在线课程"),
            Expense(person_id=p_spouse.id, amount=2000, category="日用",
                    period_value="2025-05", expense_date=date(2025, 5, 20), note="日常生活用品"),
            Expense(person_id=p_self.id, amount=1000, category="通讯",
                    period_value="2025-05", expense_date=date(2025, 5, 1), note="话费+宽带"),
        ]
        db.add_all(expenses)
        db.commit()

        # ===== 费率配置 =====
        fee_config = FeeConfig(
            fee_type="pos_swipe", rate=0.006,
            description="POS刷卡默认费率：60元/万",
            is_active=True,
        )
        db.add(fee_config)
        db.commit()

        print("种子数据已成功生成！")
        print(f"  - {db.query(Person).count()} 个人员")
        print(f"  - {db.query(LoanPlatform).count()} 个借贷平台")
        print(f"  - {db.query(Loan).count()} 笔借款")
        print(f"  - {db.query(RepaymentPlan).count()} 条还款计划")
        print(f"  - {db.query(PosSwipe).count()} 条POS刷卡记录")
        print(f"  - {db.query(CreditCard).count()} 张信用卡")
        print(f"  - {db.query(CreditCardTransaction).count()} 条信用卡消费")
        print(f"  - {db.query(CardInstallment).count()} 笔分期")
        print(f"  - {db.query(Mortgage).count()} 笔房贷")
        print(f"  - {db.query(Income).count()} 条收入")
        print(f"  - {db.query(Expense).count()} 条支出")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
