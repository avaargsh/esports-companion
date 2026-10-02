# Mini Program Frontend Architecture

The Mini Program stays on **UniApp + Vue 3**. The goal is to make the product
boundary explicit before adding more UI surface, not to migrate frameworks.

## Dependency direction

For product data access:

```text
Page
  ├── product/principal
  ├── domain/*
  │     └── api/client
  │           └── platform/http
  └── shared UI / composables
```

Rules:

- pages do not call product HTTP endpoints directly;
- pages do not resolve demo vs WeChat identities directly;
- `domain/*` must not import `product/*`;
- `platform/*` must not know product routes, order states, player roles or
  marketplace endpoint names;
- server state and `available_actions` remain authoritative for transaction
  behavior.

## Page data states

Remote-data pages model these states explicitly:

```text
loading -> ready
        -> empty
        -> error -> retry
```

A transport/auth failure must never be rendered as an empty business result.

Pages that refresh from `onShow` should preserve already useful content during
a refresh. A refresh failure may use lightweight feedback instead of replacing
valid content with a blocking error state.

Initial page state should be `loading`, not `idle`, when the page immediately
loads remote data. This avoids a first-frame empty/zero-data flash before
`onShow` runs.

## UniApp lifecycle

Tab and task pages use UniApp page lifecycle hooks deliberately:

- `onLoad` for route parameters and one-time page initialization;
- `onShow` when data must refresh after returning from a child page or switching
  back to a tab;
- `onUnload` for page-owned resource cleanup such as sockets.

Do not replace page lifecycle semantics with generic Vue component hooks when
the behavior depends on Mini Program page visibility.

## UI strategy

Keep the existing semantic UI foundation for product primitives:

- `UiButton`
- `UiCell`
- `UiBadge`
- `StatusTag`
- `PrimaryActionBar`
- shared feedback helpers and theme tokens

Native Mini Program controls remain the default for platform capabilities.

TDesign UniApp may be evaluated for complex interaction primitives such as
Popup, ActionSheet, Picker, Form and Upload. If adopted, product pages should
consume local adapters rather than importing TDesign components directly. This
keeps business code independent from a component library and allows package
size / runtime compatibility to be measured before broader adoption.

Do not add Taro, Vant Weapp or another application/component runtime merely for
component coverage.

## Reference direction

Primary references:

- UniApp official page and lifecycle documentation;
- WeChat official `miniprogram-demo` for platform capability behavior;
- TDesign MiniProgram / UniApp for complex component interaction patterns.

Large commerce projects such as litemall or CRMEB are business-flow references,
not application-framework dependencies.

## Review checklist

For a page that reads remote data:

- [ ] no raw endpoint paths in the page;
- [ ] no direct demo/WeChat identity resolution in the page;
- [ ] loading, empty, error and content are distinguishable;
- [ ] first-load error has a retry path when retry is meaningful;
- [ ] existing useful content is preserved during background/onShow refresh;
- [ ] navigation uses the shared navigation adapter;
- [ ] transaction actions remain derived from server-authoritative state;
- [ ] ordinary actions reuse shared UI primitives;
- [ ] type-check and mp-weixin builds remain green.


## Transaction action authority

Customer mutation affordances come from the server-side `available_actions`
contract whenever the action changes durable order state.

Examples:

- `PAY`
- `CANCEL`
- `CONFIRM_FINISH`
- `REQUEST_REFUND`
- `OPEN_DISPUTE`

The client may derive local navigation actions such as "order again", but it
must not recreate backend authorization by checking order status alone.

The order detail endpoint emits actions for the current viewer role. A player
or platform viewer must not inherit customer mutation affordances merely
because they can read the order.

## Order-detail boundary

The customer order detail flow is split deliberately:

```text
page
  -> features/order-detail/useCustomerOrderDetail
       -> domain/order/api
       -> domain/order/presenter
       -> domain/order/realtime
       -> platform/navigation
```

- the page owns Mini Program lifecycle hooks and rendering;
- the feature composable owns orchestration and transient interaction state;
- domain API modules own endpoint paths and request shapes;
- presenter functions are pure state-to-view decisions;
- realtime owns SocketTask protocol details and event-id deduplication.

Do not move endpoint strings, SocketTask callbacks, auth-mode branching or
transaction action derivation back into the page.
