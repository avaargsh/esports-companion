# Mini Program Theme

The Mini Program starter uses **one canonical theme source**:

`apps/miniapp/theme.json`

Do not hand-edit generated theme files.

## What theme.json controls

`theme.json` drives:

- CSS semantic color tokens in `src/styles/theme.css`
- runtime colors used by native Mini Program APIs in `src/ui/theme.ts`
- native navigation-bar colors in `src/pages.json`
- native tab-bar colors in `src/pages.json`

This keeps CSS surfaces and WeChat platform chrome aligned.

## Change the brand

Edit:

```json
{
  "colors": {
    "brand": "#6757e6",
    "brandStrong": "#5644d6",
    "brandSoft": "#efedff",
    "brandGhost": "#f7f5ff"
  },
  "chrome": {
    "tabSelected": "#6757e6"
  }
}
```

Then run:

```bash
cd apps/miniapp
npm run theme:sync
npm run theme:check
npm run type-check
npm run build:mp-weixin
```

Commit `theme.json` together with the generated files.

## Semantic palette

The starter separates light application surfaces from inverse provider surfaces.

Light tokens include:

- `--brand`
- `--ink`, `--muted`
- `--bg`, `--surface`, `--line`
- `--success`, `--warning`, `--danger`

Inverse tokens include:

- `--inverse-bg`
- `--inverse-surface`
- `--inverse-control`
- `--inverse-muted`
- `--brand-on-inverse`
- `--success-on-inverse`
- `--warning-on-inverse`
- `--danger-on-inverse`

Do not invent a second product palette inside a page. Add a semantic token only when the color represents a reusable design role.

## Generated runtime colors

Native Mini Program APIs such as `uni.showModal` require actual color strings rather than CSS variables.

The theme generator therefore also creates:

`src/ui/theme.ts`

Interaction helpers consume these generated values. Business pages should not import raw hex values.

## Theme contract

CI runs:

```bash
npm run theme:check
```

The check fails when:

- generated CSS is stale
- generated runtime theme values are stale
- native navigation or tab colors are stale
- protected core palette literals leak back into Vue/CSS/TypeScript business sources

This intentionally does **not** ban every one-off color. Illustration accents and domain-specific data visualization colors may remain local when they are not theme semantics.

## UI Showcase

The developer-only reference page is:

```text
/pages-lab/ui/index
```

It is packaged as a separate subpackage and is not linked from product navigation.

Open it directly from WeChat Developer Tools to inspect:

- theme swatches
- Button variants
- Badge tones and status dots
- Cell interaction
- native feedback helpers
- inverse/dark action surfaces

The Showcase must stay backend-independent so theme and primitive validation never depends on seeded product data.

## Native WeChat chrome

Native navigation bars and the native tab bar cannot consume CSS custom properties. The theme generator keeps those static values synchronized from the same `theme.json` source rather than replacing native navigation with a custom implementation.

That tradeoff is deliberate: use native WeChat chrome unless a product requirement genuinely needs custom navigation.
