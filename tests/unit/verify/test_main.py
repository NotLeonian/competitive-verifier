import logging
import os
import pathlib
import re
import subprocess
from datetime import datetime, timedelta, timezone

import pytest
from pytest_mock import MockerFixture

from competitive_verifier import app
from competitive_verifier.log import GitHubMessageParams
from competitive_verifier.models import (
    FileResult,
    ResultStatus,
    VerificationInput,
    VerificationResult,
    VerifyCommandResult,
)
from competitive_verifier.oj.problem import LibraryCheckerProblem
from competitive_verifier.verify import Verify
from competitive_verifier.verify.verifier import SplitState, Verifier
from tests import LogComparer


@pytest.mark.allow_mkdir
@pytest.mark.parametrize("has_metadata", [False, True])
@pytest.mark.parametrize("split_index", [None, 0, 1])
def test_sync_failure_writes_results_and_preserves_unaffected_files(
    testtemp: pathlib.Path,
    mocker: MockerFixture,
    has_metadata: bool,
    split_index: int | None,
):
    affected = [pathlib.Path("a_affected.py"), pathlib.Path("d_affected.py")]
    fresh = pathlib.Path("b_new.py")
    reused = pathlib.Path("c_reused.py")
    verifications = VerificationInput.model_validate(
        {
            "files": {
                **{
                    path: {
                        "verification": {
                            "type": "problem",
                            "command": "true",
                            "problem": "https://judge.yosupo.jp/problem/aplusb",
                        }
                    }
                    for path in affected
                },
                fresh: {"verification": {"type": "command", "command": "fresh"}},
                reused: {"verification": {"type": "command", "command": "reused"}},
            }
        }
    )
    for path in verifications.files:
        path.write_text("source")
    pathlib.Path("verify.json").write_text(verifications.model_dump_json())
    mocker.patch.object(
        LibraryCheckerProblem,
        "testdata_hash",
        return_value="previous" if has_metadata else None,
    )
    mocker.patch.object(
        LibraryCheckerProblem,
        "cached_testdata_hash",
        return_value="previous" if has_metadata else None,
    )
    verifier = Verifier(
        verifications,
        timeout=10,
        default_tle=None,
        default_mle=None,
        prev_result=None,
        split_state=None,
        use_git_timestamp=False,
        change_detection="hash",
    )
    previous = VerifyCommandResult(
        total_seconds=0,
        files={
            path: FileResult(
                content_hash=verifier.file_content_hash(path),
                testdata_hash=verifier.file_testdata_hash(path),
                verifications=[
                    VerificationResult(status=ResultStatus.SUCCESS, elapsed=0)
                ],
            )
            for path in [*affected, reused]
        },
    )
    pathlib.Path("prev.json").write_text(previous.model_dump_json())
    mocker.patch.object(
        LibraryCheckerProblem,
        "update_cloned_repository",
        side_effect=subprocess.CalledProcessError(
            128, ["git", "pull" if has_metadata else "clone"]
        ),
    )
    run = mocker.patch.object(
        Verifier, "run_verification", return_value=(ResultStatus.SUCCESS, None)
    )
    download = mocker.patch("competitive_verifier.verify.verifier.run_download")
    parsed = app.ArgumentParser().parse(
        [
            "verify",
            "--verify-json",
            "verify.json",
            "--prev-result",
            "prev.json",
            "--output",
            "result.json",
            "--change-detection",
            "hash",
            "--check-error",
            *(
                []
                if split_index is None
                else ["--split", "2", "--split-index", str(split_index)]
            ),
        ]
    )
    assert parsed.run() is False
    result = VerifyCommandResult.parse_file_relative("result.json")
    selected = (
        {affected[0], fresh, affected[1]}
        if split_index is None
        else ({affected[0]} if split_index == 0 else {fresh, affected[1]})
    )
    assert result.files.keys() == previous.files.keys() | selected
    for path in affected:
        current = result.files[path]
        assert current.newest is (path in selected)
        if path in selected:
            assert [v.status for v in current.verifications] == [ResultStatus.FAILURE]
        else:
            assert current.verifications == previous.files[path].verifications
    assert not result.files[reused].newest
    assert result.files[reused].verifications == previous.files[reused].verifications
    assert run.call_count == download.call_count == int(fresh in selected)
    if fresh in selected:
        assert result.files[fresh].is_success(allow_skip=False)
        assert result.files[fresh].newest


test_get_split_state_params = [
    (None, None, None),
    (5, 0, SplitState(size=5, index=0)),
    (5, 1, SplitState(size=5, index=1)),
    (5, 2, SplitState(size=5, index=2)),
    (5, 3, SplitState(size=5, index=3)),
    (5, 4, SplitState(size=5, index=4)),
]


@pytest.mark.parametrize(
    ("size", "index", "expected"),
    test_get_split_state_params,
    ids=str,
)
def test_get_split_state(
    size: int | None,
    index: int | None,
    expected: SplitState | None,
):
    v = Verify(
        subcommand="verify",
        verify_files_json=pathlib.Path("verify.json"),
        split=size,
        split_index=index,
    )
    assert v.split_state == expected


test_get_split_state_error_params = {
    "No split index": (
        ["--verify-json", "verify.json", "--split", "2"],
        "--split argument requires --split-index argument.",
    ),
    "No split": (
        ["--verify-json", "verify.json", "--split-index", "2"],
        "--split-index argument requires --split argument.",
    ),
    "split index": (
        ["--verify-json", "verify.json", "--split-index", "5", "--split", "5"],
        "--split-index must be greater than 0 and less than --split.",
    ),
    "split index negative": (
        ["--verify-json", "verify.json", "--split-index", "-1", "--split", "5"],
        "--split-index must be greater than 0 and less than --split.",
    ),
    "split zero": (
        ["--verify-json", "verify.json", "--split-index", "1", "--split", "0"],
        "--split must be greater than 0.",
    ),
}


