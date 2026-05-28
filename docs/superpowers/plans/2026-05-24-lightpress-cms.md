# LightPress CMS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build LightPress CMS — a professional-feeling content management platform for testing practice, with FastAPI backend, Vue 3 SPA frontend, and comprehensive pytest/Selenium test suites.

**Architecture:** FastAPI + SQLite backend with JWT auth, 38 REST endpoints across 7 route modules, Vue 3 + Tailwind CDN SPA frontend with hash routing. All tests use pytest with session-scoped temp DB fixtures.

**Tech Stack:** FastAPI 0.95, SQLAlchemy 2.0, PyJWT 2.8, Pydantic 2.x, SQLite, Vue 3 (CDN), Tailwind CSS (CDN), pytest, httpx, Selenium

---

### Task 0: Clear old code and set up new project skeleton

**Files:**
- Remove: all old `app/` contents except `.venv/`
- Create: directory structure for `app/api/v1/`, `app/static/`, `tests/unit/`, `tests/api/`, `tests/selenium/`
- Modify: `requirements.txt`

- [ ] **Step 1: Delete old app code but preserve structure**

```bash
rm -rf app/api app/crud.py app/models.py app/schemas.py app/static
mkdir -p app/api/v1 app/static tests/unit tests/api tests/selenium uploads
touch app/__init__.py app/api/__init__.py app/api/v1/__init__.py
touch tests/__init__.py tests/unit/__init__.py tests/api/__init__.py
```

- [ ] **Step 2: Update requirements.txt**

```
fastapi>=0.100.0
uvicorn[standard]>=0.22.0
sqlalchemy>=2.0.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
pyjwt>=2.8.0
passlib[bcrypt]>=1.7.4
python-multipart>=0.0.6
pytest>=8.0.0
pytest-cov>=4.1.0
httpx>=0.27.0
selenium>=4.12.0
```

```bash
source .venv/bin/activate && pip install -r requirements.txt
```

- [ ] **Step 3: Write db.py**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

SQLALCHEMY_DATABASE_URL = "sqlite:///./app.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 4: Write minimal main.py**

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from app.db import engine, Base
from app.api.v1 import auth, articles, categories, tags, media, users, dashboard

Base.metadata.create_all(bind=engine)

app = FastAPI(title="LightPress CMS", description="Content Management Platform for Testing Practice", version="1.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(auth.router, prefix="/api/v1")
app.include_router(articles.router, prefix="/api/v1")
app.include_router(categories.router, prefix="/api/v1")
app.include_router(tags.router, prefix="/api/v1")
app.include_router(media.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")

BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

@app.get("/")
def root():
    return {"message": "LightPress CMS API", "docs": "/docs", "frontend": "/static/index.html"}
```

- [ ] **Step 5: Verify skeleton works**

```bash
source .venv/bin/activate && python -c "from app.main import app; print('OK')"
# Expected: OK (may create empty app.db)
```

---

### Task 1: Models (all 7 SQLAlchemy models)

**File:** Create `app/models.py`

- [ ] **Step 1: Write all models**

```python
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
from app.db import Base

article_tags = Table(
    "article_tags", Base.metadata,
    Column("article_id", ForeignKey("articles.id"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id"), primary_key=True),
)

user_roles = Table(
    "user_roles", Base.metadata,
    Column("user_id", ForeignKey("users.id"), primary_key=True),
    Column("role_id", ForeignKey("roles.id"), primary_key=True),
)

role_permissions = Table(
    "role_permissions", Base.metadata,
    Column("role_id", ForeignKey("roles.id"), primary_key=True),
    Column("permission_id", ForeignKey("permissions.id"), primary_key=True),
)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    full_name = Column(String(100), default="")
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    articles = relationship("Article", back_populates="author")
    media = relationship("Media", back_populates="uploader")
    roles = relationship("Role", secondary=user_roles, back_populates="users")

class Article(Base):
    __tablename__ = "articles"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), index=True, nullable=False)
    slug = Column(String(200), index=True)
    content = Column(Text, default="")
    excerpt = Column(String(300), default="")
    status = Column(String(20), default="draft", index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    review_comment = Column(Text, default="")
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    author = relationship("User", foreign_keys=[author_id], back_populates="articles")
    category = relationship("Category", back_populates="articles")
    tags = relationship("Tag", secondary=article_tags, back_populates="articles")

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    slug = Column(String(50), unique=True)
    description = Column(String(200), default="")

    articles = relationship("Article", back_populates="category")

class Tag(Base):
    __tablename__ = "tags"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(30), unique=True, nullable=False)
    slug = Column(String(30), unique=True)

    articles = relationship("Article", secondary=article_tags, back_populates="tags")

class Media(Base):
    __tablename__ = "media"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    original_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer, default=0)
    mime_type = Column(String(100))
    uploader_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    uploader = relationship("User", back_populates="media")

class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(30), unique=True, nullable=False)
    description = Column(String(100), default="")

    permissions = relationship("Permission", secondary=role_permissions, back_populates="roles")
    users = relationship("User", secondary=user_roles, back_populates="roles")

