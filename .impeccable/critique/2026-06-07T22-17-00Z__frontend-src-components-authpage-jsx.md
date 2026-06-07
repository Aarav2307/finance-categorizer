---
target: AuthPage
total_score: 18
p0_count: 2
p1_count: 2
timestamp: 2026-06-07T22-17-00Z
slug: frontend-src-components-authpage-jsx
---
## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 2 | "Please wait…" (AuthPage.jsx:114) is the only loading signal — generic, doesn't say *what's* happening (signing in vs. creating an account). |
| 2 | Match Between System & Real World | 3 | Plain "Login"/"Register"/"Create Account" labels; minor friction from the unexplained "Phone Number (optional)" field. |
| 3 | User Control and Freedom | 2 | No "forgot password," no cancel mid-submit, no escape from an error state besides retyping. |
| 4 | Consistency and Standards | 1 | Imports glassmorphism, gradient text, and ambient glow blobs — none of which appear anywhere else in "The Quiet Ledger" system. The screen feels like a different product than the dashboard it gates. |
| 5 | Error Prevention | 1 | `minLength={6}` (AuthPage.jsx:108) is the *only* client-side validation; no email-format check, no password confirmation, no inline strength/requirement hints before submit. |
| 6 | Recognition Rather Than Recall | 2 | Every input is placeholder-only with no `<label>` (AuthPage.jsx:71-109) — field identity vanishes the moment the user starts typing. |
| 7 | Flexibility and Efficiency of Use | 2 | No `autoComplete` attributes anywhere, no password-manager affordances, no "remember me." |
| 8 | Aesthetic and Minimalist Design | 2 | Individually-restrained elements combine into something more ornamented (gradient title + glow blobs + glass blur + gradient button) than this brand's "restraint as craft" ethos allows. |
| 9 | Error Recovery | 2 | Error text is whatever raw string the backend returns (`data.detail`, AuthPage.jsx:34/39) — names the problem but offers no path forward (try again? reset? check spelling?). |
| 10 | Help and Documentation | 1 | Zero help affordances. The product's single biggest trust differentiator — "100% local, nothing leaves your machine" — gets a four-word subtitle clause and nothing more, on the one screen where that reassurance matters most. |
| **Total** | | **18/40** | **Poor — significant rework needed before this screen matches the rest of the product** |

Be honest with scores: most real interfaces land 20-32. This screen sits below that — and notably *below* the bar the rest of this product appears to clear, based on the specificity of its own design system documentation.

## Anti-Patterns Verdict

**Yes — this screen reads as imported-template work, not as a piece of "The Quiet Ledger."**

**LLM assessment**: This isn't "introduced a second accent hue" slop — to its credit, the palette stays violet-only. It's "imported a generic dark-glassmorphism-auth-template's *techniques*" slop: gradient-clipped headline text, large blurred ambient glow blobs sitting at rest behind a frosted-glass card, and a "please wait…" loading string — stacked together in a combination that appears nowhere else in this codebase. The rest of the product (per DESIGN.md) is built from flat tonal cards, hairline borders that brighten only on interaction, and hierarchy carried by type weight rather than decoration. This screen instead reaches for exactly the ornaments that system explicitly rules out: it violates the **Tonal Depth Rule** ("brighten, don't materialize" — no glows or blurs at rest, DESIGN.md), reuses the **one-time-only glass effect** that DESIGN.md reserves structurally for the top nav, and renders gradient text — the single most diagnostic "AI made this" signature in dark-mode UI today, and a pattern the brand's own anti-references (PRODUCT.md) name directly ("no generic SaaS dashboard chrome," "no gradient hero cards"). A user who lands here first and the dashboard second will feel like they walked through the wrong door.

**Deterministic scan**: `detect.mjs --json` on `AuthPage.jsx` returned exit code 0 with an empty findings array (`[]`) — clean. This is expected and not a contradiction: the detector scans markup/structural patterns, and every issue found here lives in the *CSS* (`index.css:344-424`) — gradient-clipped text, ambient blur blobs, `backdrop-filter` — which a markup-only scanner won't catch. The clean scan simply means there's no code-quality smell (div soup, dead links, hallucinated imports) in the component itself; the problems are entirely in the visual layer the detector doesn't see. No false positives to report — there were no positives at all.

**Visual overlays**: Not available this run — no browser automation tooling exists in the current environment (verified via exhaustive tool search; only unrelated MCP servers for Calendar/Drive/Gmail/Expedia are present, no Playwright/Puppeteer/computer-use). The dev server at `localhost:5173` is reachable (curl confirms HTTP 200), but no tab could be opened, no script injected, and no screenshot captured. This review is therefore grounded in careful reading of the component, the relevant CSS blocks, and the project's own DESIGN.md/PRODUCT.md specs — not a rendered screenshot. Treat the visual claims below (gradient text, glow placement, blur stacking) as derived from CSS source, not pixel-verified.

## Overall Impression

