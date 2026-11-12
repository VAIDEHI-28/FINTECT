from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BankingErrorCode(str, Enum):
    ACCOUNT_NOT_FOUND = "ACCOUNT_NOT_FOUND"
    ACCOUNT_ACCESS_DENIED = "ACCOUNT_ACCESS_DENIED"
    INVALID_REQUEST = "INVALID_REQUEST"
    BANKING_SERVICE_UNAVAILABLE = "BANKING_SERVICE_UNAVAILABLE"
    BANKING_OPERATION_FAILED = "BANKING_OPERATION_FAILED"
    BANKING_AUTHENTICATION_FAILED = "BANKING_AUTHENTICATION_FAILED"
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    LIMIT_EXCEEDED = "LIMIT_EXCEEDED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    OPERATION_NOT_SUPPORTED = "OPERATION_NOT_SUPPORTED"


class AccountBalanceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str = Field(min_length=1)

    @field_validator("account_id")
    @classmethod
    def validate_account_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("account_id cannot be blank")
        return value


class AccountBalanceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str = Field(min_length=1)
    account_number: str = Field(min_length=1)
    currency: str = Field(min_length=3, max_length=3)
    account_balance: Decimal
    available_balance: Decimal

    @field_validator("account_balance", "available_balance", mode="before")
    @classmethod
    def require_decimal(cls, value: object) -> Decimal:
        if not isinstance(value, Decimal):
            raise ValueError("Monetary values must be Decimal")
        return value


class BankingError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: BankingErrorCode
    message: str = Field(min_length=1)
    operation: str = Field(min_length=1)
    retryable: bool = False


class BankingException(Exception):
    """Exception carrying a canonical banking error."""

    def __init__(self, error: BankingError) -> None:
        self.error = error
        super().__init__(error.message)
