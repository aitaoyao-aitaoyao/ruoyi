# LightPress CMS — 本地测试练习系统 设计方案

## 背景

用户需要一套本地系统来练习：接口测试、自动化测试(pytest)、抓包技术、单元测试、Selenium UI 自动化。要求：(1)模拟真实产品场景，(2)接口文档完整，(3)资源占用少，(4)界面美观专业。

当前项目为基础 FastAPI CRUD，业务场景过于通用，前端简陋，不适合作为测试练习目标。决定完全重写为专业 CMS 平台。

## 产品定位

**LightPress CMS** — 精简版内容管理平台，模拟 WordPress 后台核心链路。三类角色协作：

- **作者(Author)**：撰写文章、上传媒体、提交审核
- **编辑(Editor)**：审核文章（通过/退回）、发布、管理分类/标签
- **管理员(Admin)**：管理用户和角色、系统配置

核心流程：作者写文章(draft) → 提交审核(pending) → 编辑审核 → 通过(published) 或 退回(draft) → 归档(archived)

## 技术架构

| 层 | 技术 | 说明 |
|---|------|------|
| 后端 | FastAPI 0.95 + SQLAlchemy 2.0 | 自动 Swagger 文档 |
| 数据库 | SQLite | 零配置，< 50MB 内存 |
| 认证 | PyJWT (Bearer Token) | 真实 Token 机制，支持过期/刷新 |
| 前端 | Vue 3 + Tailwind CSS (CDN) | SPA 单页应用，零构建工具 |
| 测试 | pytest + httpx + Selenium | 三层测试体系 |

## 数据模型（7 张表）

```
User ──1:N──▶ Article ──N:1──▶ Category
  │              │
  │              └──N:N──▶ Tag (article_tags)
  │
  ├──1:N──▶ Media
  └──N:N──▶ Role (user_roles) ──N:N──▶ Permission (role_permissions)
```

- **User**: id, username, email, full_name, hashed_password, is_active, is_superuser, created_at
- **Article**: id, title, slug, content, excerpt, status (draft/pending/published/archived), category_id, author_id, published_at, created_at, updated_at
- **Category**: id, name, slug, description
- **Tag**: id, name, slug
- **Media**: id, filename, original_name, file_path, file_size, mime_type, uploader_id, created_at
- **Role**: id, name, description / **Permission**: id, name, code

## API 接口（38 个端点）

### 认证 (6)
- `POST /api/v1/token` — 登录获取 JWT（公开）
- `POST /api/v1/register` — 注册（公开）
- `GET /api/v1/me` — 个人信息（登录）
- `PATCH /api/v1/me` — 更新资料（登录）
- `PATCH /api/v1/me/password` — 修改密码（登录）
- `POST /api/v1/refresh` — 刷新 Token（登录）

### 文章 (11)
- `GET/POST /api/v1/articles` — 列表(分页+筛选+搜索)/创建草稿
- `GET/PATCH/DELETE /api/v1/articles/{id}` — 详情/更新/删除
- `POST /api/v1/articles/{id}/submit` — 提交审核（作者本人）
- `POST /api/v1/articles/{id}/approve` — 审核通过（编辑）
- `POST /api/v1/articles/{id}/reject` — 审核退回+原因（编辑）
- `POST /api/v1/articles/{id}/publish` — 直接发布（编辑+）
- `POST /api/v1/articles/{id}/archive` — 归档（编辑+）
- `GET /api/v1/articles/my` — 我的文章（作者）

文章列表筛选参数：`?status=&category_id=&keyword=&tag=&page=1&size=20`

### 分类 (3) / 标签 (3)
- `GET/POST /api/v1/categories` — 列表/创建
- `DELETE /api/v1/categories/{id}` — 删除（管理员）
- `GET/POST /api/v1/tags` — 列表(含文章数)/创建
- `DELETE /api/v1/tags/{id}` — 删除（管理员）