Picture the rest of this product: flat near-black cards, one violet accent used with total discipline, hairline borders that only brighten on touch. Then picture the door to that house — gradient-clipped text, two enormous blurred violet orbs glowing at rest in the corners, and a frosted-glass card floating over them. That's the dissonance here: the AuthPage isn't badly built (the shake animation and tab logic are genuinely well-made), it's built from a *different design vocabulary* than everything it gates access to. The single biggest opportunity is also the simplest: delete the ambient decoration, let the card sit flat on `--bg-base` like every other surface in the system, and put that reclaimed visual weight into the one thing this screen should be doing better than any other — making a first-time user feel, immediately, that their financial data is about to be handled with the same restraint and precision the rest of the product demonstrates.

## What's Working

1. **The error-shake animation is genuinely well-tuned** (`auth-shake`, index.css:1363-1370): 0.38s, `cubic-bezier(0.36,0.07,0.19,0.97)`, re-triggered cleanly via a `key={shakeKey}` remount (AuthPage.jsx:40/67). It's a single, restrained physical cue tied to a real event — exactly the kind of "polish lives in motion timing, not ornament" the brand voice calls for. It doesn't loop, doesn't bounce, resolves in under half a second.
2. **The error-state input treatment is correctly minimal** (`.input-error`, index.css:1371-1373): only a softened red border (`rgba(248,113,113,0.55)`), no background wash, no icon. This is precisely the restrained error language the design system specifies elsewhere — quiet, not alarming.
3. **The tab-switch state management is small but considerate** (AuthPage.jsx:55/61): `setError(null)` fires on every mode change, so a stale error from a failed login attempt doesn't bleed into the register form. Easy to skip, and they didn't.

## Priority Issues

