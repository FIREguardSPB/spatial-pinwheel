import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class InstrumentType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    INSTRUMENT_TYPE_UNSPECIFIED: _ClassVar[InstrumentType]
    INSTRUMENT_TYPE_BOND: _ClassVar[InstrumentType]
    INSTRUMENT_TYPE_SHARE: _ClassVar[InstrumentType]
    INSTRUMENT_TYPE_CURRENCY: _ClassVar[InstrumentType]
    INSTRUMENT_TYPE_ETF: _ClassVar[InstrumentType]
    INSTRUMENT_TYPE_FUTURES: _ClassVar[InstrumentType]
    INSTRUMENT_TYPE_SP: _ClassVar[InstrumentType]
    INSTRUMENT_TYPE_OPTION: _ClassVar[InstrumentType]
    INSTRUMENT_TYPE_CLEARING_CERTIFICATE: _ClassVar[InstrumentType]

class SecurityTradingStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SECURITY_TRADING_STATUS_UNSPECIFIED: _ClassVar[SecurityTradingStatus]
    SECURITY_TRADING_STATUS_NOT_AVAILABLE_FOR_TRADING: _ClassVar[SecurityTradingStatus]
    SECURITY_TRADING_STATUS_OPENING_PERIOD: _ClassVar[SecurityTradingStatus]
    SECURITY_TRADING_STATUS_CLOSING_PERIOD: _ClassVar[SecurityTradingStatus]
    SECURITY_TRADING_STATUS_BREAK_IN_TRADING: _ClassVar[SecurityTradingStatus]
    SECURITY_TRADING_STATUS_NORMAL_TRADING: _ClassVar[SecurityTradingStatus]
    SECURITY_TRADING_STATUS_CLOSING_AUCTION: _ClassVar[SecurityTradingStatus]
    SECURITY_TRADING_STATUS_DARK_POOL_AUCTION: _ClassVar[SecurityTradingStatus]
    SECURITY_TRADING_STATUS_DISCRETE_AUCTION: _ClassVar[SecurityTradingStatus]
    SECURITY_TRADING_STATUS_OPENING_AUCTION_PERIOD: _ClassVar[SecurityTradingStatus]
    SECURITY_TRADING_STATUS_TRADING_AT_CLOSING_AUCTION_PRICE: _ClassVar[SecurityTradingStatus]
    SECURITY_TRADING_STATUS_SESSION_ASSIGNED: _ClassVar[SecurityTradingStatus]
    SECURITY_TRADING_STATUS_SESSION_CLOSE: _ClassVar[SecurityTradingStatus]
    SECURITY_TRADING_STATUS_SESSION_OPEN: _ClassVar[SecurityTradingStatus]
    SECURITY_TRADING_STATUS_DEALER_NORMAL_TRADING: _ClassVar[SecurityTradingStatus]
    SECURITY_TRADING_STATUS_DEALER_BREAK_IN_TRADING: _ClassVar[SecurityTradingStatus]
    SECURITY_TRADING_STATUS_DEALER_NOT_AVAILABLE_FOR_TRADING: _ClassVar[SecurityTradingStatus]
INSTRUMENT_TYPE_UNSPECIFIED: InstrumentType
INSTRUMENT_TYPE_BOND: InstrumentType
INSTRUMENT_TYPE_SHARE: InstrumentType
INSTRUMENT_TYPE_CURRENCY: InstrumentType
INSTRUMENT_TYPE_ETF: InstrumentType
INSTRUMENT_TYPE_FUTURES: InstrumentType
INSTRUMENT_TYPE_SP: InstrumentType
INSTRUMENT_TYPE_OPTION: InstrumentType
INSTRUMENT_TYPE_CLEARING_CERTIFICATE: InstrumentType
SECURITY_TRADING_STATUS_UNSPECIFIED: SecurityTradingStatus
SECURITY_TRADING_STATUS_NOT_AVAILABLE_FOR_TRADING: SecurityTradingStatus
SECURITY_TRADING_STATUS_OPENING_PERIOD: SecurityTradingStatus
SECURITY_TRADING_STATUS_CLOSING_PERIOD: SecurityTradingStatus
SECURITY_TRADING_STATUS_BREAK_IN_TRADING: SecurityTradingStatus
SECURITY_TRADING_STATUS_NORMAL_TRADING: SecurityTradingStatus
SECURITY_TRADING_STATUS_CLOSING_AUCTION: SecurityTradingStatus
SECURITY_TRADING_STATUS_DARK_POOL_AUCTION: SecurityTradingStatus
SECURITY_TRADING_STATUS_DISCRETE_AUCTION: SecurityTradingStatus
SECURITY_TRADING_STATUS_OPENING_AUCTION_PERIOD: SecurityTradingStatus
SECURITY_TRADING_STATUS_TRADING_AT_CLOSING_AUCTION_PRICE: SecurityTradingStatus
SECURITY_TRADING_STATUS_SESSION_ASSIGNED: SecurityTradingStatus
SECURITY_TRADING_STATUS_SESSION_CLOSE: SecurityTradingStatus
SECURITY_TRADING_STATUS_SESSION_OPEN: SecurityTradingStatus
SECURITY_TRADING_STATUS_DEALER_NORMAL_TRADING: SecurityTradingStatus
SECURITY_TRADING_STATUS_DEALER_BREAK_IN_TRADING: SecurityTradingStatus
SECURITY_TRADING_STATUS_DEALER_NOT_AVAILABLE_FOR_TRADING: SecurityTradingStatus

class MoneyValue(_message.Message):
    __slots__ = ("currency", "units", "nano")
    CURRENCY_FIELD_NUMBER: _ClassVar[int]
    UNITS_FIELD_NUMBER: _ClassVar[int]
    NANO_FIELD_NUMBER: _ClassVar[int]
    currency: str
    units: int
    nano: int
    def __init__(self, currency: _Optional[str] = ..., units: _Optional[int] = ..., nano: _Optional[int] = ...) -> None: ...

class Quotation(_message.Message):
    __slots__ = ("units", "nano")
    UNITS_FIELD_NUMBER: _ClassVar[int]
    NANO_FIELD_NUMBER: _ClassVar[int]
    units: int
    nano: int
    def __init__(self, units: _Optional[int] = ..., nano: _Optional[int] = ...) -> None: ...

class Ping(_message.Message):
    __slots__ = ("time",)
    TIME_FIELD_NUMBER: _ClassVar[int]
    time: _timestamp_pb2.Timestamp
    def __init__(self, time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...
