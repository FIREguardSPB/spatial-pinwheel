import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class OperationState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    OPERATION_STATE_UNSPECIFIED: _ClassVar[OperationState]
    OPERATION_STATE_EXECUTED: _ClassVar[OperationState]
    OPERATION_STATE_CANCELED: _ClassVar[OperationState]
    OPERATION_STATE_PROGRESS: _ClassVar[OperationState]

class OperationType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    OPERATION_TYPE_UNSPECIFIED: _ClassVar[OperationType]
    OPERATION_TYPE_INPUT: _ClassVar[OperationType]
    OPERATION_TYPE_BOND_TAX: _ClassVar[OperationType]
    OPERATION_TYPE_OUTPUT_SECURITIES: _ClassVar[OperationType]
    OPERATION_TYPE_OVERNIGHT: _ClassVar[OperationType]
    OPERATION_TYPE_TAX: _ClassVar[OperationType]
    OPERATION_TYPE_BOND_REPAYMENT_FULL: _ClassVar[OperationType]
    OPERATION_TYPE_SELL_CARD: _ClassVar[OperationType]
    OPERATION_TYPE_DIVIDEND_TAX: _ClassVar[OperationType]
    OPERATION_TYPE_OUTPUT: _ClassVar[OperationType]
    OPERATION_TYPE_BOND_REPAYMENT: _ClassVar[OperationType]
    OPERATION_TYPE_TAX_CORRECTION: _ClassVar[OperationType]
    OPERATION_TYPE_SERVICE_FEE: _ClassVar[OperationType]
    OPERATION_TYPE_BENEFIT_TAX: _ClassVar[OperationType]
    OPERATION_TYPE_MARGIN_FEE: _ClassVar[OperationType]
    OPERATION_TYPE_BUY: _ClassVar[OperationType]
    OPERATION_TYPE_BUY_CARD: _ClassVar[OperationType]
    OPERATION_TYPE_INPUT_SECURITIES: _ClassVar[OperationType]
    OPERATION_TYPE_SELL_MARGIN: _ClassVar[OperationType]
    OPERATION_TYPE_BROKER_FEE: _ClassVar[OperationType]
    OPERATION_TYPE_BUY_MARGIN: _ClassVar[OperationType]
    OPERATION_TYPE_DIVIDEND: _ClassVar[OperationType]
    OPERATION_TYPE_SELL: _ClassVar[OperationType]
    OPERATION_TYPE_COUPON: _ClassVar[OperationType]
    OPERATION_TYPE_SUCCESS_FEE: _ClassVar[OperationType]
    OPERATION_TYPE_DIVIDEND_TRANSFER: _ClassVar[OperationType]
    OPERATION_TYPE_ACCRUING_VARMARGIN: _ClassVar[OperationType]
    OPERATION_TYPE_WRITING_OFF_VARMARGIN: _ClassVar[OperationType]
    OPERATION_TYPE_DELIVERY_BUY: _ClassVar[OperationType]
    OPERATION_TYPE_DELIVERY_SELL: _ClassVar[OperationType]
    OPERATION_TYPE_TRACK_MFEE: _ClassVar[OperationType]
    OPERATION_TYPE_TRACK_PFEE: _ClassVar[OperationType]
    OPERATION_TYPE_TAX_PROGRESSIVE: _ClassVar[OperationType]
    OPERATION_TYPE_BOND_TAX_PROGRESSIVE: _ClassVar[OperationType]
    OPERATION_TYPE_DIVIDEND_TAX_PROGRESSIVE: _ClassVar[OperationType]
    OPERATION_TYPE_BENEFIT_TAX_PROGRESSIVE: _ClassVar[OperationType]
    OPERATION_TYPE_TAX_CORRECTION_PROGRESSIVE: _ClassVar[OperationType]
    OPERATION_TYPE_TAX_REPO_PROGRESSIVE: _ClassVar[OperationType]
    OPERATION_TYPE_TAX_REPO: _ClassVar[OperationType]
    OPERATION_TYPE_TAX_REPO_HOLD: _ClassVar[OperationType]
    OPERATION_TYPE_TAX_REPO_REFUND: _ClassVar[OperationType]
    OPERATION_TYPE_TAX_REPO_HOLD_PROGRESSIVE: _ClassVar[OperationType]
    OPERATION_TYPE_TAX_REPO_REFUND_PROGRESSIVE: _ClassVar[OperationType]
    OPERATION_TYPE_DIV_EXT: _ClassVar[OperationType]
    OPERATION_TYPE_TAX_CORRECTION_COUPON: _ClassVar[OperationType]
    OPERATION_TYPE_CASH_FEE: _ClassVar[OperationType]
    OPERATION_TYPE_OUT_FEE: _ClassVar[OperationType]
    OPERATION_TYPE_OUT_STAMP_DUTY: _ClassVar[OperationType]
    OPERATION_TYPE_OUTPUT_SWIFT: _ClassVar[OperationType]
    OPERATION_TYPE_INPUT_SWIFT: _ClassVar[OperationType]
    OPERATION_TYPE_OUTPUT_ACQUIRING: _ClassVar[OperationType]
    OPERATION_TYPE_INPUT_ACQUIRING: _ClassVar[OperationType]
    OPERATION_TYPE_OUTPUT_PENALTY: _ClassVar[OperationType]
    OPERATION_TYPE_ADVICE_FEE: _ClassVar[OperationType]
    OPERATION_TYPE_TRANS_IIS_BS: _ClassVar[OperationType]
    OPERATION_TYPE_TRANS_BS_BS: _ClassVar[OperationType]
    OPERATION_TYPE_OUT_MULTI: _ClassVar[OperationType]
    OPERATION_TYPE_INP_MULTI: _ClassVar[OperationType]
    OPERATION_TYPE_OVER_PLACEMENT: _ClassVar[OperationType]
    OPERATION_TYPE_OVER_COM: _ClassVar[OperationType]
    OPERATION_TYPE_OVER_INCOME: _ClassVar[OperationType]
    OPERATION_TYPE_OPTION_EXPIRATION: _ClassVar[OperationType]

class PortfolioSubscriptionStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PORTFOLIO_SUBSCRIPTION_STATUS_UNSPECIFIED: _ClassVar[PortfolioSubscriptionStatus]
    PORTFOLIO_SUBSCRIPTION_STATUS_SUCCESS: _ClassVar[PortfolioSubscriptionStatus]
    PORTFOLIO_SUBSCRIPTION_STATUS_ACCOUNT_NOT_FOUND: _ClassVar[PortfolioSubscriptionStatus]
    PORTFOLIO_SUBSCRIPTION_STATUS_INTERNAL_ERROR: _ClassVar[PortfolioSubscriptionStatus]

class PositionsAccountSubscriptionStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    POSITIONS_SUBSCRIPTION_STATUS_UNSPECIFIED: _ClassVar[PositionsAccountSubscriptionStatus]
    POSITIONS_SUBSCRIPTION_STATUS_SUCCESS: _ClassVar[PositionsAccountSubscriptionStatus]
    POSITIONS_SUBSCRIPTION_STATUS_ACCOUNT_NOT_FOUND: _ClassVar[PositionsAccountSubscriptionStatus]
    POSITIONS_SUBSCRIPTION_STATUS_INTERNAL_ERROR: _ClassVar[PositionsAccountSubscriptionStatus]
OPERATION_STATE_UNSPECIFIED: OperationState
OPERATION_STATE_EXECUTED: OperationState
OPERATION_STATE_CANCELED: OperationState
OPERATION_STATE_PROGRESS: OperationState
OPERATION_TYPE_UNSPECIFIED: OperationType
OPERATION_TYPE_INPUT: OperationType
OPERATION_TYPE_BOND_TAX: OperationType
OPERATION_TYPE_OUTPUT_SECURITIES: OperationType
OPERATION_TYPE_OVERNIGHT: OperationType
OPERATION_TYPE_TAX: OperationType
OPERATION_TYPE_BOND_REPAYMENT_FULL: OperationType
OPERATION_TYPE_SELL_CARD: OperationType
OPERATION_TYPE_DIVIDEND_TAX: OperationType
OPERATION_TYPE_OUTPUT: OperationType
OPERATION_TYPE_BOND_REPAYMENT: OperationType
OPERATION_TYPE_TAX_CORRECTION: OperationType
OPERATION_TYPE_SERVICE_FEE: OperationType
OPERATION_TYPE_BENEFIT_TAX: OperationType
OPERATION_TYPE_MARGIN_FEE: OperationType
OPERATION_TYPE_BUY: OperationType
OPERATION_TYPE_BUY_CARD: OperationType
OPERATION_TYPE_INPUT_SECURITIES: OperationType
OPERATION_TYPE_SELL_MARGIN: OperationType
OPERATION_TYPE_BROKER_FEE: OperationType
OPERATION_TYPE_BUY_MARGIN: OperationType
OPERATION_TYPE_DIVIDEND: OperationType
OPERATION_TYPE_SELL: OperationType
OPERATION_TYPE_COUPON: OperationType
OPERATION_TYPE_SUCCESS_FEE: OperationType
OPERATION_TYPE_DIVIDEND_TRANSFER: OperationType
OPERATION_TYPE_ACCRUING_VARMARGIN: OperationType
OPERATION_TYPE_WRITING_OFF_VARMARGIN: OperationType
OPERATION_TYPE_DELIVERY_BUY: OperationType
OPERATION_TYPE_DELIVERY_SELL: OperationType
OPERATION_TYPE_TRACK_MFEE: OperationType
OPERATION_TYPE_TRACK_PFEE: OperationType
OPERATION_TYPE_TAX_PROGRESSIVE: OperationType
OPERATION_TYPE_BOND_TAX_PROGRESSIVE: OperationType
OPERATION_TYPE_DIVIDEND_TAX_PROGRESSIVE: OperationType
OPERATION_TYPE_BENEFIT_TAX_PROGRESSIVE: OperationType
OPERATION_TYPE_TAX_CORRECTION_PROGRESSIVE: OperationType
OPERATION_TYPE_TAX_REPO_PROGRESSIVE: OperationType
OPERATION_TYPE_TAX_REPO: OperationType
OPERATION_TYPE_TAX_REPO_HOLD: OperationType
OPERATION_TYPE_TAX_REPO_REFUND: OperationType
OPERATION_TYPE_TAX_REPO_HOLD_PROGRESSIVE: OperationType
OPERATION_TYPE_TAX_REPO_REFUND_PROGRESSIVE: OperationType
OPERATION_TYPE_DIV_EXT: OperationType
OPERATION_TYPE_TAX_CORRECTION_COUPON: OperationType
OPERATION_TYPE_CASH_FEE: OperationType
OPERATION_TYPE_OUT_FEE: OperationType
OPERATION_TYPE_OUT_STAMP_DUTY: OperationType
OPERATION_TYPE_OUTPUT_SWIFT: OperationType
OPERATION_TYPE_INPUT_SWIFT: OperationType
OPERATION_TYPE_OUTPUT_ACQUIRING: OperationType
OPERATION_TYPE_INPUT_ACQUIRING: OperationType
OPERATION_TYPE_OUTPUT_PENALTY: OperationType
OPERATION_TYPE_ADVICE_FEE: OperationType
OPERATION_TYPE_TRANS_IIS_BS: OperationType
OPERATION_TYPE_TRANS_BS_BS: OperationType
OPERATION_TYPE_OUT_MULTI: OperationType
OPERATION_TYPE_INP_MULTI: OperationType
OPERATION_TYPE_OVER_PLACEMENT: OperationType
OPERATION_TYPE_OVER_COM: OperationType
OPERATION_TYPE_OVER_INCOME: OperationType
OPERATION_TYPE_OPTION_EXPIRATION: OperationType
PORTFOLIO_SUBSCRIPTION_STATUS_UNSPECIFIED: PortfolioSubscriptionStatus
PORTFOLIO_SUBSCRIPTION_STATUS_SUCCESS: PortfolioSubscriptionStatus
PORTFOLIO_SUBSCRIPTION_STATUS_ACCOUNT_NOT_FOUND: PortfolioSubscriptionStatus
PORTFOLIO_SUBSCRIPTION_STATUS_INTERNAL_ERROR: PortfolioSubscriptionStatus
POSITIONS_SUBSCRIPTION_STATUS_UNSPECIFIED: PositionsAccountSubscriptionStatus
POSITIONS_SUBSCRIPTION_STATUS_SUCCESS: PositionsAccountSubscriptionStatus
POSITIONS_SUBSCRIPTION_STATUS_ACCOUNT_NOT_FOUND: PositionsAccountSubscriptionStatus
POSITIONS_SUBSCRIPTION_STATUS_INTERNAL_ERROR: PositionsAccountSubscriptionStatus

class OperationsRequest(_message.Message):
    __slots__ = ("account_id", "to", "state", "figi")
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    FROM_FIELD_NUMBER: _ClassVar[int]
    TO_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    FIGI_FIELD_NUMBER: _ClassVar[int]
    account_id: str
    to: _timestamp_pb2.Timestamp
    state: OperationState
    figi: str
    def __init__(self, account_id: _Optional[str] = ..., to: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., state: _Optional[_Union[OperationState, str]] = ..., figi: _Optional[str] = ..., **kwargs) -> None: ...

class OperationsResponse(_message.Message):
    __slots__ = ("operations",)
    OPERATIONS_FIELD_NUMBER: _ClassVar[int]
    operations: _containers.RepeatedCompositeFieldContainer[Operation]
    def __init__(self, operations: _Optional[_Iterable[_Union[Operation, _Mapping]]] = ...) -> None: ...

