"""
P2-09: TBankExecutionEngine — исполнение ордеров через T-Bank Invest API.

В текущей версии — полная заглушка с структурой для будущей реализации.
Использует PaperExecutionEngine как fallback пока реальный gRPC не подключён.

Когда будет реализовано в полном объёме (TODO):
  - PostOrder через UsersService / OrdersService gRPC
  - Подтверждение исполнения через GetOrders / GetTrades
  - Синхронизация Position с реальным портфелем

ВАЖНО: Никогда не вызывать напрямую без явного trade_mode == "auto_live"
       и двойного подтверждения от пользователя.
"""
import logging

from sqlalchemy.orm import Session

from core.execution.paper import PaperExecutionEngine

logger = logging.getLogger(__name__)


class TBankExecutionEngine:
    """
    Execution engine для реальной торговли через T-Bank Invest gRPC.

    Текущий статус: STUB — делегирует в PaperExecutionEngine с предупреждением.
    Реализация: Phase P2-09 (в разработке).
    """

    def __init__(self, db: Session, token: str, account_id: str, sandbox: bool = True):
        self.db = db
        self.token = token
        self.account_id = account_id
        self.sandbox = sandbox
        self._paper_fallback = PaperExecutionEngine(db)

        if not sandbox:
            logger.critical(
                "TBankExecutionEngine initialized in LIVE mode (sandbox=False). "
                "Real money operations will be performed when fully implemented!"
            )
        else:
            logger.info("TBankExecutionEngine initialized in SANDBOX mode (stub fallback to paper).")

    async def execute_approved_signal(self, signal_id: str) -> None:
        """
        Исполнить сигнал через T-Bank.

        TODO: Реализация через gRPC:
          1. adapter.find_instrument(signal.instrument_id) → figi/uid
          2. adapter.post_order(figi, qty, side, order_type="MARKET")
          3. Дождаться подтверждения через GetOrderState или WebSocket
          4. Создать Order/Trade/Position из реального ответа брокера
          5. Обновить Position.avg_price из реального fill price

        Сейчас: fallback в PaperExecutionEngine с WARNING.
        """
        logger.warning(
            "TBankExecutionEngine.execute_approved_signal(%s): "
            "real gRPC execution NOT YET IMPLEMENTED — falling back to paper.",
            signal_id,
        )
        await self._paper_fallback.execute_approved_signal(signal_id)

    async def close_position(self, instrument_id: str, close_price: float) -> None:
        """
        TODO: Выставить SELL (или BUY для шорта) рыночный ордер через T-Bank.
        Сейчас: делегируем в PaperExecutionEngine.
        """
        logger.warning(
            "TBankExecutionEngine.close_position(%s @ %.4f): stub, using paper.",
            instrument_id, close_price,
        )
        # В paper: закрытие через PositionMonitor._close_position, здесь нет прямого метода
        # Реализовать когда будет gRPC

    async def get_portfolio(self) -> dict:
        """
        TODO: Получить реальный портфель через OperationsService.GetPortfolio.
        Сейчас: заглушка.
        """
        logger.warning("TBankExecutionEngine.get_portfolio(): stub, returning empty.")
        return {
            "total_amount_portfolio": 0.0,
            "total_amount_currencies": 0.0,
            "total_amount_shares": 0.0,
            "expected_yield": 0.0,
        }
