FIX66 audit delta

Target of this phase: move previously weak frontend/UX indicators toward a good baseline.

Addressed in code:
- accessibility semantics for dialogs and switch controls
- keyboard discoverability of help tooltips
- recoverability after UI errors
- settings cognitive load via section quick-nav
- responsive access via bottom navigation
- deterministic timeframe anchoring improved from first-candle anchor to fixed session anchor
- decision-log best-effort path made more robust for test and stub environments

Verified locally:
- backend compile ok
- backend unittest baseline green

Still requires confirmation in the user's environment:
- full frontend build/lint/test cycle after dependency installation
- long auto_paper validation for profitability and stability claims
