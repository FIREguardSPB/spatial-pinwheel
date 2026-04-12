AUDIT FIX69

What improved:
- execution path is now more forensic-friendly: every TAKE execution attempt has explicit unit-of-work metadata
- freeze policy is no longer just threshold-driven; it now exposes streak analytics needed for operator diagnostics
- frontend no longer treats every temporary degraded GET as a hard crash path
- trading schedule snapshot is now usable in UI even without broker calendar

Remaining hard truth:
- this still does not prove live-trader quality by itself
- proof still requires sustained auto_paper run with conversion, PF, DD, regime stability, and signal->trade audit
- strategy edge, exits, and allocation remain the core PnL determinant after these fixes

Recommended next block:
- portfolio-quality layer: execution slippage realism, allocator fairness, exit capture efficiency, repeated weekly live-trader validation snapshot
