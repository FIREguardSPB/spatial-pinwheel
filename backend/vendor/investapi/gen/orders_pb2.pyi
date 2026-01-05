import datetime

import common_pb2 as _common_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class OrderDirection(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ORDER_DIRECTION_UNSPECIFIED: _ClassVar[OrderDirection]
    ORDER_DIRECTION_BUY: _ClassVar[OrderDirection]
    ORDER_DIRECTION_SELL: _ClassVar[OrderDirection]

class OrderType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ORDER_TYPE_UNSPECIFIED: _ClassVar[OrderType]
    ORDER_TYPE_LIMIT: _ClassVar[OrderType]
    ORDER_TYPE_MARKET: _ClassVar[OrderType]
    ORDER_TYPE_BESTPRICE: _ClassVar[OrderType]

class OrderExecutionReportStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    EXECUTION_REPORT_STATUS_UNSPECIFIED: _ClassVar[OrderExecutionReportStatus]
    EXECUTION_REPORT_STATUS_FILL: _ClassVar[OrderExecutionReportStatus]
    EXECUTION_REPORT_STATUS_REJECTED: _ClassVar[OrderExecutionReportStatus]
    EXECUTION_REPORT_STATUS_CANCELLED: _ClassVar[OrderExecutionReportStatus]
    EXECUTION_REPORT_STATUS_NEW: _ClassVar[OrderExecutionReportStatus]
    EXECUTION_REPORT_STATUS_PARTIALLYFILL: _ClassVar[OrderExecutionReportStatus]

class PriceType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PRICE_TYPE_UNSPECIFIED: _ClassVar[PriceType]
    PRICE_TYPE_POINT: _ClassVar[PriceType]
    PRICE_TYPE_CURRENCY: _ClassVar[PriceType]
ORDER_DIRECTION_UNSPECIFIED: OrderDirection
ORDER_DIRECTION_BUY: OrderDirection
ORDER_DIRECTION_SELL: OrderDirection
ORDER_TYPE_UNSPECIFIED: OrderType
ORDER_TYPE_LIMIT: OrderType
ORDER_TYPE_MARKET: OrderType
ORDER_TYPE_BESTPRICE: OrderType
EXECUTION_REPORT_STATUS_UNSPECIFIED: OrderExecutionReportStatus
EXECUTION_REPORT_STATUS_FILL: OrderExecutionReportStatus
EXECUTION_REPORT_STATUS_REJECTED: OrderExecutionReportStatus
EXECUTION_REPORT_STATUS_CANCELLED: OrderExecutionReportStatus
EXECUTION_REPORT_STATUS_NEW: OrderExecutionReportStatus
EXECUTION_REPORT_STATUS_PARTIALLYFILL: OrderExecutionReportStatus
PRICE_TYPE_UNSPECIFIED: PriceType
PRICE_TYPE_POINT: PriceType
PRICE_TYPE_CURRENCY: PriceType

class TradesStreamRequest(_message.Message):
    __slots__ = ("accounts",)
    ACCOUNTS_FIELD_NUMBER: _ClassVar[int]
    accounts: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, accounts: _Optional[_Iterable[str]] = ...) -> None: ...

class TradesStreamResponse(_message.Message):
    __slots__ = ("order_trades", "ping")
    ORDER_TRADES_FIELD_NUMBER: _ClassVar[int]
    PING_FIELD_NUMBER: _ClassVar[int]
    order_trades: OrderTrades
    ping: _common_pb2.Ping
    def __init__(self, order_trades: _Optional[_Union[OrderTrades, _Mapping]] = ..., ping: _Optional[_Union[_common_pb2.Ping, _Mapping]] = ...) -> None: ...

class OrderTrades(_message.Message):
    __slots__ = ("order_id", "created_at", "direction", "figi", "trades", "account_id", "instrument_uid")
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    DIRECTION_FIELD_NUMBER: _ClassVar[int]
    FIGI_FIELD_NUMBER: _ClassVar[int]
    TRADES_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    INSTRUMENT_UID_FIELD_NUMBER: _ClassVar[int]
    order_id: str
    created_at: _timestamp_pb2.Timestamp
    direction: OrderDirection
    figi: str
    trades: _containers.RepeatedCompositeFieldContainer[OrderTrade]
    account_id: str
    instrument_uid: str
    def __init__(self, order_id: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., direction: _Optional[_Union[OrderDirection, str]] = ..., figi: _Optional[str] = ..., trades: _Optional[_Iterable[_Union[OrderTrade, _Mapping]]] = ..., account_id: _Optional[str] = ..., instrument_uid: _Optional[str] = ...) -> None: ...

class OrderTrade(_message.Message):
    __slots__ = ("date_time", "price", "quantity", "trade_id")
    DATE_TIME_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    TRADE_ID_FIELD_NUMBER: _ClassVar[int]
    date_time: _timestamp_pb2.Timestamp
    price: _common_pb2.Quotation
    quantity: int
    trade_id: str
    def __init__(self, date_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., price: _Optional[_Union[_common_pb2.Quotation, _Mapping]] = ..., quantity: _Optional[int] = ..., trade_id: _Optional[str] = ...) -> None: ...

