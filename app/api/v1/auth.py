"""
认证接口 — 用户注册、登录、Token 管理、个人资料

JWT Token 流程:
    1. POST /register → 注册新用户
    2. POST /token    → 用户名密码登录，获取 Token
    3. GET /me        → 用 Token 获取当前用户信息
    4. PATCH /me      → 更新个人资料
    5. PATCH /me/password → 修改密码
    6. POST /refresh  → 刷新 Token
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app import schemas
from app.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
)

router = APIRouter(tags=["认证"])


@router.post("/register", response_model=schemas.UserRead, status_code=201)
def register(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    """注册新用户：检查用户名和邮箱唯一性，密码自动 bcrypt 哈希"""
    # 检查用户名是否已被占用
    if db.query(User).filter(User.username == user_in.username).first():
        raise HTTPException(status_code=400, detail="用户名已被占用")
    # 检查邮箱是否已被注册
    if db.query(User).filter(User.email == user_in.email).first():
        raise HTTPException(status_code=400, detail="邮箱已被注册")
    # 创建用户（密码在 crud.create_user 中自动哈希）
    user = User(
        username=user_in.username,
        email=user_in.email,
        full_name=user_in.full_name,
        hashed_password=hash_password(user_in.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/token", response_model=schemas.Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    用户登录：验证用户名密码，返回 JWT Token。

    使用 OAuth2PasswordRequestForm 接收表单数据（Swagger 文档中会显示锁图标）。
    请求格式：application/x-www-form-urlencoded
    参数：username, password
    """
    # 第一步：验证用户凭据
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    # 第二步：检查账号是否被禁用
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="账号已被禁用"
        )
    # 第三步：签发 Token（sub 字段存储用户 ID）
    token = create_access_token({"sub": str(user.id)})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=schemas.UserRead)
def read_me(current_user: User = Depends(get_current_user)):
    """获取当前登录用户的个人信息（需要有效的 Token）"""
    roles = [r.name for r in current_user.roles]
    return {
        **current_user.__dict__,
        "roles": roles,
    }


@router.patch("/me", response_model=schemas.UserRead)
def update_me(
    update: schemas.UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    更新当前用户个人资料（部分更新）。

    使用 is not None 判断字段是否传入：
    - 传入的字段 → 更新
    - 未传入的字段 → 保持原值
    """
    if update.email is not None:
        current_user.email = update.email
    if update.full_name is not None:
        current_user.full_name = update.full_name
    if update.password is not None:
        current_user.hashed_password = hash_password(update.password)
    db.commit()
    db.refresh(current_user)
    roles = [r.name for r in current_user.roles]
    return {**current_user.__dict__, "roles": roles}


@router.patch("/me/password")
def change_password(
    pw: schemas.PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """修改密码：需要提供旧密码验证身份"""
    # 先验证旧密码是否正确
    if not verify_password(pw.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=400, detail="当前密码错误"
        )
    # 更新为新密码
    current_user.hashed_password = hash_password(pw.new_password)
    db.commit()
    return {"message": "密码修改成功"}


@router.post("/refresh", response_model=schemas.Token)
def refresh_token(current_user: User = Depends(get_current_user)):
    """刷新 Token：用旧 Token 换取一个新 Token（延长登录有效期）"""
    token = create_access_token({"sub": str(current_user.id)})
    return {"access_token": token, "token_type": "bearer"}
