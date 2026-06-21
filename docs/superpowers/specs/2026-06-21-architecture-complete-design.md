# 财智管家 — 完整架构设计文档

**日期:** 2026-06-21
**状态:** 综合补充，覆盖 2026-05-24 原始设计以来所有增量模块

---

## 概述

本文档是财智管家（个人债务管理系统）的完整架构设计，整合了原始基线设计 + 4 份增量设计文档 + 5 个未文档化模块，形成一份统一的技术参考。

**技术栈:** FastAPI + SQLAlchemy + SQLite + Vue 3 CDN + ECharts 5
**部署:** 本地 `python -m uvicorn` 或 CentOS 7 + Miniconda 4.7.12

---

## 一、架构总览

```
┌──────────────────────────────────────────────────────────┐
│                    前端 (SPA, CDN)                       │
│  finance.html  ──  finance-app.js  ──  finance-help.html │
│  Vue 3 Options API + Vue Router 4 + ECharts 5            │
│  18 个页面组件  ·  17 项导航  ·  暗黑金融主题              │
└──────────────────────┬───────────────────────────────────┘
                       │ REST API (JWT Bearer)
┌──────────────────────┴───────────────────────────────────┐
│                   FastAPI 后端                            │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐   │
│  │ 认证层    │  │ 路由层    │  │ 服务层                │   │
│  │ auth.py  │  │ 23 个     │  │ calc_engine.py       │   │
│  │ JWT +    │  │ Router    │  │ snapshot_service.py  │   │
│  │ pbkdf2   │  │ 模块      │  │                      │   │
│  └──────────┘  └──────────┘  └──────────────────────┘   │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │ 数据层: models.py (20个表) + crud.py + schemas.py │   │
│  └──────────────────────────────────────────────────┘   │
└──────────────────────┬───────────────────────────────────┘
                       │
                  ┌────┴────┐
                  │  SQLite  │
                  │  app.db  │
                  └─────────┘
```

---

## 二、数据模型全景（20 个表）

### 2.1 原始设计模型（13个，2026-05-24）

| 表 | 说明 | 关键字段 |
|----|------|---------|
| `persons` | 家庭成员 | name, relation |
| `loan_platforms` | 借贷平台 | name, icon |
| `loans` | 借款记录 | amount, rate, rate_type, repay_method, periods, status |
| `repayment_plans` | 还款计划 | period_no, due_date, principal, interest, total_amount, status |
| `pos_swipes` | POS刷卡 | amount, fee_rate, fee, swipe_date |
| `credit_cards` | 信用卡 | bank, card_number_last4, credit_limit, bill_day, due_day |
| `credit_card_transactions` | 信用卡消费 | amount, trans_type, trans_date |
| `card_installments` | 信用卡分期 | amount, periods, total_fee, period_principal, paid_periods |
| `mortgages` | 房贷 | total_amount, remaining_principal, rate, monthly_payment |
| `incomes` | 收入 | amount, source, period_value |
| `expenses` | 支出 | amount, category, period_value, expense_date |
| `fee_configs` | 费率配置 | fee_type, rate |
| `debt_snapshots` | 负债快照 | snapshot_date, total_debt, loan/card/installment/mortgage_debt |

### 2.2 增量模型（7个，未记录在原始设计中）

#### CashRecord — 手头现金历史

```python
class CashRecord(Base):
    __tablename__ = "cash_records"
    id = Column(Integer, primary_key=True)
    amount = Column(Float, nullable=False)           # 现金余额
    recorded_at = Column(Date, default=date.today)   # 记录日期
    note = Column(String(200), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
```

**用途:** 用户手动录入手头现金，支持历史追踪。V2 现金流破裂预警和风险评级依赖此数据。

#### CreditCardBill — 信用卡月度账单

