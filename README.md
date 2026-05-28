# LightPress CMS

受 WordPress 启发的内容管理平台，用于学习 API 测试、自动化测试、抓包分析、单元测试和 Selenium UI 自动化。基于 **FastAPI + SQLite + Vue 3** 构建，内存占用 < 50MB。

## 技术栈

| 层级 | 技术 | 说明 |
|-------|-----------|-------|
| 后端 | FastAPI + SQLAlchemy 2.0 + SQLite | 零配置数据库，自动生成 Swagger 文档 |
| 认证 | PyJWT + passlib[bcrypt] | JWT Bearer Token，支持过期和刷新 |
| 前端 | Vue 3 + Tailwind CSS (CDN) | 单页应用，Hash 路由，暗色主题，无需构建工具 |
| 测试 | pytest + httpx + Selenium | 3 层测试套件（单元、API、UI） |

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动服务
python -m uvicorn app.main:app --reload

# 3.（可选）写入种子数据 — 直接操作数据库，无需启动服务
python seed_data.py
```

**访问地址：**
- API 文档（Swagger）：http://127.0.0.1:8000/docs
- 前端管理界面：http://127.0.0.1:8000/static/index.html

**演示账号（执行 `python seed_data.py` 后可用）：**

| 用户名 | 密码 | 角色 |
|----------|----------|------|
| admin | admin123 | 管理员（超级用户） |
| editor_jane | editor123 | 编辑（审核/发布/归档） |
| author_bob | author123 | 作者（撰写/提交） |
| author_alice | author123 | 作者 |
| author_tom | author123 | 作者 |

## API 接口（共 38 个）

| 模块 | 前缀 | 接口 | 说明 |
|--------|--------|-----------|-------------|
| 认证 | `/api/v1` | register, token, me, refresh | 注册、登录、个人信息、Token 刷新 |
| 文章 | `/api/v1/articles` | 增删改查 + submit/approve/reject/publish/archive | 完整 CMS 工作流，带状态机 |
| 分类 | `/api/v1/categories` | 列表、创建、删除 | 文章分类管理 |
| 标签 | `/api/v1/tags` | 列表、创建、删除 | 文章标签管理 |
| 媒体 | `/api/v1/media` | 上传、列表、下载、删除 | 文件上传（图片≤5MB，其他≤10MB） |
| 用户 | `/api/v1/users` | 列表、创建、更新、停用 | 仅管理员可操作的用户管理 |
| 仪表盘 | `/api/v1/dashboard` | 统计、最近动态 | 数据概览和最近活动 |

### 文章工作流状态机

```
草稿 ──[提交]──→ 待审核 ──[通过]──→ 已发布 ──[归档]──→ 已归档
  ↑                 │                    │
  └─────[驳回]──────┘                    │
                                         │
         （编辑也可以从草稿直接发布）
```

## 测试套件（136 个测试）

```
tests/
├── conftest.py                 # 会话级临时 SQLite，认证夹具
├── unit/
│   ├── test_models.py          # 17 个测试：模型关系、级联、状态
│   ├── test_schemas.py         # 17 个测试：Pydantic 校验规则
│   └── test_crud.py            # 31 个测试：所有 CRUD 正常/异常路径
├── api/
│   ├── test_auth.py            # 16 个测试：注册、登录、Token、个人信息
│   ├── test_articles.py        # 24 个测试：CRUD、工作流、权限
│   ├── test_categories.py      # 7 个测试：列表、创建、删除、权限
│   ├── test_tags.py            # 7 个测试：列表、创建、删除、权限
│   ├── test_media.py           # 7 个测试：上传、列表、下载、删除
│   └── test_users.py           # 10 个测试：管理员用户管理
└── selenium/
    ├── conftest.py             # 无头 Chrome 夹具
    ├── test_login_ui.py        # 5 个测试：登录/注册表单交互
    └── test_article_ui.py      # 8 个测试：仪表盘、文章增删、导航
```

### 运行测试

```bash
# 全部测试（单元 + API）
pytest -v

# 覆盖率报告
pytest --cov=app --cov-report=term-missing -v

# 仅单元测试
pytest tests/unit -v

# 仅 API 测试
pytest tests/api -v

# Selenium UI 测试（需要 Chrome/Chromium）
pytest tests/selenium -v -m selenium
```

### 涵盖的测试技术

- **夹具作用域**：会话级、函数级，通过表截断实现测试隔离
- **参数化测试**：`@pytest.mark.parametrize` 覆盖多组输入组合
- **认证场景**：401 未认证、403 无权限（基于角色）
- **边界条件**：空字段、最大长度字符串、不存在的 ID
- **状态工作流**：草稿 → 待审核 → 已发布 → 已归档 状态流转
- **文件处理**：multipart 上传断言、二进制下载验证
- **UI 自动化**：无头 Chrome、显式等待、CSS 选择器策略

## 项目结构

```
ruoyi/
├── app/
│   ├── api/v1/
│   │   ├── auth.py             # 认证接口（注册、登录、Token）
│   │   ├── articles.py         # 文章 CRUD + 工作流接口
│   │   ├── categories.py       # 分类管理接口
│   │   ├── tags.py             # 标签管理接口
│   │   ├── media.py            # 文件上传/下载接口
│   │   ├── users.py            # 管理员用户管理接口
│   │   └── dashboard.py        # 仪表盘统计接口
│   ├── models.py               # 7 个 SQLAlchemy 模型 + 3 个关联表
│   ├── schemas.py              # Pydantic v2 请求/响应模型
│   ├── crud.py                 # 数据库 CRUD 操作
│   ├── auth.py                 # JWT、密码哈希、角色校验
│   ├── db.py                   # SQLAlchemy 引擎和会话
│   ├── main.py                 # FastAPI 应用入口
│   └── static/
│       ├── index.html          # Vue 3 SPA 外壳
│       └── app.js              # SPA：API 工具函数 + 9 个 Vue 组件
├── tests/                      # 136 个测试，覆盖 3 个层级
├── seed_data.py                # 测试数据生成器（5 个用户、50 篇文章等）
└── requirements.txt
```

## 学习路径

1. **探索 API** — 访问 `/docs`，使用 Swagger "Try it out" 进行交互式测试
2. **编写 API 测试** — 学习 `tests/api/` 中的 pytest + httpx 用法
3. **单元测试** — 学习 `tests/unit/` 中的模型和 CRUD 隔离技巧
4. **Selenium UI 测试** — 学习 `tests/selenium/` 中的浏览器自动化
5. **抓包分析** — 启动服务后，使用 Charles/Fiddler/mitmproxy 抓取请求
6. **夹具设计** — 学习 `tests/conftest.py` 中的多作用域夹具模式
