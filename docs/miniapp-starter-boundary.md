# Mini Program Starter Boundary

The Mini Program is intentionally split into a reusable **starter/platform layer** and the esports-companion **reference product layer**.

The goal is not to turn the whole application into a framework. Only capabilities that survive a domain change belong in the starter layer.

## Dependency direction

```text
Product pages / domain adapters
        │
        ▼
api/*  +  types/domain.ts  +  utils/*
        │
        ├──────────────► ui/*
        │
        ▼
platform/*
        │
        ▼
uni-app / WeChat runtime
```

The important rule is one-way dependency:

```text
product -> platform
platform -X-> product
```

CI enforces this with:

```bash
cd apps/miniapp
npm run starter:check
```

## Reusable starter layer

### `src/platform/env.ts`

Owns runtime environment parsing and normalization.

Current public contract:

- `API_ORIGIN`
- `API_BASE_URL`
- `AUTH_MODE`
- `runtimeConfig`
- `isWeChatAuthMode()`

Business modules should not read `import.meta.env.VITE_*` directly.

### `src/platform/http.ts`

Owns generic HTTP mechanics:

- base URL joining;
- JSON request headers;
- typed request options;
- non-2xx error extraction;
- optional auth headers;
- one retry after auth refresh.

It deliberately knows nothing about:

- customer/provider/admin identities;
- orders;
- payments;
- wallets;
- esports;
- backend role names.

The product adapter in `src/api/client.ts` maps the application identity model onto this generic transport.

### `src/platform/navigation.ts`

Owns small navigation mechanics:

- query encoding;
- `push` / `replace`;
- tab switching;
- back navigation.

It does **not** own product routes. Product pages still decide that `/pages/order-detail/index` is an order page.

### Theme and interaction contracts

The following are also starter-level capabilities, but remain under their existing focused directories:

- `theme.json` + generated theme artifacts;
- `src/styles/foundation.css`;
- `src/components/ui/*`;
- `src/ui/feedback.ts`;
- developer UI Showcase.

See [Mini Program Theme](miniapp-theme.md) and [Mini Program UI Foundation](miniapp-ui.md).

## Reference product layer

These files demonstrate a transactional marketplace and should be replaced or reshaped when using the repository for another domain:

- `src/types/domain.ts`;
- `src/api/demo.ts`;
- `src/api/payment.ts`;
- `src/api/realtime.ts`;
- customer/provider pages;
- order, settlement, dispute and withdrawal UI.

`src/api/auth.ts` sits at the boundary: session lifecycle mechanics are broadly reusable, but the current implementation intentionally remains a product adapter because it depends on this backend's WeChat login/refresh/logout payloads, user roles and session storage contract.

Do not move those endpoint schemas into `platform/` merely to make the directory look more generic.

## Compatibility facades

`src/api/config.ts` remains as a thin re-export facade over `platform/env.ts`.

That keeps existing product imports stable while the reusable ownership lives in the platform layer. New starter-level code should import from `platform/*` directly.

## CI ownership rules

`starter:check` currently enforces:

1. `platform/*` cannot import product API/components/pages/domain utilities.
2. product-domain endpoint/type markers cannot leak into `platform/*`.
3. direct `uni.request()` calls are forbidden outside `platform/http.ts`.
4. runtime `VITE_*` access is centralized in `platform/env.ts`.
5. the product API client must continue composing the generic platform HTTP client.

Together with:

```text
theme:check
ui-check
starter:check
type-check
mp-weixin build
staging mp-weixin build
```

this gives the starter structural, visual and interaction-level regression gates.

## Forking checklist

For a new product built from this repository:

1. keep `platform/*`, UI primitives, feedback and theme infrastructure;
2. replace `theme.json` and regenerate theme outputs;
3. replace domain types and product pages;
4. replace product API adapters while retaining `platform/http.ts`;
5. decide whether the existing WeChat session adapter matches your backend contract;
6. replace product routes while retaining the navigation helper;
7. keep the CI contracts enabled while removing domain-specific tests only when their replacement exists.

The intended result is a small reusable Mini Program kernel with an opinionated production example, not a generic framework with every business abstraction hidden behind indirection.