```python
class CreditCardBill(Base):
    __tablename__ = "credit_card_bills"
    id = Column(Integer, primary_key=True)
    card_id = Column(Integer, ForeignKey("credit_cards.id"))
    bill_month = Column(String(7))          # "2026-06"
    bill_start = Column(Date)               # 账单周期开始
    bill_end = Column(Date)                 # 账单周期结束
    due_date = Column(Date)                 # 还款截止日
    bill_amount = Column(Float, default=0)  # 账单金额（自动汇总POS+消费）
    paid_amount = Column(Float, default=0)  # 已还金额
    min_payment = Column(Float, default=0)  # 最低还款（bill_amount × 10%）
    interest = Column(Float, default=0)     # 循环利息
    fee = Column(Float, default=0)          # 手续费
    status = Column(String(20))             # unpaid/partial/paid/overdue
```

**设计决策:**
- 账单由信用卡 `bill_day` 驱动自动生成（访问页面时触发）
- 账单金额 = 当期 POS 刷卡合计 + 信用卡消费合计（可手动修改）
- 负债快照 `card_debt` 从账单计算（汇总所有未付账单），不再用 `current_balance`
- 支持全额还款 / 最低还款 / 撤销还款一键操作

#### DeletedRecord — 回收站

```python
class DeletedRecord(Base):
    __tablename__ = "deleted_records"
    id = Column(Integer, primary_key=True)
    table_name = Column(String(50))     # 来源表名
    record_id = Column(Integer)         # 原始记录 ID
    record_data = Column(Text)          # JSON 序列化的完整行数据
    deleted_at = Column(DateTime, default=datetime.utcnow)
```

**设计决策:**
- 删除操作不物理删除数据，而是写入 `deleted_records` 表（软删除）
- 支持恢复到原表（按 table_name + record_id 重建行）
- 支持永久删除（清除回收站记录）
- 覆盖所有财务表的删除操作

#### AppSetting — 应用键值设置

```python
class AppSetting(Base):
    __tablename__ = "app_settings"
    id = Column(Integer, primary_key=True)
    key = Column(String(50), unique=True)   # 设置键
    value = Column(String(500), default="") # 设置值
```

**用途:** 存储月度预算额度等应用级配置，无需新建专用表。

### 2.3 模型演变（字段级变更）

| 表 | 变更 | 原因 |
|----|------|------|
| `loans` | + `_paid_periods` (Integer) | 记录手动录入时已还期数 |
| `loans` | + `repay_day` (Integer, nullable) | 固定每月还款日（如每月1号/24号） |
| `loans` | + `total_interest` (Float, nullable) | 总利息金额录入（rate_type=total_interest 时使用） |
| `loans` | `Loan.paid_periods` (property) | `max(_paid_periods, sum(paid repayments))` — 取已还列和实际已还计划的较大值 |
| `loans` | `Loan.remaining_periods` (property) | `max(0, periods - paid_periods)` — 上限保护 |
| `credit_card_transactions` | `card_id` → nullable=True | 允许无卡 POS 退款记录 |
| `credit_card_transactions` | + `trans_type` (VARCHAR(10)) | 区分「消费」和「还款」类型 |
| `credit_cards` | + `interest_rate` (Float, default=0.1825) | 透支年化利率（日息万分之五） |

---

## 三、利息计算引擎

文件: `app/finance/calc_engine.py` — 纯函数模块，无数据库依赖。

### 3.1 利率换算

| 录入方式 | 输入 | 换算 |
|---------|------|------|
| 月利率 | `rate_type=monthly` | 直接使用 |
| 年化利率 | `rate_type=annual` | `r_monthly = r_annual / 12` |
| 总利息反推 | `rate_type=total_interest` | 二分搜索反推月利率（60次迭代） |

### 3.2 还款计划算法

**等额本息 (equal_installment):**
- 每期还款额: `amount × r × (1+r)^n / ((1+r)^n - 1)`
- 每期利息 = 剩余本金 × r，最后一期尾差调整

**先息后本 (interest_first):**
- 前 n-1 期: 本金=0, 利息=amount×r
- 最后一期: 本金=amount, 利息=amount×r

**到期还本付息 (bullet):**
- 单期: 本金=amount, 利息=amount×r×n

**灵活期限 (flexible):**
- 不生成还款计划（periods=0），全额计入贷款负债

