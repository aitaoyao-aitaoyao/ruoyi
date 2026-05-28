"""
分类接口集成测试 — 分类的列表、创建、删除及权限校验。
"""
import pytest


class TestListCategories:
    def test_list_empty(self, client):
        resp = client.get("/api/v1/categories")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_with_data(self, client, sample_category):
        resp = client.get("/api/v1/categories")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


class TestCreateCategory:
    def test_create_as_editor(self, client, editor_headers):
        resp = client.post(
            "/api/v1/categories",
            json={"name": "Python", "description": "Python articles"},
            headers=editor_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "Python"

    def test_create_as_author_fails(self, client, author_headers):
        resp = client.post(
            "/api/v1/categories",
            json={"name": "Hack"},
            headers=author_headers,
        )
        assert resp.status_code == 403

    def test_create_no_auth(self, client):
        resp = client.post("/api/v1/categories", json={"name": "Test"})
        assert resp.status_code == 401


class TestDeleteCategory:
    def test_delete_as_admin(self, client, admin_headers, sample_category):
        resp = client.delete(f"/api/v1/categories/{sample_category.id}", headers=admin_headers)
        assert resp.status_code == 204

    def test_delete_as_editor_fails(self, client, editor_headers, sample_category):
        resp = client.delete(f"/api/v1/categories/{sample_category.id}", headers=editor_headers)
        assert resp.status_code == 403

    def test_delete_not_found(self, client, admin_headers):
        resp = client.delete("/api/v1/categories/9999", headers=admin_headers)
        assert resp.status_code == 404
