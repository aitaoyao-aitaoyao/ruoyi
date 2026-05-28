"""
LightPress CMS 全局测试夹具。

夹具设计说明:
    - engine: 会话级，创建临时 SQLite 数据库文件，测试结束后自动删除
    - app: 会话级，覆盖 FastAPI 的 get_db 依赖，指向测试数据库
    - client: 会话级，基于 app 创建 TestClient，复用 HTTP 连接
    - db_session: 函数级，每个测试用例拥有独立的数据库会话，
      用例结束后通过反向遍历所有表执行 DELETE 来清理数据
    - admin/author/editor_user: 函数级，创建对应角色的测试用户
    - admin/author/editor_headers: 函数级，登录获取 JWT token 组装认证头
    - sample_*: 函数级，创建分类/标签/文章的快捷夹具
"""
import os
import sys
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import Base, get_db
from app.models import User, Article, Category, Tag, Media, Role, Permission
from app.auth import hash_password


@pytest.fixture(scope="session")
def engine():
    """会话级引擎 — 使用临时 SQLite 文件，整个测试会话共享同一个数据库文件。"""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    eng = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=eng)
    yield eng
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture(scope="session")
def app(engine):
    """会话级 FastAPI app — 替换依赖注入，将所有 DB 操作指向测试数据库。"""
    from app.main import app

    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest.fixture(scope="session")
def client(app):
    """会话级 TestClient — 模拟 HTTP 请求，无需真正启动服务器。"""
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="function")
def db_session(engine):
    """函数级数据库会话 — 每个测试用例执行后清空所有表数据，保证测试隔离。

    清理策略：反向遍历 metadata 中已排序的表，执行 DELETE 删除所有行。
    反向遍历确保先删子表再删父表，避免外键约束冲突。
    """
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    cleanup = Session()
    for table in reversed(Base.metadata.sorted_tables):
        cleanup.execute(table.delete())
    cleanup.commit()
    cleanup.close()


@pytest.fixture
def admin_user(db_session):
    """创建管理员用户（超级用户）。"""
    user = User(
        username="admin",
        email="admin@lightpress.com",
        full_name="Admin User",
        hashed_password=hash_password("admin123"),
        is_superuser=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def author_user(db_session):
    """创建作者角色用户，关联 author 角色。"""
    role = db_session.query(Role).filter(Role.name == "author").first()
    if not role:
        role = Role(name="author", description="Author")
        db_session.add(role)
        db_session.commit()
    user = User(
        username="author",
        email="author@lightpress.com",
        full_name="Author User",
        hashed_password=hash_password("author123"),
    )
    user.roles.append(role)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def editor_user(db_session):
    """创建编辑角色用户，关联 editor 角色。"""
    role = db_session.query(Role).filter(Role.name == "editor").first()
    if not role:
        role = Role(name="editor", description="Editor")
        db_session.add(role)
        db_session.commit()
    user = User(
        username="editor",
        email="editor@lightpress.com",
        full_name="Editor User",
        hashed_password=hash_password("editor123"),
    )
    user.roles.append(role)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_headers(client, admin_user):
    """管理员认证头 — 通过 /api/v1/token 登录获取 JWT，组装 Authorization 头。"""
    resp = client.post("/api/v1/token", data={"username": "admin", "password": "admin123"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def author_headers(client, author_user):
    """作者认证头。"""
    resp = client.post("/api/v1/token", data={"username": "author", "password": "author123"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def editor_headers(client, editor_user):
    """编辑认证头。"""
    resp = client.post("/api/v1/token", data={"username": "editor", "password": "editor123"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_category(db_session):
    """创建示例分类。"""
    cat = Category(name="Test Category", slug="test-category", description="A test category")
    db_session.add(cat)
    db_session.commit()
    db_session.refresh(cat)
    return cat


@pytest.fixture
def sample_tag(db_session):
    """创建示例标签。"""
    tag = Tag(name="python", slug="python")
    db_session.add(tag)
    db_session.commit()
    db_session.refresh(tag)
    return tag


@pytest.fixture
def sample_article(db_session, author_user, sample_category, sample_tag):
    """创建示例文章（草稿状态），关联测试分类和标签。"""
    article = Article(
        title="Test Article",
        slug="test-article",
        content="This is a test article.",
        excerpt="Test excerpt",
        status="draft",
        category_id=sample_category.id,
        author_id=author_user.id,
    )
    article.tags.append(sample_tag)
    db_session.add(article)
    db_session.commit()
    db_session.refresh(article)
    return article
