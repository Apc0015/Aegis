# Aegis — Design system

**Register:** Product (dark, restrained). Feel: control-room precision — Linear's
craft with a security console's seriousness. Not a terminal, not a generic slate
SaaS dashboard.

## Color (OKLCH, dark)
Tokens are raw OKLCH channel triples in `index.css`; Tailwind wraps them with an
alpha channel so `bg-accent/15` etc. work.

Layered near-black neutrals with a faint cool tint (hue 265):
- `bg` deepest → `surface` (nav/panels) → `card` → `elevated` (menus/popovers)
- Ink ramp: `ink` (near-white) · `ink-muted` · `ink-faint`
- `border` / `border-strong`

Two meaningful color roles (restrained, semantic — never decorative):
- **`accent`** (blue-violet, hue 264): interactive — primary actions, current
  selection, focus, links.
- **`warning`** (amber): the **governance signal** — firewall activity, blocked /
  anonymized columns, medium confidence, degraded health. This amber is Aegis's
  second identity color because governance is the product.
- `success` (emerald) = permitted / high / healthy. `danger` (rose) = denied /
  refused / error / blocked-count.

## Type
- **Inter Variable** for all UI (one family, weights carry hierarchy).
- **JetBrains Mono Variable** for machine data: IDs, model names, latency, tokens,
  collection names, verdict codes, JSON.
- Fixed rem scale (product, not fluid). Steps ~1.15–1.2. Tight tracking on large
  sizes only (≥ -0.02em, never past -0.04em).

## Elevation & shape
- Depth via layered surfaces + 1px borders, **not** border+big-shadow ghost cards.
- Radius: 10px cards/inputs, 8px controls, pill for tags. Never 24px+.
- Shadows reserved for true overlays (menus, dialogs, toasts).

## Motion
- 150–220ms, ease-out (expo/quart). State + feedback only, no page-load theater.
- Streaming caret, row/hover transitions, skeleton shimmer, subtle mount fade-up
  on route content. Full `prefers-reduced-motion` fallbacks.

## Components
Every interactive element ships default / hover / focus-visible / active /
disabled / loading. Skeletons for loading content (no center spinners). Empty
states teach the interface.