### 3.3 辅助计算

| 函数 | 公式 |
|------|------|
| 分期年化利率 | `period_rate × periods × 24 / (periods + 1)` |
| POS 手续费 | `amount × fee_rate` |

### 3.4 利息统计规则

**当月应付利息**（仪表盘）: 贷款利息（pending 计划在本月窗口内）+ 分期手续费（全部期数中落在本月的）+ 房贷月利息

**已付利息统计**（统计报告）: 贷款利息（status=paid）+ POS 手续费 + 分期手续费（按已还期数比例）+ 房贷利息

**利息统计不包含信用卡循环利息** — POS 刷卡的手续费已覆盖刷卡成本。

---

## 四、负债快照服务

文件: `app/finance/snapshot_service.py`

### 4.1 计算规则

| 负债类型 | 计算方式 |
|---------|---------|
| 贷款负债 | 汇总 pending 还款计划的 principal；无还款计划的用 loan.amount |
| 信用卡负债 | 汇总所有未付账单的 `bill_amount - paid_amount` |
| 分期负债 | `amount - period_principal × min(paid_periods, periods)` |
| 房贷负债 | `SUM(remaining_principal) WHERE status=active` |
| 总负债 | 以上四项之和 |

### 4.2 触发机制

- 每次访问仪表盘时，删除当日旧快照并重新计算（确保数据实时准确）
- 历史快照保留在 `debt_snapshots` 表中，用于趋势图

---

## 五、未文档化模块详细设计

### 5.1 回收站系统

**文件:** `app/api/v1/finance/recycle_bin.py`
**路由前缀:** `/api/v1/finance/recycle-bin`

**端点:**

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 列出所有已删除记录（含预览） |
| POST | `/{id}/restore` | 恢复到原表 |
| DELETE | `/{id}` | 永久删除单条 |
| DELETE | `/clear` | 清空回收站（需 admin） |

**恢复机制:**
- 从 `record_data` (JSON) 反序列化行数据
- 通过 SQLAlchemy 直接 INSERT 到原表（绕过 ORM 关系约束）
- 恢复后从回收站删除记录

**触发时机:** 所有财务表的 DELETE 操作（Loan, PosSwipe, CreditCard, CardInstallment, Mortgage, Income, Expense 等）先将数据 JSON 序列化存入 `deleted_records`，再从原表删除。

---

### 5.2 数据导出系统

**文件:** `app/api/v1/finance/export.py`
**路由:** `GET /api/v1/finance/export/all`

**导出内容（CSV 格式，UTF-8 BOM，Excel 可直接打开）:**

| 区块 | 导出的表 | 关键字段 |
|------|---------|---------|
| 贷款 | loans | ID, 人员, 平台, 金额, 利率, 还款方式, 期数, 已还/剩余 |
| 还款计划（已还） | repayment_plans | 期数, 本金, 利息, 总还款, 到期日, 还款日 |
| POS 刷卡 | pos_swipes | 金额, 费率, 手续费, 日期 |
| 信用卡 | credit_cards | 银行, 尾号, 额度, 余额, 账单日, 还款日 |
| 信用卡账单 | credit_card_bills | 月份, 账单周期, 账单金额, 已还, 利息, 状态 |
| 分期 | card_installments | 金额, 期数, 每期还款, 已还, 总手续费 |
| 房贷 | mortgages | 银行, 房产, 贷款总额, 剩余本金, 月供 |
| 收入 | incomes | 金额, 来源, 类型, 周期 |
| 支出 | expenses | 金额, 分类, 周期, 日期 |
| 手头现金 | cash_records | 金额, 日期, 备注 |

**设计决策:**
- 使用 `StreamingResponse`，内存友好
- `text/csv; charset=utf-8-sig` 确保 Excel 正确识别中文
- 文件名含导出日期: `caizhiguanjia_export_YYYY-MM-DD.csv`

---

### 5.3 系统运维模块

**文件:** `app/api/v1/finance/settings.py`
**路由前缀:** `/api/v1/finance/settings`

