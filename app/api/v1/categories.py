"""
分类管理接口 — 文章分类的增删查

权限控制:
    - 查看: 所有已登录用户
    - 创建: editor / admin
    - 删除: admin only
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app import schemas
from app.auth import get_current_user, require_role
from app import crud

router = APIRouter(tags=["分类管理"])


@router.get("/categories", response_model=list[schemas.CategoryRead])
def list_categories(
    db: Session = Depends(get_db),
):
    """获取全部分类列表"""
    return crud.get_categories(db)


@router.post("/categories", response_model=schemas.CategoryRead, status_code=201)
def create_category(
    cat_in: schemas.CategoryCreate,
    current_user: User = Depends(require_role("editor", "admin")),
    db: Session = Depends(get_db),
):
    """创建新分类（需要 editor/admin 角色），名称自动生成 slug"""
    return crud.create_category(db, cat_in)


@router.delete("/categories/{category_id}", status_code=204)
def delete_category(
    category_id: int,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """删除分类（仅管理员）"""
    cat = crud.get_category(db, category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="分类不存在")
    crud.delete_category(db, cat)
