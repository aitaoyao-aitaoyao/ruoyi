# 信用卡账单系统 + 移动端适配 + 系统优化

**日期:** 2026-06-14

## 概述

三个目标并行：
1. 信用卡从「简单透支余额」升级为「银行式账单管理」
2. 移动端纯CSS适配（不碰Vue模板）
3. 系统功能审计 + 缺失功能补齐

---

## 一、信用卡账单系统

### 新增表 `credit_card_bills`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | PK | — |
| card_id | FK→credit_cards | 关联信用卡 |
| bill_month | varchar(7) | "2026-06" |
| bill_start | date | 账单周期开始（自动） |
| bill_end | date | 账单周期结束（自动） |
| due_date | date | 还款截止日（自动） |
| bill_amount | float | 账单金额（自动汇总POS+消费，可手动改） |
| paid_amount | float | 已还金额，默认0 |
| min_payment | float | 最低还款额（bill_amount×10%） |
| interest | float | 本期循环利息 |
| fee | float | 本期手续费 |
| status | varchar(20) | unpaid/partial/paid/overdue |
| note | varchar(200) | 备注 |

### 账单生成规则
- 根据信用卡的 `bill_day` 自动计算每期账单周期
- 当期账单不存在时，访问信用卡页面自动创建
- 账单金额 = 当期POS刷卡合计 + 信用卡消费合计（自动汇总，可手动改）
- 最低还款 = 账单金额 × 10%
- 如超过还款日未还清 → 状态变为 overdue

### 还款操作
- **全额还款**：paid_amount = bill_amount，status = paid
- **最低还款**：paid_amount = min_payment，status = partial
- **自定义还款**：手动输入金额

### 数据联动
- `snapshot_service.card_debt` → 改为从未还账单计算
- 仪表盘总负债/负债明细/V2指标 → 全部联动
- 统计报告利息统计 → 从账单 interest 字段读取
- 还款提醒 → 根据 due_date 生成

### 后端文件
- 新增 `app/api/v1/finance/credit_card_bills.py`
- 修改 `app/models.py` — 新增 CreditCardBill
- 修改 `app/schemas.py` — 新增相关schema
- 修改 `app/crud.py` — 新增CRUD
- 修改 `app/finance/snapshot_service.py` — card_debt改用账单计算
- 修改 `app/main.py` — 注册路由

### 前端文件
- 修改 `app/static/finance-app.js` — 信用卡管理页改造为卡片式+账单列表
- 修改 `app/static/finance.html` — CSS

---

## 二、移动端适配

纯CSS方案，不修改Vue模板结构：

### 断点策略
| 断点 | 作用 |
|------|------|
| ≤768px | 侧边栏隐藏、底部导航栏、表格横向滚动、模态框全宽 |
| ≤640px | 表单双列→单列 |
| ≤480px | 统计卡片→2列 |

### CSS规则（finance.html 新增）
- `@media (max-width: 768px)` — 侧边栏隐藏、主区域全宽
- `.mobile-nav` — 固定在底部的导航栏（5个高频入口）
- `.table-wrapper` — 表格外层 overflow-x:auto
- `.modal` 改为 100vw 全宽底部弹出

**不涉及**：Vue组件、路由、模板结构 — 全部不变。

---

## 三、系统优化（P0优先级）

| 序号 | 优化项 | 说明 |
|------|--------|------|
| 1 | 信用卡账单系统 | 见上文 |
| 2 | 移动端适配 | 纯CSS |
| 3 | 仪表盘负债联动 | 由账单驱动 |
| 4 | 预算设置页 | 月预算额度、分类预算 |
| 5 | 净资产卡片 | 仪表盘显示：现金+资产-负债 |

---

## 实施顺序

1. 信用卡账单后端（模型+API+快照联动）
2. 信用卡账单前端（卡片式页面+账单管理）
3. 移动端CSS
4. 预算设置 + 净资产卡片
5. 全局联动测试
