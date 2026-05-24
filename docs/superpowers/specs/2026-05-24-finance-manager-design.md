# 个人财务管理平台 — 设计方案

## 概述

在现有 LightPress CMS（FastAPI + SQLite + Vue 3）基础上，新增个人财务管理模块，覆盖借贷、POS 刷卡、信用卡、分期、房贷、收入支出等全场景，提供利息自动计算、还款提醒、收支缺口分析和多维度统计报告。

**目标用户**：个人自用，单用户本地运行，后续可部署至阿里云服务器。

**设计原则**：复用现有项目基础设施，前端重新设计为暗黑金融主题风格。

---

## 一、架构方案

**选择方案 A：集成到现有 LightPress CMS。**

- 后端：新增数据模型、API 路由、利息计算服务模块，复用 FastAPI + SQLAlchemy + SQLite 基础设施
- 前端：新建 Vue 3 组件套件，使用暗黑金融主题 + ECharts 图表，替换现有 CMS 前端（或作为 `/finance` 子路径独立存在）
- SQLite 用于本地使用，后续部署阿里云时迁移至 MySQL/PostgreSQL

**部署策略**：
- 本地开发：`python -m uvicorn app.main:app --reload`，SQLite
- 阿里云部署：Docker 容器化（已有 Dockerfile），gunicorn + uvicorn，MySQL
- 通过环境变量控制数据库切换（`DATABASE_URL`），无需改代码
- 更新方式：git pull + docker rebuild，或 rsync 同步新包

---

## 二、数据模型设计

### 2.1 人员实体（新增）

```python
class Person(Base):
    __tablename__ = "persons"
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    relation = Column(String(20), default="本人")  # 本人/配偶/父母/子女
    created_at = Column(DateTime, default=datetime.utcnow)
```

所有金融实体通过 `person_id` 关联到人员，支持区分不同家庭成员的银行卡、贷款等。系统初始化时自动创建「本人」记录。

### 2.2 借贷平台（新增）

```python
class LoanPlatform(Base):
    __tablename__ = "loan_platforms"
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)  # 借呗/微粒贷/抖音月付/招商银行等
    icon = Column(String(10), default="")
    description = Column(String(200), default="")
```

### 2.3 借款记录（新增）

```python
class Loan(Base):
    __tablename__ = "loans"
    id = Column(Integer, primary_key=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    platform_id = Column(Integer, ForeignKey("loan_platforms.id"), nullable=False)
    amount = Column(Float, nullable=False)                    # 借款金额
    rate = Column(Float, nullable=False)                      # 利率值
    rate_type = Column(String(10), nullable=False)            # monthly / annual / total_interest
    total_interest = Column(Float, nullable=True)             # 总利息（rate_type=total_interest 时填写）
    repay_method = Column(String(20), nullable=False)         # equal_installment / interest_first / bullet
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    periods = Column(Integer, nullable=False)                 # 总期数
    status = Column(String(20), default="active")             # active / closed
    note = Column(String(200), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    person = relationship("Person")
    platform = relationship("LoanPlatform")
    repayments = relationship("RepaymentPlan", back_populates="loan")
```

### 2.4 还款计划（新增）

```python
class RepaymentPlan(Base):
    __tablename__ = "repayment_plans"
    id = Column(Integer, primary_key=True)
    loan_id = Column(Integer, ForeignKey("loans.id"), nullable=False)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    period_no = Column(Integer, nullable=False)               # 第几期
    due_date = Column(Date, nullable=False)
    principal = Column(Float, nullable=False)                 # 本期本金
    interest = Column(Float, nullable=False)                  # 本期利息
    total_amount = Column(Float, nullable=False)              # 本期总还款额
    status = Column(String(20), default="pending")            # pending / paid / overdue
    paid_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    loan = relationship("Loan", back_populates="repayments")
```

录入借款时，系统根据还款方式自动生成全部还款计划。等额本息/先息后本/到期还本付息三种方式。

