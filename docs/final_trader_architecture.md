# Final trader architecture target

Core layers:
1. Global risk kernel
2. Per-symbol profile store
3. Offline trainer on long history
4. Online recalibration on new trades/candles
5. Regime engine
6. Playbook selector
7. Adaptive trade manager
8. AI second-opinion layer
9. Capital reallocation layer
10. Observability / backtest / walk-forward validation

This phase implements layers 2, 3, 4 and enriches 8.
