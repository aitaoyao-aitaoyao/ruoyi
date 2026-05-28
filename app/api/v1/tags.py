"""
标签管理接口 — 文章标签的增删查

返回的标签数据包含 article_count（使用了该标签的文章数）。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app import schemas
from app.auth import get_current_user, require_role
from app import crud

router = APIRouter(tags=["标签管理"])


@router.get("/tags", response_model=list[schemas.TagRead])
def list_tags(
    db: Session = Depends(get_db),
):
    """获取全部标签列表（含每个标签的文章数）"""
    tags = crud.get_tags(db)
    return [
        {"id": t.id, "name": t.name, "slug": t.slug, "article_count": len(t.articles)}
        for t in tags
    ]


@router.post("/tags", response_model=schemas.TagRead, status_code=201)
def create_tag(
    tag_in: schemas.TagCreate,
    current_user: User = Depends(require_role("author", "editor", "admin")),
    db: Session = Depends(get_db),
):
    """创建新标签（需要 author/editor/admin 角色），名称自动生成 slug"""
    return crud.create_tag(db, tag_in)


@router.delete("/tags/{tag_id}", status_code=204)
def delete_tag(
    tag_id: int,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """删除标签（仅管理员）"""
    tag = crud.get_tag(db, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="标签不存在")
    crud.delete_tag(db, tag)
