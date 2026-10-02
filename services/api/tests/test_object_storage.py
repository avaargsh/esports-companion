from datetime import timedelta

from app.providers.object_storage import MinIOImageStorage


class FakeMinioClient:
    def __init__(self):
        self.bucket_exists_calls: list[str] = []
        self.make_bucket_calls: list[str] = []
        self.policy_calls: list[tuple[str, str]] = []
        self.presigned_calls: list[tuple[str, str, timedelta]] = []
        self.remove_calls: list[tuple[str, str]] = []
        self.existing_buckets: set[str] = set()

    def bucket_exists(self, bucket_name: str) -> bool:
        self.bucket_exists_calls.append(bucket_name)
        return bucket_name in self.existing_buckets

    def make_bucket(self, bucket_name: str) -> None:
        self.make_bucket_calls.append(bucket_name)
        self.existing_buckets.add(bucket_name)

    def set_bucket_policy(self, bucket_name: str, policy: str) -> None:
        self.policy_calls.append((bucket_name, policy))

    def presigned_put_object(
        self,
        bucket_name: str,
        object_name: str,
        expires: timedelta,
    ) -> str:
        self.presigned_calls.append((bucket_name, object_name, expires))
        return f"http://minio.local/{bucket_name}/{object_name}?signature=test"

    def remove_object(self, bucket_name: str, object_name: str) -> None:
        self.remove_calls.append((bucket_name, object_name))


def test_presigned_upload_url_creates_bucket_policy_and_safe_key():
    client = FakeMinioClient()
    storage = MinIOImageStorage(
        endpoint="localhost:9000",
        access_key="minioadmin",
        secret_key="minioadmin",
        bucket_name="images",
        public_url="http://cdn.example.com",
        client=client,
    )

    result = storage.presigned_upload_url("My Avatar.PNG", expires_seconds=600)

    assert result.key.startswith("images/")
    assert result.key.endswith(".png")
    assert " " not in result.key
    assert result.upload_url.endswith("?signature=test")
    assert client.bucket_exists_calls == ["images"]
    assert client.make_bucket_calls == ["images"]
    assert len(client.policy_calls) == 1
    assert '"s3:GetObject"' in client.policy_calls[0][1]
    assert client.presigned_calls[0] == (
        "images",
        result.key,
        timedelta(seconds=600),
    )


def test_public_url_quotes_key_without_changing_slashes():
    storage = MinIOImageStorage(
        endpoint="localhost:9000",
        access_key="minioadmin",
        secret_key="minioadmin",
        bucket_name="images",
        public_url="http://cdn.example.com/assets/",
        client=FakeMinioClient(),
    )

    assert (
        storage.get_public_url("images/user avatar.png")
        == "http://cdn.example.com/assets/images/images/user%20avatar.png"
    )


def test_delete_file_removes_object_from_bucket():
    client = FakeMinioClient()
    storage = MinIOImageStorage(
        endpoint="localhost:9000",
        access_key="minioadmin",
        secret_key="minioadmin",
        bucket_name="images",
        public_url="http://cdn.example.com",
        client=client,
    )

    storage.delete_file("images/avatar.png")

    assert client.remove_calls == [("images", "images/avatar.png")]
