"""
媒体文件接口 — 文件上传/下载/列表/删除

上传限制:
    - 允许的 MIME 类型: 图片(jpg/png/gif/webp)、PDF、文本、ZIP、Word 文档
    - 图片最大 5MB，其他文件最大 10MB
    - 文件名使用 UUID 重命名防止冲突和安全问题

文件存储路径: 项目根目录/uploads/
"""
import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app import schemas
from app.auth import get_current_user, require_role
from app import crud

router = APIRouter(tags=["媒体管理"])

# 上传目录：项目根目录下的 uploads 文件夹
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "uploads")

# 允许上传的文件类型白名单
ALLOWED_MIME_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "application/pdf", "text/plain", "application/zip",
    "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

MAX_IMAGE_SIZE = 5 * 1024 * 1024   # 图片 5MB 限制
MAX_FILE_SIZE = 10 * 1024 * 1024   # 其他文件 10MB 限制


@router.post("/media/upload", response_model=schemas.MediaRead, status_code=201)
async def upload_media(
    file: UploadFile = File(...),
    current_user: User = Depends(require_role("author", "editor", "admin")),
    db: Session = Depends(get_db),
):
    """
    上传文件。

    流程:
        1. 检查文件类型是否在白名单内
        2. 读取文件内容，检查大小限制
        3. 用 UUID 重命名文件（防止文件名冲突和路径遍历攻击）
        4. 保存到 uploads/ 目录
        5. 将文件信息写入数据库
    """
    # 检查文件类型
    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {file.content_type}")

    # 读取文件内容并检查大小
    content = await file.read()
    file_size = len(content)

    is_image = file.content_type and file.content_type.startswith("image/")
    max_size = MAX_IMAGE_SIZE if is_image else MAX_FILE_SIZE
    if file_size > max_size:
        limit_mb = max_size // (1024 * 1024)
        raise HTTPException(status_code=400, detail=f"文件大小超过 {limit_mb}MB 限制")

    # 确保上传目录存在
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # 生成唯一文件名（UUID + 原始扩展名）
    ext = os.path.splitext(file.filename or "file")[1]
    filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(UPLOAD_DIR, filename)

    # 写入磁盘
    with open(file_path, "wb") as f:
        f.write(content)

    # 记录到数据库
    media = crud.create_media(
        db,
        filename=filename,
        original_name=file.filename or "unknown",
        file_path=file_path,
        file_size=file_size,
        mime_type=file.content_type or "application/octet-stream",
        uploader_id=current_user.id,
    )
    return media


@router.get("/media", response_model=schemas.MediaListResponse)
def list_media(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """媒体文件列表（分页）"""
    skip = (page - 1) * size
    items = crud.get_media_list(db, skip=skip, limit=size)
    total = crud.count_media(db)
    return {"items": items, "total": total, "page": page, "size": size}


@router.get("/media/{media_id}")
def get_media(
    media_id: int,
    db: Session = Depends(get_db),
):
    """
    下载/查看文件。

    返回 FileResponse，浏览器会根据 MIME 类型自动处理：
    - 图片/PDF → 浏览器内预览
    - 其他类型 → 下载
    """
    media = crud.get_media(db, media_id)
    if not media:
        raise HTTPException(status_code=404, detail="文件不存在")
    if not os.path.exists(media.file_path):
        raise HTTPException(status_code=404, detail="文件在磁盘上不存在")
    return FileResponse(
        media.file_path,
        media_type=media.mime_type,
        filename=media.original_name,
    )


@router.delete("/media/{media_id}", status_code=204)
def delete_media(
    media_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    删除媒体文件。

    权限：只能删除自己上传的文件，超级管理员可以删除任何文件。
    同时删除磁盘文件 + 数据库记录。
    """
    media = crud.get_media(db, media_id)
    if not media:
        raise HTTPException(status_code=404, detail="文件不存在")
    if media.uploader_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="无权删除此文件")
    # 删除磁盘上的物理文件
    if os.path.exists(media.file_path):
        os.remove(media.file_path)
    crud.delete_media(db, media)
