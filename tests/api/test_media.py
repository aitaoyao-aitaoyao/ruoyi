"""
媒体接口集成测试 — 文件上传/下载/列表/删除及权限校验。
"""
import io
import pytest


class TestUploadMedia:
    def test_upload_text_file(self, client, author_headers):
        content = b"Hello, this is a test file."
        resp = client.post(
            "/api/v1/media/upload",
            files={"file": ("test.txt", io.BytesIO(content), "text/plain")},
            headers=author_headers,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["original_name"] == "test.txt"
        assert body["mime_type"] == "text/plain"
        assert body["file_size"] == len(content)

    def test_upload_image(self, client, author_headers):
        content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        resp = client.post(
            "/api/v1/media/upload",
            files={"file": ("photo.png", io.BytesIO(content), "image/png")},
            headers=author_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["mime_type"] == "image/png"

    def test_upload_no_auth(self, client):
        resp = client.post(
            "/api/v1/media/upload",
            files={"file": ("test.txt", io.BytesIO(b"x"), "text/plain")},
        )
        assert resp.status_code == 401

    def test_upload_disallowed_type(self, client, author_headers):
        resp = client.post(
            "/api/v1/media/upload",
            files={"file": ("script.exe", io.BytesIO(b"x"), "application/x-msdownload")},
            headers=author_headers,
        )
        assert resp.status_code == 400


class TestListMedia:
    def test_list_media(self, client, author_headers, sample_article):
        resp = client.get("/api/v1/media", headers=author_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        assert "total" in body
        assert "page" in body


class TestGetMedia:
    def test_get_media_not_found(self, client):
        resp = client.get("/api/v1/media/9999")
        assert resp.status_code == 404


class TestDeleteMedia:
    def test_delete_media_not_found(self, client, author_headers):
        resp = client.delete("/api/v1/media/9999", headers=author_headers)
        assert resp.status_code == 404
