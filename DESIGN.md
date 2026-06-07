---
name: Finance Categorizer
description: A local-first finance dashboard for monthly transaction review, categorization, and spending trends
colors:
  bg-base: "#08080f"
  bg-surface: "#0f0f1a"
  bg-elevated: "#16162a"
  border: "rgba(255,255,255,0.07)"
  border-hover: "rgba(255,255,255,0.14)"
  accent: "#7c6fda"
  accent-bright: "#9b8ee8"
  accent-glow: "rgba(124,111,218,0.2)"
  text-primary: "#f0f0fa"
  text-secondary: "#8888aa"
  text-muted: "#55556a"
  green: "#34d399"
  red: "#f87171"
  yellow: "#fbbf24"
typography:
  display:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: "4rem"
    fontWeight: 800
    lineHeight: 1.07
    letterSpacing: "-2.5px"
  headline:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: "1.7rem"
    fontWeight: 800
    lineHeight: 1.2
    letterSpacing: "-0.03em"
  title:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "normal"
  body:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 500
    lineHeight: 1.65
    letterSpacing: "normal"
  label:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: "0.72rem"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "0.07em"
rounded:
  sm: "6px"
  md: "10px"
  lg: "16px"
  pill: "999px"
spacing:
  xs: "0.4rem"
  sm: "0.75rem"
  md: "1.25rem"
  lg: "1.75rem"
  xl: "3rem"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "#ffffff"
    rounded: "{rounded.md}"
    padding: "0.6rem 1.5rem"
  button-primary-hover:
    backgroundColor: "{colors.accent-bright}"
    textColor: "#ffffff"
    rounded: "{rounded.md}"
  card:
    backgroundColor: "{colors.bg-surface}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.lg}"
    padding: "1.75rem"
  input:
    backgroundColor: "{colors.bg-elevated}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.md}"
    padding: "0.6rem 0.9rem"
  pill:
    backgroundColor: "{colors.bg-surface}"
    textColor: "{colors.text-secondary}"
    rounded: "{rounded.pill}"
    padding: "0.28rem 0.85rem"
---

# Design System: Finance Categorizer

## 1. Overview

**Creative North Star: "The Quiet Ledger"**