#### 手头现金管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/cash` | 录入当前现金余额（每次录入生成一条历史记录） |
| GET | `/cash/latest` | 获取最近一次录入的余额 |
| GET | `/cash/history` | 获取历史记录列表（默认24条，可调） |

#### 应用设置（键值存储）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/app/{key}` | 读取设置值 |
| POST | `/app` | 写入/更新设置值 |

当前支持: `monthly_budget`（月度预算额度）

#### 数据清理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/cleanup` | 清理系统自动生成的测试数据（description 以 `[系统自动]` 开头的交易记录） |

#### 数据库备份

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/backup` | 复制 app.db 到 `backups/app_YYYYMMDD_HHMMSS.db`，保留最近30份 |

**备份目录结构:**
```
backups/
├── app_20260618_143022.db
├── app_20260619_091500.db
└── ...
```

---

### 5.4 收支缺口深度分析

**文件:** `app/api/v1/finance/reports.py`（`gap_analysis_detail` 端点）
**路由:** `GET /api/v1/finance/reports/gap-analysis-detail`

#### 分析维度

| 维度 | 内容 |
|------|------|
| 当期缺口 | 收入 - 支出 - 待还债务，储蓄率，负债收入比 |
| 近6月趋势 | 逐月收入/支出/缺口/储蓄率 |
| 债务结构 | 信用卡/贷款/分期/房贷余额 + 加权平均利率 |
| 分类趋势 | 近3月各类支出金额变化 |

#### 洞察生成规则（6种）

| 严重度 | 触发条件 | 示例 |
|--------|---------|------|
| critical | 连续多月储蓄率为负且恶化 | "连续3个月为负，较上月进一步恶化" |
| warning | 负债率 > 50%，高息债务 | "待还债务占收入比 65%，超过警戒线" |
| neutral | 储蓄率 0-10%，收入来源单一 | "储蓄率虽然为正但低于建议的10%底线" |
| positive | 储蓄率 ≥ 20%，缺口持续收窄 | "近3个月收支缺口持续收窄，财务状况正在改善" |

#### 改进建议生成规则（5类）

| 优先级 | 类别 | 触发条件 |
|--------|------|---------|
| 1 | 高息债务 | 信用卡有余额 → 优先偿还建议 + 还清时间估算 |
| 2 | 多笔贷款 | 利率差 > 2% → 雪崩法建议 |
| 3 | 储蓄率 | < 10% → 目标储蓄 + 可削减支出识别 |
| 4 | 应急金 | 建立3月储备需 > 6月 → 起点建议 |
| 5 | 收入多元化 | 仅1个收入来源 → 拓展建议 |

#### 基准数据

- 中国 CPI: 约 0.3%（2026年4月）
- 建议储蓄率: 20-30%
- 健康负债收入比: < 40%

---

### 5.5 负债预测引擎

**文件:** `app/api/v1/finance/reports.py`（`debt_forecast` 端点）
**路由:** `GET /api/v1/finance/reports/debt-forecast`

#### 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `months` | 12 (1-36) | 预测月数 |
| `include_mortgage` | true | 是否包含房贷 |
| `monthly_surplus` | auto | 月均结余（不传则自动从近6月收支缺口计算） |
| `monthly_new_borrowing` | 0 | 预估月均新增借款 |

#### 逐月推演逻辑

```
for 每月:
  1. 信用卡产生循环利息 (card_balance × annual_rate / 12)
  2. 按还款计划扣除贷款/分期/房贷本金
  3. 月结余按雪崩法优先偿还: 信用卡(利率最高) → 贷款
  4. 新增借款加入贷款负债