class Operation(_message.Message):
    __slots__ = ("id", "parent_operation_id", "currency", "payment", "price", "state", "quantity", "quantity_rest", "figi", "instrument_type", "date", "type", "operation_type", "trades", "asset_uid", "position_uid", "instrument_uid")
    ID_FIELD_NUMBER: _ClassVar[int]
    PARENT_OPERATION_ID_FIELD_NUMBER: _ClassVar[int]
    CURRENCY_FIELD_NUMBER: _ClassVar[int]
    PAYMENT_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_REST_FIELD_NUMBER: _ClassVar[int]
    FIGI_FIELD_NUMBER: _ClassVar[int]
    INSTRUMENT_TYPE_FIELD_NUMBER: _ClassVar[int]
    DATE_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    OPERATION_TYPE_FIELD_NUMBER: _ClassVar[int]
    TRADES_FIELD_NUMBER: _ClassVar[int]
    ASSET_UID_FIELD_NUMBER: _ClassVar[int]
    POSITION_UID_FIELD_NUMBER: _ClassVar[int]
    INSTRUMENT_UID_FIELD_NUMBER: _ClassVar[int]
    id: str
    parent_operation_id: str
    currency: str
    payment: _common_pb2.MoneyValue
    price: _common_pb2.MoneyValue
    state: OperationState
    quantity: int
    quantity_rest: int
    figi: str
    instrument_type: str
    date: _timestamp_pb2.Timestamp
    type: str
    operation_type: OperationType
    trades: _containers.RepeatedCompositeFieldContainer[OperationTrade]
    asset_uid: str
    position_uid: str
    instrument_uid: str
    def __init__(self, id: _Optional[str] = ..., parent_operation_id: _Optional[str] = ..., currency: _Optional[str] = ..., payment: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., price: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., state: _Optional[_Union[OperationState, str]] = ..., quantity: _Optional[int] = ..., quantity_rest: _Optional[int] = ..., figi: _Optional[str] = ..., instrument_type: _Optional[str] = ..., date: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., type: _Optional[str] = ..., operation_type: _Optional[_Union[OperationType, str]] = ..., trades: _Optional[_Iterable[_Union[OperationTrade, _Mapping]]] = ..., asset_uid: _Optional[str] = ..., position_uid: _Optional[str] = ..., instrument_uid: _Optional[str] = ...) -> None: ...

class OperationTrade(_message.Message):
    __slots__ = ("trade_id", "date_time", "quantity", "price")
    TRADE_ID_FIELD_NUMBER: _ClassVar[int]
    DATE_TIME_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    trade_id: str
    date_time: _timestamp_pb2.Timestamp
    quantity: int
    price: _common_pb2.MoneyValue
    def __init__(self, trade_id: _Optional[str] = ..., date_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., quantity: _Optional[int] = ..., price: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ...) -> None: ...

