from fintect.domain.enums import (
    AccountStatus,
    AccountType,
    TransactionStatus,
)


def test_account_types() -> None:
    assert [item.value for item in AccountType] == [
        "savings",
        "current",
    ]


def test_account_statuses() -> None:
    assert [item.value for item in AccountStatus] == [
        "active",
        "frozen",
        "closed",
    ]


def test_transaction_statuses() -> None:
    assert [item.value for item in TransactionStatus] == [
        "pending",
        "completed",
        "failed",
        "reversed",
    ]


def test_enum_members_behave_like_strings() -> None:
    assert AccountStatus.ACTIVE == "active"
    assert AccountType.SAVINGS == "savings"
    assert TransactionStatus.COMPLETED == "completed"
