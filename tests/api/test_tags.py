"""
标签接口集成测试 — 标签的列表、创建、删除及权限校验。
"""
import pytest


class TestListTags:
    def test_list_empty(self, client):
        resp = client.get("/api/v1/tags")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_with_data(self, client, sample_tag):
        resp = client.get("/api/v1/tags")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


class TestCreateTag:
    def test_create_as_author(self, client, author_headers):
        resp = client.post("/api/v1/tags", json={"name": "python"}, headers=author_headers)
        assert resp.status_code == 201
        assert resp.json()["name"] == "python"

    def test_create_no_auth(self, client):
        resp = client.post("/api/v1/tags", json={"name": "test"})
        assert resp.status_code == 401


class TestDeleteTag:
    def test_delete_as_admin(self, client, admin_headers, sample_tag):
        resp = client.delete(f"/api/v1/tags/{sample_tag.id}", headers=admin_headers)
        assert resp.status_code == 204

    def test_delete_as_author_fails(self, client, author_headers, sample_tag):
        resp = client.delete(f"/api/v1/tags/{sample_tag.id}", headers=author_headers)
        assert resp.status_code == 403

    def test_delete_not_found(self, client, admin_headers):
        resp = client.delete("/api/v1/tags/9999", headers=admin_headers)
        assert resp.status_code == 404