class PortfolioRequest(_message.Message):
    __slots__ = ("account_id", "currency")
    class CurrencyRequest(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        RUB: _ClassVar[PortfolioRequest.CurrencyRequest]
        USD: _ClassVar[PortfolioRequest.CurrencyRequest]
        EUR: _ClassVar[PortfolioRequest.CurrencyRequest]
    RUB: PortfolioRequest.CurrencyRequest
    USD: PortfolioRequest.CurrencyRequest
    EUR: PortfolioRequest.CurrencyRequest
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    CURRENCY_FIELD_NUMBER: _ClassVar[int]
    account_id: str
    currency: PortfolioRequest.CurrencyRequest
    def __init__(self, account_id: _Optional[str] = ..., currency: _Optional[_Union[PortfolioRequest.CurrencyRequest, str]] = ...) -> None: ...

class PortfolioResponse(_message.Message):
    __slots__ = ("total_amount_shares", "total_amount_bonds", "total_amount_etf", "total_amount_currencies", "total_amount_futures", "expected_yield", "positions", "account_id", "total_amount_options", "total_amount_sp", "total_amount_portfolio", "virtual_positions")
    TOTAL_AMOUNT_SHARES_FIELD_NUMBER: _ClassVar[int]
    TOTAL_AMOUNT_BONDS_FIELD_NUMBER: _ClassVar[int]
    TOTAL_AMOUNT_ETF_FIELD_NUMBER: _ClassVar[int]
    TOTAL_AMOUNT_CURRENCIES_FIELD_NUMBER: _ClassVar[int]
    TOTAL_AMOUNT_FUTURES_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_YIELD_FIELD_NUMBER: _ClassVar[int]
    POSITIONS_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    TOTAL_AMOUNT_OPTIONS_FIELD_NUMBER: _ClassVar[int]
    TOTAL_AMOUNT_SP_FIELD_NUMBER: _ClassVar[int]
    TOTAL_AMOUNT_PORTFOLIO_FIELD_NUMBER: _ClassVar[int]
    VIRTUAL_POSITIONS_FIELD_NUMBER: _ClassVar[int]
    total_amount_shares: _common_pb2.MoneyValue
    total_amount_bonds: _common_pb2.MoneyValue
    total_amount_etf: _common_pb2.MoneyValue
    total_amount_currencies: _common_pb2.MoneyValue
    total_amount_futures: _common_pb2.MoneyValue
    expected_yield: _common_pb2.Quotation
    positions: _containers.RepeatedCompositeFieldContainer[PortfolioPosition]
    account_id: str
    total_amount_options: _common_pb2.MoneyValue
    total_amount_sp: _common_pb2.MoneyValue
    total_amount_portfolio: _common_pb2.MoneyValue
    virtual_positions: _containers.RepeatedCompositeFieldContainer[VirtualPortfolioPosition]
    def __init__(self, total_amount_shares: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., total_amount_bonds: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., total_amount_etf: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., total_amount_currencies: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., total_amount_futures: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., expected_yield: _Optional[_Union[_common_pb2.Quotation, _Mapping]] = ..., positions: _Optional[_Iterable[_Union[PortfolioPosition, _Mapping]]] = ..., account_id: _Optional[str] = ..., total_amount_options: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., total_amount_sp: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., total_amount_portfolio: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., virtual_positions: _Optional[_Iterable[_Union[VirtualPortfolioPosition, _Mapping]]] = ...) -> None: ...

class PositionsRequest(_message.Message):
    __slots__ = ("account_id",)
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    account_id: str
    def __init__(self, account_id: _Optional[str] = ...) -> None: ...

class PositionsResponse(_message.Message):
    __slots__ = ("money", "blocked", "securities", "limits_loading_in_progress", "futures", "options")
    MONEY_FIELD_NUMBER: _ClassVar[int]
    BLOCKED_FIELD_NUMBER: _ClassVar[int]
    SECURITIES_FIELD_NUMBER: _ClassVar[int]
    LIMITS_LOADING_IN_PROGRESS_FIELD_NUMBER: _ClassVar[int]
    FUTURES_FIELD_NUMBER: _ClassVar[int]
    OPTIONS_FIELD_NUMBER: _ClassVar[int]
    money: _containers.RepeatedCompositeFieldContainer[_common_pb2.MoneyValue]
    blocked: _containers.RepeatedCompositeFieldContainer[_common_pb2.MoneyValue]
    securities: _containers.RepeatedCompositeFieldContainer[PositionsSecurities]
    limits_loading_in_progress: bool
    futures: _containers.RepeatedCompositeFieldContainer[PositionsFutures]
    options: _containers.RepeatedCompositeFieldContainer[PositionsOptions]
    def __init__(self, money: _Optional[_Iterable[_Union[_common_pb2.MoneyValue, _Mapping]]] = ..., blocked: _Optional[_Iterable[_Union[_common_pb2.MoneyValue, _Mapping]]] = ..., securities: _Optional[_Iterable[_Union[PositionsSecurities, _Mapping]]] = ..., limits_loading_in_progress: bool = ..., futures: _Optional[_Iterable[_Union[PositionsFutures, _Mapping]]] = ..., options: _Optional[_Iterable[_Union[PositionsOptions, _Mapping]]] = ...) -> None: ...

class WithdrawLimitsRequest(_message.Message):
    __slots__ = ("account_id",)
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    account_id: str
    def __init__(self, account_id: _Optional[str] = ...) -> None: ...

class WithdrawLimitsResponse(_message.Message):
    __slots__ = ("money", "blocked", "blocked_guarantee")
    MONEY_FIELD_NUMBER: _ClassVar[int]
    BLOCKED_FIELD_NUMBER: _ClassVar[int]
    BLOCKED_GUARANTEE_FIELD_NUMBER: _ClassVar[int]
    money: _containers.RepeatedCompositeFieldContainer[_common_pb2.MoneyValue]
    blocked: _containers.RepeatedCompositeFieldContainer[_common_pb2.MoneyValue]
    blocked_guarantee: _containers.RepeatedCompositeFieldContainer[_common_pb2.MoneyValue]
    def __init__(self, money: _Optional[_Iterable[_Union[_common_pb2.MoneyValue, _Mapping]]] = ..., blocked: _Optional[_Iterable[_Union[_common_pb2.MoneyValue, _Mapping]]] = ..., blocked_guarantee: _Optional[_Iterable[_Union[_common_pb2.MoneyValue, _Mapping]]] = ...) -> None: ...

class PortfolioPosition(_message.Message):
    __slots__ = ("figi", "instrument_type", "quantity", "average_position_price", "expected_yield", "current_nkd", "average_position_price_pt", "current_price", "average_position_price_fifo", "quantity_lots", "blocked", "blocked_lots", "position_uid", "instrument_uid", "var_margin", "expected_yield_fifo")
    FIGI_FIELD_NUMBER: _ClassVar[int]
    INSTRUMENT_TYPE_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    AVERAGE_POSITION_PRICE_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_YIELD_FIELD_NUMBER: _ClassVar[int]
    CURRENT_NKD_FIELD_NUMBER: _ClassVar[int]
    AVERAGE_POSITION_PRICE_PT_FIELD_NUMBER: _ClassVar[int]
    CURRENT_PRICE_FIELD_NUMBER: _ClassVar[int]
    AVERAGE_POSITION_PRICE_FIFO_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_LOTS_FIELD_NUMBER: _ClassVar[int]
    BLOCKED_FIELD_NUMBER: _ClassVar[int]
    BLOCKED_LOTS_FIELD_NUMBER: _ClassVar[int]
    POSITION_UID_FIELD_NUMBER: _ClassVar[int]
    INSTRUMENT_UID_FIELD_NUMBER: _ClassVar[int]
    VAR_MARGIN_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_YIELD_FIFO_FIELD_NUMBER: _ClassVar[int]
    figi: str
    instrument_type: str
    quantity: _common_pb2.Quotation
    average_position_price: _common_pb2.MoneyValue
    expected_yield: _common_pb2.Quotation
    current_nkd: _common_pb2.MoneyValue
    average_position_price_pt: _common_pb2.Quotation
    current_price: _common_pb2.MoneyValue
    average_position_price_fifo: _common_pb2.MoneyValue
    quantity_lots: _common_pb2.Quotation
    blocked: bool
    blocked_lots: _common_pb2.Quotation
    position_uid: str
    instrument_uid: str
    var_margin: _common_pb2.MoneyValue
    expected_yield_fifo: _common_pb2.Quotation
    def __init__(self, figi: _Optional[str] = ..., instrument_type: _Optional[str] = ..., quantity: _Optional[_Union[_common_pb2.Quotation, _Mapping]] = ..., average_position_price: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., expected_yield: _Optional[_Union[_common_pb2.Quotation, _Mapping]] = ..., current_nkd: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., average_position_price_pt: _Optional[_Union[_common_pb2.Quotation, _Mapping]] = ..., current_price: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., average_position_price_fifo: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., quantity_lots: _Optional[_Union[_common_pb2.Quotation, _Mapping]] = ..., blocked: bool = ..., blocked_lots: _Optional[_Union[_common_pb2.Quotation, _Mapping]] = ..., position_uid: _Optional[str] = ..., instrument_uid: _Optional[str] = ..., var_margin: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., expected_yield_fifo: _Optional[_Union[_common_pb2.Quotation, _Mapping]] = ...) -> None: ...

class VirtualPortfolioPosition(_message.Message):
    __slots__ = ("position_uid", "instrument_uid", "figi", "instrument_type", "quantity", "average_position_price", "expected_yield", "expected_yield_fifo", "expire_date", "current_price", "average_position_price_fifo")
    POSITION_UID_FIELD_NUMBER: _ClassVar[int]
    INSTRUMENT_UID_FIELD_NUMBER: _ClassVar[int]
    FIGI_FIELD_NUMBER: _ClassVar[int]
    INSTRUMENT_TYPE_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    AVERAGE_POSITION_PRICE_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_YIELD_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_YIELD_FIFO_FIELD_NUMBER: _ClassVar[int]
    EXPIRE_DATE_FIELD_NUMBER: _ClassVar[int]
    CURRENT_PRICE_FIELD_NUMBER: _ClassVar[int]
    AVERAGE_POSITION_PRICE_FIFO_FIELD_NUMBER: _ClassVar[int]
    position_uid: str
    instrument_uid: str
    figi: str
    instrument_type: str
    quantity: _common_pb2.Quotation
    average_position_price: _common_pb2.MoneyValue
    expected_yield: _common_pb2.Quotation
    expected_yield_fifo: _common_pb2.Quotation
    expire_date: _timestamp_pb2.Timestamp
    current_price: _common_pb2.MoneyValue
    average_position_price_fifo: _common_pb2.MoneyValue
    def __init__(self, position_uid: _Optional[str] = ..., instrument_uid: _Optional[str] = ..., figi: _Optional[str] = ..., instrument_type: _Optional[str] = ..., quantity: _Optional[_Union[_common_pb2.Quotation, _Mapping]] = ..., average_position_price: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., expected_yield: _Optional[_Union[_common_pb2.Quotation, _Mapping]] = ..., expected_yield_fifo: _Optional[_Union[_common_pb2.Quotation, _Mapping]] = ..., expire_date: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., current_price: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., average_position_price_fifo: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ...) -> None: ...

class PositionsSecurities(_message.Message):
    __slots__ = ("figi", "blocked", "balance", "position_uid", "instrument_uid", "exchange_blocked", "instrument_type")
    FIGI_FIELD_NUMBER: _ClassVar[int]
    BLOCKED_FIELD_NUMBER: _ClassVar[int]
    BALANCE_FIELD_NUMBER: _ClassVar[int]
    POSITION_UID_FIELD_NUMBER: _ClassVar[int]
    INSTRUMENT_UID_FIELD_NUMBER: _ClassVar[int]
    EXCHANGE_BLOCKED_FIELD_NUMBER: _ClassVar[int]
    INSTRUMENT_TYPE_FIELD_NUMBER: _ClassVar[int]
    figi: str
    blocked: int
    balance: int
    position_uid: str
    instrument_uid: str
    exchange_blocked: bool
    instrument_type: str
    def __init__(self, figi: _Optional[str] = ..., blocked: _Optional[int] = ..., balance: _Optional[int] = ..., position_uid: _Optional[str] = ..., instrument_uid: _Optional[str] = ..., exchange_blocked: bool = ..., instrument_type: _Optional[str] = ...) -> None: ...

class PositionsFutures(_message.Message):
    __slots__ = ("figi", "blocked", "balance", "position_uid", "instrument_uid")
    FIGI_FIELD_NUMBER: _ClassVar[int]
    BLOCKED_FIELD_NUMBER: _ClassVar[int]
    BALANCE_FIELD_NUMBER: _ClassVar[int]
    POSITION_UID_FIELD_NUMBER: _ClassVar[int]
    INSTRUMENT_UID_FIELD_NUMBER: _ClassVar[int]
    figi: str
    blocked: int
    balance: int
    position_uid: str
    instrument_uid: str
    def __init__(self, figi: _Optional[str] = ..., blocked: _Optional[int] = ..., balance: _Optional[int] = ..., position_uid: _Optional[str] = ..., instrument_uid: _Optional[str] = ...) -> None: ...

class PositionsOptions(_message.Message):
    __slots__ = ("position_uid", "instrument_uid", "blocked", "balance")
    POSITION_UID_FIELD_NUMBER: _ClassVar[int]
    INSTRUMENT_UID_FIELD_NUMBER: _ClassVar[int]
    BLOCKED_FIELD_NUMBER: _ClassVar[int]
    BALANCE_FIELD_NUMBER: _ClassVar[int]
    position_uid: str
    instrument_uid: str
    blocked: int
    balance: int
    def __init__(self, position_uid: _Optional[str] = ..., instrument_uid: _Optional[str] = ..., blocked: _Optional[int] = ..., balance: _Optional[int] = ...) -> None: ...

class BrokerReportRequest(_message.Message):
    __slots__ = ("generate_broker_report_request", "get_broker_report_request")
    GENERATE_BROKER_REPORT_REQUEST_FIELD_NUMBER: _ClassVar[int]
    GET_BROKER_REPORT_REQUEST_FIELD_NUMBER: _ClassVar[int]
    generate_broker_report_request: GenerateBrokerReportRequest
    get_broker_report_request: GetBrokerReportRequest
    def __init__(self, generate_broker_report_request: _Optional[_Union[GenerateBrokerReportRequest, _Mapping]] = ..., get_broker_report_request: _Optional[_Union[GetBrokerReportRequest, _Mapping]] = ...) -> None: ...

class BrokerReportResponse(_message.Message):
    __slots__ = ("generate_broker_report_response", "get_broker_report_response")
    GENERATE_BROKER_REPORT_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    GET_BROKER_REPORT_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    generate_broker_report_response: GenerateBrokerReportResponse
    get_broker_report_response: GetBrokerReportResponse
    def __init__(self, generate_broker_report_response: _Optional[_Union[GenerateBrokerReportResponse, _Mapping]] = ..., get_broker_report_response: _Optional[_Union[GetBrokerReportResponse, _Mapping]] = ...) -> None: ...

class GenerateBrokerReportRequest(_message.Message):
    __slots__ = ("account_id", "to")
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    FROM_FIELD_NUMBER: _ClassVar[int]
    TO_FIELD_NUMBER: _ClassVar[int]
    account_id: str
    to: _timestamp_pb2.Timestamp
    def __init__(self, account_id: _Optional[str] = ..., to: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., **kwargs) -> None: ...

class GenerateBrokerReportResponse(_message.Message):
    __slots__ = ("task_id",)
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    def __init__(self, task_id: _Optional[str] = ...) -> None: ...

class GetBrokerReportRequest(_message.Message):
    __slots__ = ("task_id", "page")
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    PAGE_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    page: int
    def __init__(self, task_id: _Optional[str] = ..., page: _Optional[int] = ...) -> None: ...

class GetBrokerReportResponse(_message.Message):
    __slots__ = ("broker_report", "itemsCount", "pagesCount", "page")
    BROKER_REPORT_FIELD_NUMBER: _ClassVar[int]
    ITEMSCOUNT_FIELD_NUMBER: _ClassVar[int]
    PAGESCOUNT_FIELD_NUMBER: _ClassVar[int]
    PAGE_FIELD_NUMBER: _ClassVar[int]
    broker_report: _containers.RepeatedCompositeFieldContainer[BrokerReport]
    itemsCount: int
    pagesCount: int
    page: int
    def __init__(self, broker_report: _Optional[_Iterable[_Union[BrokerReport, _Mapping]]] = ..., itemsCount: _Optional[int] = ..., pagesCount: _Optional[int] = ..., page: _Optional[int] = ...) -> None: ...

class BrokerReport(_message.Message):
    __slots__ = ("trade_id", "order_id", "figi", "execute_sign", "trade_datetime", "exchange", "class_code", "direction", "name", "ticker", "price", "quantity", "order_amount", "aci_value", "total_order_amount", "broker_commission", "exchange_commission", "exchange_clearing_commission", "repo_rate", "party", "clear_value_date", "sec_value_date", "broker_status", "separate_agreement_type", "separate_agreement_number", "separate_agreement_date", "delivery_type")
    TRADE_ID_FIELD_NUMBER: _ClassVar[int]
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    FIGI_FIELD_NUMBER: _ClassVar[int]
    EXECUTE_SIGN_FIELD_NUMBER: _ClassVar[int]
    TRADE_DATETIME_FIELD_NUMBER: _ClassVar[int]
    EXCHANGE_FIELD_NUMBER: _ClassVar[int]
    CLASS_CODE_FIELD_NUMBER: _ClassVar[int]
    DIRECTION_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    TICKER_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    ORDER_AMOUNT_FIELD_NUMBER: _ClassVar[int]
    ACI_VALUE_FIELD_NUMBER: _ClassVar[int]
    TOTAL_ORDER_AMOUNT_FIELD_NUMBER: _ClassVar[int]
    BROKER_COMMISSION_FIELD_NUMBER: _ClassVar[int]
    EXCHANGE_COMMISSION_FIELD_NUMBER: _ClassVar[int]
    EXCHANGE_CLEARING_COMMISSION_FIELD_NUMBER: _ClassVar[int]
    REPO_RATE_FIELD_NUMBER: _ClassVar[int]
    PARTY_FIELD_NUMBER: _ClassVar[int]
    CLEAR_VALUE_DATE_FIELD_NUMBER: _ClassVar[int]
    SEC_VALUE_DATE_FIELD_NUMBER: _ClassVar[int]
    BROKER_STATUS_FIELD_NUMBER: _ClassVar[int]
    SEPARATE_AGREEMENT_TYPE_FIELD_NUMBER: _ClassVar[int]
    SEPARATE_AGREEMENT_NUMBER_FIELD_NUMBER: _ClassVar[int]
    SEPARATE_AGREEMENT_DATE_FIELD_NUMBER: _ClassVar[int]
    DELIVERY_TYPE_FIELD_NUMBER: _ClassVar[int]
    trade_id: str
    order_id: str
    figi: str
    execute_sign: str
    trade_datetime: _timestamp_pb2.Timestamp
    exchange: str
    class_code: str
    direction: str
    name: str
    ticker: str
    price: _common_pb2.MoneyValue
    quantity: int
    order_amount: _common_pb2.MoneyValue
    aci_value: _common_pb2.Quotation
    total_order_amount: _common_pb2.MoneyValue
    broker_commission: _common_pb2.MoneyValue
    exchange_commission: _common_pb2.MoneyValue
    exchange_clearing_commission: _common_pb2.MoneyValue
    repo_rate: _common_pb2.Quotation
    party: str
    clear_value_date: _timestamp_pb2.Timestamp
    sec_value_date: _timestamp_pb2.Timestamp
    broker_status: str
    separate_agreement_type: str
    separate_agreement_number: str
    separate_agreement_date: str
    delivery_type: str
    def __init__(self, trade_id: _Optional[str] = ..., order_id: _Optional[str] = ..., figi: _Optional[str] = ..., execute_sign: _Optional[str] = ..., trade_datetime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., exchange: _Optional[str] = ..., class_code: _Optional[str] = ..., direction: _Optional[str] = ..., name: _Optional[str] = ..., ticker: _Optional[str] = ..., price: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., quantity: _Optional[int] = ..., order_amount: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., aci_value: _Optional[_Union[_common_pb2.Quotation, _Mapping]] = ..., total_order_amount: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., broker_commission: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., exchange_commission: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., exchange_clearing_commission: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., repo_rate: _Optional[_Union[_common_pb2.Quotation, _Mapping]] = ..., party: _Optional[str] = ..., clear_value_date: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., sec_value_date: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., broker_status: _Optional[str] = ..., separate_agreement_type: _Optional[str] = ..., separate_agreement_number: _Optional[str] = ..., separate_agreement_date: _Optional[str] = ..., delivery_type: _Optional[str] = ...) -> None: ...

class GetDividendsForeignIssuerRequest(_message.Message):
    __slots__ = ("generate_div_foreign_issuer_report", "get_div_foreign_issuer_report")
    GENERATE_DIV_FOREIGN_ISSUER_REPORT_FIELD_NUMBER: _ClassVar[int]
    GET_DIV_FOREIGN_ISSUER_REPORT_FIELD_NUMBER: _ClassVar[int]
    generate_div_foreign_issuer_report: GenerateDividendsForeignIssuerReportRequest
    get_div_foreign_issuer_report: GetDividendsForeignIssuerReportRequest
    def __init__(self, generate_div_foreign_issuer_report: _Optional[_Union[GenerateDividendsForeignIssuerReportRequest, _Mapping]] = ..., get_div_foreign_issuer_report: _Optional[_Union[GetDividendsForeignIssuerReportRequest, _Mapping]] = ...) -> None: ...

class GetDividendsForeignIssuerResponse(_message.Message):
    __slots__ = ("generate_div_foreign_issuer_report_response", "div_foreign_issuer_report")
    GENERATE_DIV_FOREIGN_ISSUER_REPORT_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    DIV_FOREIGN_ISSUER_REPORT_FIELD_NUMBER: _ClassVar[int]
    generate_div_foreign_issuer_report_response: GenerateDividendsForeignIssuerReportResponse
    div_foreign_issuer_report: GetDividendsForeignIssuerReportResponse
    def __init__(self, generate_div_foreign_issuer_report_response: _Optional[_Union[GenerateDividendsForeignIssuerReportResponse, _Mapping]] = ..., div_foreign_issuer_report: _Optional[_Union[GetDividendsForeignIssuerReportResponse, _Mapping]] = ...) -> None: ...

class GenerateDividendsForeignIssuerReportRequest(_message.Message):
    __slots__ = ("account_id", "to")
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    FROM_FIELD_NUMBER: _ClassVar[int]
    TO_FIELD_NUMBER: _ClassVar[int]
    account_id: str
    to: _timestamp_pb2.Timestamp
    def __init__(self, account_id: _Optional[str] = ..., to: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., **kwargs) -> None: ...

class GetDividendsForeignIssuerReportRequest(_message.Message):
    __slots__ = ("task_id", "page")
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    PAGE_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    page: int
    def __init__(self, task_id: _Optional[str] = ..., page: _Optional[int] = ...) -> None: ...

class GenerateDividendsForeignIssuerReportResponse(_message.Message):
    __slots__ = ("task_id",)
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    def __init__(self, task_id: _Optional[str] = ...) -> None: ...

class GetDividendsForeignIssuerReportResponse(_message.Message):
    __slots__ = ("dividends_foreign_issuer_report", "itemsCount", "pagesCount", "page")
    DIVIDENDS_FOREIGN_ISSUER_REPORT_FIELD_NUMBER: _ClassVar[int]
    ITEMSCOUNT_FIELD_NUMBER: _ClassVar[int]
    PAGESCOUNT_FIELD_NUMBER: _ClassVar[int]
    PAGE_FIELD_NUMBER: _ClassVar[int]
    dividends_foreign_issuer_report: _containers.RepeatedCompositeFieldContainer[DividendsForeignIssuerReport]
    itemsCount: int
    pagesCount: int
    page: int
    def __init__(self, dividends_foreign_issuer_report: _Optional[_Iterable[_Union[DividendsForeignIssuerReport, _Mapping]]] = ..., itemsCount: _Optional[int] = ..., pagesCount: _Optional[int] = ..., page: _Optional[int] = ...) -> None: ...

class DividendsForeignIssuerReport(_message.Message):
    __slots__ = ("record_date", "payment_date", "security_name", "isin", "issuer_country", "quantity", "dividend", "external_commission", "dividend_gross", "tax", "dividend_amount", "currency")
    RECORD_DATE_FIELD_NUMBER: _ClassVar[int]
    PAYMENT_DATE_FIELD_NUMBER: _ClassVar[int]
    SECURITY_NAME_FIELD_NUMBER: _ClassVar[int]
    ISIN_FIELD_NUMBER: _ClassVar[int]
    ISSUER_COUNTRY_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    DIVIDEND_FIELD_NUMBER: _ClassVar[int]
    EXTERNAL_COMMISSION_FIELD_NUMBER: _ClassVar[int]
    DIVIDEND_GROSS_FIELD_NUMBER: _ClassVar[int]
    TAX_FIELD_NUMBER: _ClassVar[int]
    DIVIDEND_AMOUNT_FIELD_NUMBER: _ClassVar[int]
    CURRENCY_FIELD_NUMBER: _ClassVar[int]
    record_date: _timestamp_pb2.Timestamp
    payment_date: _timestamp_pb2.Timestamp
    security_name: str
    isin: str
    issuer_country: str
    quantity: int
    dividend: _common_pb2.Quotation
    external_commission: _common_pb2.Quotation
    dividend_gross: _common_pb2.Quotation
    tax: _common_pb2.Quotation
    dividend_amount: _common_pb2.Quotation
    currency: str
    def __init__(self, record_date: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., payment_date: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., security_name: _Optional[str] = ..., isin: _Optional[str] = ..., issuer_country: _Optional[str] = ..., quantity: _Optional[int] = ..., dividend: _Optional[_Union[_common_pb2.Quotation, _Mapping]] = ..., external_commission: _Optional[_Union[_common_pb2.Quotation, _Mapping]] = ..., dividend_gross: _Optional[_Union[_common_pb2.Quotation, _Mapping]] = ..., tax: _Optional[_Union[_common_pb2.Quotation, _Mapping]] = ..., dividend_amount: _Optional[_Union[_common_pb2.Quotation, _Mapping]] = ..., currency: _Optional[str] = ...) -> None: ...

class PortfolioStreamRequest(_message.Message):
    __slots__ = ("accounts",)
    ACCOUNTS_FIELD_NUMBER: _ClassVar[int]
    accounts: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, accounts: _Optional[_Iterable[str]] = ...) -> None: ...