### 2.5 POS 刷卡记录（新增）

```python
class PosSwipe(Base):
    __tablename__ = "pos_swipes"
    id = Column(Integer, primary_key=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    amount = Column(Float, nullable=False)                    # 刷卡金额
    fee_rate = Column(Float, nullable=False)                  # 费率（如 0.006 表示 60/万）
    fee = Column(Float, nullable=False)                       # 手续费（自动计算）
    bank_card = Column(String(50), default="")                # 刷的银行卡
    pos_machine = Column(String(50), default="")              # POS 机名称
    swipe_date = Column(DateTime, nullable=False)
    note = Column(String(200), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    person = relationship("Person")
```

### 2.6 信用卡（新增）

```python
class CreditCard(Base):
    __tablename__ = "credit_cards"
    id = Column(Integer, primary_key=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    bank = Column(String(50), nullable=False)
    card_number_last4 = Column(String(4), nullable=False)
    credit_limit = Column(Float, nullable=False)
    current_balance = Column(Float, default=0)                # 当期账单金额
    bill_day = Column(Integer, nullable=False)                # 账单日（每月几号）
    due_day = Column(Integer, nullable=False)                 # 还款日（每月几号）
    status = Column(String(20), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)

    person = relationship("Person")
    installments = relationship("CardInstallment", back_populates="card")
    transactions = relationship("CreditCardTransaction", back_populates="card")
```

### 2.7 信用卡消费记录（新增）

```python
class CreditCardTransaction(Base):
    __tablename__ = "credit_card_transactions"
    id = Column(Integer, primary_key=True)
    card_id = Column(Integer, ForeignKey("credit_cards.id"), nullable=False)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    amount = Column(Float, nullable=False)
    description = Column(String(200), default="")
    trans_date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    person = relationship("Person")
    card = relationship("CreditCard", back_populates="transactions")
```

### 2.8 信用卡分期（新增）

```python
class CardInstallment(Base):
    __tablename__ = "card_installments"
    id = Column(Integer, primary_key=True)
    card_id = Column(Integer, ForeignKey("credit_cards.id"), nullable=False)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    amount = Column(Float, nullable=False)                    # 分期金额
    periods = Column(Integer, nullable=False)                 # 分期期数
    period_rate = Column(Float, nullable=False)               # 每期手续费率（如 0.006）
    annual_rate = Column(Float, nullable=True)                # 年化利率（自动计算）
    total_fee = Column(Float, nullable=False)                 # 总手续费（自动计算）
    period_principal = Column(Float, nullable=False)          # 每期本金（自动计算）
    period_fee = Column(Float, nullable=False)                # 每期手续费（自动计算）
    period_total = Column(Float, nullable=False)              # 每期总还款（自动计算）
    paid_periods = Column(Integer, default=0)
    start_date = Column(Date, nullable=False)
    note = Column(String(200), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    person = relationship("Person")
    card = relationship("CreditCard", back_populates="installments")
```

### 2.9 房贷（新增）

```python
class Mortgage(Base):
    __tablename__ = "mortgages"
    id = Column(Integer, primary_key=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    bank = Column(String(50), nullable=False)                 # 贷款银行
    house_name = Column(String(100), default="")              # 房产名称
    total_amount = Column(Float, nullable=False)              # 贷款总额
    remaining_principal = Column(Float, nullable=False)       # 剩余本金
    rate = Column(Float, nullable=False)                      # 年化利率
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    total_periods = Column(Integer, nullable=False)           # 总期数（如360期=30年）
    monthly_payment = Column(Float, nullable=False)           # 月供
    repay_method = Column(String(20), default="equal_installment")
    status = Column(String(20), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)

    person = relationship("Person")
```

### 2.10 收入记录（新增）

