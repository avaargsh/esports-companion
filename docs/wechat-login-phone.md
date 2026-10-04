# WeChat Login and Phone Binding

This project supports WeChat Mini Program one-tap login and encrypted phone number binding through FastAPI.

## Backend Endpoints

### Login

```http
POST /api/user/wx-login
Content-Type: application/json

{"code":"wx.login code"}
```

The backend calls `https://api.weixin.qq.com/sns/jscode2session` with `requests`, creates a `users` row when the `openid` is new, creates an `auth_sessions` row, stores the WeChat `session_key` on that session, and returns a JWT access token.

### Bind Phone

```http
POST /api/user/bind-phone
Authorization: Bearer <access token>
Content-Type: application/json

{"encryptedData":"...","iv":"..."}
```

The backend loads the current `auth_sessions.provider_session_key`, decrypts the phone payload with AES-CBC through `pycryptodome`, validates the WeChat watermark AppID when configured, and writes `users.phone`.

Both endpoints return:

```json
{"code":0,"message":"ok","data":{}}
```

Errors return:

```json
{"code":1,"message":"ERROR_CODE","data":null}
```

## Database Design

The project reuses the existing user/session tables instead of creating a second account system.

```sql
CREATE TABLE users (
  id UUID PRIMARY KEY,
  openid VARCHAR(128) UNIQUE,
  unionid VARCHAR(128),
  nickname VARCHAR(80) NOT NULL DEFAULT '',
  avatar_url VARCHAR(512),
  phone VARCHAR(32),
  role VARCHAR(32) NOT NULL DEFAULT 'USER',
  status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE auth_sessions (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  refresh_token_hash VARCHAR(64) UNIQUE NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  revoked_at TIMESTAMPTZ,
  rotated_from_id UUID REFERENCES auth_sessions(id),
  provider VARCHAR(32) NOT NULL,
  provider_session_key VARCHAR(256),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_used_at TIMESTAMPTZ
);
```

`provider_session_key` is session-scoped. It is used only to decrypt the phone binding payload for the current login session.

## Environment

Configure the backend `.env`:

```env
WECHAT_APP_ID=your-mini-program-appid
WECHAT_APP_SECRET=your-mini-program-appsecret
SESSION_SIGNING_KEY=replace-with-at-least-32-random-bytes
```

In staging/production also set:

```env
AUTH_PROVIDER=wechat
APP_ENV=staging
```

Run migrations after pulling this change:

```bash
docker compose run --rm api alembic upgrade head
docker compose up --build -d api
```

## Mini Program Usage

The profile page provides:

```vue
<button @click="loginWithWeChat">微信一键登录</button>
<button open-type="getPhoneNumber" @getphonenumber="onBindPhone">绑定手机号</button>
```

`wxUserLogin()` calls `uni.login`, posts the code to `/api/user/wx-login`, and stores the returned business token in the existing auth storage. `bindPhoneNumber()` sends `encryptedData` and `iv` with the Bearer token.

## WeChat Console Configuration

- Use the real Mini Program AppID in WeChat Developer Tools.
- Add the API HTTPS host to Mini Program request legal domains.
- For local simulator testing, Developer Tools can disable domain validation; real devices and production require HTTPS legal domains.
- Keep AppSecret only on the backend. Never put AppSecret, session_key, or JWT signing key in Mini Program code.
- The phone binding payload must be decrypted promptly with the session_key from the same wx.login session.