class PortfolioStreamResponse(_message.Message):
    __slots__ = ("subscriptions", "portfolio", "ping")
    SUBSCRIPTIONS_FIELD_NUMBER: _ClassVar[int]
    PORTFOLIO_FIELD_NUMBER: _ClassVar[int]
    PING_FIELD_NUMBER: _ClassVar[int]
    subscriptions: PortfolioSubscriptionResult
    portfolio: PortfolioResponse
    ping: _common_pb2.Ping
    def __init__(self, subscriptions: _Optional[_Union[PortfolioSubscriptionResult, _Mapping]] = ..., portfolio: _Optional[_Union[PortfolioResponse, _Mapping]] = ..., ping: _Optional[_Union[_common_pb2.Ping, _Mapping]] = ...) -> None: ...

class PortfolioSubscriptionResult(_message.Message):
    __slots__ = ("accounts",)
    ACCOUNTS_FIELD_NUMBER: _ClassVar[int]
    accounts: _containers.RepeatedCompositeFieldContainer[AccountSubscriptionStatus]
    def __init__(self, accounts: _Optional[_Iterable[_Union[AccountSubscriptionStatus, _Mapping]]] = ...) -> None: ...

class AccountSubscriptionStatus(_message.Message):
    __slots__ = ("account_id", "subscription_status")
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    SUBSCRIPTION_STATUS_FIELD_NUMBER: _ClassVar[int]
    account_id: str
    subscription_status: PortfolioSubscriptionStatus
    def __init__(self, account_id: _Optional[str] = ..., subscription_status: _Optional[_Union[PortfolioSubscriptionStatus, str]] = ...) -> None: ...