class PostOrderRequest(_message.Message):
    __slots__ = ("figi", "quantity", "price", "direction", "account_id", "order_type", "order_id", "instrument_id")
    FIGI_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    DIRECTION_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    ORDER_TYPE_FIELD_NUMBER: _ClassVar[int]
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    INSTRUMENT_ID_FIELD_NUMBER: _ClassVar[int]
    figi: str
    quantity: int
    price: _common_pb2.Quotation
    direction: OrderDirection
    account_id: str
    order_type: OrderType
    order_id: str
    instrument_id: str
    def __init__(self, figi: _Optional[str] = ..., quantity: _Optional[int] = ..., price: _Optional[_Union[_common_pb2.Quotation, _Mapping]] = ..., direction: _Optional[_Union[OrderDirection, str]] = ..., account_id: _Optional[str] = ..., order_type: _Optional[_Union[OrderType, str]] = ..., order_id: _Optional[str] = ..., instrument_id: _Optional[str] = ...) -> None: ...

class PostOrderResponse(_message.Message):
    __slots__ = ("order_id", "execution_report_status", "lots_requested", "lots_executed", "initial_order_price", "executed_order_price", "total_order_amount", "initial_commission", "executed_commission", "aci_value", "figi", "direction", "initial_security_price", "order_type", "message", "initial_order_price_pt", "instrument_uid")
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    EXECUTION_REPORT_STATUS_FIELD_NUMBER: _ClassVar[int]
    LOTS_REQUESTED_FIELD_NUMBER: _ClassVar[int]
    LOTS_EXECUTED_FIELD_NUMBER: _ClassVar[int]
    INITIAL_ORDER_PRICE_FIELD_NUMBER: _ClassVar[int]
    EXECUTED_ORDER_PRICE_FIELD_NUMBER: _ClassVar[int]
    TOTAL_ORDER_AMOUNT_FIELD_NUMBER: _ClassVar[int]
    INITIAL_COMMISSION_FIELD_NUMBER: _ClassVar[int]
    EXECUTED_COMMISSION_FIELD_NUMBER: _ClassVar[int]
    ACI_VALUE_FIELD_NUMBER: _ClassVar[int]
    FIGI_FIELD_NUMBER: _ClassVar[int]
    DIRECTION_FIELD_NUMBER: _ClassVar[int]
    INITIAL_SECURITY_PRICE_FIELD_NUMBER: _ClassVar[int]
    ORDER_TYPE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    INITIAL_ORDER_PRICE_PT_FIELD_NUMBER: _ClassVar[int]
    INSTRUMENT_UID_FIELD_NUMBER: _ClassVar[int]
    order_id: str
    execution_report_status: OrderExecutionReportStatus
    lots_requested: int
    lots_executed: int
    initial_order_price: _common_pb2.MoneyValue
    executed_order_price: _common_pb2.MoneyValue
    total_order_amount: _common_pb2.MoneyValue
    initial_commission: _common_pb2.MoneyValue
    executed_commission: _common_pb2.MoneyValue
    aci_value: _common_pb2.MoneyValue
    figi: str
    direction: OrderDirection
    initial_security_price: _common_pb2.MoneyValue
    order_type: OrderType
    message: str
    initial_order_price_pt: _common_pb2.Quotation
    instrument_uid: str
    def __init__(self, order_id: _Optional[str] = ..., execution_report_status: _Optional[_Union[OrderExecutionReportStatus, str]] = ..., lots_requested: _Optional[int] = ..., lots_executed: _Optional[int] = ..., initial_order_price: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., executed_order_price: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., total_order_amount: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., initial_commission: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., executed_commission: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., aci_value: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., figi: _Optional[str] = ..., direction: _Optional[_Union[OrderDirection, str]] = ..., initial_security_price: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., order_type: _Optional[_Union[OrderType, str]] = ..., message: _Optional[str] = ..., initial_order_price_pt: _Optional[_Union[_common_pb2.Quotation, _Mapping]] = ..., instrument_uid: _Optional[str] = ...) -> None: ...

class CancelOrderRequest(_message.Message):
    __slots__ = ("account_id", "order_id")
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    account_id: str
    order_id: str
    def __init__(self, account_id: _Optional[str] = ..., order_id: _Optional[str] = ...) -> None: ...

