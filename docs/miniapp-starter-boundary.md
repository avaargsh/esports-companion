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

### `src/platform/session.ts`

Owns backend-neutral session mechanics:

- validated synchronous storage;
- access-expiry freshness checks with skew;
- refresh-expiry checks;
- single-flight protection so concurrent callers share one refresh/login task.

It does not know WeChat login endpoints, user roles, backend payloads or application-specific storage schemas. Those remain in `src/api/auth.ts`.

### `src/platform/wechat.ts`

Owns direct WeChat-native capability calls that should not leak across product
modules:

- WeChat login code acquisition;
- WeChat payment invocation;
- subscription-message authorization.

Product adapters still own backend endpoints, payment preparation and business
copy. The platform adapter owns only the native runtime invocation and normalized
runtime errors.

When privacy/user-service capabilities are added, follow the current official
Mini Program demo contract and keep the native API call in this module rather
than scattering `wx.*` / `uni.*` calls across pages.

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

`src/api/auth.ts` sits at the boundary: it composes the generic session store/freshness/single-flight primitives, but intentionally retains this backend's WeChat login/refresh/logout payloads, user roles and session schema.

Do not move those endpoint schemas into `platform/` merely to make the directory look more generic.

## Compatibility facades

`src/api/config.ts` remains as a thin re-export facade over `platform/env.ts`.

That keeps existing product imports stable while the reusable ownership lives in the platform layer. New starter-level code should import from `platform/*` directly.

## CI ownership rules

`starter:check` currently enforces:

1. `platform/*` cannot import product API/components/pages/domain utilities.
2. product-domain endpoint/type markers cannot leak into `platform/*`.
3. direct `uni.request()` calls are forbidden outside `platform/http.ts`.
4. direct login/payment/subscription-message native calls are forbidden outside
   `platform/wechat.ts`.
5. runtime `VITE_*` access is centralized in `platform/env.ts`.
6. the product API client must continue composing the generic platform HTTP client;
7. the product auth adapter must continue composing the generic platform session kernel.

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


## Machine-readable extraction surface

The reusable file surface is declared in:

`apps/miniapp/starter.manifest.json`

This is intentionally a **manifest, not an extraction script**. It makes the boundary reviewable and CI-verifiable before automating repository generation.

CI checks that:

- every declared starter path still exists;
- required platform/theme/UI/contract surfaces remain declared;
- product roots are never included;
- the manifest has no duplicate entries.

Run:

```bash
cd apps/miniapp
npm run starter:manifest:check
```

When a reusable capability moves or is added, update the manifest in the same change. Product pages and domain API adapters must remain outside it.


## Standalone extraction smoke test

The repository does not maintain a second checked-in starter tree. Instead, CI proves the declared reusable surface can become a standalone Mini Program.

Extraction command:

```bash
python3 scripts/extract_miniapp_starter.py /tmp/miniapp-starter
```

The extractor:

1. copies only paths declared by `starter.manifest.json`;
2. generates a minimal generic UniApp shell around the existing UI Showcase;
3. refuses to extract inside the source repository;
4. verifies product API/pages/domain roots are absent.

The dedicated **MiniApp Starter Smoke** CI job then runs, from the extracted workspace:

```bash
npm install
npm run theme:check
npm run type-check
npm run build:mp-weixin
```

and verifies the built WeChat app contains the Showcase page.

This is the promotion gate before creating or publishing a separate template repository: the starter boundary must first survive a real clean extraction and build.


## Deterministic distribution artifacts

The same clean-room extraction is also used to build source distributions:

```bash
python3 scripts/package_miniapp_starter.py /tmp/miniapp-starter-dist
```

The output is:

```text
miniapp-starter.tar.gz
miniapp-starter.zip
miniapp-starter.provenance.json
SHA256SUMS
```

Both archives contain the same top-level `miniapp-starter/` tree and an internal
`STARTER-PROVENANCE.json`.

The packager normalizes archive metadata that would otherwise change between runs:

- file ordering;
- timestamps;
- uid/gid and owner names;
- file modes;
- gzip header metadata;
- ZIP timestamps.

The external provenance document records:

- source repository and commit;
- SHA256 of `starter.manifest.json`;
- every distributed file with size and SHA256;
- SHA256 and size of both archive formats.

`SHA256SUMS` covers the tarball, ZIP and external provenance document.

CI generates the distribution twice from the same commit and requires byte-for-byte
identity before uploading the artifacts. The **MiniApp Starter Smoke** job therefore
proves both standalone buildability and deterministic packaging.

The source bundle deliberately excludes `node_modules` and compiled `dist`
output. Consumers install dependencies and build locally; the distribution remains
small, auditable and tied to source provenance.
