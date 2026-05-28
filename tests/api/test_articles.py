"""
文章接口集成测试 — 文章的增删改查、工作流（提交→审核→发布→归档）。
"""
import pytest


class TestCreateArticle:
    def test_create_draft_as_author(self, client, author_headers):
        resp = client.post(
            "/api/v1/articles",
            json={"title": "My New Article", "content": "Body text"},
            headers=author_headers,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["title"] == "My New Article"
        assert body["status"] == "draft"
        assert body["slug"] == "my-new-article"

    def test_create_article_no_auth(self, client):
        resp = client.post("/api/v1/articles", json={"title": "Test"})
        assert resp.status_code == 401

    def test_create_article_empty_title(self, client, author_headers):
        resp = client.post("/api/v1/articles", json={"title": "   "}, headers=author_headers)
        assert resp.status_code == 422

    def test_create_article_as_admin(self, client, admin_headers):
        resp = client.post(
            "/api/v1/articles",
            json={"title": "Admin Article"},
            headers=admin_headers,
        )
        assert resp.status_code == 201


class TestListArticles:
    def test_list_articles(self, client, author_headers, sample_article):
        resp = client.get("/api/v1/articles", headers=author_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1
        assert len(body["items"]) >= 1
        assert body["page"] == 1

    def test_list_articles_filter_by_status(self, client, author_headers, sample_article):
        resp = client.get("/api/v1/articles?status=draft", headers=author_headers)
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["status"] == "draft"

    def test_list_articles_filter_by_keyword(self, client, author_headers, sample_article):
        resp = client.get("/api/v1/articles?keyword=Test+Article", headers=author_headers)
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    def test_list_articles_pagination(self, client, author_headers):
        resp = client.get("/api/v1/articles?page=1&size=5", headers=author_headers)
        assert resp.status_code == 200
        assert resp.json()["size"] == 5

    def test_list_articles_no_auth(self, client):
        resp = client.get("/api/v1/articles")
        assert resp.status_code == 401


class TestMyArticles:
    def test_my_articles(self, client, author_headers, sample_article):
        resp = client.get("/api/v1/articles/my", headers=author_headers)
        assert resp.status_code == 200
        items = resp.json()["items"]
        author_ids = [a["author_id"] for a in items]
        # All articles should belong to the author
        assert len(set(author_ids)) <= 1


class TestGetArticle:
    def test_get_article(self, client, author_headers, sample_article):
        resp = client.get(f"/api/v1/articles/{sample_article.id}", headers=author_headers)
        assert resp.status_code == 200
        assert resp.json()["title"] == "Test Article"

    def test_get_article_not_found(self, client, author_headers):
        resp = client.get("/api/v1/articles/9999", headers=author_headers)
        assert resp.status_code == 404


class TestUpdateArticle:
    def test_update_own_article(self, client, author_headers, sample_article):
        resp = client.patch(
            f"/api/v1/articles/{sample_article.id}",
            json={"title": "Updated Title"},
            headers=author_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated Title"

    def test_update_others_article(self, client, admin_headers, sample_article):
        resp = client.patch(
            f"/api/v1/articles/{sample_article.id}",
            json={"title": "Hacked"},
            headers=admin_headers,
        )
        assert resp.status_code == 200  # superuser can edit any


class TestDeleteArticle:
    def test_delete_own_article(self, client, author_headers, sample_article):
        resp = client.delete(f"/api/v1/articles/{sample_article.id}", headers=author_headers)
        assert resp.status_code == 204


class TestSubmitArticle:
    def test_submit_draft(self, client, author_headers, sample_article):
        resp = client.post(
            f"/api/v1/articles/{sample_article.id}/submit",
            headers=author_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"

    def test_submit_others_article(self, client, editor_headers, sample_article):
        resp = client.post(
            f"/api/v1/articles/{sample_article.id}/submit",
            headers=editor_headers,
        )
        assert resp.status_code == 403


class TestApproveReject:
    @pytest.fixture
    def pending_article(self, client, author_headers, sample_article):
        client.post(f"/api/v1/articles/{sample_article.id}/submit", headers=author_headers)
        return sample_article

    def test_approve_pending(self, client, editor_headers, pending_article):
        resp = client.post(
            f"/api/v1/articles/{pending_article.id}/approve",
            headers=editor_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "published"

    def test_reject_pending(self, client, editor_headers, pending_article):
        resp = client.post(
            f"/api/v1/articles/{pending_article.id}/reject",
            json={"comment": "Needs revision"},
            headers=editor_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "draft"

    def test_approve_as_author_fails(self, client, author_headers, pending_article):
        resp = client.post(
            f"/api/v1/articles/{pending_article.id}/approve",
            headers=author_headers,
        )
        assert resp.status_code == 403


class TestPublish:
    def test_direct_publish_as_editor(self, client, editor_headers, sample_article):
        resp = client.post(
            f"/api/v1/articles/{sample_article.id}/publish",
            headers=editor_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "published"


class TestArchive:
    def test_archive_as_editor(self, client, editor_headers, sample_article):
        resp = client.post(
            f"/api/v1/articles/{sample_article.id}/archive",
            headers=editor_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "archived"

    def test_archive_as_author_fails(self, client, author_headers, sample_article):
        resp = client.post(
            f"/api/v1/articles/{sample_article.id}/archive",
            headers=author_headers,
        )
        assert resp.status_code == 403


class TestFullWorkflow:
    def test_draft_to_published_flow(
        self, client, author_headers, editor_headers, sample_article
    ):
        # Submit
        r1 = client.post(f"/api/v1/articles/{sample_article.id}/submit", headers=author_headers)
        assert r1.status_code == 200
        assert r1.json()["status"] == "pending"

        # Approve
        r2 = client.post(f"/api/v1/articles/{sample_article.id}/approve", headers=editor_headers)
        assert r2.status_code == 200
        assert r2.json()["status"] == "published"

        # Archive
        r3 = client.post(f"/api/v1/articles/{sample_article.id}/archive", headers=editor_headers)
        assert r3.status_code == 200
        assert r3.json()["status"] == "archived"