class GetOperationsByCursorRequest(_message.Message):
    __slots__ = ("account_id", "instrument_id", "to", "cursor", "limit", "operation_types", "state", "without_commissions", "without_trades", "without_overnights")
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    INSTRUMENT_ID_FIELD_NUMBER: _ClassVar[int]
    FROM_FIELD_NUMBER: _ClassVar[int]
    TO_FIELD_NUMBER: _ClassVar[int]
    CURSOR_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    OPERATION_TYPES_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    WITHOUT_COMMISSIONS_FIELD_NUMBER: _ClassVar[int]
    WITHOUT_TRADES_FIELD_NUMBER: _ClassVar[int]
    WITHOUT_OVERNIGHTS_FIELD_NUMBER: _ClassVar[int]
    account_id: str
    instrument_id: str
    to: _timestamp_pb2.Timestamp
    cursor: str
    limit: int
    operation_types: _containers.RepeatedScalarFieldContainer[OperationType]
    state: OperationState
    without_commissions: bool
    without_trades: bool
    without_overnights: bool
    def __init__(self, account_id: _Optional[str] = ..., instrument_id: _Optional[str] = ..., to: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., cursor: _Optional[str] = ..., limit: _Optional[int] = ..., operation_types: _Optional[_Iterable[_Union[OperationType, str]]] = ..., state: _Optional[_Union[OperationState, str]] = ..., without_commissions: bool = ..., without_trades: bool = ..., without_overnights: bool = ..., **kwargs) -> None: ...

