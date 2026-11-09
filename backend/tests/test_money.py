from decimal import Decimal

from fintect.domain.money import (
    MONEY_PRECISION,
    MONEY_ROUNDING,
    normalize_money,
)


def test_money_precision_is_two_decimal_places() -> None:
    assert MONEY_PRECISION == Decimal("0.01")


def test_money_rounding_is_half_up() -> None:
    assert MONEY_ROUNDING == "ROUND_HALF_UP"


def test_normalize_money_whole_amount() -> None:
    assert normalize_money(Decimal("100")) == Decimal("100.00")


def test_normalize_money_one_decimal_place() -> None:
    assert normalize_money(Decimal("100.5")) == Decimal("100.50")


def test_normalize_money_rounds_half_up() -> None:
    assert normalize_money(Decimal("100.555")) == Decimal("100.56")


def test_normalize_money_rounds_down() -> None:
    assert normalize_money(Decimal("100.554")) == Decimal("100.55")
