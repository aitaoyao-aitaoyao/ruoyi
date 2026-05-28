"""
SQLAlchemy 模型单元测试 — 测试 ORM 关系映射、字段约束和级联行为。
"""
import pytest
from app.models import User, Article, Category, Tag, Media, Role, Permission
from app.auth import hash_password


class TestUserModel:
    def test_create_user(self, db_session):
        user = User(
            username="test1",
            email="test1@test.com",
            hashed_password=hash_password("pass123"),
        )
        db_session.add(user)
        db_session.commit()
        assert user.id is not None
        assert user.is_active is True
        assert user.is_superuser is False
        assert user.created_at is not None

    def test_user_username_unique(self, db_session):
        user1 = User(username="unique1", email="a@a.com", hashed_password="x")
        user2 = User(username="unique1", email="b@b.com", hashed_password="y")
        db_session.add(user1)
        db_session.commit()
        db_session.add(user2)
        with pytest.raises(Exception):
            db_session.commit()
        db_session.rollback()

    def test_user_email_unique(self, db_session):
        user1 = User(username="u1", email="dup@test.com", hashed_password="x")
        user2 = User(username="u2", email="dup@test.com", hashed_password="y")
        db_session.add(user1)
        db_session.commit()
        db_session.add(user2)
        with pytest.raises(Exception):
            db_session.commit()
        db_session.rollback()


class TestUserArticleRelationship:
    def test_user_has_articles(self, db_session, author_user):
        article = Article(title="A", slug="a", content="Content", author_id=author_user.id)
        db_session.add(article)
        db_session.commit()
        db_session.refresh(author_user)
        assert len(author_user.articles) == 1
        assert author_user.articles[0].title == "A"

    def test_article_belongs_to_author(self, db_session, author_user):
        article = Article(title="B", slug="b", content="Content", author_id=author_user.id)
        db_session.add(article)
        db_session.commit()
        assert article.author.id == author_user.id
        assert article.author.username == "author"


class TestArticleCategoryRelationship:
    def test_category_has_articles(self, db_session, sample_category, author_user):
        a1 = Article(title="A1", slug="a1", category_id=sample_category.id, author_id=author_user.id)
        a2 = Article(title="A2", slug="a2", category_id=sample_category.id, author_id=author_user.id)
        db_session.add_all([a1, a2])
        db_session.commit()
        db_session.refresh(sample_category)
        assert len(sample_category.articles) == 2

    def test_article_without_category(self, db_session, author_user):
        article = Article(title="No Cat", slug="no-cat", author_id=author_user.id)
        db_session.add(article)
        db_session.commit()
        assert article.category is None


class TestArticleTagRelationship:
    def test_article_has_tags(self, db_session, sample_tag, author_user):
        article = Article(title="Tagged", slug="tagged", author_id=author_user.id)
        article.tags.append(sample_tag)
        db_session.add(article)
        db_session.commit()
        assert len(article.tags) == 1
        assert article.tags[0].name == "python"

    def test_article_multiple_tags(self, db_session, author_user):
        tag1 = Tag(name="python", slug="python")
        tag2 = Tag(name="testing", slug="testing")
        db_session.add_all([tag1, tag2])
        db_session.flush()
        article = Article(title="Multi", slug="multi", author_id=author_user.id)
        article.tags.extend([tag1, tag2])
        db_session.add(article)
        db_session.commit()
        assert len(article.tags) == 2


class TestArticleWorkflowStates:
    def test_default_status_is_draft(self, db_session, author_user):
        article = Article(title="Draft", slug="draft", author_id=author_user.id)
        db_session.add(article)
        db_session.commit()
        assert article.status == "draft"

    def test_status_transitions(self, db_session, author_user):
        article = Article(title="Flow", slug="flow", author_id=author_user.id)
        db_session.add(article)
        db_session.commit()

        article.status = "pending"
        db_session.commit()
        assert article.status == "pending"

        article.status = "published"
        db_session.commit()
        assert article.status == "published"

        article.status = "archived"
        db_session.commit()
        assert article.status == "archived"


class TestMediaModel:
    def test_create_media(self, db_session, author_user):
        media = Media(
            filename="abc123.jpg",
            original_name="photo.jpg",
            file_path="/uploads/abc123.jpg",
            file_size=1024,
            mime_type="image/jpeg",
            uploader_id=author_user.id,
        )
        db_session.add(media)
        db_session.commit()
        assert media.id is not None
        assert media.uploader.id == author_user.id


class TestRolePermission:
    def test_role_has_permissions(self, db_session):
        perm = Permission(name="Create Article", code="article:create")
        role = Role(name="author", description="Author")
        role.permissions.append(perm)
        db_session.add_all([perm, role])
        db_session.commit()
        assert len(role.permissions) == 1
        assert role.permissions[0].code == "article:create"

    def test_user_has_roles(self, db_session):
        role = Role(name="editor", description="Editor")
        user = User(username="editor2", email="ed2@test.com", hashed_password="x")
        user.roles.append(role)
        db_session.add_all([role, user])
        db_session.commit()
        assert len(user.roles) == 1
        assert user.roles[0].name == "editor"

    def test_multiple_roles_per_user(self, db_session):
        r1 = Role(name="role1", description="R1")
        r2 = Role(name="role2", description="R2")
        user = User(username="multi", email="multi@test.com", hashed_password="x")
        user.roles.extend([r1, r2])
        db_session.add_all([r1, r2, user])
        db_session.commit()
        assert len(user.roles) == 2