class Permission(Base):
    __tablename__ = "permissions"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    description = Column(String(100), default="")

    roles = relationship("Role", secondary=role_permissions, back_populates="permissions")
```

- [ ] **Step 2: Verify models create tables**

```bash
source .venv/bin/activate && python -c "
from app.db import engine, Base
from app.models import User, Article, Category, Tag, Media, Role, Permission
Base.metadata.create_all(bind=engine)
print('Tables created OK')
"
```

- [ ] **Step 3: Commit**

```bash
git add app/models.py app/db.py app/main.py
git commit -m "feat: add database models and app skeleton"
```

---

### Task 2: JWT Auth module

**Files:**
- Create: `app/auth.py`
- Create: `app/api/v1/auth.py`

- [ ] **Step 1: Write JWT auth core**

```python
# app/auth.py
from datetime import datetime, timedelta
from passlib.context import CryptContext
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import User

SECRET_KEY = "lightpress-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/token")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user

def require_role(*roles: str):
    def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.is_superuser:
            return current_user
        user_role_names = [r.name for r in current_user.roles]
        if not any(r in user_role_names for r in roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Requires one of: {roles}")
        return current_user
    return checker
```

- [ ] **Step 2: Write schemas for auth**

Append to `app/schemas.py`:

```python
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenRefresh(BaseModel):
    access_token: str

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    full_name: str = ""
    password: str

    @field_validator("username")
    @classmethod
    def username_min_length(cls, v):
        if len(v.strip()) < 2:
            raise ValueError("Username must be at least 2 characters")
        return v.strip()

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v):
        if len(v) < 4:
            raise ValueError("Password must be at least 4 characters")
        return v