A finance tool that looks like it keeps a careful record, not one that's trying to sell you something. The surface sits in near-total darkness (#08080f) so the numbers, not the chrome, hold the user's attention during a long monthly review session. One muted violet (#7c6fda) carries every signal that matters: a focus ring, a primary action, a glow under a button. Everywhere else, the palette stays quiet, deep, and tonal, layered in three steps of near-black (base, surface, elevated) rather than dressed up with shadows or color blocking.

This system explicitly rejects the gradient-hero-card, stat-tile SaaS template and the cartoon-bright consumer-budgeting look. There is no mascot energy here, no badges, no playful chart skins. Confidence comes from restraint: thin 1px borders that barely register until hover, type that holds its hierarchy through weight rather than ornament, and a single accent that earns attention by how rarely it competes for it.

**Key Characteristics:**
- Near-black, three-step tonal surface stack (base → surface → elevated), no pure black and no warm neutrals
- One accent color (muted violet, #7c6fda) doing all the signaling work: focus, primary actions, glow, links
- Flat cards with hairline borders that only brighten on hover; depth implied by tone, not shadow
- Type carries hierarchy through weight and negative letter-spacing on display sizes, not decoration
- Category and status color exist only inside data visualizations (charts, pills, deltas) — never as page chrome

## 2. Colors: The Quiet Ledger Palette

A near-monochrome dark system built on three tonal layers, with one accent color doing all of the signaling and a small reporting palette reserved strictly for data (category charts, gains/losses, status).

### Primary
- **Muted Violet** (`#7c6fda`): the system's one quiet signal. Appears on primary buttons, active nav states, focus rings, links, badges, and as a soft ambient glow (`rgba(124,111,218,0.2)`) under interactive elements. It is rare by design — when it shows up, it means "this is the action" or "this is active."
- **Bright Periwinkle** (`#9b8ee8`): the lifted half of the accent gradient on primary buttons and avatars (`linear-gradient(135deg, #7c6fda, #9b8ee8)`). Never used solo; it exists to give the accent a sense of depth on raised surfaces.

### Neutral
- **Void** (`#08080f`): the base canvas. The deepest layer; everything else sits on top of it.
- **Surface** (`#0f0f1a`): the resting plane for cards, panels, and tables — one step lifted from Void.
- **Elevated** (`#16162a`): the plane for things that float above content — dropdown menus, inputs, skeleton states, tooltips.
- **Hairline Border** (`rgba(255,255,255,0.07)`) / **Hover Border** (`rgba(255,255,255,0.14)`): the only structural lines in the system. They exist to be almost invisible at rest and to brighten, not thicken, on interaction.
- **Ledger White** (`#f0f0fa`): primary text and the brightest value in the system, reserved for things that must be read first (headline numbers, active labels).
- **Quiet Grey** (`#8888aa`): secondary text — labels, captions, supporting copy that should recede behind the primary figure.
- **Faint Grey** (`#55556a`): muted text — placeholders, timestamps, disabled states, anything that should be present but not compete.

### Reporting Palette (data only)
- **Gain Green** (`#34d399`), **Loss Red** (`#f87171`), **Watch Yellow** (`#fbbf24`): reserved exclusively for financial meaning — positive/negative deltas, income vs. spending, recurring-charge status. The category palette (in `constants.js`, e.g. Groceries `#00c853`, Dining `#ff6b35`, Transport `#3d5afe`) follows the same rule: vivid hues exist only inside charts, pills, and legends, never as page chrome.

### Token Composition
Translucent fills (confirmation badges, status washes, animated highlights) are built from the same hex values two ways: literal `rgba(124,111,218,0.X)` / `rgba(248,113,113,0.X)` for the accent and red, and a dedicated `--green-rgb: 52, 211, 153` component variable (`rgba(var(--green-rgb), 0.X)`) for green, since CSS can't destructure a hex token into `rgba()` components inline. New translucent-green fills should reuse `--green-rgb` rather than restating the hex in `rgba()` form; new translucent reds and violets follow the existing literal-`rgba()` convention already established by `.delete-btn` and the accent glow.

### Named Rules
**The One Signal Rule.** Muted Violet is the only accent used for interface chrome (actions, focus, active state, glow). If a second "brand" color appears outside of a chart or category pill, it's a mistake — route it back to violet or to a neutral.

**The Tonal Depth Rule.** Depth comes from moving one step up the Void → Surface → Elevated stack, never from drop shadows on resting elements. Shadows are reserved for things that visually float above the page (menus, modals, tooltips), at `0 8px 32px rgba(0,0,0,0.5–0.65)`.

## 3. Typography

**Display & Body Font:** Inter (with `system-ui, sans-serif` fallback)

**Character:** A single, well-weighted grotesque doing every job in the system — display, body, and labels — distinguished only by size, weight, and letter-spacing. This is deliberate: one typeface reads as a considered decision; three would read as indecision in a tool whose entire job is to be trusted with numbers.

### Hierarchy
- **Display** (800, 4rem / `clamp` down on smaller surfaces, line-height 1.07, letter-spacing −2.5px): the upload-screen headline only. The single loudest moment in the product; everywhere else stays well below it.
- **Headline** (800, 1.7rem, letter-spacing −0.03em): page-level titles (auth card title, year markers in history).
- **Title** (600, 1rem): card and section headers (`h2`). Quiet, not shouted — weight carries the hierarchy, not size.
- **Body** (500, 0.875rem, line-height 1.65): transaction rows, form labels, descriptive copy. Generous line-height keeps dense data scannable over a long session.
- **Label** (600, 0.7–0.78rem, letter-spacing 0.06–0.1em, uppercase where used): category badges, section eyebrows inside cards (e.g. "RECURRING", year-stat captions), pill text. Uppercase is reserved for these short, structural labels only — never for sentences.

### Named Rules
**The Weight-Over-Size Rule.** Hierarchy is built primarily through font-weight steps (500 → 600 → 700/800) and negative letter-spacing on the largest sizes, not through a wide type scale. Most of the interface lives between 0.7rem and 1rem; only the upload hero and history year markers break past 1.7rem.

## 4. Elevation

The system is tonally layered, not shadow-driven. At rest, every surface is flat: cards and panels separate from the page only through a one-step lift in background tone (Void → Surface) and a near-invisible hairline border. Shadows exist solely as a structural signal that something is floating above the content plane — dropdown menus, statement pickers, chart tooltips — and they're always soft, dark, and ambient, never crisp or colored (except the accent glow on interactive elements, which is its own category).

### Shadow Vocabulary
- **Ambient Float** (`box-shadow: 0 8px 32px rgba(0,0,0,0.5–0.65)`): dropdown menus, statement pickers, chart tooltips. Signals "this is above the page," not "this card is important."
- **Accent Glow — Resting** (`box-shadow: 0 4px 18px rgba(124,111,218,0.2)`): primary buttons and submit actions at rest. A soft halo that says "this is the action," not a hard drop shadow.
- **Accent Glow — Active** (`box-shadow: 0 0 22–40px rgba(124,111,218,0.2)`): hover/focus state for primary actions and the upload dropzone — the glow widens and softens rather than darkening or sharpening.

### Named Rules
**The Float-Or-Flat Rule.** A surface either sits flush on the page (flat, tonal lift only) or visibly floats above it (ambient shadow). There is no in-between "slightly raised card" — that's the lazy SaaS card-on-card look this system rejects.

## 5. Components

Quiet and structured: components recede at rest and respond with restraint, never with bounce or color shock. Borders brighten by 0.07 → 0.14 opacity on hover; buttons lift 1px and widen their glow; nothing scales past 0.97–1.0. The vocabulary is small on purpose — cards, pills, inputs, and one button form cover nearly the entire product.

### Buttons
- **Shape:** 10px radius (`{rounded.md}`) on primary actions; 8px on compact actions (export, small utility buttons).
- **Primary:** `linear-gradient(135deg, #7c6fda, #9b8ee8)` fill, white text, weight 600, padding `0.6rem 1.5rem`, resting glow `0 4px 18px rgba(124,111,218,0.2)`.
- **Hover / Focus:** glow widens to `0 0 22px rgba(124,111,218,0.2)` and the button lifts `translateY(-1px)`; on `:active` it compresses to `scale(0.97)`. Transitions run on `box-shadow` and `transform` only, ~0.12–0.18s.
- **Secondary / Ghost:** `bg-surface` background with a hairline border (`nav-link-light`, `statement-trigger`); text in Quiet Grey, brightening to Ledger White and border to Hover Border on interaction. No fill, no glow — restraint is the differentiator from primary.

### Pills & Badges
- **Filter / type pills:** `bg-surface` fill, hairline border, 999px radius, Quiet Grey text that turns to Bright Periwinkle (`#c4b8ff`) and bolds on active/selected — color signals state, not a border or fill change.
- **Category pills (`cat-pill`):** 999px radius, 15% category-color tint as background with the full-saturation category color as text. Each category owns one hue from the reporting palette (`constants.js`); never reused for chrome.
- **Recurring-type badges:** 4px radius, small and dense (0.7rem, weight 600), each charge type (subscription, fixed bill, variable bill, frequent) gets its own muted tint-on-tint pairing.

### Cards / Containers
- **Corner Style:** 16px radius (`{rounded.lg}`) for primary content cards (table, summary, recurring, trends); 12–20px for secondary surfaces (history rows, auth card).
- **Background:** `bg-surface` (#0f0f1a), one tonal step above the page.
- **Shadow Strategy:** none at rest — see Elevation's Float-Or-Flat Rule. Depth comes from the tonal step and the hairline border alone.
- **Border:** 1px solid hairline border (`rgba(255,255,255,0.07)`), brightening to `rgba(255,255,255,0.14)` on hover. This is the system's only "interactive card" cue — never a background-color shift.
- **Internal Padding:** 1.75rem (`{spacing.lg}`) standard; 2.5–3rem for centered, single-focus surfaces (auth card, upload dropzone).

### Inputs / Fields
- **Style:** `bg-elevated` background (one step brighter than cards, since inputs float conceptually above the surface they sit in), hairline border, 8–10px radius, Ledger White text, Faint Grey placeholder.
- **Focus:** border brightens to `rgba(124,111,218,0.5)` — a direct, single-property shift. No glow, no outline ring on inputs (glow is reserved for buttons and the dropzone).
- **Error:** red (`#fc8181` / `#f87171`) text directly beneath the field; no red border or background wash.

### Navigation
- **Style:** flat text links (`nav-link`) in Quiet Grey, brightening to Ledger White on hover, with a 1.5px accent underline that scales in from `scaleX(0)` to `scaleX(1)` — the only "moving chrome" element in the system, and it's reserved for primary navigation alone.
- **Top bar:** `rgba(8,8,15,0.8)` translucent fill with `blur(20px)` backdrop-filter, hairline bottom border — a quiet glass effect used exactly once, structurally, not decoratively.

### Proportional Bars (Category Breakdown)
- **Style:** each row in the dashboard's top-categories list (`dash-cat-item`) is a clickable grid: a 7px category-color dot, name in Quiet Grey, amount in Ledger White (weight 600), percentage in Faint Grey, and underneath, a hairline 3px track (`bg-elevated`) filled to the category's share of spend in that category's own hue.
- **Motion:** the fill animates in from `scaleX(0)` with `transform-origin: left` over 0.55s on a custom ease (`cubic-bezier(0.25,0.1,0.25,1)`) — a single deliberate reveal per row, not a uniform list-stagger reflex. Respects `prefers-reduced-motion` (transition removed).
- **State:** row background brightens to `bg-elevated` on hover and to the accent glow wash (`accent-glow`) when the category is the active drill-down filter — selection reads through background tint, never through the bar's own color.

### Data Tables (Recent Transactions)
- **Style:** borderless `border-collapse` table; each row is separated only by a hairline bottom border (`var(--border)`), matching the system's "structure through hairlines, not boxes" philosophy. No header chrome beyond a visually-hidden (`sr-only`) `<th>` row for assistive tech.
- **Hover / Focus:** the entire row's cells lift one tonal step to `bg-elevated`, **and** the leading cell's left edge brightens from `transparent` to Muted Violet (`2px solid var(--accent)`). This is the row-hover analogue of the Tonal Depth Rule's "brighten, don't materialize" treatment — the edge exists at `2px solid transparent` at rest and only gains color on interaction, so it reads as a focus cue, not a static decorative stripe (see the Named Rule below).
- **Cell roles:** date and account in Faint Grey (de-emphasized, supporting), transaction name in Ledger White, amount in weight-600 with Gain Green / Loss Red by sign, category as a small muted label with its category-color dot.

### Drill-down / Contextual Filter Header
- **Style:** a quiet, label-weight (`0.72rem`, uppercase, `0.12em` tracking, Faint Grey) line that states the active filter in prose ("Showing **Groceries** · 14 transactions"), with the filtered term itself lifted to Bright Periwinkle. A plain-text "Clear filter" action sits opposite, in Quiet Grey brightening to Ledger White on hover — no button chrome, because clearing a filter is a low-stakes, frequent action that shouldn't compete visually with primary actions.
- **Empty state:** when the filter matches nothing, the panel collapses to a single muted sentence rather than an illustrated empty state — consistent with the system's preference for typographic restraint over decorative emptiness (the History view's empty state follows the same logic, deliberately stating the fact in prose with no icon).

### Inline Load Errors
- **Style:** a flat, bordered block in a translucent red wash (`rgba(248,113,113,0.06)` fill, `rgba(248,113,113,0.2)` border, 16px radius) — the system's only sanctioned use of color-as-background, reserved strictly for error states. Body copy stays in Quiet Grey with the failing detail emphasized in Loss Red; a ghost-style retry button (`bg-elevated`, hairline border) sits below, never inside the tinted block.

## 6. Do's and Don'ts

### Do:
- **Do** keep the page in the three-step tonal stack (#08080f → #0f0f1a → #16162a); every surface's depth should be readable from its background alone.
- **Do** let Muted Violet (#7c6fda) be the only chrome accent — focus rings, primary actions, active nav, glows. If it shows up twice in the same view doing two different jobs, that's the system working as intended.
- **Do** reserve saturated color (the reporting palette and `CATEGORY_COLORS`) for data: charts, pills, deltas, badges. These are the only places vivid hue belongs.
- **Do** build hierarchy with font-weight (500/600/700/800) and tight letter-spacing on display sizes, keeping the type scale narrow (0.7rem–1.7rem covers nearly everything; 4rem is reserved for the single hero moment).
- **Do** use the Float-Or-Flat rule: flat tonal cards at rest, soft ambient shadows (`0 8px 32px rgba(0,0,0,0.5-0.65)`) only for things that visually float above the page.

### Don't:
- **Don't** add gradient hero cards, stat-tile templates, or "enterprise analytics" dashboard chrome — PRODUCT.md names these directly as anti-references, and this system's whole point is that it doesn't look like it's selling anything.
- **Don't** introduce gamified, consumer-budgeting-app energy: no badges-as-rewards, no cartoon chart skins, no mascot copy, no over-friendly micro-copy. The category pills and recurring badges are informational, not playful.
- **Don't** use `border-left`/`border-right` colored stripes as *static decorative* accents on cards or list rows — every card uses a full hairline border; a stripe would be the one inconsistent shape in the system. The one exception is the recent-transactions table, where the leading cell's edge sits at `2px solid transparent` and only brightens to violet on row hover/focus — that's the Tonal Depth Rule's "brighten on interaction" treatment applied to a table row, not a static stripe. If you're adding a colored edge that's visible at rest, it's the banned pattern; if it only appears on interaction as a focus cue, it's this exception.
- **Don't** add drop shadows to resting cards, or stack "card on card" — depth comes from the tonal lift (Void → Surface → Elevated), never from shadow-on-flat-surface layering.
- **Don't** introduce a second accent hue for interface chrome. If something needs to stand out, widen the violet glow or shift weight/contrast — don't reach for a new color.
- **Don't** push the type scale past what's already here: no fonts beyond Inter, no display sizes beyond 4rem, no letter-spacing tighter than −2.5px. The narrow scale is what keeps a data-dense surface calm.