```

**关键假设:**
- 信用卡利率使用各卡 `interest_rate` 加权平均
- 贷款/分期/房贷每月本金减少量来自 pending 还款计划均值
- 月结余自动从近6月 `收入-支出-待还` 均值计算
- 最大预测 600 个月，超过认为"永续债务"

#### 输出

```json
{
  "base": {"loan_debt": ..., "card_debt": ..., "total_debt": ...},
  "trends": {"loan_trend": ..., "card_trend": ..., "auto_monthly_surplus": ...},
  "trend_desc": "月均结余 ¥1,200 用于加速还款",
  "forecasts": [
    {"month": "2026-07", "loan_debt": ..., "card_debt": ..., "total_debt": ...},
    ...
  ]
}
```

---

## 六、还款提醒系统

**文件:** `app/api/v1/finance/dashboard.py`（`repay_reminders` 端点）

### 6.1 合并规则

**贷款提醒:** 按 `平台名称 + 人员ID` 合并
- 同一人在同一平台的多笔贷款合并为一条
- 取最早的 due_date、汇总 total_amount
- `due_date >= today AND due_date <= today+7days`

**信用卡提醒:** 按卡汇总，含分期
- 根据 `due_day` 计算当月还款日
- 账单金额来自最新未付账单
- 分期每期金额合并到对应卡

### 6.2 逾期判断

**文件:** `app/api/v1/finance/dashboard.py`（`repay_overdue` 端点）

```
pending AND due_date < today AND period_no > loan._paid_periods
```

- 只显示真正逾期的（已还期数范围内的 pending 计划不显示）
- 已录入时标记为 paid 的计划不产生逾期

---

## 七、V2 风险分析

### 7.1 五项核心指标

**文件:** `app/api/v1/finance/v2_dashboard.py`

| # | 指标 | 公式 | 风险阈值 |
|---|------|------|---------|
| 1 | 债务燃烧率 | 月利息 + 月POS费 - 月减少本金 | ≤0健康, ≤1000关注, >1000高危 |
| 2 | 生存线 | 月收入 - 月支出 - 月利息 - 月POS费 | <0高危, <收入10%关注, ≥收入10%健康 |
| 3 | 债务自由预期 | 总负债 ÷ 生存线 | ≤24月健康, ≤60月关注, >60月高危 |
| 4 | 现金流破裂预警 | 手头现金 ÷ |缺口| | <3月高危, <6月关注, ≥6月健康 |
| 5 | 利息消耗率 | 月利息 ÷ 月收入 × 100% | ≤15%健康, ≤30%关注, >30%高危 |

### 7.2 综合风险评级（5维度加权）

**文件:** `app/api/v1/finance/v2_simulator.py`（`risk_assessment` 端点）

| 维度 | 权重 | A | B | C | D | E |
|------|------|---|---|---|---|---|
| 生存线 | 25% | >月收入10% | 0~10% | -10%~0 | -30%~-10% | <-30% |
| 利息吞噬率 | 25% | <15% | 15-25% | 25-40% | 40-60% | >60% |
| 资产负债率 | 20% | <30% | 30-50% | 50-80% | 80-100% | >100% |
| 现金流破裂 | 15% | 无风险 | >12月 | 6-12月 | 3-6月 | <3月 |
| 手头现金 | 15% | >6月开支 | 3-6月 | 1-3月 | <1月 | 0 |

**综合评分:** A=1, B=2, C=3, D=4, E=5 → 加权总分 → 映射回 A~E

### 7.3 情景模拟器

**文件:** `app/api/v1/finance/v2_simulator.py`

**`/v2/simulator`** — 接收 salary/side_income/extra_payment，返回模拟后的生存线、利息吞噬率、债务自由预期等。

**`/v2/presets`** — 预设薪资档位(12000/15000/18000/22000/30000) + 副业档位(1000/3000/5000/10000) + 提前还款档位(1000/5000/10000)，一次返回所有组合。

---

## 八、还款优先级（雪崩 vs 雪球）

**文件:** `app/api/v1/finance/reports.py`（`repay_priority` 端点）

| 方法 | 排序规则 | 优势 |
|------|---------|------|
| 雪崩法 (avalanche) | 按年化利率降序 | 总利息支出最小，数学最优 |
| 雪球法 (snowball) | 按剩余余额升序 | 快速清零小债务，心理激励强 |

**估算逻辑:** 模拟每月用估算还款额按顺序偿还债务，直到全部还清（最多600月），统计总月数和总利息。

---

## 九、前端架构

### 9.1 技术选型

- **框架:** Vue 3 Options API（CDN: `vue@3.4`, `vue-router@4`）
- **图表:** ECharts 5 CDN
- **主题:** 暗黑金融风（#0d0d1a 背景, #e94560 强调, #00d2a0 安全）
- **路由:** Hash 模式 (`#/finance/...`)
- **模板编译:** 运行时 DOM 内编译（无构建工具）

