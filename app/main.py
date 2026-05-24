"""
FastAPI 应用入口 — LightPress CMS

启动方式:
    python -m uvicorn app.main:app --reload
    或执行项目根目录的 run.py
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from app.db import engine, Base
from app.api.v1 import auth, articles, categories, tags, media, users, dashboard
from app.api.v1.finance import persons, platforms, loans, pos_swipes
from app.api.v1.finance import credit_cards, card_transactions, card_installments
from app.api.v1.finance import mortgages, incomes, expenses, fee_configs
from app.api.v1.finance import dashboard as fin_dashboard, calc, transactions, reports

# 自动创建所有数据库表（如果表已存在则跳过）
Base.metadata.create_all(bind=engine)

# 创建 FastAPI 应用实例，配置 Swagger 文档信息
app = FastAPI(
    title="LightPress CMS",
    description="内容管理平台 — 用于接口测试、自动化测试练习",
    version="1.0.0",
)

# 跨域中间件：允许前端（可能在不同端口）访问 API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册各模块的路由，统一使用 /api/v1 前缀
app.include_router(auth.router, prefix="/api/v1")
app.include_router(articles.router, prefix="/api/v1")
app.include_router(categories.router, prefix="/api/v1")
app.include_router(tags.router, prefix="/api/v1")
app.include_router(media.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(persons.router, prefix="/api/v1")
app.include_router(platforms.router, prefix="/api/v1")
app.include_router(loans.router, prefix="/api/v1")
app.include_router(pos_swipes.router, prefix="/api/v1")
app.include_router(credit_cards.router, prefix="/api/v1")
app.include_router(card_transactions.router, prefix="/api/v1")
app.include_router(card_installments.router, prefix="/api/v1")
app.include_router(mortgages.router, prefix="/api/v1")
app.include_router(incomes.router, prefix="/api/v1")
app.include_router(expenses.router, prefix="/api/v1")
app.include_router(fee_configs.router, prefix="/api/v1")
app.include_router(fin_dashboard.router, prefix="/api/v1")
app.include_router(calc.router, prefix="/api/v1")
app.include_router(transactions.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")

# 挂载静态文件目录（前端 Vue SPA）
BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/")
def root():
    """根路径：返回服务基本信息和入口链接"""
    return {
        "message": "LightPress CMS API",
        "docs": "/docs",
        "frontend": "/static/index.html",
    }
