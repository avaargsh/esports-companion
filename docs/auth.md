# Production Authentication and Sessions

The production identity chain is:

```text
WeChat wx.login()
  -> login code
  -> WeChatAuthProvider / code2Session
  -> external openid / unionid
  -> internal User
  -> durable AuthSession
  -> short-lived Access JWT
  -> rotating opaque Refresh Token
```

## Token model

Access token:

- JWT / HS256
- default TTL: 15 minutes
- contains internal `user_id` and `session_id`
- authorization does not trust embedded roles as the final source of truth

Refresh token:

- cryptographically random opaque token
- default TTL: 30 days
- only SHA-256 hash is stored in PostgreSQL
- rotates on every refresh
- the previous session is revoked immediately

## Session revocation

Every authenticated API request validates both:

1. the JWT signature/expiry;
2. the referenced PostgreSQL `auth_sessions` row.

Therefore logout or refresh rotation immediately invalidates the old access token,
even if its JWT expiry time has not yet passed.

## Roles

The effective role set is recalculated from current durable state on each request:

```text
USER
  every ACTIVE user

PLAYER
  ACTIVE user + APPROVED PlayerProfile

PLATFORM
  ACTIVE user with users.role PLATFORM/ADMIN
```

This means player approval/rejection and platform privilege removal take effect
without waiting for token refresh.

## API

```http
POST /api/v1/auth/wechat/login
POST /api/v1/auth/refresh
POST /api/v1/auth/logout
GET  /api/v1/auth/me
```

Production clients use:

```http
Authorization: Bearer <access-token>
```

Legacy development headers:

```text
X-User-Id
X-Admin-Id
```

remain available only when `APP_ENV` is not `production`. They are rejected
in production.

## Required production settings

```text
APP_ENV=production
SESSION_SIGNING_KEY=<at least 32 random characters>
ACCESS_TOKEN_TTL_SECONDS=900
REFRESH_TOKEN_TTL_SECONDS=2592000
AUTH_PROVIDER=wechat
```

The default development signing key is deliberately rejected in production.
