"""
用户管理接口 — 管理员对用户的增删改查

所有接口仅限 admin 角色访问。
删除用户采用软删除（将 is_active 设为 False），不物理删除数据。
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User, Article
from app import schemas
from app.auth import get_current_user, require_role, hash_password
from app import crud

router = APIRouter(tags=["用户管理"])


def _user_to_read(user: User) -> dict:
    """将 ORM User 对象转换为 API 响应字典（含角色列表）"""
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "is_active": user.is_active,
        "is_superuser": user.is_superuser,
        "created_at": user.created_at,
        "roles": [r.name for r in user.roles],
    }


@router.get("/users", response_model=list[schemas.UserRead])
def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """获取用户列表（分页，仅管理员）"""
    skip = (page - 1) * size
    users = crud.get_users(db, skip=skip, limit=size)
    return [_user_to_read(u) for u in users]


@router.post("/users", response_model=schemas.UserRead, status_code=201)
def create_user(
    user_in: schemas.UserAdminCreate,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """
    管理员创建新用户（可同时分配角色）。

    与普通注册不同：
    - 可以指定 role_ids 分配角色
    - 不需要验证邮箱唯一性
    """
    if crud.get_user_by_username(db, user_in.username):
        raise HTTPException(status_code=400, detail="用户名已被占用")
    # 先创建基础用户
    base = schemas.UserCreate(
        username=user_in.username,
        email=user_in.email,
        full_name=user_in.full_name,
        password=user_in.password,
    )
    user = crud.create_user(db, base)
    # 如果指定了角色，关联角色
    if user_in.role_ids:
        roles = [crud.get_role(db, rid) for rid in user_in.role_ids]
        user.roles = [r for r in roles if r is not None]
        db.commit()
        db.refresh(user)
    return _user_to_read(user)


@router.patch("/users/{user_id}", response_model=schemas.UserRead)
def update_user(
    user_id: int,
    update_in: schemas.UserAdminUpdate,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """
    管理员更新用户信息（部分更新）。

    可更新的字段:
        - email: 邮箱
        - full_name: 显示名称
        - is_active: 启用/禁用
        - role_ids: 角色列表（会用新列表完全替换旧角色）
    """
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if update_in.email is not None:
        user.email = update_in.email
    if update_in.full_name is not None:
        user.full_name = update_in.full_name
    if update_in.is_active is not None:
        user.is_active = update_in.is_active
    if update_in.role_ids is not None:
        roles = [crud.get_role(db, rid) for rid in update_in.role_ids]
        user.roles = [r for r in roles if r is not None]
    db.commit()
    db.refresh(user)
    return _user_to_read(user)


@router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """
    停用用户（软删除）。

    不物理删除数据库记录，只是将 is_active 设为 False。
    这样用户无法登录，但历史数据（文章等）不受影响。
    """
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.is_active = False
    db.commit()


@router.get("/users/{user_id}/articles", response_model=schemas.ArticleListResponse)
def user_articles(
    user_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查看指定用户的文章列表"""
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    skip = (page - 1) * size
    items = crud.get_articles(db, skip=skip, limit=size, author_id=user_id)
    total = crud.count_articles(db, author_id=user_id)

    def _article_to_read(article):
        return {
            "id": article.id,
            "title": article.title,
            "slug": article.slug,
            "content": article.content,
            "excerpt": article.excerpt,
            "status": article.status,
            "category_id": article.category_id,
            "category_name": article.category.name if article.category else "",
            "author_id": article.author_id,
            "author_name": article.author.full_name or article.author.username,
            "tags": [
                {"id": t.id, "name": t.name, "slug": t.slug, "article_count": len(t.articles)}
                for t in article.tags
            ],
            "review_comment": article.review_comment,
            "published_at": article.published_at,
            "created_at": article.created_at,
            "updated_at": article.updated_at,
        }

    return {
        "items": [_article_to_read(a) for a in items],
        "total": total,
        "page": page,
        "size": size,
    }
