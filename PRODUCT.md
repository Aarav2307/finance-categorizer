# Product

## Register

product

## Users

A single person (the developer/owner) using their own personal finance tool for a monthly deep-review session: importing bank statements, correcting AI-generated categorizations, checking recurring subscriptions and billing cycles, and reviewing spending trends across accounts. Sessions are infrequent but focused — the user sits down to reconcile a month at a time, not to glance at a quick daily snapshot. The interface needs to reward sustained attention: dense transaction data, trend comparisons, and correction workflows all need to stay legible and fast over a longer working session.

## Product Purpose

Finance Categorizer ingests bank statements (CSV/PDF from UWCU, Amex, Chase, Wells Fargo), categorizes transactions through a cache → regex → local-LLM pipeline, detects recurring charges and billing cycles, and visualizes spending across multiple accounts — entirely on-device, with no data leaving the machine. Success looks like: categorization the user trusts (and can correct, with the correction sticking), a monthly review that surfaces what changed and what's recurring without digging, and charts that make multi-account spending legible at a glance.

## Brand Personality

Calm, precise, trustworthy. The voice of a well-kept ledger, not a sales pitch — confident in the numbers it shows, quiet about how it shows them. Think modern fintech restraint (Mercury-style): polished surfaces, careful color use, numbers that feel authoritative rather than decorative. No hype, no forced friendliness — the tool earns trust by being legible and correct, not by being charming.

## Anti-references

Generic SaaS dashboard clichés: stock gradient hero cards, cookie-cutter stat tiles, "enterprise analytics" chrome, hero-metric templates, identical card grids. Also avoid gamified consumer-finance-app energy (Mint/Rocket-Money style badges, cartoonish charts, over-friendly mascot copy) — this is a precision tool for someone who already understands their finances, not a tool trying to make budgeting fun.

## Design Principles

- **Numbers are the interface.** Every layout decision should make the data more legible, not more decorative — typography and spacing carry the hierarchy, not chrome.
- **Correction is a first-class workflow.** Categorization will be wrong sometimes; fixing it (and trusting the fix sticks) is as important a flow as viewing data, and should feel just as considered.
- **Calm density over sparse minimalism.** A monthly deep-review session means scanning a lot of transactions and trends in one sitting — favor information density that stays scannable over whitespace for its own sake.
- **Local-first, quietly.** The product's defining trait (nothing leaves the device) should be reflected in a confident, unhurried tone — not over-explained, just present where it matters (auth, upload, settings).
- **Restraint as craft.** Calm and precise means resisting the urge to add visual flourish that doesn't serve comprehension; polish shows up in alignment, contrast, and motion timing, not ornament.

## Accessibility & Inclusion

Standard good practice: WCAG AA contrast for all text and data labels, respect `prefers-reduced-motion` for count-up animations and transitions, and avoid color-only signaling — category charts and delta indicators (better/worse, income/spending) should remain distinguishable through shape, label, or position as well as hue.
