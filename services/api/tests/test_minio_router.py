from fastapi.testclient import TestClient

from app.main import app
from app.routers import minio as minio_router


class StubStorage:
    def __init__(self):
        self.deleted: list[str] = []

    def presigned_upload_url(self, filename: str, expires_seconds: int):
        assert filename == "avatar.png"
        assert expires_seconds > 0
        return minio_router.PresignedUpload(
            upload_url="http://minio.local/esports-images/images/avatar.png?signature=test",
            key="images/avatar.png",
        )

    def get_public_url(self, key: str) -> str:
        assert key == "images/avatar.png"
        return "http://minio.local/esports-images/images/avatar.png"

    def delete_file(self, key: str) -> None:
        self.deleted.append(key)


class BrokenStorage:
    def presigned_upload_url(self, filename: str, expires_seconds: int):
        raise RuntimeError("storage unavailable")

    def get_public_url(self, key: str) -> str:
        raise RuntimeError("storage unavailable")

    def delete_file(self, key: str) -> None:
        raise RuntimeError("storage unavailable")


def test_get_upload_url_returns_standard_json():
    app.dependency_overrides[minio_router.get_storage] = lambda: StubStorage()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/minio/get-upload-url",
                json={"filename": "avatar.png"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "code": 0,
        "message": "ok",
        "data": {
            "uploadUrl": "http://minio.local/esports-images/images/avatar.png?signature=test",
            "key": "images/avatar.png",
        },
    }


def test_versioned_get_url_returns_standard_json():
    app.dependency_overrides[minio_router.get_storage] = lambda: StubStorage()
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/minio/get-url",
                params={"key": "images/avatar.png"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "code": 0,
        "message": "ok",
        "data": {"url": "http://minio.local/esports-images/images/avatar.png"},
    }


def test_delete_img_returns_standard_json():
    storage = StubStorage()
    app.dependency_overrides[minio_router.get_storage] = lambda: storage
    try:
        with TestClient(app) as client:
            response = client.delete(
                "/api/minio/delete-img",
                params={"key": "images/avatar.png"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "code": 0,
        "message": "ok",
        "data": {"deleted": True},
    }
    assert storage.deleted == ["images/avatar.png"]


def test_storage_errors_return_standard_json():
    app.dependency_overrides[minio_router.get_storage] = lambda: BrokenStorage()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/minio/get-upload-url",
                json={"filename": "avatar.png"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    assert response.json() == {
        "code": 1,
        "message": "MINIO_ERROR:storage unavailable",
        "data": None,
    }