```python
class Income(Base):
    __tablename__ = "incomes"
    id = Column(Integer, primary_key=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    amount = Column(Float, nullable=False)
    source = Column(String(50), nullable=False)               # 工资/兼职/投资/租金/其他
    period_type = Column(String(10), nullable=False)          # monthly / yearly / once
    period_value = Column(String(7), nullable=False)          # 2025-05 格式
    note = Column(String(200), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    person = relationship("Person")
```

### 2.11 日常支出记录（新增）

```python
class Expense(Base):
    __tablename__ = "expenses"
    id = Column(Integer, primary_key=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String(30), nullable=False)             # 餐饮/交通/购物/娱乐/医疗/教育/居住/其他
    period_value = Column(String(7), nullable=False)          # 2025-05 格式
    expense_date = Column(Date, nullable=False)
    note = Column(String(200), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    person = relationship("Person")
```

### 2.12 费率配置（新增）

```python
class FeeConfig(Base):
    __tablename__ = "fee_configs"
    id = Column(Integer, primary_key=True)
    fee_type = Column(String(30), nullable=False)             # pos_swipe / other
    rate = Column(Float, nullable=False)                      # 费率值
    description = Column(String(100), default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
```

### 2.13 负债快照（新增）

```python
class DebtSnapshot(Base):
    __tablename__ = "debt_snapshots"
    id = Column(Integer, primary_key=True)
    snapshot_date = Column(Date, nullable=False, index=True)
    total_debt = Column(Float, default=0)                     # 总负债
    loan_debt = Column(Float, default=0)                      # 贷款负债
    card_debt = Column(Float, default=0)                      # 信用卡已用额度
    installment_debt = Column(Float, default=0)               # 分期余额
    mortgage_debt = Column(Float, default=0)                  # 房贷余额
    pos_fee_total = Column(Float, default=0)                  # 累计 POS 手续费
    created_at = Column(DateTime, default=datetime.utcnow)
```

每日自动生成（首次访问仪表盘时触发），用于负债趋势图。

---

## 三、利息计算引擎

### 3.1 利率换算

支持三种利率录入方式，统一换算为月利率用于计算：

| 录入方式 | 输入 | 换算公式 |
|---------|------|---------|
| 月利率 | r_monthly | `r_monthly` |
| 年化利率 | r_annual | `r_monthly = r_annual / 12` |
| 总利息反推 | total_interest, amount, periods | 根据还款方式反推月利率 |

### 3.2 还款方式计算

**等额本息（equal_installment）**：
- 每期还款额 = `amount × r × (1+r)^n / ((1+r)^n - 1)`
- 每期利息 = 剩余本金 × r
- 每期本金 = 每期还款额 - 每期利息

**先息后本（interest_first）**：
- 前 n-1 期：每期利息 = amount × r，本金为 0
- 最后一期：利息 = amount × r，本金 = amount

**到期还本付息（bullet）**：
- 到期日：利息 = amount × r × n，本金 = amount

### 3.3 POS 手续费计算

- `fee = amount × fee_rate`（fee_rate 默认 0.006，即 60 元/万，可通过 FeeConfig 修改）

### 3.4 分期年化利率计算

信用卡分期实际年化利率（考虑资金占用时间）：
- `annual_rate ≈ period_rate × periods × 24 / (periods + 1)`

---

## 四、API 路由设计

