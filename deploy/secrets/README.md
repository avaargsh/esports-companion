# Production secret files

This directory is intentionally ignored by Git except for this README.

Create the following files before starting the production Compose stack:

```text
postgres_password
session_signing_key
wechat_app_secret
wechat_mch_private_key
wechat_pay_api_v3_key
wechat_platform_certificate
```

Requirements:

- `postgres_password`: strong PostgreSQL password.
- `session_signing_key`: random secret, at least 32 characters.
- `wechat_app_secret`: Mini Program AppSecret.
- `wechat_mch_private_key`: merchant RSA private key in PEM format.
- `wechat_pay_api_v3_key`: exactly the configured WeChat Pay APIv3 key.
- `wechat_platform_certificate`: WeChat Pay platform certificate PEM matching the serial configured in `.env.production`.

Example:

```bash
openssl rand -hex 32 > deploy/secrets/session_signing_key
```

Do not commit real secret material.
