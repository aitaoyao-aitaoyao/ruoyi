# Mobile Responsive Design — 财智管家移动端适配设计

**日期:** 2026-05-28

## 概述

将财智管家个人财务管理平台适配手机浏览器，核心策略：

- 桌面端（>768px）：现有侧边栏布局完全不变
- 移动端（≤768px）：底部 5 Tab 导航 + 顶部子导航芯片栏
- 零外部依赖，纯 CSS 媒体查询 + Vue 动态组件
- 15 个现有页面组件零改动

## 导航结构

### 底部 5 Tab 分组

| Tab | 图标 | 子导航 |
|-----|------|--------|
| 总览 | 📊 | 无（仪表盘） |
| 交易 | 💳 | POS刷卡 / 信用卡消费 / 收入 / 支出 / 统一流水 |
| 报表 | 📈 | 无（统计报告） |
| 负债 | 💰 | 借贷管理 / 信用卡 / 分期管理 / 房贷管理 |
| 我的 | 👤 | 人员管理 / 借贷平台 / 回收站 / 设置 |

### 子导航交互

每个 Tab 内使用横向可滚动的 `filter-chip` 芯片栏切换子页面，与现有 filter-bar 风格一致。当前激活的子页面通过动态组件 `<component :is>` 渲染，无页面刷新。

## CSS 响应式改动（finance.html）

### 断点策略

| 断点 | 宽度 | 作用 |
|------|------|------|
| ≤768px | 侧边栏隐藏、底部 Tab 栏显示、表格横向滚动、模态框底部弹出、主区域去除左边距和 padding |
| ≤640px | 表单双列 → 单列 |
| ≤480px | 统计卡片 → 单列 |

### 新增 CSS 关键规则

- `.mobile-tab-bar` — 固定在底部，flex 均匀分布，含 `safe-area-inset-bottom` 适配 iPhone
- `.mobile-header` — sticky 顶部，深色背景
- `.mobile-sub-nav` — 横向滚动，隐藏滚动条，`-webkit-overflow-scrolling: touch`
- `.table-wrapper` — 表格外层包裹，`overflow-x: auto`
- `.modal` — 宽度变为 100vw，底部弹出（`border-radius: 16px 16px 0 0`）
- `.form-row` — 单列
- `.stat-cards` — 单列（≤480px）
- `.chart-inner` — 高度降至 220px（≤480px 时 200px）

## Vue 组件改动（finance-app.js）

### 新增 MobileShell 组件

包装组件，负责：

- 根据 `activeTab` 渲染当前 Tab 的内容
- 渲染底部 Tab 栏
- 渲染顶部子导航芯片栏（当子页面 >1 时）
- 管理 `activeTab` 和 `currentSub` 状态
- 切换到新 Tab 时重置 `currentSub` 为默认子页面
- Tab 切换时 lazy：首次访问才挂载，之后 keep-alive

### App 根组件改动

- 新增 `isMobile: window.innerWidth <= 768` 响应式数据
- `mounted` 中 `window.addEventListener('resize', ...)` 实时检测
- `beforeUnmount` 中移除 resize 监听
- 模板：`isMobile ? MobileShell : 侧边栏 + router-view`
- `navItems` 保持不变（桌面端使用）

### 不变的部分

- 15 个页面组件（DashboardPage、LoansPage、PosPage、CreditCardsPage、CardTransactionsPage、InstallmentsPage、MortgagesPage、IncomesPage、ExpensesPage、TransactionsPage、ReportsPage、PersonsPage、PlatformsPage、RecycleBinPage、SettingsPage）— 零改动
- LoginPage — 零改动（已有 `max-width: 90vw`）
- NotFoundPage — 零改动
- ChartMixin、ToastMixin、BatchDeleteMixin — 零改动
- 路由定义 — 零改动（桌面端继续用 router-view）
- API 调用、数据处理逻辑 — 零改动

## 移动端细节处理

- 表格：外层包裹 `table-wrapper`，设置 `min-width: 600px` 保证内容不挤压
- 统计卡片：≤480px 单列，480-700px 双列，700-1100px 三列
- 模态框：`max-height: 85vh` 内部可滚动，底部弹出贴合手机操作
- 图表：ECharts 自动 resize 已有 ChartMixin 处理，移动端 chart-inner 高度降低
- 触摸：底部 Tab 最小点击区域 44px（苹果 HIG 标准），芯片间距 ≥8px
- 安全区域：`env(safe-area-inset-bottom)` 适配 iPhone X+ 底部横条
- 登录页：已有 `max-width: 90vw`，粒子动画已有窗口 resize 适配

## 实施顺序

1. `finance.html` — 新增所有移动端 CSS
2. `finance-app.js` — 新增 MobileShell 组件
3. `finance-app.js` — 修改 App 根组件（isMobile 逻辑 + 模板分支）
4. 现有页面组件模板 — 给表格外层加 `<div class="table-wrapper">`
5. 本地测试验证
