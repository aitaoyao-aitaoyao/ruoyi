"""
认证授权模块 — JWT Token + bcrypt 密码哈希 + 角色权限控制

核心流程:
    1. 用户注册 → 密码经 bcrypt 哈希后存入数据库（永不明文存储）
    2. 用户登录 → 验证密码 → 签发 JWT Token（有效期 480 分钟）
    3. 后续请求 → 从 Authorization 头取出 Token → 解码验证 → 获取当前用户
    4. 权限检查 → 检查用户角色是否匹配（超级管理员直接放行）

JWT (JSON Web Token) 结构:
    Header.Payload.Signature
    包含用户 ID(sub) 和过期时间(exp)，服务端用密钥签名防止篡改
"""
import os
from datetime import datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User

SECRET_KEY = os.environ.get("SECRET_KEY", "lightpress-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 43200  # Token 有效期 30 天

# passlib 密码上下文：使用 bcrypt 算法，自动处理加盐(salt)和哈希
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# OAuth2 密码流：告诉 FastAPI 从哪个端点获取 Token（Swagger 文档中的锁图标会用到）
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/token")


def hash_password(password: str) -> str:
    """对明文密码进行 bcrypt 哈希（不可逆）"""
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """验证明文密码是否与哈希值匹配"""
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict) -> str:
    """
    创建 JWT Token。
    data 中应包含 {"sub": user_id}，sub 是 JWT 标准字段，代表"主体"。
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    """
    FastAPI 依赖：从请求头中解析 JWT Token，返回当前登录用户。

    验证步骤:
        1. 解码 Token，提取用户 ID
        2. 从数据库查询用户
        3. 检查用户是否存在且未被禁用

    用法：
        @app.get("/me")
        def me(user: User = Depends(get_current_user)):
            return user
    """
    try:
        # 第一步：解码并验证 Token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的 Token"
            )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 已过期"
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的 Token"
        )
    # 第二步：查询用户并检查状态
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已被禁用",
        )
    return user


def require_role(*roles: str):
    """
    FastAPI 依赖工厂：返回一个检查用户角色的依赖函数。

    工作原理（闭包）:
        1. 外层函数接收允许的角色列表（如 "editor", "admin"）
        2. 内层函数 checker 被 FastAPI 调用，接收当前用户
        3. 超级管理员直接放行
        4. 普通用户检查其角色是否在允许列表中

    用法：
        @app.post("/articles/{id}/approve")
        def approve(user: User = Depends(require_role("editor", "admin"))):
            ...
    """
    def checker(current_user: User = Depends(get_current_user)) -> User:
        # 超级管理员拥有所有权限，直接放行
        if current_user.is_superuser:
            return current_user
        # 提取当前用户的所有角色名
        user_role_names = [r.name for r in current_user.roles]
        # 检查是否有交集
        if not any(r in user_role_names for r in roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"需要以下角色之一: {roles}",
            )
        return current_user

    return checker