@pytest.mark.parametrize(
    ("args", "message"),
    test_get_split_state_error_params.values(),
    ids=test_get_split_state_error_params.keys(),
)
def test_get_split_state_error(args: list[str], message: str):
    parsed = app.ArgumentParser().parse(["verify", *args])

    assert isinstance(parsed, app.Verify)

    with pytest.raises(ValueError, match=rf"^{re.escape(message)}$"):
        _ = parsed.split_state


def test_invalid_prev_result(
    testtemp: pathlib.Path,
    caplog: pytest.LogCaptureFixture,
):
    (testtemp / "prev.json").write_bytes(b'[1,2,3,"invalid"]')
    parsed = app.ArgumentParser().parse(
        [
            "verify",
            "--verify-json",
            "verify.json",
            "--prev-result",
            str(testtemp / "prev.json"),
        ]
    )
    assert isinstance(parsed, app.Verify)

    assert parsed.read_prev_result() is None

    assert caplog.records == [
        LogComparer(
            f"Failed to parse prev_result: {testtemp / 'prev.json'}",
            logging.WARNING,
            github=GitHubMessageParams(file=testtemp / "prev.json"),
        )
    ]


def test_prev_result(testtemp: pathlib.Path):
    parsed = app.ArgumentParser().parse(["verify", "--verify-json", "verify.json"])
    assert isinstance(parsed, app.Verify)
    assert parsed.read_prev_result() is None

    (testtemp / "prev.json").write_text(
        '{"total_seconds":1.25,"files":{'
        '"' + (testtemp / "file1.txt").as_posix() + '"'
        ':{"verifications":[{"verification_name":"v1","status":"success","elapsed":1.2,"last_execution_time":"2025-09-21T08:09:10.001131-02:00"}],"newest":false},'
        '"file2.txt":{"verifications":[{"verification_name":"v2","status":"success","elapsed":1.3,"last_execution_time":"2025-09-21T08:09:11.004253-09:00"}],"newest":true}}}'
    )
    parsed = app.ArgumentParser().parse(
        [
            "verify",
            "--verify-json",
            "verify.json",
            "--prev-result",
            str(testtemp / "prev.json"),
        ]
    )
    assert isinstance(parsed, app.Verify)

    assert parsed.read_prev_result() == VerifyCommandResult(
        total_seconds=1.25,
        files={
            pathlib.Path("file1.txt"): FileResult(
                newest=False,
                verifications=[
                    VerificationResult(
                        verification_name="v1",
                        status=ResultStatus.SUCCESS,
                        last_execution_time=datetime(
                            2025,
                            9,
                            21,
                            8,
                            9,
                            10,
                            1131,
                            tzinfo=timezone(timedelta(hours=-2)),
                        ),
                        elapsed=1.2,
                    ),
                ],
            ),
            pathlib.Path("file2.txt"): FileResult(
                newest=True,
                verifications=[
                    VerificationResult(
                        verification_name="v2",
                        status=ResultStatus.SUCCESS,
                        last_execution_time=datetime(
                            2025,
                            9,
                            21,
                            8,
                            9,
                            11,
                            4253,
                            tzinfo=timezone(timedelta(hours=-9)),
                        ),
                        elapsed=1.3,
                    ),
                ],
            ),
        },
    )


@pytest.mark.allow_mkdir
@pytest.mark.parametrize("output", [True, False])
def test_write_result_output(
    output: bool,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
    testtemp: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
):
    monkeypatch.chdir(testtemp)
    mocker.patch.dict(
        os.environ, {"GITHUB_STEP_SUMMARY": str(testtemp / "summary.md")}, clear=True
    )
    parsed = app.ArgumentParser().parse(
        [
            "verify",
            "--write-summary",
            "--verify-json",
            "verify.json",
            *(["--output", "result.json"] if output else []),
        ]
    )
    assert isinstance(parsed, app.Verify)
    parsed.write_result(
        VerifyCommandResult(
            total_seconds=5e-5,
            files={
                pathlib.Path("lib.c"): FileResult(
                    verifications=[
                        VerificationResult(
                            status=ResultStatus.SKIPPED,
                            elapsed=5e-6,
                            last_execution_time=datetime(
                                2021, 2, 28, 9, 17, tzinfo=timezone(timedelta(hours=9))
                            ),
                        )
                    ],
                )
            },
        )
    )
    expected = """{"total_seconds":0.00005,"files":{"lib.c":{"verifications":[{"status":"skipped","elapsed":5e-6,"last_execution_time":"2021-02-28T09:17:00+09:00"}],"newest":true}}}"""
    out, err = capsys.readouterr()
    assert out.strip() == expected
    assert err == ""

    if output:
        assert (testtemp / "result.json").read_text("utf-8") == expected
    else:
        assert not (testtemp / "result.json").exists()

    assert (
        (testtemp / "summary.md").read_text("utf-8")
        == """# ⚠ Verification result

- ✔&nbsp;&nbsp;All test case results are `success`
- ❌&nbsp;&nbsp;Test case results contain `failure`
- ⚠&nbsp;&nbsp;Test case results contain `skipped`


## Results
|📝&nbsp;&nbsp;File|✔<br>Passed|❌<br>Failed|⚠<br>Skipped|∑<br>Total|⏳<br>Elapsed|🦥<br>Slowest|🐘<br>Heaviest|
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
|_**Sum**_|-|-|1|1|0ms|-|-|
|||||||||
|⚠&nbsp;&nbsp;lib.c|-|-|1|1|0ms|-|-|
"""
    )
