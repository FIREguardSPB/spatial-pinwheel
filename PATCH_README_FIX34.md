FIX34

- Frontend SSE reconnect logic rewritten to avoid reconnect storms and intrusive notifications.
- Stream disconnect/recovery toasts removed from the reconnect path.
- Added heartbeat event support and idle watchdog based on real stream activity.
- Backend SSE keepalive reduced to 5s and switched from comment ping to explicit heartbeat events.
- Background runtime polling errors (/health and /worker/status) no longer flood global API error state.