### 9.2 页面组件（18个）

| 组件 | 路由 | 功能 |
|------|------|------|
| `LoginPage` | `/finance/login` | JWT 登录 |
| `DashboardPage` | `/finance/dashboard` | 仪表盘: V2卡片 + 负债明细 + 图表 + 提醒 + 缺口 |
| `LoansPage` | `/finance/loans` | 借贷管理: CRUD + 还款计划 + 灵活期限 |
| `PosPage` | `/finance/pos` | POS 刷卡: 录入 + 统计 + 退款 |
| `CreditCardsPage` | `/finance/credit-cards` | 信用卡: 卡片管理 + 账单列表 + 还款操作 |
| `CardTransactionsPage` | `/finance/card-transactions` | 信用卡消费/还款记录 |
| `InstallmentsPage` | `/finance/installments` | 分期管理: 录入 + 已还标记 |
| `MortgagesPage` | `/finance/mortgages` | 房贷管理: CRUD + 提前还款 |
| `IncomesPage` | `/finance/incomes` | 收入管理: CRUD + 编辑 |
| `ExpensesPage` | `/finance/expenses` | 支出管理: CRUD + 分类统计 |
| `TransactionsPage` | `/finance/transactions` | 统一流水: 多表 UNION + 筛选 |
| `ReportsPage` | `/finance/reports` | 统计报告: 汇总 + 平台 + 缺口 + 利息 + 负债 + 预测 + POS |
| `RecycleBinPage` | `/finance/recycle-bin` | 回收站: 查看 + 恢复 + 删除 |
| `SimulatorPage` | `/finance/simulator` | 债务模拟器: 收入测算 + 提前还款 + 风险拆解 |
| `SettingsPage` | `/finance/settings` | 设置: 现金 + 预算 + 备份 + 清理 |
| `PersonsPage` | `/finance/persons` | 人员管理 |
| `PlatformsPage` | `/finance/platforms` | 借贷平台管理 |
| `NotFoundPage` | `/:pathMatch(.*)*` | 404 页面 |

### 9.3 全局 Mixin

`ChartMixin` — 封装 ECharts 初始化和窗口 resize 自适应，所有含图表的页面复用。

### 9.4 移动端适配

**纯 CSS 方案，不修改 Vue 模板:**

| 断点 | 作用 |
|------|------|
| ≤768px | 侧边栏隐藏、主区域全宽、底部导航栏显示、表格横向滚动 |
| ≤640px | 表单双列→单列 |
| ≤480px | 统计卡片→2列 |

**底部导航栏（17项）:** 横向可滚动，覆盖所有主要页面入口。

---

## 十、完整 API 端点地图

### 10.1 仪表盘与风险

| 方法 | 路径 | 文件 |
|------|------|------|
| GET | `/api/v1/finance/dashboard` | dashboard.py |
| GET | `/api/v1/finance/repay-overdue` | dashboard.py |
| GET | `/api/v1/finance/repay-reminders` | dashboard.py |
| GET | `/api/v1/finance/monthly-interest-detail` | dashboard.py |
| GET | `/api/v1/finance/v2/dashboard` | v2_dashboard.py |
| GET | `/api/v1/finance/v2/simulator` | v2_simulator.py |
| GET | `/api/v1/finance/v2/presets` | v2_simulator.py |
| GET | `/api/v1/finance/v2/risk-assessment` | v2_simulator.py |

### 10.2 业务 CRUD

