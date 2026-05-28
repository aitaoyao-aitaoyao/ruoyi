"""
用户管理接口集成测试 — 用户列表、创建、更新、软删除（仅管理员）。
"""
import pytest


class TestListUsers:
    def test_list_as_admin(self, client, admin_headers):
        resp = client.get("/api/v1/users", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_as_author_fails(self, client, author_headers):
        resp = client.get("/api/v1/users", headers=author_headers)
        assert resp.status_code == 403

    def test_list_no_auth(self, client):
        resp = client.get("/api/v1/users")
        assert resp.status_code == 401


class TestCreateUser:
    def test_create_user_as_admin(self, client, admin_headers):
        resp = client.post(
            "/api/v1/users",
            json={
                "username": "createdbyadmin",
                "email": "cba@test.com",
                "full_name": "Created",
                "password": "pass123",
                "role_ids": [],
            },
            headers=admin_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["username"] == "createdbyadmin"

    def test_create_user_as_author_fails(self, client, author_headers):
        resp = client.post(
            "/api/v1/users",
            json={"username": "hack", "email": "h@t.com", "password": "pass123", "role_ids": []},
            headers=author_headers,
        )
        assert resp.status_code == 403

    def test_create_duplicate_username(self, client, admin_headers, admin_user):
        resp = client.post(
            "/api/v1/users",
            json={"username": "admin", "email": "diff@t.com", "password": "pass123", "role_ids": []},
            headers=admin_headers,
        )
        assert resp.status_code == 400


class TestUpdateUser:
    def test_update_user_as_admin(self, client, admin_headers, author_user):
        resp = client.patch(
            f"/api/v1/users/{author_user.id}",
            json={"full_name": "Updated Name"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "Updated Name"

    def test_update_user_not_found(self, client, admin_headers):
        resp = client.patch(
            "/api/v1/users/9999",
            json={"full_name": "X"},
            headers=admin_headers,
        )
        assert resp.status_code == 404


class TestDeleteUser:
    def test_deactivate_user(self, client, admin_headers, author_user):
        resp = client.delete(f"/api/v1/users/{author_user.id}", headers=admin_headers)
        assert resp.status_code == 204


class TestUserArticles:
    def test_user_articles(self, client, author_headers, sample_article):
        resp = client.get(
            f"/api/v1/users/{sample_article.author_id}/articles",
            headers=author_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1
