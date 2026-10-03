import json
import re
from io import BytesIO
import uuid
from dataclasses import dataclass
from datetime import timedelta
from pathlib import PurePosixPath
from urllib.parse import quote


_SAFE_FILENAME_RE = re.compile(r"[^a-zA-Z0-9._-]+")
_ALLOWED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".bmp",
    ".svg",
}


@dataclass(frozen=True)
class PresignedUpload:
    upload_url: str
    key: str


class MinIOImageStorage:
    def __init__(
        self,
        *,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket_name: str,
        secure: bool = False,
        public_url: str = "",
        client=None,
    ):
        self.endpoint = endpoint.strip()
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket_name = bucket_name.strip()
        self.secure = secure
        self.public_url = (public_url or self._default_public_url()).rstrip("/")
        self._client = client

    @property
    def client(self):
        if self._client is None:
            from minio import Minio

            self._client = Minio(
                self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure,
            )
        return self._client

    def ensure_bucket(self) -> None:
        if not self.client.bucket_exists(self.bucket_name):
            self.client.make_bucket(self.bucket_name)
        self.set_public_read_policy()

    def set_public_read_policy(self) -> None:
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": ["*"]},
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{self.bucket_name}/*"],
                }
            ],
        }
        self.client.set_bucket_policy(self.bucket_name, json.dumps(policy))

    def presigned_upload_url(
        self,
        filename: str,
        *,
        expires_seconds: int,
    ) -> PresignedUpload:
        self.ensure_bucket()
        key = self._make_object_key(filename)
        upload_url = self.client.presigned_put_object(
            self.bucket_name,
            key,
            expires=timedelta(seconds=expires_seconds),
        )
        return PresignedUpload(upload_url=upload_url, key=key)

    def upload_image_bytes(
        self,
        *,
        filename: str,
        content: bytes,
        content_type: str,
    ) -> str:
        self.ensure_bucket()
        key = self._make_object_key(filename)
        self.client.put_object(
            self.bucket_name,
            key,
            BytesIO(content),
            length=len(content),
            content_type=content_type or "application/octet-stream",
        )
        return key

    def get_public_url(self, key: str) -> str:
        clean_key = self._validate_key(key)
        quoted_key = quote(clean_key, safe="/")
        return f"{self.public_url}/{self.bucket_name}/{quoted_key}"

    def delete_file(self, key: str) -> None:
        clean_key = self._validate_key(key)
        self.client.remove_object(self.bucket_name, clean_key)

    def _default_public_url(self) -> str:
        scheme = "https" if self.secure else "http"
        return f"{scheme}://{self.endpoint}"

    @staticmethod
    def _validate_key(key: str) -> str:
        clean_key = key.strip().lstrip("/")
        if not clean_key or ".." in PurePosixPath(clean_key).parts:
            raise ValueError("INVALID_FILE_KEY")
        return clean_key

    @staticmethod
    def _make_object_key(filename: str) -> str:
        raw_name = filename.strip()
        if not raw_name:
            raise ValueError("FILENAME_REQUIRED")
        safe_name = _SAFE_FILENAME_RE.sub("-", PurePosixPath(raw_name).name)
        suffix = PurePosixPath(safe_name).suffix.lower()
        if suffix not in _ALLOWED_IMAGE_EXTENSIONS:
            raise ValueError("UNSUPPORTED_IMAGE_TYPE")
        stem = PurePosixPath(safe_name).stem[:40].strip(".-_") or "image"
        return f"images/{uuid.uuid4().hex}-{stem}{suffix}"