| 方法 | 路径 | 文件 |
|------|------|------|
| CRUD | `/api/v1/finance/persons` | persons.py |
| CRUD | `/api/v1/finance/platforms` | platforms.py |
| CRUD | `/api/v1/finance/loans` | loans.py |
| GET | `/api/v1/finance/loans/{id}/repayments` | loans.py |
| POST | `/api/v1/finance/loans/{id}/regenerate-plan` | loans.py |
| PATCH | `/api/v1/finance/repayments/{id}/pay` | loans.py |
| CRUD | `/api/v1/finance/pos-swipes` | pos_swipes.py |
| CRUD | `/api/v1/finance/credit-cards` | credit_cards.py |
| CRUD | `/api/v1/finance/card-transactions` | card_transactions.py |
| CRUD | `/api/v1/finance/card-installments` | card_installments.py |
| CRUD | `/api/v1/finance/credit-card-bills` | credit_card_bills.py |
| POST | `/api/v1/finance/credit-card-bills/{id}/pay-full` | credit_card_bills.py |
| POST | `/api/v1/finance/credit-card-bills/{id}/pay-minimum` | credit_card_bills.py |
| POST | `/api/v1/finance/credit-card-bills/{id}/undo-payment` | credit_card_bills.py |
| CRUD | `/api/v1/finance/mortgages` | mortgages.py |
| CRUD | `/api/v1/finance/incomes` | incomes.py |
| CRUD | `/api/v1/finance/expenses` | expenses.py |
| CRUD | `/api/v1/finance/fee-configs` | fee_configs.py |

### 10.3 统计报告

| 方法 | 路径 | 文件 |
|------|------|------|
| GET | `/api/v1/finance/reports/summary` | reports.py |
| GET | `/api/v1/finance/reports/by-platform` | reports.py |
| GET | `/api/v1/finance/reports/by-month` | reports.py |
| GET | `/api/v1/finance/reports/gap-analysis` | reports.py |
| GET | `/api/v1/finance/reports/gap-analysis-detail` | reports.py |
| GET | `/api/v1/finance/reports/interest-detail` | reports.py |
| GET | `/api/v1/finance/reports/interest-stats` | reports.py |
| GET | `/api/v1/finance/reports/repay-priority` | reports.py |
| GET | `/api/v1/finance/reports/debt-summary` | reports.py |
| GET | `/api/v1/finance/reports/debt-forecast` | reports.py |
| GET | `/api/v1/finance/reports/pos-count` | reports.py |
| GET | `/api/v1/finance/reports/snapshots` | reports.py |

### 10.4 系统工具

| 方法 | 路径 | 文件 |
|------|------|------|
| GET | `/api/v1/finance/transactions` | transactions.py |
| POST | `/api/v1/finance/calc/interest` | calc.py |
| POST | `/api/v1/finance/calc/annual-rate` | calc.py |
| GET | `/api/v1/finance/export/all` | export.py |
| GET | `/api/v1/finance/recycle-bin/` | recycle_bin.py |
| POST | `/api/v1/finance/recycle-bin/{id}/restore` | recycle_bin.py |
| DELETE | `/api/v1/finance/recycle-bin/{id}` | recycle_bin.py |
| DELETE | `/api/v1/finance/recycle-bin/clear` | recycle_bin.py |
| POST | `/api/v1/finance/settings/cash` | settings.py |
| GET | `/api/v1/finance/settings/cash/latest` | settings.py |
| GET | `/api/v1/finance/settings/cash/history` | settings.py |
| GET/POST | `/api/v1/finance/settings/app/{key}` | settings.py |
| POST | `/api/v1/finance/settings/cleanup` | settings.py |
| POST | `/api/v1/finance/settings/backup` | settings.py |

---

## 十一、文件结构

