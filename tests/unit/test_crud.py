"""
CRUD 操作单元测试 — 覆盖所有实体类型的增删改查和业务逻辑。
"""
import pytest
from app import crud
from app import schemas
from app.models import User, Article, Category, Tag


class TestUserCRUD:
    def test_get_user(self, db_session, admin_user):
        user = crud.get_user(db_session, admin_user.id)
        assert user is not None
        assert user.username == "admin"

    def test_get_user_not_found(self, db_session):
        user = crud.get_user(db_session, 9999)
        assert user is None

    def test_get_user_by_username(self, db_session, admin_user):
        user = crud.get_user_by_username(db_session, "admin")
        assert user is not None
        assert user.email == "admin@lightpress.com"

    def test_get_users_pagination(self, db_session):
        for i in range(5):
            db_session.add(User(username=f"u{i}", email=f"u{i}@t.com", hashed_password="x"))
        db_session.commit()
        users = crud.get_users(db_session, skip=0, limit=3)
        assert len(users) == 3

    def test_count_users(self, db_session, admin_user):
        count = crud.count_users(db_session)
        assert count >= 1

    def test_create_user(self, db_session):
        user_in = schemas.UserCreate(
            username="newuser", email="new@test.com", password="pass123", full_name="New"
        )
        user = crud.create_user(db_session, user_in)
        assert user.id is not None
        assert user.username == "newuser"
        assert user.hashed_password != "pass123"


class TestArticleCRUD:
    def test_create_article(self, db_session, author_user, sample_category):
        article_in = schemas.ArticleCreate(
            title="New Article", content="Content", category_id=sample_category.id
        )
        article = crud.create_article(db_session, article_in, author_user.id)
        assert article.id is not None
        assert article.status == "draft"
        assert article.slug == "new-article"

    def test_create_article_duplicate_slug(self, db_session, author_user):
        a1 = Article(title="Same Title", slug="same-title", author_id=author_user.id)
        db_session.add(a1)
        db_session.commit()

        article_in = schemas.ArticleCreate(title="Same Title")
        a2 = crud.create_article(db_session, article_in, author_user.id)
        assert a2.slug == "same-title-1"

    def test_get_article(self, db_session, sample_article):
        article = crud.get_article(db_session, sample_article.id)
        assert article is not None
        assert article.title == "Test Article"

    def test_get_article_not_found(self, db_session):
        article = crud.get_article(db_session, 9999)
        assert article is None

    def test_get_articles_filter_by_status(self, db_session, author_user):
        a1 = Article(title="Draft 1", slug="draft-1", status="draft", author_id=author_user.id)
        a2 = Article(title="Published", slug="published", status="published", author_id=author_user.id)
        db_session.add_all([a1, a2])
        db_session.commit()

        drafts = crud.get_articles(db_session, status="draft")
        assert all(a.status == "draft" for a in drafts)

    def test_get_articles_filter_by_category(self, db_session, sample_category, author_user):
        a1 = Article(title="Cat", slug="cat", category_id=sample_category.id, author_id=author_user.id)
        db_session.add(a1)
        db_session.commit()

        results = crud.get_articles(db_session, category_id=sample_category.id)
        assert len(results) >= 1

    def test_get_articles_filter_by_keyword(self, db_session, author_user):
        a1 = Article(title="UniqueKeyword Article", slug="uk", content="Some content", author_id=author_user.id)
        db_session.add(a1)
        db_session.commit()

        results = crud.get_articles(db_session, keyword="UniqueKeyword")
        assert len(results) >= 1

    def test_get_articles_by_author(self, db_session, author_user, admin_user):
        a1 = Article(title="Author's", slug="authors", author_id=author_user.id)
        db_session.add(a1)
        db_session.commit()

        results = crud.get_articles(db_session, author_id=author_user.id)
        assert all(a.author_id == author_user.id for a in results)

    def test_update_article(self, db_session, sample_article):
        update_in = schemas.ArticleUpdate(title="Updated Title", content="New content")
        article = crud.update_article(db_session, sample_article, update_in)
        assert article.title == "Updated Title"
        assert article.content == "New content"

    def test_update_article_tags(self, db_session, sample_article, sample_tag):
        tag2 = Tag(name="docker", slug="docker")
        db_session.add(tag2)
        db_session.commit()

        update_in = schemas.ArticleUpdate(tag_ids=[sample_tag.id, tag2.id])
        article = crud.update_article(db_session, sample_article, update_in)
        assert len(article.tags) == 2

    def test_delete_article(self, db_session, sample_article):
        aid = sample_article.id
        crud.delete_article(db_session, sample_article)
        assert crud.get_article(db_session, aid) is None

    def test_submit_article(self, db_session, sample_article):
        article = crud.submit_article(db_session, sample_article)
        assert article.status == "pending"

    def test_approve_article(self, db_session, sample_article):
        sample_article.status = "pending"
        db_session.commit()
        article = crud.approve_article(db_session, sample_article, 1)
        assert article.status == "published"
        assert article.published_at is not None

    def test_reject_article(self, db_session, sample_article):
        sample_article.status = "pending"
        db_session.commit()
        article = crud.reject_article(db_session, sample_article, 1, "Needs work")
        assert article.status == "draft"
        assert article.review_comment == "Needs work"

    def test_publish_article(self, db_session, sample_article):
        article = crud.publish_article(db_session, sample_article)
        assert article.status == "published"

    def test_archive_article(self, db_session, sample_article):
        article = crud.archive_article(db_session, sample_article)
        assert article.status == "archived"


class TestCategoryCRUD:
    def test_create_category(self, db_session):
        cat_in = schemas.CategoryCreate(name="Python")
        cat = crud.create_category(db_session, cat_in)
        assert cat.id is not None
        assert cat.slug == "python"

    def test_get_categories(self, db_session):
        for name in ["A", "B", "C"]:
            db_session.add(Category(name=name, slug=name.lower()))
        db_session.commit()
        cats = crud.get_categories(db_session)
        assert len(cats) >= 3

    def test_get_category(self, db_session, sample_category):
        cat = crud.get_category(db_session, sample_category.id)
        assert cat is not None
        assert cat.name == "Test Category"

    def test_delete_category(self, db_session, sample_category):
        cid = sample_category.id
        crud.delete_category(db_session, sample_category)
        assert crud.get_category(db_session, cid) is None


class TestTagCRUD:
    def test_create_tag(self, db_session):
        tag_in = schemas.TagCreate(name="Python")
        tag = crud.create_tag(db_session, tag_in)
        assert tag.id is not None
        assert tag.slug == "python"

    def test_get_tags(self, db_session):
        for name in ["X", "Y"]:
            db_session.add(Tag(name=name, slug=name.lower()))
        db_session.commit()
        tags = crud.get_tags(db_session)
        assert len(tags) >= 2

    def test_get_tag(self, db_session, sample_tag):
        tag = crud.get_tag(db_session, sample_tag.id)
        assert tag is not None
        assert tag.name == "python"

    def test_delete_tag(self, db_session, sample_tag):
        tid = sample_tag.id
        crud.delete_tag(db_session, sample_tag)
        assert crud.get_tag(db_session, tid) is None


class TestDashboard:
    def test_get_dashboard_stats(self, db_session, author_user, sample_article):
        stats = crud.get_dashboard_stats(db_session)
        assert stats["total_articles"] >= 1
        assert "published_articles" in stats
        assert "total_users" in stats

    def test_get_recent_articles(self, db_session, sample_article):
        recent = crud.get_recent_articles(db_session, limit=5)
        assert len(recent) >= 1
        assert recent[0].id == sample_article.id