### 媒体 (4)
- `POST /api/v1/media/upload` — 上传（multipart, 图片≤5MB, 其他≤10MB）
- `GET /api/v1/media` — 列表（分页）
- `GET /api/v1/media/{id}` — 查看/下载
- `DELETE /api/v1/media/{id}` — 删除

### 用户管理 (5) / 仪表盘 (2)
- `GET/POST /api/v1/users` — 用户列表/创建（管理员）
- `PATCH/DELETE /api/v1/users/{id}` — 更新/停用（管理员）
- `GET /api/v1/users/{id}/articles` — 用户文章（登录）
- `GET /api/v1/dashboard/stats` — 统计（登录）
- `GET /api/v1/dashboard/recent` — 最近动态（登录）

## 前端设计

Vue 3 SPA 单页应用，Hash 路由，所有静态资源从 `/static/` 加载。

### 页面结构
- **登录/注册页**：居中卡片，表单切换
- **仪表盘**：4 统计卡片 + 最近文章列表 + 快速操作
- **文章管理**：筛选栏 + 文章表格 + 分页 + 新建/编辑弹窗
- **文章编辑器**：标题/摘要/分类/标签 + 富文本正文 + 存草稿/提交按钮
- **媒体库**：网格布局，图片预览，上传拖拽区
- **分类/标签管理**：简单列表 + 创建表单
- **用户管理**（管理员）：用户列表 + 创建/编辑/角色分配

### 视觉风格
Tailwind CSS 暗色主题：
- 背景: slate-900 / 卡片: slate-800 / 边框: slate-700
- 主色: blue-500 / 成功: green-400 / 警告: amber-400 / 危险: red-400
- 圆角: 8-12px，阴影适度，过渡动画 200ms

## 项目结构

```
lightpress/
├── app/
│   ├── api/v1/
│   │   ├── __init__.py
│   │   ├── auth.py           # JWT 认证 + 注册登录
│   │   ├── articles.py       # 文章 CRUD + 审核流程
│   │   ├── categories.py     # 分类管理
│   │   ├── tags.py           # 标签管理
│   │   ├── media.py          # 文件上传/管理
│   │   ├── users.py          # 用户管理（仅管理员）
│   │   └── dashboard.py      # 统计 + 动态
│   ├── models.py             # 7 个 SQLAlchemy 模型
│   ├── schemas.py            # Pydantic 请求/响应模型
│   ├── crud.py               # 数据库操作层
│   ├── auth.py               # JWT 编解码 + 依赖注入
│   ├── db.py                 # SQLite 连接配置
│   ├── main.py               # FastAPI 应用入口
│   └── static/
│       ├── index.html        # Vue SPA 入口
│       ├── app.js            # Vue 应用主文件
│       └── components/       # Vue 组件拆分
├── tests/
│   ├── conftest.py           # 多作用域夹具
│   ├── unit/                 # 模型/CRUD/schema 单元测试
│   ├── api/                  # 接口集成测试（全覆盖）
│   └── selenium/             # UI 自动化测试
├── seed_data.py              # 种子数据（3角色+50文章+100标签等）
├── requirements.txt
└── uploads/                  # 上传文件存储目录
```

## 测试覆盖目标

| 层级 | 文件 | 目标用例数 | 覆盖场景 |
|------|------|----------|---------|
| 单元 | test_models.py | 10+ | 模型关系、级联、约束 |
| 单元 | test_schemas.py | 15+ | Pydantic 校验，必填/格式/边界 |
| 单元 | test_crud.py | 25+ | 所有 CRUD 正常+异常，权限逻辑 |
| 单元 | test_auth.py | 10+ | JWT 生成/验证/过期 |
| API | test_auth_api.py | 12+ | 注册/登录/刷新/401/403 |
| API | test_articles.py | 25+ | CRUD + 5 种状态流转 + 筛选/搜索/分页 |
| API | test_categories.py | 6+ | CRUD |
| API | test_tags.py | 6+ | CRUD |
| API | test_media.py | 8+ | 上传/列表/下载/删除/文件大小限制 |
| API | test_users.py | 10+ | 管理员 CRUD + 权限拦截 |
| Selenium | test_login_ui.py | 5+ | 登录成功/失败/注册/登出 |
| Selenium | test_article_ui.py | 8+ | 创建/编辑/提交审核/筛选/分页 |
| **合计** | | **~140** | |

