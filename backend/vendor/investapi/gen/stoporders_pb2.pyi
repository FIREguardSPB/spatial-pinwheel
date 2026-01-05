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

class StopOrderDirection(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    STOP_ORDER_DIRECTION_UNSPECIFIED: _ClassVar[StopOrderDirection]
    STOP_ORDER_DIRECTION_BUY: _ClassVar[StopOrderDirection]
    STOP_ORDER_DIRECTION_SELL: _ClassVar[StopOrderDirection]

class StopOrderExpirationType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    STOP_ORDER_EXPIRATION_TYPE_UNSPECIFIED: _ClassVar[StopOrderExpirationType]
    STOP_ORDER_EXPIRATION_TYPE_GOOD_TILL_CANCEL: _ClassVar[StopOrderExpirationType]
    STOP_ORDER_EXPIRATION_TYPE_GOOD_TILL_DATE: _ClassVar[StopOrderExpirationType]

class StopOrderType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    STOP_ORDER_TYPE_UNSPECIFIED: _ClassVar[StopOrderType]
    STOP_ORDER_TYPE_TAKE_PROFIT: _ClassVar[StopOrderType]
    STOP_ORDER_TYPE_STOP_LOSS: _ClassVar[StopOrderType]
    STOP_ORDER_TYPE_STOP_LIMIT: _ClassVar[StopOrderType]
STOP_ORDER_DIRECTION_UNSPECIFIED: StopOrderDirection
STOP_ORDER_DIRECTION_BUY: StopOrderDirection
STOP_ORDER_DIRECTION_SELL: StopOrderDirection
STOP_ORDER_EXPIRATION_TYPE_UNSPECIFIED: StopOrderExpirationType
STOP_ORDER_EXPIRATION_TYPE_GOOD_TILL_CANCEL: StopOrderExpirationType
STOP_ORDER_EXPIRATION_TYPE_GOOD_TILL_DATE: StopOrderExpirationType
STOP_ORDER_TYPE_UNSPECIFIED: StopOrderType
STOP_ORDER_TYPE_TAKE_PROFIT: StopOrderType
STOP_ORDER_TYPE_STOP_LOSS: StopOrderType
STOP_ORDER_TYPE_STOP_LIMIT: StopOrderType

class PostStopOrderRequest(_message.Message):
    __slots__ = ("figi", "quantity", "price", "stop_price", "direction", "account_id", "expiration_type", "stop_order_type", "expire_date", "instrument_id")
    FIGI_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    STOP_PRICE_FIELD_NUMBER: _ClassVar[int]
    DIRECTION_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    EXPIRATION_TYPE_FIELD_NUMBER: _ClassVar[int]
    STOP_ORDER_TYPE_FIELD_NUMBER: _ClassVar[int]
    EXPIRE_DATE_FIELD_NUMBER: _ClassVar[int]
    INSTRUMENT_ID_FIELD_NUMBER: _ClassVar[int]
    figi: str
    quantity: int
    price: _common_pb2.Quotation
    stop_price: _common_pb2.Quotation
    direction: StopOrderDirection
    account_id: str
    expiration_type: StopOrderExpirationType
    stop_order_type: StopOrderType
    expire_date: _timestamp_pb2.Timestamp
    instrument_id: str
    def __init__(self, figi: _Optional[str] = ..., quantity: _Optional[int] = ..., price: _Optional[_Union[_common_pb2.Quotation, _Mapping]] = ..., stop_price: _Optional[_Union[_common_pb2.Quotation, _Mapping]] = ..., direction: _Optional[_Union[StopOrderDirection, str]] = ..., account_id: _Optional[str] = ..., expiration_type: _Optional[_Union[StopOrderExpirationType, str]] = ..., stop_order_type: _Optional[_Union[StopOrderType, str]] = ..., expire_date: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., instrument_id: _Optional[str] = ...) -> None: ...

class PostStopOrderResponse(_message.Message):
    __slots__ = ("stop_order_id",)
    STOP_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    stop_order_id: str
    def __init__(self, stop_order_id: _Optional[str] = ...) -> None: ...

class GetStopOrdersRequest(_message.Message):
    __slots__ = ("account_id",)
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    account_id: str
    def __init__(self, account_id: _Optional[str] = ...) -> None: ...

class GetStopOrdersResponse(_message.Message):
    __slots__ = ("stop_orders",)
    STOP_ORDERS_FIELD_NUMBER: _ClassVar[int]
    stop_orders: _containers.RepeatedCompositeFieldContainer[StopOrder]
    def __init__(self, stop_orders: _Optional[_Iterable[_Union[StopOrder, _Mapping]]] = ...) -> None: ...

class CancelStopOrderRequest(_message.Message):
    __slots__ = ("account_id", "stop_order_id")
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    STOP_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    account_id: str
    stop_order_id: str
    def __init__(self, account_id: _Optional[str] = ..., stop_order_id: _Optional[str] = ...) -> None: ...

class CancelStopOrderResponse(_message.Message):
    __slots__ = ("time",)
    TIME_FIELD_NUMBER: _ClassVar[int]
    time: _timestamp_pb2.Timestamp
    def __init__(self, time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class StopOrder(_message.Message):
    __slots__ = ("stop_order_id", "lots_requested", "figi", "direction", "currency", "order_type", "create_date", "activation_date_time", "expiration_time", "price", "stop_price", "instrument_uid")
    STOP_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    LOTS_REQUESTED_FIELD_NUMBER: _ClassVar[int]
    FIGI_FIELD_NUMBER: _ClassVar[int]
    DIRECTION_FIELD_NUMBER: _ClassVar[int]
    CURRENCY_FIELD_NUMBER: _ClassVar[int]
    ORDER_TYPE_FIELD_NUMBER: _ClassVar[int]
    CREATE_DATE_FIELD_NUMBER: _ClassVar[int]
    ACTIVATION_DATE_TIME_FIELD_NUMBER: _ClassVar[int]
    EXPIRATION_TIME_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    STOP_PRICE_FIELD_NUMBER: _ClassVar[int]
    INSTRUMENT_UID_FIELD_NUMBER: _ClassVar[int]
    stop_order_id: str
    lots_requested: int
    figi: str
    direction: StopOrderDirection
    currency: str
    order_type: StopOrderType
    create_date: _timestamp_pb2.Timestamp
    activation_date_time: _timestamp_pb2.Timestamp
    expiration_time: _timestamp_pb2.Timestamp
    price: _common_pb2.MoneyValue
    stop_price: _common_pb2.MoneyValue
    instrument_uid: str
    def __init__(self, stop_order_id: _Optional[str] = ..., lots_requested: _Optional[int] = ..., figi: _Optional[str] = ..., direction: _Optional[_Union[StopOrderDirection, str]] = ..., currency: _Optional[str] = ..., order_type: _Optional[_Union[StopOrderType, str]] = ..., create_date: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., activation_date_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., expiration_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., price: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., stop_price: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., instrument_uid: _Optional[str] = ...) -> None: ...
