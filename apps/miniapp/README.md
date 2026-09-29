# WeChat Mini Program

Target stack: UniApp + Vue 3 + TypeScript + Pinia.

One Mini Program contains both Customer and Player workspaces.

## Local development

1. Start backend from repository root:

```bash
cp .env.example .env
docker compose up --build
```

2. Install and build the Mini Program:

```bash
cd apps/miniapp
npm install
npm run dev:mp-weixin
```

3. Import `dist/dev/mp-weixin` in WeChat DevTools.

The default API origin is `http://localhost:8000`. Override it with:

```bash
VITE_API_ORIGIN=http://YOUR_HOST:8000 npm run dev:mp-weixin
```

Demo mode auto-discovers seeded Customer / Player identities. No WeChat AppID or payment merchant account is required for the Golden Slice.

## Demo flow

```text
Customer: Home -> Game -> Create -> Mock Pay
Player: Workbench -> Order Pool -> Claim -> Start -> Finish
Customer: Order Detail -> Confirm -> Settlement -> Review
```
