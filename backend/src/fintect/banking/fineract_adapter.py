from decimal import Decimal, InvalidOperation

import httpx
from pydantic import ValidationError

from fintect.banking.http_client import create_fineract_client
from fintect.banking.interface import BankingInterface
from fintect.banking.models import (
    AccountBalanceRequest,
    AccountBalanceResponse,
    BankingError,
    BankingErrorCode,
    BankingException,
)
from fintect.config import Settings


class FineractAdapter(BankingInterface):
    """Banking adapter backed by Apache Fineract."""

    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._client = client or create_fineract_client(settings)

    @staticmethod
    def _raise_for_banking_error(response: httpx.Response) -> None:
        """Translate Fineract HTTP errors into canonical banking errors."""
        status_code = response.status_code

        if status_code < 400:
            return

        if status_code == 404:
            code = BankingErrorCode.ACCOUNT_NOT_FOUND
            message = "Bank account was not found."
            retryable = False
        elif status_code == 400:
            code = BankingErrorCode.INVALID_REQUEST
            message = "Banking request is invalid."
            retryable = False
        elif status_code in (401, 403):
            code = BankingErrorCode.BANKING_AUTHENTICATION_FAILED
            message = "Banking service authentication failed."
            retryable = False
        elif status_code == 429 or status_code >= 500:
            code = BankingErrorCode.BANKING_SERVICE_UNAVAILABLE
            message = "Banking service is temporarily unavailable."
            retryable = True
        else:
            code = BankingErrorCode.BANKING_OPERATION_FAILED
            message = "Banking operation failed."
            retryable = False

        raise BankingException(
            BankingError(
                code=code,
                message=message,
                operation="get_account_balance",
                retryable=retryable,
            )
        )

    async def get_account_balance(
        self,
        request: AccountBalanceRequest,
    ) -> AccountBalanceResponse:
        """Retrieve an account balance from Fineract."""
        try:
            response = await self._client.get(f"savingsaccounts/{request.account_id}")
        except httpx.TimeoutException as exc:
            raise BankingException(
                BankingError(
                    code=BankingErrorCode.BANKING_SERVICE_UNAVAILABLE,
                    message="Banking service request timed out.",
                    operation="get_account_balance",
                    retryable=True,
                )
            ) from exc
        except httpx.RequestError as exc:
            raise BankingException(
                BankingError(
                    code=BankingErrorCode.BANKING_SERVICE_UNAVAILABLE,
                    message="Unable to connect to banking service.",
                    operation="get_account_balance",
                    retryable=True,
                )
            ) from exc

        # HTTP errors must be handled before parsing the response body.
        self._raise_for_banking_error(response)

        try:
            data = response.json()
            summary = data["summary"]

            return AccountBalanceResponse(
                account_id=str(data["id"]),
                account_number=str(data["accountNo"]),
                currency=data["currency"]["code"],
                account_balance=Decimal(str(summary["accountBalance"])),
                available_balance=Decimal(str(summary["availableBalance"])),
            )
        except (
            KeyError,
            TypeError,
            ValueError,
            InvalidOperation,
            ValidationError,
        ) as exc:
            raise BankingException(
                BankingError(
                    code=BankingErrorCode.BANKING_OPERATION_FAILED,
                    message="Banking service returned an invalid response.",
                    operation="get_account_balance",
                    retryable=False,
                )
            ) from exc