## 实施顺序

1. 清空旧代码，建立新项目骨架（db.py / main.py / 目录结构）
2. 实现 JWT 认证模块（models.User + crud + auth router）
3. 实现文章模块（Article + Category + Tag 模型 + CRUD + 审核流程）
4. 实现媒体模块（上传/存储/管理）
5. 实现用户管理和仪表盘
6. 构建 Vue 3 SPA 前端（7 个页面）
7. 编写种子数据脚本
8. 编写测试用例（单元 → API → Selenium）
9. README 和学习路径文档

## 验证方式

```bash
python -m uvicorn app.main:app --reload   # 启动
python seed_data.py                        # 造数据
pytest -v                                  # 运行全部测试
pytest --cov=app --cov-report=term-missing # 覆盖率
```

---

# FinManager — 个人财务管理平台

## 背景

在 LightPress CMS 基础上集成个人财务管理功能，用于管理多平台借贷、POS 刷卡、信用卡消费、分期、房贷、收支等财务数据。支持利率计算、还款提醒、统一流水、多维度报表和收支缺口分析。

## 技术架构

- **后端**：FastAPI 路由模块化（14 个 finance 子模块），纯函数计算引擎（`app/finance/calc_engine.py`）
- **数据库**：13 张财务表（SQLAlchemy ORM），通过 `Person` 区分家庭成员
- **前端**：Vue 3 CDN + Vue Router 4 (Hash 路由) + ECharts 5，深色金融主题
- **计算引擎**：等额本息、先息后本、到期还本付息、分期年化利率、POS 手续费，支持总利息反推利率（二分搜索）

## 数据模型（13 张财务表）

```
Person ──1:N──▶ Loan ──1:N──▶ RepaymentPlan
  │               │
  │               └──N:1──▶ LoanPlatform
  │
  ├──1:N──▶ PosSwipe
  ├──1:N──▶ CreditCard ──1:N──▶ CreditCardTransaction
  │               │
  │               └──1:N──▶ CardInstallment
  ├──1:N──▶ Mortgage
  ├──1:N──▶ Income
  ├──1:N──▶ Expense
  └── FeeConfig (独立配置)
  └── DebtSnapshot (每日快照)
```

- **Person**: 姓名、关系（本人/配偶/父母/子女）— 区分家庭成员
- **LoanPlatform**: 借贷平台名称、图标、描述（如借呗、微粒贷、抖音月付）
- **Loan**: 借款金额、利率（月利率/年利率/总利息反推）、还款方式（等额本息/先息后本/到期还本付息）、总期数、状态、已还期数（@property 计算）、剩余期数（@property 计算）
- **RepaymentPlan**: 期数、到期日、本金、利息、总还款、状态（pending/paid）、还款日期
- **PosSwipe**: 金额、费率、手续费、银行卡、POS 机、刷卡时间
- **CreditCard**: 银行、卡号后四位、额度、已用额度、账单日、还款日、状态
- **CreditCardTransaction**: 金额、描述、消费时间
- **CardInstallment**: 分期金额、期数、费率方式（每期费率/年化利率/总手续费）、每期费率、年化利率、总手续费、每期还款、已还期数、剩余期数（@property 计算）
- **Mortgage**: 银行、房产名称、总金额、剩余本金、年利率、月供、总期数、还款方式、状态
- **Income**: 金额、来源、类型（月度/年度/一次性）、周期
- **Expense**: 金额、分类（餐饮/交通/购物/娱乐/医疗/教育/居住/通讯/日用/其他）、周期、日期
- **FeeConfig**: 费率类型、费率、描述、启用状态
- **DebtSnapshot**: 快照日期、总负债、贷款负债、信用卡负债、分期负债、房贷负债、POS 手续费合计（每日自动计算）