class GetOperationsByCursorResponse(_message.Message):
    __slots__ = ("has_next", "next_cursor", "items")
    HAS_NEXT_FIELD_NUMBER: _ClassVar[int]
    NEXT_CURSOR_FIELD_NUMBER: _ClassVar[int]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    has_next: bool
    next_cursor: str
    items: _containers.RepeatedCompositeFieldContainer[OperationItem]
    def __init__(self, has_next: bool = ..., next_cursor: _Optional[str] = ..., items: _Optional[_Iterable[_Union[OperationItem, _Mapping]]] = ...) -> None: ...

class OperationItem(_message.Message):
    __slots__ = ("cursor", "broker_account_id", "id", "parent_operation_id", "name", "date", "type", "description", "state", "instrument_uid", "figi", "instrument_type", "instrument_kind", "position_uid", "payment", "price", "commission", "yield_relative", "accrued_int", "quantity", "quantity_rest", "quantity_done", "cancel_date_time", "cancel_reason", "trades_info", "asset_uid")
    CURSOR_FIELD_NUMBER: _ClassVar[int]
    BROKER_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    PARENT_OPERATION_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DATE_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    INSTRUMENT_UID_FIELD_NUMBER: _ClassVar[int]
    FIGI_FIELD_NUMBER: _ClassVar[int]
    INSTRUMENT_TYPE_FIELD_NUMBER: _ClassVar[int]
    INSTRUMENT_KIND_FIELD_NUMBER: _ClassVar[int]
    POSITION_UID_FIELD_NUMBER: _ClassVar[int]
    PAYMENT_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    COMMISSION_FIELD_NUMBER: _ClassVar[int]
    YIELD_FIELD_NUMBER: _ClassVar[int]
    YIELD_RELATIVE_FIELD_NUMBER: _ClassVar[int]
    ACCRUED_INT_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_REST_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_DONE_FIELD_NUMBER: _ClassVar[int]
    CANCEL_DATE_TIME_FIELD_NUMBER: _ClassVar[int]
    CANCEL_REASON_FIELD_NUMBER: _ClassVar[int]
    TRADES_INFO_FIELD_NUMBER: _ClassVar[int]
    ASSET_UID_FIELD_NUMBER: _ClassVar[int]
    cursor: str
    broker_account_id: str
    id: str
    parent_operation_id: str
    name: str
    date: _timestamp_pb2.Timestamp
    type: OperationType
    description: str
    state: OperationState
    instrument_uid: str
    figi: str
    instrument_type: str
    instrument_kind: _common_pb2.InstrumentType
    position_uid: str
    payment: _common_pb2.MoneyValue
    price: _common_pb2.MoneyValue
    commission: _common_pb2.MoneyValue
    yield_relative: _common_pb2.Quotation
    accrued_int: _common_pb2.MoneyValue
    quantity: int
    quantity_rest: int
    quantity_done: int
    cancel_date_time: _timestamp_pb2.Timestamp
    cancel_reason: str
    trades_info: OperationItemTrades
    asset_uid: str
    def __init__(self, cursor: _Optional[str] = ..., broker_account_id: _Optional[str] = ..., id: _Optional[str] = ..., parent_operation_id: _Optional[str] = ..., name: _Optional[str] = ..., date: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., type: _Optional[_Union[OperationType, str]] = ..., description: _Optional[str] = ..., state: _Optional[_Union[OperationState, str]] = ..., instrument_uid: _Optional[str] = ..., figi: _Optional[str] = ..., instrument_type: _Optional[str] = ..., instrument_kind: _Optional[_Union[_common_pb2.InstrumentType, str]] = ..., position_uid: _Optional[str] = ..., payment: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., price: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., commission: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., yield_relative: _Optional[_Union[_common_pb2.Quotation, _Mapping]] = ..., accrued_int: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., quantity: _Optional[int] = ..., quantity_rest: _Optional[int] = ..., quantity_done: _Optional[int] = ..., cancel_date_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., cancel_reason: _Optional[str] = ..., trades_info: _Optional[_Union[OperationItemTrades, _Mapping]] = ..., asset_uid: _Optional[str] = ..., **kwargs) -> None: ...

