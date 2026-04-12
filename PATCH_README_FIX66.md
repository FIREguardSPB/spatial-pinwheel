FIX66 — frontend/UX hardening + deterministic timeframe anchor

Closed in this phase:
- accessible modal/dialog semantics and keyboard focus handling
- route-scoped error recovery
- settings quick navigation
- mobile bottom navigation and skip link
- type/prop contract drift reduced and core frontend contracts aligned
- deterministic intraday timeframe anchoring to session start
- safer decision-log object instantiation for best-effort telemetry
- backend test baseline restored to green after timeframe-anchor update

Verified locally in this environment:
- python -m compileall -q backend — ok
- PYTHONPATH=backend python -m unittest discover -s backend/tests -p 'test_*.py' — 302 passed, 4 skipped

Not fully confirmed here:
- full npm build/lint/test cycle, because package installation in this container depends on a registry/auth setup that was not consistently available during validation
