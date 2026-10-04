import json
import pathlib

from competitive_verifier.models import FileResult, ResultStatus, VerificationResult
from tests.integration.command.mock import MockVerifyCommandResult


def test_json_dump_forwards_options_without_mutating_results():
    result = MockVerifyCommandResult(
        total_seconds=1.25,
        files={
            pathlib.Path("テスト.py"): FileResult(
                content_hash="original-content",
                testdata_hash="original-testdata",
                verifications=[
                    VerificationResult(status=ResultStatus.SUCCESS, elapsed=0.5)
                ],
            )
        },
    )
    original = result.model_copy(deep=True)

    dumped = result.model_dump_json(
        ensure_ascii=True,
        by_alias=None,
        exclude_none=True,
        context={"test": "serialization"},
    )
    data = json.loads(dumped)
    assert dumped.isascii()
    assert data["files"]["テスト.py"]["content_hash"] != "original-content"
    assert "testcases" not in data["files"]["テスト.py"]["verifications"][0]
    assert result == original
    assert (
        result.model_dump_json(include={"total_seconds"}) == '{"total_seconds":1312.56}'
    )
