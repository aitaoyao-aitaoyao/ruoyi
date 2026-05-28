"""
文章接口 — 文章 CRUD + 工作流（提交审核/审核通过/驳回/发布/归档）

文章状态机流转:
    draft ──[提交审核]──→ pending ──[审核通过]──→ published ──[归档]──→ archived
      ↑                      │
      └──────[驳回]──────────┘

权限控制:
    - 作者(author): 创建文章、编辑自己的文章、提交审核
    - 编辑(editor): 审核通过/驳回/发布/归档任何文章
    - 管理员(admin): 所有权限
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Article, User
from app import schemas
from app.auth import get_current_user, require_role
from app import crud

router = APIRouter(tags=["文章管理"])


def _article_to_read(article: Article) -> dict:
    """将 ORM Article 对象转换为 API 响应字典（含关联信息）"""
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


@router.get("/articles", response_model=schemas.ArticleListResponse)
def list_articles(
    status: Optional[str] = Query(None),
    category_id: Optional[int] = Query(None),
    tag: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    文章列表（分页 + 多条件筛选）。

    查询参数:
        status:      按状态筛选 draft/pending/published/archived
        category_id: 按分类 ID 筛选
        tag:         按标签名筛选
        keyword:     按关键词搜索（模糊匹配标题和正文）
        page:        页码（从 1 开始）
        size:        每页条数（1-100）
    """
    skip = (page - 1) * size
    items = crud.get_articles(
        db,
        skip=skip,
        limit=size,
        status=status,
        category_id=category_id,
        tag=tag,
        keyword=keyword,
    )
    total = crud.count_articles(
        db,
        status=status,
        category_id=category_id,
        tag=tag,
        keyword=keyword,
    )
    return {
        "items": [_article_to_read(a) for a in items],
        "total": total,
        "page": page,
        "size": size,
    }


@router.post("/articles", response_model=schemas.ArticleRead, status_code=201)
def create_article(
    article_in: schemas.ArticleCreate,
    current_user: User = Depends(require_role("author", "editor", "admin")),
    db: Session = Depends(get_db),
):
    """创建新文章（需要 author/editor/admin 角色），初始状态为 draft"""
    article = crud.create_article(db, article_in, current_user.id)
    return _article_to_read(article)


@router.get("/articles/my", response_model=schemas.ArticleListResponse)
def my_articles(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """我的文章：只返回当前登录用户创建的文章"""
    skip = (page - 1) * size
    items = crud.get_articles(db, skip=skip, limit=size, author_id=current_user.id)
    total = crud.count_articles(db, author_id=current_user.id)
    return {
        "items": [_article_to_read(a) for a in items],
        "total": total,
        "page": page,
        "size": size,
    }


@router.get("/articles/{article_id}", response_model=schemas.ArticleRead)
def get_article(
    article_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取文章详情"""
    article = crud.get_article(db, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
    return _article_to_read(article)


@router.patch("/articles/{article_id}", response_model=schemas.ArticleRead)
def update_article(
    article_id: int,
    update_in: schemas.ArticleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    更新文章（部分更新）。

    权限：只能编辑自己的文章，超级管理员可以编辑任何文章。
    """
    article = crud.get_article(db, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
    if article.author_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="只能编辑自己的文章")
    article = crud.update_article(db, article, update_in)
    return _article_to_read(article)


@router.delete("/articles/{article_id}", status_code=204)
def delete_article(
    article_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    删除文章（物理删除）。

    权限：只能删除自己的文章，超级管理员可以删除任何文章。
    """
    article = crud.get_article(db, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
    if article.author_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="无权删除此文章")
    crud.delete_article(db, article)


# ======================== 文章工作流接口 ========================

@router.post("/articles/{article_id}/submit", response_model=schemas.ArticleRead)
def submit_article(
    article_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """提交审核：draft → pending（作者提交给编辑审核）"""
    article = crud.get_article(db, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
    if article.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="只能提交自己的文章")
    if article.status != "draft":
        raise HTTPException(status_code=400, detail="只有草稿状态的文章可以提交审核")
    article = crud.submit_article(db, article)
    return _article_to_read(article)


@router.post("/articles/{article_id}/approve", response_model=schemas.ArticleRead)
def approve_article(
    article_id: int,
    current_user: User = Depends(require_role("editor", "admin")),
    db: Session = Depends(get_db),
):
    """审核通过：pending → published（编辑或管理员操作）"""
    article = crud.get_article(db, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
    if article.status != "pending":
        raise HTTPException(status_code=400, detail="只有待审核状态的文章可以通过")
    article = crud.approve_article(db, article, current_user.id)
    return _article_to_read(article)


@router.post("/articles/{article_id}/reject", response_model=schemas.ArticleRead)
def reject_article(
    article_id: int,
    reject_in: schemas.RejectRequest,
    current_user: User = Depends(require_role("editor", "admin")),
    db: Session = Depends(get_db),
):
    """驳回文章：pending → draft（编辑驳回，需填写驳回意见）"""
    article = crud.get_article(db, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
    if article.status != "pending":
        raise HTTPException(status_code=400, detail="只有待审核状态的文章可以驳回")
    article = crud.reject_article(db, article, current_user.id, reject_in.comment)
    return _article_to_read(article)


@router.post("/articles/{article_id}/publish", response_model=schemas.ArticleRead)
def publish_article(
    article_id: int,
    current_user: User = Depends(require_role("editor", "admin")),
    db: Session = Depends(get_db),
):
    """直接发布：draft 或 pending → published（跳过审核流程）"""
    article = crud.get_article(db, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
    if article.status not in ("draft", "pending"):
        raise HTTPException(status_code=400, detail="只能发布草稿或待审核状态的文章")
    article = crud.publish_article(db, article)
    return _article_to_read(article)


@router.post("/articles/{article_id}/archive", response_model=schemas.ArticleRead)
def archive_article(
    article_id: int,
    current_user: User = Depends(require_role("editor", "admin")),
    db: Session = Depends(get_db),
):
    """归档文章：published → archived"""
    article = crud.get_article(db, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
    if article.status == "archived":
        raise HTTPException(status_code=400, detail="文章已归档")
    article = crud.archive_article(db, article)
    return _article_to_read(article)
