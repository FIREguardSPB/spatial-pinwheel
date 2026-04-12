# FIX65 — validation stage

Что закрыто в этой фазе:
- live trader checklist API
- weekly/regime validation analytics
- validation snapshots
- UI-блок для жёсткой оценки auto_paper как "живого" трейдера

Что добавлено:
- `GET /api/v1/validation/live-checklist?days=45&weeks=8`
- `POST /api/v1/validation/snapshot`
- `GET /api/v1/validation/snapshots`
- сервис `backend/core/services/live_validation.py`
- UI-секция `Live trader checklist` на странице Account
- backend test `test_live_validation.py`

Что оценивает checklist:
- Profit Factor
- Expectancy per trade (нормированная к средней убыточной сделке)
- Max Drawdown
- Hit rate / PF по режимам рынка
- Weekly stability
- Execution quality
- Portfolio discipline
- Post-trade analytics maturity

Проверки:
- `python -m compileall -q backend`
- `PYTHONPATH=backend python -m unittest discover -s backend/tests -p 'test_*.py'`
- transpile-проверка `src/types/index.ts` и `src/features/account/AccountPage.tsx`
