# Presets runbook

## Что это
Presets — это snapshots безопасной части live settings. Они помогают быстро переключаться между калиброванными конфигурациями без ручного перебора полей.

## Как пользоваться
1. Открой SettingsPage.
2. В панели Presets выбери существующий preset или нажми «Сохранить текущую как…».
3. Для применения preset посмотри краткий diff и подтверди действие.
4. User-created presets можно удалить, system presets — только читать и применять.

## Что входит в snapshot
- risk / trade / AI / ML thresholds
- filters, sessions, mode, RR, cooldowns
- watchlist (массив instrument_id)

## Что не входит
- telegram_bot_token
- telegram_chat_id
- runtime-only поля и metadata
- поля, которые могут неожиданно изменить состояние рантайма

## Apply semantics
- shallow merge: ключи из preset заменяют текущие live settings
- отсутствующие ключи остаются как есть
- watchlist синхронизируется отдельно
- применение логируется как decision-log event `settings_preset_applied`