class CancelOrderResponse(_message.Message):
    __slots__ = ("time",)
    TIME_FIELD_NUMBER: _ClassVar[int]
    time: _timestamp_pb2.Timestamp
    def __init__(self, time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class GetOrderStateRequest(_message.Message):
    __slots__ = ("account_id", "order_id")
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    account_id: str
    order_id: str
    def __init__(self, account_id: _Optional[str] = ..., order_id: _Optional[str] = ...) -> None: ...

class GetOrdersRequest(_message.Message):
    __slots__ = ("account_id",)
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    account_id: str
    def __init__(self, account_id: _Optional[str] = ...) -> None: ...

class GetOrdersResponse(_message.Message):
    __slots__ = ("orders",)
    ORDERS_FIELD_NUMBER: _ClassVar[int]
    orders: _containers.RepeatedCompositeFieldContainer[OrderState]
    def __init__(self, orders: _Optional[_Iterable[_Union[OrderState, _Mapping]]] = ...) -> None: ...

class OrderState(_message.Message):
    __slots__ = ("order_id", "execution_report_status", "lots_requested", "lots_executed", "initial_order_price", "executed_order_price", "total_order_amount", "average_position_price", "initial_commission", "executed_commission", "figi", "direction", "initial_security_price", "stages", "service_commission", "currency", "order_type", "order_date", "instrument_uid", "order_request_id")
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    EXECUTION_REPORT_STATUS_FIELD_NUMBER: _ClassVar[int]
    LOTS_REQUESTED_FIELD_NUMBER: _ClassVar[int]
    LOTS_EXECUTED_FIELD_NUMBER: _ClassVar[int]
    INITIAL_ORDER_PRICE_FIELD_NUMBER: _ClassVar[int]
    EXECUTED_ORDER_PRICE_FIELD_NUMBER: _ClassVar[int]
    TOTAL_ORDER_AMOUNT_FIELD_NUMBER: _ClassVar[int]
    AVERAGE_POSITION_PRICE_FIELD_NUMBER: _ClassVar[int]
    INITIAL_COMMISSION_FIELD_NUMBER: _ClassVar[int]
    EXECUTED_COMMISSION_FIELD_NUMBER: _ClassVar[int]
    FIGI_FIELD_NUMBER: _ClassVar[int]
    DIRECTION_FIELD_NUMBER: _ClassVar[int]
    INITIAL_SECURITY_PRICE_FIELD_NUMBER: _ClassVar[int]
    STAGES_FIELD_NUMBER: _ClassVar[int]
    SERVICE_COMMISSION_FIELD_NUMBER: _ClassVar[int]
    CURRENCY_FIELD_NUMBER: _ClassVar[int]
    ORDER_TYPE_FIELD_NUMBER: _ClassVar[int]
    ORDER_DATE_FIELD_NUMBER: _ClassVar[int]
    INSTRUMENT_UID_FIELD_NUMBER: _ClassVar[int]
    ORDER_REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    order_id: str
    execution_report_status: OrderExecutionReportStatus
    lots_requested: int
    lots_executed: int
    initial_order_price: _common_pb2.MoneyValue
    executed_order_price: _common_pb2.MoneyValue
    total_order_amount: _common_pb2.MoneyValue
    average_position_price: _common_pb2.MoneyValue
    initial_commission: _common_pb2.MoneyValue
    executed_commission: _common_pb2.MoneyValue
    figi: str
    direction: OrderDirection
    initial_security_price: _common_pb2.MoneyValue
    stages: _containers.RepeatedCompositeFieldContainer[OrderStage]
    service_commission: _common_pb2.MoneyValue
    currency: str
    order_type: OrderType
    order_date: _timestamp_pb2.Timestamp
    instrument_uid: str
    order_request_id: str
    def __init__(self, order_id: _Optional[str] = ..., execution_report_status: _Optional[_Union[OrderExecutionReportStatus, str]] = ..., lots_requested: _Optional[int] = ..., lots_executed: _Optional[int] = ..., initial_order_price: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., executed_order_price: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., total_order_amount: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., average_position_price: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., initial_commission: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., executed_commission: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., figi: _Optional[str] = ..., direction: _Optional[_Union[OrderDirection, str]] = ..., initial_security_price: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., stages: _Optional[_Iterable[_Union[OrderStage, _Mapping]]] = ..., service_commission: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., currency: _Optional[str] = ..., order_type: _Optional[_Union[OrderType, str]] = ..., order_date: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., instrument_uid: _Optional[str] = ..., order_request_id: _Optional[str] = ...) -> None: ...

class OrderStage(_message.Message):
    __slots__ = ("price", "quantity", "trade_id")
    PRICE_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    TRADE_ID_FIELD_NUMBER: _ClassVar[int]
    price: _common_pb2.MoneyValue
    quantity: int
    trade_id: str
    def __init__(self, price: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., quantity: _Optional[int] = ..., trade_id: _Optional[str] = ...) -> None: ...

class ReplaceOrderRequest(_message.Message):
    __slots__ = ("account_id", "order_id", "idempotency_key", "quantity", "price", "price_type")
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    IDEMPOTENCY_KEY_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    PRICE_TYPE_FIELD_NUMBER: _ClassVar[int]
    account_id: str
    order_id: str
    idempotency_key: str
    quantity: int
    price: _common_pb2.Quotation
    price_type: PriceType
    def __init__(self, account_id: _Optional[str] = ..., order_id: _Optional[str] = ..., idempotency_key: _Optional[str] = ..., quantity: _Optional[int] = ..., price: _Optional[_Union[_common_pb2.Quotation, _Mapping]] = ..., price_type: _Optional[_Union[PriceType, str]] = ...) -> None: ...