## API 接口（42+ 端点）

### 基础设施
- `GET/POST /api/v1/finance/persons` — 人员列表/新增
- `DELETE /api/v1/finance/persons/{id}` — 删除人员
- `GET/POST /api/v1/finance/platforms` — 平台列表/新增
- `DELETE /api/v1/finance/platforms/{id}` — 删除平台

### 借贷管理
- `POST /api/v1/finance/loans` — 新增借款（自动生成还款计划，支持总利息反推利率，支持设置已还期数）
- `GET /api/v1/finance/loans` — 借款列表（含已还/剩余期数，可按人员筛选）
- `GET /api/v1/finance/loans/{id}` — 借款详情
- `GET /api/v1/finance/loans/{id}/repayments` — 查看还款计划
- `PATCH /api/v1/finance/loans/repayments/{id}/pay` — 标记单期已还
- `DELETE /api/v1/finance/loans/{id}` — 删除借款

### POS 刷卡
- `GET/POST /api/v1/finance/pos-swipes` — 列表/新增（自动计算手续费）
- `DELETE /api/v1/finance/pos-swipes/{id}` — 删除

### 信用卡管理
- `GET/POST /api/v1/finance/credit-cards` — 列表/新增
- `PATCH /api/v1/finance/credit-cards/{id}` — 更新额度/已用额度/账单日/还款日
- `DELETE /api/v1/finance/credit-cards/{id}` — 删除

### 信用卡消费
- `GET/POST /api/v1/finance/card-transactions` — 列表/新增
- `DELETE /api/v1/finance/card-transactions/{id}` — 删除

### 分期管理
- `POST /api/v1/finance/card-installments` — 新增分期（支持 3 种费率输入：每期手续费率/年化利率/总手续费，系统自动计算其余字段）
- `GET /api/v1/finance/card-installments` — 列表（可按信用卡/人员筛选，含剩余期数）
- `PATCH /api/v1/finance/card-installments/{id}/pay-period` — 还一期
- `DELETE /api/v1/finance/card-installments/{id}` — 删除
- `POST /api/v1/finance/card-installments/batch-delete` — 批量删除

### 房贷管理
- `GET/POST /api/v1/finance/mortgages` — 列表/新增
- `PATCH /api/v1/finance/mortgages/{id}` — 更新剩余本金
- `DELETE /api/v1/finance/mortgages/{id}` — 删除

### 收入/支出
- `GET/POST /api/v1/finance/incomes` — 收入列表/新增
- `DELETE /api/v1/finance/incomes/{id}` — 删除收入
- `GET/POST /api/v1/finance/expenses` — 支出列表/新增（可按分类筛选）
- `DELETE /api/v1/finance/expenses/{id}` — 删除支出

### 仪表盘与报表
- `GET /api/v1/finance/dashboard` — 仪表盘汇总（总负债/总资产/月利息/月POS费，自动计算每日债务快照）
- `GET /api/v1/finance/repay-reminders` — 最近 7 天还款提醒（贷款/信用卡/分期）
- `GET /api/v1/finance/reports/summary` — 汇总报告
- `GET /api/v1/finance/reports/by-platform` — 各平台贷款分布
- `GET /api/v1/finance/reports/by-month` — 月度 POS 手续费
- `GET /api/v1/finance/reports/gap-analysis` — 收支缺口分析
- `GET /api/v1/finance/reports/snapshots` — 负债趋势快照（近 N 月）

### 工具与费率
- `POST /api/v1/finance/calc/interest` — 利息计算器
- `POST /api/v1/finance/calc/annual-rate` — 分期年化利率换算
- `GET/POST /api/v1/finance/fee-configs` — POS 费率配置
- `DELETE /api/v1/finance/fee-configs/{id}` — 删除费率
- `DELETE /api/v1/finance/fee-configs/admin/clear-all` — 清空所有财务数据

