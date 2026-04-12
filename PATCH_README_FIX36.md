FIX36

- убран жёсткий rate-limit для GET /api/v1/signals; чувствительный лимит оставлен только для bot-control и approve/reject сигналов
- 429 на фоновых GET больше не поднимает глобальную аварийную плашку и не спамит toast
- refetch/invalidate по сигналам во фронте задушен: limit уменьшен, invalidation теперь throttled
- статус в шапке больше не орёт API DISCONNECTED, если отвалился только live-stream; вместо этого показывается LIVE UPDATES PAUSED
- глобальный banner больше не показывается только из-за disconnected SSE без реальной backend-error