```
app/
├── main.py                          # 应用入口，路由注册，数据库迁移
├── models.py                        # 20 个 ORM 模型
├── schemas.py                       # Pydantic 请求/响应 Schema（50+类）
├── crud.py                          # 通用 CRUD + 财务专用操作
├── auth.py                          # JWT + pbkdf2_sha256 认证
├── db.py                            # SQLAlchemy 引擎 + Session
├── finance/
│   ├── __init__.py
│   ├── calc_engine.py               # 利息计算纯函数
│   └── snapshot_service.py          # 负债快照计算
├── api/v1/
│   ├── auth.py                      # 认证路由
│   ├── articles.py                  # CMS 文章（原始功能）
│   ├── categories.py                # CMS 分类
│   ├── tags.py                      # CMS 标签
│   ├── media.py                     # CMS 媒体
│   ├── users.py                     # 用户管理
│   ├── dashboard.py                 # CMS 仪表盘
│   └── finance/
│       ├── __init__.py
│       ├── dashboard.py             # 财务仪表盘 + 提醒 + 逾期 + 利息明细
│       ├── v2_dashboard.py          # V2 五项风险指标
│       ├── v2_simulator.py          # 模拟器 + 情景预设 + 风险评级
│       ├── persons.py               # 人员管理
│       ├── platforms.py             # 借贷平台
│       ├── loans.py                 # 借款 + 还款计划 + 灵活期限
│       ├── pos_swipes.py            # POS 刷卡
│       ├── credit_cards.py          # 信用卡管理
│       ├── card_transactions.py     # 信用卡消费/还款
│       ├── card_installments.py     # 分期管理
│       ├── credit_card_bills.py     # 账单管理 + 还款操作
│       ├── mortgages.py             # 房贷管理
│       ├── incomes.py               # 收入管理
│       ├── expenses.py              # 支出管理
│       ├── transactions.py          # 统一流水
│       ├── reports.py               # 统计报告（12个端点）
│       ├── fee_configs.py           # 费率配置
│       ├── calc.py                  # 计算器工具
│       ├── recycle_bin.py           # 回收站
│       ├── settings.py              # 设置/现金/备份/清理
│       └── export.py                # CSV 导出
└── static/
    ├── finance.html                 # 财务管理前端入口 + CSS
    ├── finance-app.js               # Vue 3 应用（2453行，18个组件）
    ├── finance-help.html            # 产品功能介绍文档
    ├── index.html                   # CMS 前端
    └── app.js                       # CMS Vue 应用
```

---

## 十二、关键设计决策

1. **利息不重复计算:** 信用卡透支利息通过 POS 手续费体现，不在利息统计中另行计算
2. **负债快照实时更新:** 每次访问仪表盘删除当日旧快照重新计算，确保数据准确性
3. **软删除 + 回收站:** 所有删除操作可恢复，防止误删
4. **账单驱动的信用卡负债:** `card_debt` 从账单表汇总而非卡 `current_balance`，确保与实际账单一致
5. **paid_periods 双保险:** property 取 `max(列值, 实际 paid 数)`，防止数据不一致
6. **逾期只算真正逾期的:** `period_no > loan._paid_periods` 过滤掉录入时已标记为还的期数
7. **灵活期限贷款:** `repay_method=flexible` 不生成还款计划，全额计入负债
8. **还款日修正:** `repay_day` 字段允许统一修正还款计划日期到每月固定日
9. **纯 CSS 移动端:** 不修改 Vue 模板，通过 `@media` 查询适配手机
10. **无构建工具:** 前端使用 CDN + DOM 内模板编译，零配置运行

---

## 十三、设计文档索引

| 文档 | 覆盖范围 |
|------|---------|
| `2026-05-24-finance-manager-design.md` | 原始 13 模型 + 利息引擎 + 基础 API + 前端布局 |
| `2026-05-28-mobile-responsive-design.md` | 移动端 CSS 适配方案 |
| `2026-06-08-debt-v2-design.md` | V2 风险指标 + 模拟器 + 风险评级 + 雪崩/雪球 |
| `2026-06-14-credit-card-bills-design.md` | 信用卡账单系统 + 移动端 + 预算/净资产 |
| **`2026-06-21-architecture-complete-design.md`** (本文档) | **完整架构补充: 回收站 + 导出 + 运维 + 缺口深度分析 + 负债预测 + 模型演变 + 完整 API 地图** |