**[P0] Ambient glow blobs and card backdrop-blur contradict the system's own named rules**
- **Why it matters**: `index.css:350-365` places two enormous (700px/600px) radial-gradient violet blobs, blurred at 72px, sitting at rest in the page corners; `index.css:371-372` then frosts the card itself with `backdrop-filter: blur(20px)`. This is the highest-leverage "looks templated" signal on the page — it's the textbook "gradient-mesh-behind-glass-card" SaaS auth aesthetic that PRODUCT.md names as an anti-reference, and it directly violates the Tonal Depth Rule ("brighten, don't materialize" — no glows or blurs at rest) and the documented one-time-only use of glassmorphism (reserved structurally for the nav bar). Nothing else in the product looks like this; it's the first thing every user sees.
- **Fix**: Delete the `::before`/`::after` blobs entirely; let `.auth-page` sit on flat `--bg-base`. Drop `backdrop-filter` from `.auth-card` — once the blobs are gone there's nothing behind the card that needs obscuring, and a flat `--bg-surface` card with a hairline border (matching `.table-wrap`, `.summary`, etc.) is exactly what this system already uses for every other surface.
- **Suggested command**: `/impeccable quieter` (the screen is overstimulated relative to the brand's restraint) or `/impeccable polish` if scoping to a final pass.

**[P0] Gradient-clipped title text**
- **Why it matters**: `index.css:378-379` — `background: linear-gradient(...); -webkit-background-clip: text; -webkit-text-fill-color: transparent`. Gradient text is the single most overused "this was made with an AI template" tell in current dark-mode UI, full stop. It also directly contradicts this product's own stated philosophy that hierarchy is carried "through weight, not decoration," and creates a second competing focal point against the gradient submit button just below it — two loud elements stacked on one small card.
- **Fix**: Render the title in solid `--text-primary` at its existing weight/size/tracking (800 / 1.7rem / -0.03em). Let violet appear exactly once on this screen — on the submit button, where the system already sanctions it.
- **Suggested command**: `/impeccable quieter`

**[P1] Placeholder-only inputs fail accessibility and create unnecessary recall burden**
- **Why it matters**: Every field (AuthPage.jsx:71-109) relies solely on `placeholder` text — no `<label>` elements, no `htmlFor`/`id` pairing, no `autoComplete` attributes, and the error paragraph (`<p className="error">`, line 111) has no `aria-describedby`/`role="alert"` link to its input. This is a textbook WCAG gap (placeholder text vanishes on focus, isn't reliably announced by screen readers, and has weaker contrast than label text), and it's also a real usability tax: on the four-field register form, a user who tabs back to correct something has no persistent cue for which field is which. PRODUCT.md commits explicitly to "WCAG AA contrast for all text and data labels" — this is where that promise breaks first.
- **Fix**: Add visually-present `<label>` elements above each input (small, weight-600, tracked — matching the system's existing label/eyebrow type scale), wire `htmlFor`/`id`, add `autoComplete` values (`email`, `current-password`, `new-password`, `given-name`, `family-name`, `tel`), and link the error text via `aria-describedby` + `aria-live="polite"`.
- **Suggested command**: `/impeccable harden`

**[P1] An unexplained "Phone Number (optional)" field undermines trust at the highest-stakes moment**
- **Why it matters**: AuthPage.jsx:84-89 asks for a phone number on a *finance app* registration form with zero stated purpose. For a brand whose entire pitch is "calm, precise, trustworthy" and "100% local — nothing leaves your machine," an unexplained personal-data request at signup is exactly the kind of "wait, why do you need this?" friction that erodes the trust the product is trying hardest to build. It reads as a vestigial field copied from a generic consumer-SaaS signup template (where phone numbers serve 2FA/marketing) rather than something this single-user, local-first tool actually requires.
- **Fix**: Either remove the field outright, or add a single quiet caption explaining its purpose ("for account recovery only — never shared, never leaves this device"). Silence here reads as carelessness, not the restraint the brand otherwise practices deliberately.
- **Suggested command**: `/impeccable clarify`

**[P2] No password confirmation or visible requirements; loading copy is generic**
- **Why it matters**: This is the single highest-stakes form in the product (it gates access to the user's financial data), yet it has the thinnest error-prevention of any flow in the codebase: `minLength={6}` (AuthPage.jsx:108) is invisible until violated, there's no confirm-password field on register, and a typo'd password means a user locked out of their own data with no recovery path visible (no "forgot password" link). Separately, `'Please wait…'` (line 114) is filler that doesn't tell the user whether the app is signing them in or creating their account — small, but it's the kind of placeholder copy that signals nobody finished thinking about the moment.
- **Fix**: Show the 6-character minimum as a quiet caption *before* submission; add a confirm-password field for register mode; swap the loading string for mode-specific copy ("Signing in…" / "Creating your account…").
- **Suggested command**: `/impeccable clarify`

## Persona Red Flags

**Sam (Accessibility-Dependent User)**:
- No `<label>` elements anywhere (AuthPage.jsx:71-109) — a screen reader announces nothing meaningful for any field; placeholder text disappears the moment a low-vision user begins typing.
- The error message (line 111) isn't wired to `aria-live`/`aria-describedby`/`role="alert"` — submitting bad credentials produces a shake Sam can't perceive and a paragraph that may never be announced.
- The `auth-shake` keyframe (index.css:1363-1370) is **not** included in the `prefers-reduced-motion` media query that covers every other animation in the system (`dash-cat-bar-fill`, `dash-skeleton`, `recurring-icon-pulse` all are) — a direct, checkable gap between the product's stated motion policy and its implementation, on the one screen every single user must pass through.

**Jordan (Confused First-Timer)**:
- Lands on a screen promising "100% local" (AuthPage.jsx:50) and gets nothing more — exactly the moment PRODUCT.md says that reassurance should be *present*, and it's nearly absent. A first-timer deciding whether to trust a finance app with bank statements gets four words and a generic gradient card.
- The unexplained phone-number field (line 86) will make Jordan pause mid-registration and wonder what it's for — friction at precisely the point where abandonment is most costly.
- No password requirements shown until failure — Jordan types a 4-character password, hits submit, and meets a native browser tooltip that doesn't match the app's visual language at all.

**Riley (Deliberate Stress Tester)**:
- Rapid mode-switching mid-submit isn't guarded — `loading` only disables the submit button (line 113), not the tab buttons (lines 53-65), so Riley can flip from Register to Login while a POST is in flight and produce a state mismatch.
- Bad-credential submission surfaces whatever raw string the backend returns as `data.detail` (lines 34/39) with no discrimination between "validation failed" and "network/server unreachable" — Riley will find the seam quickly (e.g., stop the local API and submit).
- The `key={shakeKey}` remount (line 67) forces the entire form to remount on every error — Riley spamming submit on bad credentials will find their cursor and focus dropping out of the password field on every single retry, a small but genuinely irritating discovery to make by just trying again.

## Minor Observations

- `BASE = 'http://localhost:8000'` is hardcoded directly in the component (AuthPage.jsx:4) rather than pulled from the shared `api` module's config — a maintainability smell more than a design one, but worth folding into any pass that touches this file.
- `.auth-tab` only transitions `color` (index.css:393); the underline's `border-bottom-color` change is instant, slightly less considered than the scale-in underline treatment used on nav links elsewhere in the system.
- `.auth-subtitle` uses `--text-muted` / "Faint Grey" (index.css:381), a shade the system reserves for placeholders/timestamps/disabled states — not page-level taglines, which read more naturally in `--text-secondary` / "Quiet Grey." As written, the subtitle sits close to illegible against `--bg-surface`.
- No "forgot password" affordance anywhere on the Login tab. For a single-user local tool this *might* be an intentional constraint (no server-side mail relay to support resets) — but its silent absence, with no explanatory note, will read as an oversight rather than a decision.
- The card's `2.5rem` padding (index.css:369) and gradient submit button (index.css:415, sanctioned per the system's documented button-primary spec) are both correctly in-system — worth noting as precision amid the larger issues, so the fix doesn't over-correct and strip out things that are actually fine.