class UserRead(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    is_active: bool
    is_superuser: bool
    created_at: datetime

    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    password: Optional[str] = None

class PasswordChange(BaseModel):
    old_password: str
    new_password: str
```

- [ ] **Step 3: Write auth router**

```python
# app/api/v1/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import User
from app import schemas
from app.auth import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter(tags=["auth"])

@router.post("/register", response_model=schemas.UserRead, status_code=201)
def register(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == user_in.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")
    if db.query(User).filter(User.email == user_in.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(username=user_in.username, email=user_in.email,
                full_name=user_in.full_name, hashed_password=hash_password(user_in.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@router.post("/token", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account disabled")
    token = create_access_token({"sub": str(user.id)})
    return {"access_token": token, "token_type": "bearer"}

@router.get("/me", response_model=schemas.UserRead)
def read_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.patch("/me", response_model=schemas.UserRead)
def update_me(update: schemas.UserUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if update.email is not None:
        current_user.email = update.email
    if update.full_name is not None:
        current_user.full_name = update.full_name
    if update.password is not None:
        current_user.hashed_password = hash_password(update.password)
    db.commit()
    db.refresh(current_user)
    return current_user

@router.patch("/me/password")
def change_password(pw: schemas.PasswordChange, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(pw.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    current_user.hashed_password = hash_password(pw.new_password)
    db.commit()
    return {"message": "Password changed"}

@router.post("/refresh", response_model=schemas.Token)
def refresh_token(current_user: User = Depends(get_current_user)):
    token = create_access_token({"sub": str(current_user.id)})
    return {"access_token": token, "token_type": "bearer"}
```

- [ ] **Step 4: Verify auth endpoints**

```bash
source .venv/bin/activate && python -c "from app.main import app; from app.api.v1 import auth; print('Auth module loads OK')"
```

- [ ] **Step 5: Commit**

```bash
git add app/auth.py app/schemas.py app/api/v1/auth.py
git commit -m "feat: add JWT auth module with register/login/me/password/refresh"
```

---

### Task 3: Article schemas + CRUD + router

**Files:**
- Modify: `app/schemas.py`
- Create: `app/crud.py`
- Create: `app/api/v1/articles.py`

- [ ] **Step 1: Add article schemas to schemas.py**

```python
class CategoryBase(BaseModel):
    name: str
    description: str = ""

class CategoryCreate(CategoryBase):
    pass

class CategoryRead(CategoryBase):
    id: int
    slug: str

    class Config:
        from_attributes = True

class TagBase(BaseModel):
    name: str

class TagCreate(TagBase):
    pass

class TagRead(TagBase):
    id: int
    slug: str
    article_count: int = 0

    class Config:
        from_attributes = True

class ArticleBase(BaseModel):
    title: str
    content: str = ""
    excerpt: str = ""
    category_id: Optional[int] = None

class ArticleCreate(ArticleBase):
    tag_ids: list[int] = []

class ArticleUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    excerpt: Optional[str] = None
    category_id: Optional[int] = None
    tag_ids: Optional[list[int]] = None

class ArticleRead(ArticleBase):
    id: int
    slug: str
    status: str
    author_id: int
    author_name: str = ""
    category_name: str = ""
    tags: list[TagRead] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ArticleListResponse(BaseModel):
    items: list[ArticleRead]
    total: int
    page: int
    size: int
```

- [ ] **Step 2: Write CRUD operations**


- [ ] **Step 3: Write articles router with all 11 endpoints**

- [ ] **Step 4: Verify and commit**

---

### Task 4: Categories + Tags + Media + Users + Dashboard routers

**Files:**
- Create: `app/api/v1/categories.py`
- Create: `app/api/v1/tags.py`
- Create: `app/api/v1/media.py`
- Create: `app/api/v1/users.py`
- Create: `app/api/v1/dashboard.py`

(All routers follow same pattern: thin route handlers calling CRUD functions)

- [ ] **Step 1: Write categories router (GET list, POST create, DELETE)**
- [ ] **Step 2: Write tags router (GET list w/ article_count, POST create, DELETE)**
- [ ] **Step 3: Write media router (POST upload, GET list, GET file, DELETE)**
- [ ] **Step 4: Write users router (GET list, POST create, PATCH update, DELETE deactivate, GET user articles) — admin only**
- [ ] **Step 5: Write dashboard router (GET stats, GET recent)**
- [ ] **Step 6: Commit**

---

### Task 5: Test conftest + Unit tests

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/unit/test_models.py`
- Create: `tests/unit/test_schemas.py`
- Create: `tests/unit/test_crud.py`

- [ ] **Step 1: Write conftest.py with session-scoped temp DB + auth fixtures + seed helpers**
- [ ] **Step 2: Write test_models.py (~12 tests)**
- [ ] **Step 3: Write test_schemas.py (~18 tests)**
- [ ] **Step 4: Write test_crud.py (~25 tests)**
- [ ] **Step 5: Run unit tests and fix until all pass**
- [ ] **Step 6: Commit**

---

### Task 6: API integration tests

**Files:**
- Create: `tests/api/test_auth.py`
- Create: `tests/api/test_articles.py`
- Create: `tests/api/test_categories.py`
- Create: `tests/api/test_tags.py`
- Create: `tests/api/test_media.py`
- Create: `tests/api/test_users.py`

- [ ] **Step 1: Write test_auth.py (~15 tests: register success/fail, login success/fail, me, password change, refresh, 401 scenarios)**
- [ ] **Step 2: Write test_articles.py (~30 tests: CRUD, 5 status transitions, filter/search/pagination, edge cases, authorization)**
- [ ] **Step 3: Write test_categories.py (~8 tests)**
- [ ] **Step 4: Write test_tags.py (~8 tests)**
- [ ] **Step 5: Write test_media.py (~10 tests: upload/download/delete, file types, size limits)**
- [ ] **Step 6: Write test_users.py (~12 tests: admin CRUD, role assignment, permission checks)**
- [ ] **Step 7: Run API tests and fix until all pass**
- [ ] **Step 8: Commit**

---

### Task 7: Vue 3 SPA Frontend

**Files:**
- Create: `app/static/index.html`
- Create: `app/static/app.js`

The frontend is a single Vue 3 SPA using CDN (no build tools). All components inline in app.js.

- [ ] **Step 1: Write index.html with Tailwind CDN + Vue 3 CDN + app.js script**

```html
<!DOCTYPE html>
<html lang="zh-CN" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>LightPress CMS</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script>tailwind.config={darkMode:'class',theme:{extend:{}}}</script>
  <script src="https://unpkg.com/vue@3/dist/vue.global.prod.js"></script>
  <script src="/static/app.js" defer></script>
</head>
<body class="bg-slate-900 text-slate-100 min-h-screen">
  <div id="app"></div>
</body>
</html>
```

- [ ] **Step 2: Write app.js — Vue app structure**

Key sections:
- Vue Router (hash mode): `/login`, `/dashboard`, `/articles`, `/media`, `/categories`, `/tags`, `/users`
- API helper with JWT interceptor
- Components: LoginForm, Dashboard, ArticleList, ArticleEditor, MediaLibrary, CategoryManager, TagManager, UserManager, SidebarLayout
- Auth store (localStorage token)

- [ ] **Step 3: Verify frontend loads**

```bash
source .venv/bin/activate && python -m uvicorn app.main:app &
curl -s http://127.0.0.1:8000/static/index.html | head -5
# Expected: HTML content
kill %1
```

- [ ] **Step 4: Commit**

---

### Task 8: Seed data + Selenium tests + README

**Files:**
- Create: `seed_data.py`
- Create: `tests/selenium/test_login_ui.py`
- Create: `tests/selenium/test_article_ui.py`
- Modify: `README.md`

- [ ] **Step 1: Write seed_data.py** — creates 3 roles (author/editor/admin), 5 users, 5 categories, 8 tags, 50 articles across 4 statuses, 20 media entries
- [ ] **Step 2: Write Selenium login tests (~5 tests)**
- [ ] **Step 3: Write Selenium article UI tests (~8 tests)**
- [ ] **Step 4: Write README.md with architecture docs, quickstart, test guide, API overview**
- [ ] **Step 5: Final verification — run all tests**

```bash
pytest -v --tb=short
# Target: 100+ tests pass, 0 fail
```

- [ ] **Step 6: Commit final delivery**

---

### Task 9: Verification checklist

- [ ] `python -m uvicorn app.main:app --reload` starts without errors
- [ ] `curl http://127.0.0.1:8000/docs` returns Swagger UI
- [ ] `curl http://127.0.0.1:8000/api/v1/token -X POST -d 'username=demo&password=demo123'` returns JWT
- [ ] Vue SPA loads at `/static/index.html` and displays login page
- [ ] `python seed_data.py` generates 50+ articles
- [ ] `pytest tests/unit -v` all pass
- [ ] `pytest tests/api -v` all pass
- [ ] `pytest tests/selenium -v -m selenium` (with Chrome) all pass
- [ ] `pytest --cov=app --cov-report=term-missing` shows >80% coverage
