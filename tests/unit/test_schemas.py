"""
Pydantic 模式校验单元测试 — 测试数据验证规则（字段长度、类型、必填等）。
"""
import pytest
from pydantic import ValidationError
from app import schemas


class TestUserCreateSchema:
    def test_valid_user_create(self):
        user = schemas.UserCreate(
            username="john", email="john@test.com", full_name="John", password="pass1234"
        )
        assert user.username == "john"
        assert user.email == "john@test.com"

    def test_username_too_short(self):
        with pytest.raises(ValidationError) as exc:
            schemas.UserCreate(username="x", email="x@x.com", password="pass123")
        errors = exc.value.errors()
        assert any("用户名至少需要 2 个字符" in str(e["msg"]) for e in errors)

    def test_username_whitespace_stripped(self):
        user = schemas.UserCreate(username="  john  ", email="a@a.com", password="pass123")
        assert user.username == "john"

    def test_password_too_short(self):
        with pytest.raises(ValidationError) as exc:
            schemas.UserCreate(username="john", email="a@a.com", password="ab")
        errors = exc.value.errors()
        assert any("密码至少需要 4 个字符" in str(e["msg"]) for e in errors)

    def test_invalid_email(self):
        with pytest.raises(ValidationError):
            schemas.UserCreate(username="john", email="not-an-email", password="pass123")

    def test_empty_full_name_defaults(self):
        user = schemas.UserCreate(username="john", email="a@a.com", password="pass123")
        assert user.full_name == ""


class TestArticleCreateSchema:
    def test_valid_article_create(self):
        article = schemas.ArticleCreate(
            title="Hello World", content="Content here", excerpt="Summary"
        )
        assert article.title == "Hello World"
        assert article.tag_ids == []

    def test_title_empty(self):
        with pytest.raises(ValidationError) as exc:
            schemas.ArticleCreate(title="   ", content="x")
        errors = exc.value.errors()
        assert any("标题不能为空" in str(e["msg"]) for e in errors)

    def test_default_values(self):
        article = schemas.ArticleCreate(title="Test")
        assert article.content == ""
        assert article.excerpt == ""
        assert article.category_id is None
        assert article.tag_ids == []

    def test_with_category_and_tags(self):
        article = schemas.ArticleCreate(title="Test", category_id=3, tag_ids=[1, 2, 3])
        assert article.category_id == 3
        assert article.tag_ids == [1, 2, 3]


class TestArticleUpdateSchema:
    def test_partial_update(self):
        update = schemas.ArticleUpdate(title="New Title")
        assert update.title == "New Title"
        assert update.content is None
        assert update.category_id is None

    def test_empty_update(self):
        update = schemas.ArticleUpdate()
        assert update.title is None
        assert update.tag_ids is None

    def test_update_tags(self):
        update = schemas.ArticleUpdate(tag_ids=[1, 2])
        assert update.tag_ids == [1, 2]


class TestPasswordChangeSchema:
    def test_valid_password_change(self):
        pw = schemas.PasswordChange(old_password="old", new_password="new123")
        assert pw.old_password == "old"
        assert pw.new_password == "new123"


class TestCategorySchema:
    def test_valid_category(self):
        cat = schemas.CategoryCreate(name="Python", description="Python articles")
        assert cat.name == "Python"


class TestTagSchema:
    def test_valid_tag(self):
        tag = schemas.TagCreate(name="python")
        assert tag.name == "python"


class TestDashboardStats:
    def test_dashboard_stats(self):
        stats = schemas.DashboardStats(
            total_articles=10,
            published_articles=5,
            pending_articles=2,
            draft_articles=3,
            total_users=4,
            total_categories=3,
            total_tags=6,
            total_media=0,
        )
        assert stats.total_articles == 10


class TestArticleListResponse:
    def test_paginated_response(self):
        resp = schemas.ArticleListResponse(items=[], total=0, page=1, size=20)
        assert resp.total == 0
        assert resp.page == 1
