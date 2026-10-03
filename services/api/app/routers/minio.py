from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.providers.object_storage import MinIOImageStorage, PresignedUpload


router = APIRouter(tags=["minio"])


class StandardResponse(BaseModel):
    code: int
    message: str
    data: Any = None


class UploadUrlRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)


def get_storage() -> MinIOImageStorage:
    return MinIOImageStorage(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        bucket_name=settings.minio_bucket_name,
        secure=settings.minio_secure,
        public_url=settings.minio_public_url,
    )


def ok(data: Any) -> StandardResponse:
    return StandardResponse(code=0, message="ok", data=data)


def error_response(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"code": 1, "message": message, "data": None},
    )


def _upload_response(
    body: UploadUrlRequest,
    storage: MinIOImageStorage,
) -> StandardResponse | JSONResponse:
    try:
        result: PresignedUpload = storage.presigned_upload_url(
            body.filename,
            expires_seconds=settings.minio_presigned_expires_seconds,
        )
        return ok({"uploadUrl": result.upload_url, "key": result.key})
    except ValueError as exc:
        return error_response(400, str(exc))
    except Exception as exc:
        return error_response(500, f"MINIO_ERROR:{exc}")


def _url_response(
    key: str,
    storage: MinIOImageStorage,
) -> StandardResponse | JSONResponse:
    try:
        return ok({"url": storage.get_public_url(key)})
    except ValueError as exc:
        return error_response(400, str(exc))
    except Exception as exc:
        return error_response(500, f"MINIO_ERROR:{exc}")


def _delete_response(
    key: str,
    storage: MinIOImageStorage,
) -> StandardResponse | JSONResponse:
    try:
        storage.delete_file(key)
        return ok({"deleted": True})
    except ValueError as exc:
        return error_response(400, str(exc))
    except Exception as exc:
        return error_response(500, f"MINIO_ERROR:{exc}")


@router.post("/api/minio/get-upload-url", response_model=StandardResponse)
@router.post("/api/v1/minio/get-upload-url", response_model=StandardResponse)
def get_upload_url(
    body: UploadUrlRequest,
    storage: MinIOImageStorage = Depends(get_storage),
):
    return _upload_response(body, storage)


@router.get("/api/minio/get-url", response_model=StandardResponse)
@router.get("/api/v1/minio/get-url", response_model=StandardResponse)
def get_url(
    key: str,
    storage: MinIOImageStorage = Depends(get_storage),
):
    return _url_response(key, storage)


@router.delete("/api/minio/delete-img", response_model=StandardResponse)
@router.delete("/api/v1/minio/delete-img", response_model=StandardResponse)
def delete_img(
    key: str,
    storage: MinIOImageStorage = Depends(get_storage),
):
    return _delete_response(key, storage)
