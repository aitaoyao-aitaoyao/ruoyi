"""
仪表盘接口 — 后台首页的统计数据和最近动态
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app import schemas
from app.auth import get_current_user
from app import crud

router = APIRouter(tags=["仪表盘"])


@router.get("/dashboard/stats", response_model=schemas.DashboardStats)
def get_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取仪表盘统计数据：文章数、用户数、分类数等"""
    return crud.get_dashboard_stats(db)


@router.get("/dashboard/recent", response_model=list[schemas.RecentActivity])
def get_recent(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取最近更新的 10 篇文章（用于仪表盘动态列表）"""
    articles = crud.get_recent_articles(db, limit=10)
    return [
        {
            "id": a.id,
            "title": a.title,
            "status": a.status,
            "author_name": a.author.full_name or a.author.username,
            "updated_at": a.updated_at,
        }
        for a in articles
    ]