class OperationItemTrades(_message.Message):
    __slots__ = ("trades",)
    TRADES_FIELD_NUMBER: _ClassVar[int]
    trades: _containers.RepeatedCompositeFieldContainer[OperationItemTrade]
    def __init__(self, trades: _Optional[_Iterable[_Union[OperationItemTrade, _Mapping]]] = ...) -> None: ...

class OperationItemTrade(_message.Message):
    __slots__ = ("num", "date", "quantity", "price", "yield_relative")
    NUM_FIELD_NUMBER: _ClassVar[int]
    DATE_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    YIELD_FIELD_NUMBER: _ClassVar[int]
    YIELD_RELATIVE_FIELD_NUMBER: _ClassVar[int]
    num: str
    date: _timestamp_pb2.Timestamp
    quantity: int
    price: _common_pb2.MoneyValue
    yield_relative: _common_pb2.Quotation
    def __init__(self, num: _Optional[str] = ..., date: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., quantity: _Optional[int] = ..., price: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., yield_relative: _Optional[_Union[_common_pb2.Quotation, _Mapping]] = ..., **kwargs) -> None: ...

class PositionsStreamRequest(_message.Message):
    __slots__ = ("accounts",)
    ACCOUNTS_FIELD_NUMBER: _ClassVar[int]
    accounts: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, accounts: _Optional[_Iterable[str]] = ...) -> None: ...

class PositionsStreamResponse(_message.Message):
    __slots__ = ("subscriptions", "position", "ping")
    SUBSCRIPTIONS_FIELD_NUMBER: _ClassVar[int]
    POSITION_FIELD_NUMBER: _ClassVar[int]
    PING_FIELD_NUMBER: _ClassVar[int]
    subscriptions: PositionsSubscriptionResult
    position: PositionData
    ping: _common_pb2.Ping
    def __init__(self, subscriptions: _Optional[_Union[PositionsSubscriptionResult, _Mapping]] = ..., position: _Optional[_Union[PositionData, _Mapping]] = ..., ping: _Optional[_Union[_common_pb2.Ping, _Mapping]] = ...) -> None: ...

class PositionsSubscriptionResult(_message.Message):
    __slots__ = ("accounts",)
    ACCOUNTS_FIELD_NUMBER: _ClassVar[int]
    accounts: _containers.RepeatedCompositeFieldContainer[PositionsSubscriptionStatus]
    def __init__(self, accounts: _Optional[_Iterable[_Union[PositionsSubscriptionStatus, _Mapping]]] = ...) -> None: ...

class PositionsSubscriptionStatus(_message.Message):
    __slots__ = ("account_id", "subscription_status")
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    SUBSCRIPTION_STATUS_FIELD_NUMBER: _ClassVar[int]
    account_id: str
    subscription_status: PositionsAccountSubscriptionStatus
    def __init__(self, account_id: _Optional[str] = ..., subscription_status: _Optional[_Union[PositionsAccountSubscriptionStatus, str]] = ...) -> None: ...

class PositionData(_message.Message):
    __slots__ = ("account_id", "money", "securities", "futures", "options", "date")
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    MONEY_FIELD_NUMBER: _ClassVar[int]
    SECURITIES_FIELD_NUMBER: _ClassVar[int]
    FUTURES_FIELD_NUMBER: _ClassVar[int]
    OPTIONS_FIELD_NUMBER: _ClassVar[int]
    DATE_FIELD_NUMBER: _ClassVar[int]
    account_id: str
    money: _containers.RepeatedCompositeFieldContainer[PositionsMoney]
    securities: _containers.RepeatedCompositeFieldContainer[PositionsSecurities]
    futures: _containers.RepeatedCompositeFieldContainer[PositionsFutures]
    options: _containers.RepeatedCompositeFieldContainer[PositionsOptions]
    date: _timestamp_pb2.Timestamp
    def __init__(self, account_id: _Optional[str] = ..., money: _Optional[_Iterable[_Union[PositionsMoney, _Mapping]]] = ..., securities: _Optional[_Iterable[_Union[PositionsSecurities, _Mapping]]] = ..., futures: _Optional[_Iterable[_Union[PositionsFutures, _Mapping]]] = ..., options: _Optional[_Iterable[_Union[PositionsOptions, _Mapping]]] = ..., date: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class PositionsMoney(_message.Message):
    __slots__ = ("available_value", "blocked_value")
    AVAILABLE_VALUE_FIELD_NUMBER: _ClassVar[int]
    BLOCKED_VALUE_FIELD_NUMBER: _ClassVar[int]
    available_value: _common_pb2.MoneyValue
    blocked_value: _common_pb2.MoneyValue
    def __init__(self, available_value: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., blocked_value: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ...) -> None: ...