### 统一流水
- `GET /api/v1/finance/transactions` — 跨表 UNION 查询（按类型/人员/日期筛选，分页）

## 前端功能（14 个页面）

### 导航菜单
📊 仪表盘 / 👤 人员管理 / 🏢 借贷平台 / 💰 借贷管理 / 💳 POS 刷卡 / 🏦 信用卡 / 🛒 信用卡消费 / 📋 分期管理 / 🏠 房贷管理 / 📈 收入管理 / 📉 支出管理 / 📜 统一流水 / 📊 统计报告 / ⚙️ 设置

### 核心功能
- **仪表盘**：4 统计卡片（总负债/总资产/月利息/月 POS 费）+ 负债明细（点击跳转到对应管理页）+ 负债分布饼图 + 负债趋势折线图 + 7 天还款提醒（中文化类型标签：贷款/信用卡/分期）+ 收支缺口柱线混合图
- **人员管理**：家庭成员 CRUD，关系选择（本人/配偶/父母/子女），批量删除
- **借贷平台**：平台 CRUD（名称/图标/描述），批量删除
- **借贷管理**：借款 CRUD，支持 3 种利率方式（月利率/年利率/总利息反推），支持设置已还期数（适配已有借款场景），还款计划弹窗（逐期标记已还），展示已还期数/剩余期数，人员筛选，批量删除
- **POS 刷卡**：刷卡记录管理，自动计算手续费（公式：金额 × 费率），默认日期填充，批量删除
- **信用卡管理**：信用卡 CRUD（银行/尾号/额度/已用额度/账单日/还款日），编辑更新，批量删除
- **信用卡消费**：消费明细记录，显示关联信用卡信息，默认日期填充，批量删除
- **分期管理**：支持 3 种费率输入方式（每期手续费率 %/年化利率 %/总手续费元），系统自动换算并填充所有字段，展示剩余期数，还一期操作，批量删除
- **房贷管理**：房贷 CRUD（银行/房产/总额/剩余本金/利率/月供/期数），更新剩余本金
- **收入管理**：收入 CRUD（来源/类型/周期），批量删除
- **支出管理**：支出 CRUD（10 种分类/周期/日期），分类筛选，批量删除
- **统一流水**：跨 6 表联合查询，中文化类型标签（贷款/POS刷卡/分期/信用卡消费/收入/支出），日期范围筛选，分页
- **统计报告**：活跃贷款总额 + 累计 POS 手续费统计卡片，平台贷款分布饼图，月度 POS 手续费柱状图，收支缺口分析（年份/月份输入 + 结果展示）
- **设置**：数据管理（一键清空所有财务数据 + 确认提示），POS 费率配置（添加/删除）

### 视觉风格
深色金融主题（CSS 变量）：
- 背景: `#0d0d1a` / 卡片: `rgba(26,26,46,0.8)` / 边框: `rgba(255,255,255,0.06)`
- 红色: `#e94560`（负债/危险） / 绿色: `#00d2a0`（资产/盈利）
- 黄色: `#f9ca24`（利息/警告） / 蓝色: `#4facfe`（手续费/信息）
- 毛玻璃卡片效果 + 12px 圆角 + 响应式网格布局

## 计算引擎（6 个纯函数）

| 函数 | 功能 | 公式 |
|------|------|------|
| `convert_to_monthly_rate(rate, rate_type, amount, periods, method)` | 统一转为月利率；total_interest 模式使用二分搜索反推 | — |
| `calc_equal_installment_plan()` | 等额本息还款计划 | `月供 = P × r × (1+r)^n / ((1+r)^n - 1)` |
| `calc_interest_first_plan()` | 先息后本还款计划 | 每月利息 = P × r，最后一期还本 |
| `calc_bullet_plan()` | 到期还本付息 | 总利息 = P × r × n |
| `calc_installment_annual_rate()` | 分期近似年化利率 (IRR) | `r × n × 24 / (n + 1)` |
| `calc_pos_fee()` | POS 刷卡手续费 | `金额 × 费率` |

