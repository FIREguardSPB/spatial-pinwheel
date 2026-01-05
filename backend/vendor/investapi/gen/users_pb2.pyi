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

class AccountType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ACCOUNT_TYPE_UNSPECIFIED: _ClassVar[AccountType]
    ACCOUNT_TYPE_TINKOFF: _ClassVar[AccountType]
    ACCOUNT_TYPE_TINKOFF_IIS: _ClassVar[AccountType]
    ACCOUNT_TYPE_INVEST_BOX: _ClassVar[AccountType]

class AccountStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ACCOUNT_STATUS_UNSPECIFIED: _ClassVar[AccountStatus]
    ACCOUNT_STATUS_NEW: _ClassVar[AccountStatus]
    ACCOUNT_STATUS_OPEN: _ClassVar[AccountStatus]
    ACCOUNT_STATUS_CLOSED: _ClassVar[AccountStatus]

class AccessLevel(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ACCOUNT_ACCESS_LEVEL_UNSPECIFIED: _ClassVar[AccessLevel]
    ACCOUNT_ACCESS_LEVEL_FULL_ACCESS: _ClassVar[AccessLevel]
    ACCOUNT_ACCESS_LEVEL_READ_ONLY: _ClassVar[AccessLevel]
    ACCOUNT_ACCESS_LEVEL_NO_ACCESS: _ClassVar[AccessLevel]
ACCOUNT_TYPE_UNSPECIFIED: AccountType
ACCOUNT_TYPE_TINKOFF: AccountType
ACCOUNT_TYPE_TINKOFF_IIS: AccountType
ACCOUNT_TYPE_INVEST_BOX: AccountType
ACCOUNT_STATUS_UNSPECIFIED: AccountStatus
ACCOUNT_STATUS_NEW: AccountStatus
ACCOUNT_STATUS_OPEN: AccountStatus
ACCOUNT_STATUS_CLOSED: AccountStatus
ACCOUNT_ACCESS_LEVEL_UNSPECIFIED: AccessLevel
ACCOUNT_ACCESS_LEVEL_FULL_ACCESS: AccessLevel
ACCOUNT_ACCESS_LEVEL_READ_ONLY: AccessLevel
ACCOUNT_ACCESS_LEVEL_NO_ACCESS: AccessLevel

class GetAccountsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetAccountsResponse(_message.Message):
    __slots__ = ("accounts",)
    ACCOUNTS_FIELD_NUMBER: _ClassVar[int]
    accounts: _containers.RepeatedCompositeFieldContainer[Account]
    def __init__(self, accounts: _Optional[_Iterable[_Union[Account, _Mapping]]] = ...) -> None: ...

class Account(_message.Message):
    __slots__ = ("id", "type", "name", "status", "opened_date", "closed_date", "access_level")
    ID_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    OPENED_DATE_FIELD_NUMBER: _ClassVar[int]
    CLOSED_DATE_FIELD_NUMBER: _ClassVar[int]
    ACCESS_LEVEL_FIELD_NUMBER: _ClassVar[int]
    id: str
    type: AccountType
    name: str
    status: AccountStatus
    opened_date: _timestamp_pb2.Timestamp
    closed_date: _timestamp_pb2.Timestamp
    access_level: AccessLevel
    def __init__(self, id: _Optional[str] = ..., type: _Optional[_Union[AccountType, str]] = ..., name: _Optional[str] = ..., status: _Optional[_Union[AccountStatus, str]] = ..., opened_date: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., closed_date: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., access_level: _Optional[_Union[AccessLevel, str]] = ...) -> None: ...

class GetMarginAttributesRequest(_message.Message):
    __slots__ = ("account_id",)
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    account_id: str
    def __init__(self, account_id: _Optional[str] = ...) -> None: ...

class GetMarginAttributesResponse(_message.Message):
    __slots__ = ("liquid_portfolio", "starting_margin", "minimal_margin", "funds_sufficiency_level", "amount_of_missing_funds", "corrected_margin")
    LIQUID_PORTFOLIO_FIELD_NUMBER: _ClassVar[int]
    STARTING_MARGIN_FIELD_NUMBER: _ClassVar[int]
    MINIMAL_MARGIN_FIELD_NUMBER: _ClassVar[int]
    FUNDS_SUFFICIENCY_LEVEL_FIELD_NUMBER: _ClassVar[int]
    AMOUNT_OF_MISSING_FUNDS_FIELD_NUMBER: _ClassVar[int]
    CORRECTED_MARGIN_FIELD_NUMBER: _ClassVar[int]
    liquid_portfolio: _common_pb2.MoneyValue
    starting_margin: _common_pb2.MoneyValue
    minimal_margin: _common_pb2.MoneyValue
    funds_sufficiency_level: _common_pb2.Quotation
    amount_of_missing_funds: _common_pb2.MoneyValue
    corrected_margin: _common_pb2.MoneyValue
    def __init__(self, liquid_portfolio: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., starting_margin: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., minimal_margin: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., funds_sufficiency_level: _Optional[_Union[_common_pb2.Quotation, _Mapping]] = ..., amount_of_missing_funds: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ..., corrected_margin: _Optional[_Union[_common_pb2.MoneyValue, _Mapping]] = ...) -> None: ...

class GetUserTariffRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetUserTariffResponse(_message.Message):
    __slots__ = ("unary_limits", "stream_limits")
    UNARY_LIMITS_FIELD_NUMBER: _ClassVar[int]
    STREAM_LIMITS_FIELD_NUMBER: _ClassVar[int]
    unary_limits: _containers.RepeatedCompositeFieldContainer[UnaryLimit]
    stream_limits: _containers.RepeatedCompositeFieldContainer[StreamLimit]
    def __init__(self, unary_limits: _Optional[_Iterable[_Union[UnaryLimit, _Mapping]]] = ..., stream_limits: _Optional[_Iterable[_Union[StreamLimit, _Mapping]]] = ...) -> None: ...

class UnaryLimit(_message.Message):
    __slots__ = ("limit_per_minute", "methods")
    LIMIT_PER_MINUTE_FIELD_NUMBER: _ClassVar[int]
    METHODS_FIELD_NUMBER: _ClassVar[int]
    limit_per_minute: int
    methods: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, limit_per_minute: _Optional[int] = ..., methods: _Optional[_Iterable[str]] = ...) -> None: ...

class StreamLimit(_message.Message):
    __slots__ = ("limit", "streams", "open")
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    STREAMS_FIELD_NUMBER: _ClassVar[int]
    OPEN_FIELD_NUMBER: _ClassVar[int]
    limit: int
    streams: _containers.RepeatedScalarFieldContainer[str]
    open: int
    def __init__(self, limit: _Optional[int] = ..., streams: _Optional[_Iterable[str]] = ..., open: _Optional[int] = ...) -> None: ...

class GetInfoRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetInfoResponse(_message.Message):
    __slots__ = ("prem_status", "qual_status", "qualified_for_work_with", "tariff")
    PREM_STATUS_FIELD_NUMBER: _ClassVar[int]
    QUAL_STATUS_FIELD_NUMBER: _ClassVar[int]
    QUALIFIED_FOR_WORK_WITH_FIELD_NUMBER: _ClassVar[int]
    TARIFF_FIELD_NUMBER: _ClassVar[int]
    prem_status: bool
    qual_status: bool
    qualified_for_work_with: _containers.RepeatedScalarFieldContainer[str]
    tariff: str
    def __init__(self, prem_status: bool = ..., qual_status: bool = ..., qualified_for_work_with: _Optional[_Iterable[str]] = ..., tariff: _Optional[str] = ...) -> None: ...
