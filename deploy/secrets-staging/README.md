# Staging secret files

Staging uses the same secret contract as production, but **never reuse
production secret values**.

Create:

```text
postgres_password
session_signing_key
wechat_app_secret
wechat_mch_private_key
wechat_pay_api_v3_key
wechat_platform_certificate
minio_access_key
minio_secret_key
```

Use the dedicated staging Mini Program / merchant configuration where
available. Use separate MinIO keys for staging. Do not copy this directory into images or commit it to Git.

Run `make staging-preflight` before starting the staging stack.
