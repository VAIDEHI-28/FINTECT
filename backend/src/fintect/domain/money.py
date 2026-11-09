from decimal import ROUND_HALF_UP, Decimal
from typing import TypeAlias

Money: TypeAlias = Decimal

MONEY_PRECISION = Decimal("0.01")
MONEY_ROUNDING = ROUND_HALF_UP


def normalize_money(amount: Money) -> Money:
    """Normalize a monetary amount to two decimal places."""
    return amount.quantize(
        MONEY_PRECISION,
        rounding=MONEY_ROUNDING,
    )