## 启动方式

```bash
./run.sh              # 启动服务（自动检查依赖、生成种子数据、释放端口）
./run.sh --seed       # 启动并重新生成种子数据
./run.sh stop         # 停止服务（释放 8000 端口）
./run.sh restart      # 重启服务

# 访问地址
# 财务管理平台: http://127.0.0.1:8000/static/finance.html
# API 文档:      http://127.0.0.1:8000/docs
```

## 测试覆盖

| 文件 | 用例数 | 覆盖场景 |
|------|--------|---------|
| `tests/unit/test_models.py` | 13+ | 财务模型关系、属性计算（paid_periods/remaining_periods） |
| `tests/unit/test_schemas.py` | 15+ | Pydantic 校验（rate_type/repay_method/金额边界） |
| `tests/unit/test_crud.py` | 25+ | 所有财务 CRUD + 快照生成 + 清空数据 |
| `tests/unit/test_calc_engine.py` | 6+ | 6 个计算函数验证 |

---

# 系统访问地址汇总

## 财务管理平台 (FinManager / 财智管家)

| 页面 | URL |
|------|-----|
| 仪表盘 | http://127.0.0.1:8000/static/finance.html#/finance/dashboard |
| POS 刷卡 | http://127.0.0.1:8000/static/finance.html#/finance/pos |
| 借贷管理 | http://127.0.0.1:8000/static/finance.html#/finance/loans |
| 信用卡 | http://127.0.0.1:8000/static/finance.html#/finance/credit-cards |
| 信用卡消费 | http://127.0.0.1:8000/static/finance.html#/finance/card-transactions |
| 分期管理 | http://127.0.0.1:8000/static/finance.html#/finance/installments |
| 房贷管理 | http://127.0.0.1:8000/static/finance.html#/finance/mortgages |
| 收入管理 | http://127.0.0.1:8000/static/finance.html#/finance/incomes |
| 支出管理 | http://127.0.0.1:8000/static/finance.html#/finance/expenses |
| 统一流水 | http://127.0.0.1:8000/static/finance.html#/finance/transactions |
| 统计报告 | http://127.0.0.1:8000/static/finance.html#/finance/reports |
| 人员管理 | http://127.0.0.1:8000/static/finance.html#/finance/persons |
| 借贷平台 | http://127.0.0.1:8000/static/finance.html#/finance/platforms |
| 设置 | http://127.0.0.1:8000/static/finance.html#/finance/settings |

## CMS 管理后台 (LightPress CMS)

| 页面 | URL |
|------|-----|
| CMS 首页 | http://127.0.0.1:8000/static/index.html |
| 登录页 | http://127.0.0.1:8000/static/index.html#/login |
| 注册页 | http://127.0.0.1:8000/static/index.html#/register |
| 仪表盘 | http://127.0.0.1:8000/static/index.html#/dashboard |
| 文章管理 | http://127.0.0.1:8000/static/index.html#/articles |
| 分类管理 | http://127.0.0.1:8000/static/index.html#/categories |
| 标签管理 | http://127.0.0.1:8000/static/index.html#/tags |
| 媒体库 | http://127.0.0.1:8000/static/index.html#/media |
| 用户管理 | http://127.0.0.1:8000/static/index.html#/users |

## 后端接口

| 接口 | URL |
|------|-----|
| API 文档 (Swagger) | http://127.0.0.1:8000/docs |
| ReDoc 文档 | http://127.0.0.1:8000/redoc |
| 健康检查 | http://127.0.0.1:8000/ |
| Finance API 前缀 | http://127.0.0.1:8000/api/v1/finance/ |
| CMS API 前缀 | http://127.0.0.1:8000/api/v1/ |