所有接口挂载在 `/api/v1/finance/` 前缀下：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/finance/dashboard` | 仪表盘汇总数据（负债、资产、本月应付、到期提醒） |
| GET | `/api/v1/finance/repay-reminders` | 最近 7 天还款提醒 |
| CRUD | `/api/v1/finance/persons` | 人员管理 |
| CRUD | `/api/v1/finance/platforms` | 借贷平台管理 |
| CRUD | `/api/v1/finance/loans` | 借款记录，POST 时自动生成还款计划 |
| GET | `/api/v1/finance/loans/{id}/repayments` | 某笔借款的还款计划 |
| PATCH | `/api/v1/finance/repayments/{id}/pay` | 标记某期已还款 |
| CRUD | `/api/v1/finance/pos-swipes` | POS 刷卡记录 |
| CRUD | `/api/v1/finance/credit-cards` | 信用卡管理 |
| CRUD | `/api/v1/finance/card-transactions` | 信用卡消费记录 |
| CRUD | `/api/v1/finance/card-installments` | 信用卡分期 |
| CRUD | `/api/v1/finance/mortgages` | 房贷管理 |
| CRUD | `/api/v1/finance/incomes` | 收入记录 |
| CRUD | `/api/v1/finance/expenses` | 支出记录 |
| GET | `/api/v1/finance/transactions` | 统一流水查询（UNION ALL 多表） |
| GET | `/api/v1/finance/gap-analysis` | 收支缺口分析（按月/年） |
| GET | `/api/v1/finance/reports/summary` | 统计报告汇总 |
| GET | `/api/v1/finance/reports/by-platform` | 按平台统计 |
| GET | `/api/v1/finance/reports/by-month` | 按月统计 |
| CRUD | `/api/v1/finance/fee-configs` | 费率配置 |

**统一流水接口参数**：
- `type`: loan / pos / installment / card_trans / repay / income / expense
- `person_id`: 人员 ID
- `date_from` / `date_to`: 时间范围
- `page` / `page_size`: 分页

**计算工具接口**：
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/finance/calc/interest` | 利息计算器（传入 amount/rate/periods/method，返回还款计划） |
| POST | `/api/v1/finance/calc/annual-rate` | 年化利率计算（传入分期费率/期数，返回实际年化率） |

---

## 五、前端设计

### 5.1 技术选型

- **框架**：Vue 3（CDN 方式，无构建工具，与现有前端一致）
- **图表**：ECharts CDN（替换 Chart.js，功能更丰富、动画更炫）
- **图标**：使用 Unicode emoji 或简单的 SVG 图标
- **主题**：暗黑金融风（深色背景 #0d0d1a，霓虹强调色，玻璃拟态卡片）

### 5.2 配色方案

| 用途 | 颜色 | 色值 |
|------|------|------|
| 背景主色 | 深蓝黑 | #0d0d1a |
| 背景辅色 | 深蓝紫 | #13132b |
| 卡片背景 | 半透明 | rgba(26,26,46,0.8) |
| 主强调色（亏损/负债） | 霓虹红 | #e94560 |
| 次强调色（盈利/资产） | 绿 | #00d2a0 |
| 警告色 | 金 | #f9ca24 |
| 信息色 | 蓝 | #4facfe |
| 文字色 | 白 | #ffffff |
| 辅助文字 | 灰 | #888 |

### 5.3 页面结构

**布局**：左侧边栏导航（200px 宽）+ 右侧内容区

**路由**（Hash 路由，与现有前端一致）：

```
#/finance/dashboard        — 仪表盘
#/finance/loans            — 借贷管理
#/finance/pos              — POS 刷卡
#/finance/credit-cards     — 信用卡管理
#/finance/installments     — 分期管理
#/finance/mortgages        — 房贷管理
#/finance/incomes          — 收入管理
#/finance/expenses         — 支出管理
#/finance/transactions     — 统一流水
#/finance/reports          — 统计报告
#/finance/settings         — 费率配置 / 人员管理
```

### 5.4 仪表盘布局

```
┌─────────────────────────────────────────────────────┐
│ [总负债]  [总资产]  [本月利息]  [本月POS手续费]      │  4 个统计卡片
├────────────────────────┬────────────────────────────┤
│ 月度利息趋势（折线图）   │  各平台负债占比（饼图）      │  图表行
├────────────────────────┴────────────────────────────┤
│ 🔔 最近7天还款提醒                                    │  提醒组件
│ [还剩1天] 交通银行  ¥11,200   [还剩3天] 借呗  ¥3,580 │
├─────────────────────────────────────────────────────┤
│ 月度收支缺口：-¥5,887  ⚠️ 入不敷出                   │  缺口速览
│ [月度缺口趋势柱状图 — 全年12月]                       │
└─────────────────────────────────────────────────────┘
```

