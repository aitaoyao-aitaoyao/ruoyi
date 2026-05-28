"""
认证接口集成测试 — 注册、登录、个人信息、密码修改、Token 刷新。
"""
import pytest


class TestRegister:
    def test_register_success(self, client, db_session):
        resp = client.post(
            "/api/v1/register",
            json={"username": "newuser", "email": "new@test.com", "password": "pass123", "full_name": "New"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["username"] == "newuser"
        assert body["email"] == "new@test.com"
        assert "password" not in body

    def test_register_duplicate_username(self, client, db_session, admin_user):
        resp = client.post(
            "/api/v1/register",
            json={"username": "admin", "email": "diff@test.com", "password": "pass123"},
        )
        assert resp.status_code == 400

    def test_register_duplicate_email(self, client, db_session, admin_user):
        resp = client.post(
            "/api/v1/register",
            json={"username": "diffuser", "email": "admin@lightpress.com", "password": "pass123"},
        )
        assert resp.status_code == 400

    def test_register_short_username(self, client, db_session):
        resp = client.post(
            "/api/v1/register",
            json={"username": "x", "email": "x@t.com", "password": "pass123"},
        )
        assert resp.status_code == 422

    def test_register_short_password(self, client, db_session):
        resp = client.post(
            "/api/v1/register",
            json={"username": "valid", "email": "v@t.com", "password": "ab"},
        )
        assert resp.status_code == 422

    def test_register_invalid_email(self, client, db_session):
        resp = client.post(
            "/api/v1/register",
            json={"username": "valid", "email": "notanemail", "password": "pass123"},
        )
        assert resp.status_code == 422


class TestLogin:
    def test_login_success(self, client, db_session, admin_user):
        resp = client.post("/api/v1/token", data={"username": "admin", "password": "admin123"})
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"

    def test_login_wrong_password(self, client, db_session, admin_user):
        resp = client.post("/api/v1/token", data={"username": "admin", "password": "wrong"})
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client, db_session):
        resp = client.post("/api/v1/token", data={"username": "nobody", "password": "x"})
        assert resp.status_code == 401


class TestMe:
    def test_get_me(self, client, admin_headers):
        resp = client.get("/api/v1/me", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["username"] == "admin"

    def test_get_me_no_token(self, client):
        resp = client.get("/api/v1/me")
        assert resp.status_code == 401


class TestUpdateMe:
    def test_update_full_name(self, client, admin_headers):
        resp = client.patch("/api/v1/me", json={"full_name": "Updated Admin"}, headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "Updated Admin"


class TestPasswordChange:
    def test_change_password_success(self, client, admin_headers):
        resp = client.patch(
            "/api/v1/me/password",
            json={"old_password": "admin123", "new_password": "newpass123"},
            headers=admin_headers,
        )
        assert resp.status_code == 200

    def test_change_password_wrong_old(self, client, admin_headers):
        resp = client.patch(
            "/api/v1/me/password",
            json={"old_password": "wrongpassword", "new_password": "newpass123"},
            headers=admin_headers,
        )
        assert resp.status_code == 400


class TestRefresh:
    def test_refresh_token(self, client, admin_headers):
        resp = client.post("/api/v1/refresh", headers=admin_headers)
        assert resp.status_code == 200
        assert "access_token" in resp.json()
