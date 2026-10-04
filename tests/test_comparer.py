import logging

import pytest

from competitive_verifier.log import GitHubMessageParams
from tests import LogComparer
from tests.conftest import pytest_assertrepr_compare


def test_assertrepr_preserves_log_records(pytestconfig: pytest.Config):
    record = logging.makeLogRecord({"msg": "actual"})
    comparer = LogComparer(message="expected")
    records = [record]
    expected = [comparer]

    assert pytest_assertrepr_compare(pytestconfig, "==", records, expected)
    assert records[0] is record
    assert expected[0] is comparer


def test_comparer():
    assert LogComparer(message="123") == LogComparer(message="123")
    assert LogComparer(message="123") != LogComparer(message="124")

    assert LogComparer(message="123") == logging.makeLogRecord(
        {"msg": "%d", "args": (123,)}
    )
    assert LogComparer(message="123") != logging.makeLogRecord(
        {"msg": "%d", "args": (124,)}
    )

    assert LogComparer(message="123", level=1) == logging.makeLogRecord(
        {"msg": "%d", "args": (123,), "levelno": 1}
    )
    assert LogComparer(message="123", level=1) != logging.makeLogRecord(
        {"msg": "%d", "args": (123,), "levelno": 2}
    )

    assert LogComparer(message="123", name="1") == logging.makeLogRecord(
        {"msg": "%d", "args": (123,), "name": "1"}
    )
    assert LogComparer(message="123", name="1") != logging.makeLogRecord(
        {"msg": "%d", "args": (123,), "name": "2"}
    )

    assert LogComparer(
        message="123", github=GitHubMessageParams(title="air")
    ) == logging.makeLogRecord(
        {"msg": "%d", "args": (123,), "github": GitHubMessageParams(title="air")}
    )
    assert LogComparer(
        message="123", github=GitHubMessageParams(title="air2")
    ) != logging.makeLogRecord(
        {"msg": "%d", "args": (123,), "github": GitHubMessageParams(title="air")}
    )
    assert LogComparer(message="123") != logging.makeLogRecord(
        {"msg": "%d", "args": (123,), "github": GitHubMessageParams(title="air")}
    )
