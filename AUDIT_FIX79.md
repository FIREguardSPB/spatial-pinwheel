# AUDIT FIX79

## Focus
This phase was not another generic frontend patch. It was targeted at three user-visible regressions:
1. missing chart on dashboard,
2. reduced settings flexibility/informativeness,
3. suspicious trading schedule next-open date.

## Result
- Dashboard is more informative again and now contains a working instrument chart shell plus an equity curve.
- Settings are no longer compressed into one thin card; they are grouped by entity and closer to the intended operational model.
- Trading schedule logic is more robust for MOEX fallback mode and no longer points `next_open` to an obviously wrong future date for the tested Thursday→Friday scenario.

## Remaining honesty notes
- This phase improves schedule sanity and UI structure, but it does not guarantee the broker-provided trading-calendar payload is always complete.
- If broker schedule data is malformed upstream, backend still needs logs for deeper diagnosis.
- The chart depends on candle endpoint/runtime data; if candle cache and broker fetch are both unavailable, it will still degrade to fallback history.