---

## 六、路由与导航集成

现有 LightPress CMS 前端入口为 `/static/index.html`。新增财务模块有两种集成方式：

**选择：新建独立入口 `/static/finance.html`，通过右上角导航切换。**

- CMS 管理界面：`/static/index.html`（不变）
- 财务管理平台：`/static/finance.html`（新建）
- 两个页面共享 `/static/app.js` 中的部分工具函数（API 请求封装等）
- 财务管理有独立的 Vue 应用和路由

---

## 七、文件结构变更

```
app/
├── api/v1/
│   ├── finance/
│   │   ├── __init__.py
│   │   ├── dashboard.py        # 仪表盘 + 提醒
│   │   ├── persons.py          # 人员管理
│   │   ├── platforms.py        # 借贷平台
│   │   ├── loans.py            # 借款 + 还款计划
│   │   ├── pos_swipes.py       # POS 刷卡
│   │   ├── credit_cards.py     # 信用卡
│   │   ├── card_transactions.py
│   │   ├── card_installments.py
│   │   ├── mortgages.py        # 房贷
│   │   ├── incomes.py          # 收入
│   │   ├── expenses.py         # 支出
│   │   ├── transactions.py     # 统一流水
│   │   ├── reports.py          # 统计报告
│   │   ├── fee_configs.py      # 费率配置
│   │   └── calc.py             # 利息计算器
│   └── ...（现有路由不变）
├── finance/
│   ├── __init__.py
│   ├── calc_engine.py          # 利息计算核心引擎
│   └── snapshot_service.py     # 负债快照服务
├── models.py                   # 新增 12 个模型
├── schemas.py                  # 新增 Pydantic schemas
├── crud.py                     # 新增财务 CRUD
├── static/
│   ├── finance.html            # 财务管理前端入口
│   ├── finance-app.js          # 财务管理 Vue 应用
│   ├── index.html              # CMS 前端（不变）
│   └── app.js                  # CMS Vue 应用（不变）
└── main.py                     # 注册新路由
```

---

## 八、核心实现要点

1. **利息计算引擎**：独立的纯函数模块 `app/finance/calc_engine.py`，不依赖数据库，方便单元测试
2. **还款计划自动生成**：创建 Loan 时触发，POST 接口中调用 calc_engine 生成 RepaymentPlan 列表并批量写入
3. **负债快照**：每次访问仪表盘时，检查当天是否已有快照，无则自动计算并写入
4. **统一流水**：后端 UNION ALL 查询多表，按时间倒序分页返回，前端无需关心数据来源
5. **还款提醒**：定时或每次访问时查询到期日在 7 天内的 RepaymentPlan + CardInstallment + 基于 CreditCard.due_day 计算的当期账单
6. **数据库迁移**：不破坏现有 CMS 表结构，所有新表独立存在

---

## 九、测试策略

- 利息计算引擎：纯函数，完整的参数化单元测试（各种利率/还款方式组合）
- API 测试：pytest + httpx，覆盖 CRUD + 计算 + 流水查询
- 前端：手动验证（个人工具，不强制 E2E 测试）

---

## 十、验收标准

1. 能录入各平台借款，自动生成还款计划，利息计算正确（与支付宝/银行 APP 对比验证）
2. POS 刷卡自动计算手续费
3. 信用卡账单日/还款日提醒正确
4. 分期年化利率换算正确
5. 统一流水按类型/人员/时间筛选正常工作
6. 月度收支缺口与实际情况一致
7. 仪表盘数据卡片、图表渲染正常
8. 本地 SQLite 正常运行，切换 MySQL 环境变量后可在阿里云运行
