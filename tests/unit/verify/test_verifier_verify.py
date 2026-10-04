import datetime
import hashlib
import json
import logging
import os
import pathlib
from typing import Any

import pytest
from pytest_mock import MockerFixture

from competitive_verifier.config import COMPETITIVE_VERIFY_CONFIG_PATH
from competitive_verifier.log import GitHubMessageParams
from competitive_verifier.models import (
    ConstVerification,
    FileResult,
    LocalProblemVerification,
    ProblemVerification,
    ResultStatus,
    Verification,
    VerificationInput,
    VerificationResult,
    VerifyCommandResult,
)
from competitive_verifier.oj.problem import LibraryCheckerProblem, YukicoderProblem
from competitive_verifier.verify.verifier import (
    BaseVerifier,
    ChangeDetection,
    SplitState,
    Verifier,
    content_hash,
)
from tests import LogComparer

SUCCESS = ResultStatus.SUCCESS
FAILURE = ResultStatus.FAILURE


class NotSkippableConstVerification(ConstVerification):
    @property
    def is_lightweight(self) -> bool:
        return False


class MockVerifier(BaseVerifier):
    def __init__(
        self,
        verifications: Any = None,
        *,
        verification_time: datetime.datetime,
        prev_result: VerifyCommandResult | None = None,
        split_state: SplitState | None = None,
        file_hashes: dict[str, str] | None = None,
        change_detection: ChangeDetection = "timestamp",
    ) -> None:
        super().__init__(
            verifications=VerificationInput.model_validate(verifications),
            verification_time=verification_time,
            prev_result=prev_result,
            split_state=split_state,
            change_detection=change_detection,
            default_tle=10,
            default_mle=256,
            timeout=10,
        )
        self.file_hashes = file_hashes

    def get_file_timestamp(self, path: pathlib.Path) -> datetime.datetime:
        return datetime.datetime(2005, 1, 2, 15, 4, 5)

    def file_content_hash(self, path: pathlib.Path) -> str | None:
        if self.file_hashes is None:
            return None
        return self.file_hashes.get(path.as_posix())


test_verify_params: list[tuple[MockVerifier, dict[str, Any]]] = [
    (
        MockVerifier(
            {
                "files": {
                    "lib/hoge1.py": {},
                    "test/foo.py": {
                        "dependencies": ["lib/hoge1.py"],
                        "verification": [
                            NotSkippableConstVerification(status=ResultStatus.SUCCESS)
                        ],
                    },
                    "test/skip.py": {
                        "dependencies": ["lib/hoge1.py"],
                        "verification": [
                            ConstVerification(status=ResultStatus.SUCCESS)
                        ],
                    },
                }
            },
            verification_time=datetime.datetime(2007, 1, 2, 15, 4, 5),
        ),
        {
            "total_seconds": 8.0,
            "files": {
                "test/foo.py": FileResult(
                    newest=True,
                    verifications=[
                        VerificationResult(
                            status=ResultStatus.SUCCESS,
                            elapsed=2.0,
                            last_execution_time=datetime.datetime(2007, 1, 2, 15, 4, 5),
                        ),
                    ],
                ),
                "test/skip.py": FileResult(
                    newest=True,
                    verifications=[
                        VerificationResult(
                            status=ResultStatus.SUCCESS,
                            elapsed=2.0,
                            last_execution_time=datetime.datetime(2007, 1, 2, 15, 4, 5),
                        ),
                    ],
                ),
            },
        },
    ),
    (
        MockVerifier(
            {
                "files": {
                    "lib/hoge1.py": {},
                    "test/foo.py": {
                        "dependencies": ["lib/hoge1.py"],
                        "verification": [
                            NotSkippableConstVerification(status=ResultStatus.SUCCESS)
                        ],
                    },
                    "test/foo1.py": {
                        "dependencies": ["lib/hoge1.py"],
                        "verification": [
                            NotSkippableConstVerification(status=ResultStatus.SUCCESS)
                        ],
                    },
                    "test/foo2.py": {
                        "dependencies": ["lib/hoge1.py"],
                        "verification": [
                            NotSkippableConstVerification(status=ResultStatus.SUCCESS)
                        ],
                    },
                    "test/foo3.py": {
                        "dependencies": ["lib/hoge1.py"],
                        "verification": [
                            NotSkippableConstVerification(status=ResultStatus.SUCCESS)
                        ],
                    },
                    "test/skip.py": {
                        "dependencies": ["lib/hoge1.py"],
                        "verification": [
                            ConstVerification(status=ResultStatus.SUCCESS)
                        ],
                    },
                }
            },
            verification_time=datetime.datetime(2007, 1, 2, 15, 4, 5),
            split_state=SplitState(size=2, index=0),
        ),
        {
            "total_seconds": 12.0,
            "files": {
                "test/foo.py": FileResult(
                    newest=True,
                    verifications=[
                        VerificationResult(
                            status=ResultStatus.SUCCESS,
                            elapsed=2.0,
                            last_execution_time=datetime.datetime(2007, 1, 2, 15, 4, 5),
                        ),
                    ],
                ),
                "test/foo1.py": FileResult(
                    newest=True,
                    verifications=[
                        VerificationResult(
                            status=ResultStatus.SUCCESS,
                            elapsed=2.0,
                            last_execution_time=datetime.datetime(2007, 1, 2, 15, 4, 5),
                        ),
                    ],
                ),
                "test/skip.py": FileResult(
                    newest=True,
                    verifications=[
                        VerificationResult(
                            status=ResultStatus.SUCCESS,
                            elapsed=2.0,
                            last_execution_time=datetime.datetime(2007, 1, 2, 15, 4, 5),
                        ),
                    ],
                ),
            },
        },
    ),
    (
        MockVerifier(
            {
                "files": {
                    "lib/hoge1.py": {},
                    "test/foo.py": {
                        "dependencies": ["lib/hoge1.py"],
                        "verification": [
                            NotSkippableConstVerification(status=ResultStatus.SUCCESS)
                        ],
                    },
                    "test/foo1.py": {
                        "dependencies": ["lib/hoge1.py"],
                        "verification": [
                            NotSkippableConstVerification(status=ResultStatus.SUCCESS)
                        ],
                    },
                    "test/foo2.py": {
                        "dependencies": ["lib/hoge1.py"],
                        "verification": [
                            NotSkippableConstVerification(status=ResultStatus.SUCCESS)
                        ],
                    },
                    "test/foo3.py": {
                        "dependencies": ["lib/hoge1.py"],
                        "verification": [
                            NotSkippableConstVerification(status=ResultStatus.SUCCESS)
                        ],
                    },
                    "test/skip.py": {
                        "dependencies": ["lib/hoge1.py"],
                        "verification": [
                            ConstVerification(status=ResultStatus.SUCCESS)
                        ],
                    },
                }
            },
            verification_time=datetime.datetime(2007, 1, 2, 15, 4, 5),
            split_state=SplitState(size=2, index=1),
        ),
        {
            "total_seconds": 9.0,
            "files": {
                "test/foo2.py": FileResult(
                    newest=True,
                    verifications=[
                        VerificationResult(
                            status=ResultStatus.SUCCESS,
                            elapsed=2.0,
                            last_execution_time=datetime.datetime(2007, 1, 2, 15, 4, 5),
                        ),
                    ],
                ),
                "test/foo3.py": FileResult(
                    newest=True,
                    verifications=[
                        VerificationResult(
                            status=ResultStatus.SUCCESS,
                            elapsed=2.0,
                            last_execution_time=datetime.datetime(2007, 1, 2, 15, 4, 5),
                        ),
                    ],
                ),
            },
        },
    ),
    (
        MockVerifier(
            {
                "files": {
                    "lib/hoge1.py": {},
                    "test/foo.py": {
                        "dependencies": ["lib/hoge1.py"],
                        "verification": [
                            NotSkippableConstVerification(status=ResultStatus.SUCCESS)
                        ],
                    },
                    "test/foo1.py": {
                        "dependencies": ["lib/hoge1.py"],
                        "verification": [
                            NotSkippableConstVerification(status=ResultStatus.SUCCESS)
                        ],
                    },
                    "test/foo2.py": {
                        "dependencies": ["lib/hoge1.py"],
                        "verification": [
                            NotSkippableConstVerification(status=ResultStatus.SUCCESS)
                        ],
                    },
                    "test/foo3.py": {
                        "dependencies": ["lib/hoge1.py"],
                        "verification": [
                            NotSkippableConstVerification(status=ResultStatus.SUCCESS)
                        ],
                    },
                    "test/skip.py": {
                        "dependencies": ["lib/hoge1.py"],
                        "verification": [
                            ConstVerification(status=ResultStatus.SUCCESS)
                        ],
                    },
                }
            },
            prev_result=VerifyCommandResult.model_validate(
                {
                    "total_seconds": 6.0,
                    "files": {
                        "test/foo.py": FileResult(
                            newest=True,
                            content_hash="hash:test/foo.py",
                            verifications=[
                                VerificationResult(
                                    status=ResultStatus.SUCCESS,
                                    elapsed=1.0,
                                    last_execution_time=datetime.datetime(
                                        2005, 12, 2, 15, 4, 5
                                    ),
                                ),
                            ],
                        ),
                        "test/foo1.py": FileResult(
                            newest=True,
                            content_hash="hash:test/foo1.py",
                            verifications=[
                                VerificationResult(
                                    status=ResultStatus.SUCCESS,
                                    elapsed=1.0,
                                    last_execution_time=datetime.datetime(
                                        2005, 12, 2, 15, 4, 5
                                    ),
                                ),
                            ],
                        ),
                        "test/foo2.py": FileResult(
                            newest=True,
                            content_hash="hash:test/foo2.py",
                            verifications=[
                                VerificationResult(
                                    status=ResultStatus.SUCCESS,
                                    elapsed=1.0,
                                    last_execution_time=datetime.datetime(
                                        2005, 12, 2, 15, 4, 5
                                    ),
                                ),
                            ],
                        ),
                        "test/foo3.py": FileResult(
                            newest=True,
                            content_hash="outdated-hash",
                            verifications=[
                                VerificationResult(
                                    status=ResultStatus.SUCCESS,
                                    elapsed=1.0,
                                    last_execution_time=datetime.datetime(
                                        2000, 1, 2, 15, 4, 5
                                    ),
                                ),
                            ],
                        ),
                        "test/skip.py": FileResult(
                            newest=False,
                            content_hash="hash:test/skip.py",
                            verifications=[
                                VerificationResult(
                                    status=ResultStatus.SUCCESS,
                                    elapsed=1.0,
                                    last_execution_time=datetime.datetime(
                                        2000, 1, 2, 15, 4, 5
                                    ),
                                ),
                            ],
                        ),
                    },
                }
            ),
            verification_time=datetime.datetime(2007, 1, 2, 15, 4, 5),
            file_hashes={
                "test/foo.py": "hash:test/foo.py",
                "test/foo1.py": "hash:test/foo1.py",
                "test/foo2.py": "hash:test/foo2.py",
                "test/foo3.py": "hash:test/foo3.py",
                "test/skip.py": "hash:test/skip.py",
            },
        ),
        {
            "total_seconds": 8.0,
            "files": {
                "test/foo.py": FileResult(
                    newest=False,
                    content_hash="hash:test/foo.py",
                    verifications=[
                        VerificationResult(
                            status=ResultStatus.SUCCESS,
                            elapsed=1.0,
                            last_execution_time=datetime.datetime(
                                2005, 12, 2, 15, 4, 5
                            ),
                        ),
                    ],
                ),
                "test/foo1.py": FileResult(
                    newest=False,
                    content_hash="hash:test/foo1.py",
                    verifications=[
                        VerificationResult(
                            status=ResultStatus.SUCCESS,
                            elapsed=1.0,
                            last_execution_time=datetime.datetime(
                                2005, 12, 2, 15, 4, 5
                            ),
                        ),
                    ],
                ),
                "test/foo2.py": FileResult(
                    newest=False,
                    content_hash="hash:test/foo2.py",
                    verifications=[
                        VerificationResult(
                            status=ResultStatus.SUCCESS,
                            elapsed=1.0,
                            last_execution_time=datetime.datetime(
                                2005, 12, 2, 15, 4, 5
                            ),
                        ),
                    ],
                ),
                "test/foo3.py": FileResult(
                    newest=True,
                    content_hash="hash:test/foo3.py",
                    verifications=[
                        VerificationResult(
                            status=ResultStatus.SUCCESS,
                            elapsed=2.0,
                            last_execution_time=datetime.datetime(2007, 1, 2, 15, 4, 5),
                        ),
                    ],
                ),
                "test/skip.py": FileResult(
                    newest=True,
                    content_hash="hash:test/skip.py",
                    verifications=[
                        VerificationResult(
                            status=ResultStatus.SUCCESS,
                            elapsed=2.0,
                            last_execution_time=datetime.datetime(2007, 1, 2, 15, 4, 5),
                        ),
                    ],
                ),
            },
        },
    ),
]


@pytest.mark.usefixtures("mock_perf_counter")
@pytest.mark.parametrize(
    ("verifier", "expected"),
    test_verify_params,
)
def test_verify(
    verifier: MockVerifier,
    expected: Any,
    mocker: MockerFixture,
):
    mocker.patch.object(pathlib.Path, "exists", return_value=True)
    assert verifier.verify(download=False) == VerifyCommandResult.model_validate(
        expected
    )


@pytest.mark.parametrize("change_detection", ["timestamp", "hash"])
@pytest.mark.parametrize("lightweight", [False, True])
@pytest.mark.parametrize("changed_file", [None, "source.py", "dependency.py"])
def test_verify_content_hash_during_execution(
    testtemp: pathlib.Path,
    mocker: MockerFixture,
    change_detection: ChangeDetection,
    lightweight: bool,
    changed_file: str | None,
):
    source = pathlib.Path("source.py")
    dependency = pathlib.Path("dependency.py")
    source.write_bytes(b"original source")
    dependency.write_bytes(b"original dependency")
    verification_class = (
        ConstVerification if lightweight else NotSkippableConstVerification
    )
    verifier = Verifier(
        VerificationInput.model_validate(
            {
                "files": {
                    source: {
                        "dependencies": [dependency],
                        "verification": verification_class(status=SUCCESS),
                    },
                    dependency: {},
                },
            }
        ),
        timeout=10,
        default_tle=None,
        default_mle=None,
        prev_result=None,
        split_state=None,
        use_git_timestamp=False,
        change_detection=change_detection,
    )
    original_hash = verifier.file_content_hash(source)
    assert original_hash is not None

    def run_verification(
        verification: Verification,
        *,
        deadline: float = float("inf"),
    ) -> tuple[ResultStatus, None]:
        if changed_file is not None:
            pathlib.Path(changed_file).write_bytes(b"changed during verification")
        return SUCCESS, None

    run = mocker.patch.object(
        verifier, "run_verification", side_effect=run_verification
    )
    result = verifier.verify(download=False)
    run.assert_called_once()
    assert result.is_success()
    file_result = result.files[source]
    if changed_file is None:
        assert file_result.content_hash == original_hash
    else:
        assert file_result.content_hash is None

    verifier.change_detection = "hash"
    assert verifier.file_need_verification(source, file_result) is (
        changed_file is not None
    )


@pytest.mark.allow_mkdir
@pytest.mark.parametrize("change_detection", ["timestamp", "hash"])
@pytest.mark.parametrize("download", [False, True])
@pytest.mark.parametrize("change", ["unchanged", "input", "output", "missing"])
def test_verify_testdata_hash_during_execution(
    testtemp: pathlib.Path,
    mocker: MockerFixture,
    change_detection: ChangeDetection,
    download: bool,
    change: str,
):
    source = pathlib.Path("source.py")
    source.write_bytes(b"source")
    cases = pathlib.Path("cases")
    input_path = cases / "a.in"
    output_path = cases / "a.out"

    def prepare_cases(*args: Any, **kwargs: Any) -> bool:
        cases.mkdir()
        input_path.write_bytes(b"1 2\n")
        output_path.write_bytes(b"3\n")
        return True

    if not download:
        prepare_cases()
    download_cases = mocker.patch(
        "competitive_verifier.verify.verifier.run_download", side_effect=prepare_cases
    )
    verifier = Verifier(
        VerificationInput.model_validate(
            {
                "files": {
                    source: {
                        "verification": LocalProblemVerification(
                            command="true", input=cases
                        )
                    }
                }
            }
        ),
        timeout=10,
        default_tle=None,
        default_mle=None,
        prev_result=None,
        split_state=None,
        use_git_timestamp=False,
        change_detection=change_detection,
    )
    executed_hashes: list[str] = []

    def run_verification(*args: Any, **kwargs: Any) -> tuple[ResultStatus, None]:
        testdata_hash = verifier.file_testdata_hash(source, cached=True)
        assert testdata_hash is not None
        executed_hashes.append(testdata_hash)
        if change == "input":
            input_path.write_bytes(b"1 3\n")
        elif change == "output":
            output_path.write_bytes(b"4\n")
        elif change == "missing":
            input_path.unlink()
            output_path.unlink()
            cases.rmdir()
        return SUCCESS, None

    run = mocker.patch.object(
        verifier, "run_verification", side_effect=run_verification
    )
    result = verifier.verify(download=download)
    assert result.is_success()
    run.assert_called_once()
    assert download_cases.call_count == int(download)
    file_result = result.files[source]
    if change == "unchanged":
        assert file_result.testdata_hash == executed_hashes[0]
    else:
        assert file_result.testdata_hash is None

    verifier.change_detection = "hash"
    assert verifier.file_need_verification(source, file_result) is (
        change != "unchanged"
    )


@pytest.mark.allow_mkdir
def test_verify_rechecks_local_cases_with_nul_bytes(
    testtemp: pathlib.Path, mocker: MockerFixture
):
    source = pathlib.Path("source.py")
    source.write_text("source")
    cases = pathlib.Path("cases")
    cases.mkdir()
    input_path = cases / "a.in"
    output_path = cases / "a.out"
    input_path.write_bytes(b"a\0b")
    output_path.write_bytes(b"c")
    verifications = VerificationInput.model_validate(
        {
            "files": {
                source: {
                    "verification": LocalProblemVerification(
                        command="true", input=cases
                    )
                }
            }
        }
    )

    def verify(previous: VerifyCommandResult | None = None) -> VerifyCommandResult:
        return Verifier(
            verifications,
            timeout=10,
            default_tle=None,
            default_mle=None,
            prev_result=previous,
            split_state=None,
            use_git_timestamp=False,
            change_detection="hash",
        ).verify(download=False)

    run = mocker.patch.object(
        Verifier, "run_verification", return_value=(SUCCESS, None)
    )
    previous = verify()
    assert previous.is_success()
    assert previous.files[source].testdata_hash is not None
    reused = verify(previous)
    assert not reused.files[source].newest
    run.assert_called_once()

    input_path.write_bytes(b"a")
    output_path.write_bytes(b"b\0c")
    current = verify(reused)
    assert current.is_success()
    assert current.files[source].newest
    assert current.files[source].testdata_hash != previous.files[source].testdata_hash
    assert run.call_count == 2
    assert not verify(current).files[source].newest
    assert run.call_count == 2


@pytest.mark.allow_mkdir
@pytest.mark.parametrize("with_previous_result", [False, True])
def test_verify_continues_after_local_case_read_error(
    testtemp: pathlib.Path, mocker: MockerFixture, with_previous_result: bool
):
    source = pathlib.Path("source.py")
    other_source = pathlib.Path("other.py")
    source.write_text("source")
    other_source.write_text("other source")
    cases = pathlib.Path("cases")
    cases.mkdir()
    input_path = cases / "a.in"
    input_path.write_bytes(b"1 2\n")
    (cases / "a.out").write_bytes(b"3\n")
    verifications = VerificationInput.model_validate(
        {
            "files": {
                source: {
                    "verification": LocalProblemVerification(
                        command="true", input=cases
                    )
                },
                other_source: {
                    "verification": NotSkippableConstVerification(status=SUCCESS)
                },
            }
        }
    )

    def create_verifier(previous: VerifyCommandResult | None = None) -> Verifier:
        return Verifier(
            verifications,
            timeout=10,
            default_tle=None,
            default_mle=None,
            prev_result=previous,
            split_state=None,
            use_git_timestamp=False,
            change_detection="hash",
        )

    def run_verification(
        verification: Verification, *, deadline: float = float("inf")
    ) -> tuple[ResultStatus, None]:
        if isinstance(verification, LocalProblemVerification):
            input_path.read_bytes()
        return SUCCESS, None

    run = mocker.patch.object(
        Verifier, "run_verification", side_effect=run_verification
    )
    previous = (
        create_verifier().verify(download=False) if with_previous_result else None
    )
    if previous is not None:
        assert previous.is_success()
        assert previous.files[source].testdata_hash is not None
        other_source.write_text("changed source")
    run.reset_mock()
    original_read_bytes = pathlib.Path.read_bytes

    def read_bytes(path: pathlib.Path) -> bytes:
        if path == input_path:
            raise PermissionError("Cannot read local input")
        return original_read_bytes(path)

    mocker.patch.object(
        pathlib.Path, "read_bytes", autospec=True, side_effect=read_bytes
    )
    result = create_verifier(previous).verify(download=False)

    assert not result.is_success()
    assert result.files[source].newest
    assert result.files[source].verifications[0].status == FAILURE
    assert result.files[source].testdata_hash is None
    assert result.files[other_source].newest
    assert result.files[other_source].verifications[0].status == SUCCESS
    assert run.call_count == 2


@pytest.mark.parametrize(
    "change",
    [
        "unchanged",
        "command",
        "compile",
        "problem",
        "added",
        "default_tle",
        "default_mle",
        "legacy_hash",
    ],
)
def test_verify_reuses_only_matching_configuration(
    testtemp: pathlib.Path,
    mocker: MockerFixture,
    change: str,
):
    source = pathlib.Path("source.py")
    source.write_bytes(b"unchanged source")
    verification = {
        "type": "problem",
        "command": "run source.py",
        "compile": "compile source.py",
        "problem": "https://judge.yosupo.jp/problem/aplusb",
    }
    verification_list = [verification]

    def create_verifier(
        prev_result: VerifyCommandResult | None = None,
        *,
        default_tle: float | None = None,
        default_mle: float | None = None,
    ) -> Verifier:
        return Verifier(
            VerificationInput.model_validate(
                {"files": {source: {"verification": verification_list}}}
            ),
            timeout=10,
            default_tle=default_tle,
            default_mle=default_mle,
            prev_result=prev_result,
            split_state=None,
            use_git_timestamp=False,
            change_detection="hash",
        )

    mocker.patch.object(ProblemVerification, "is_testdata_cached", return_value=True)
    verifier = create_verifier()
    initial_run = mocker.patch.object(
        verifier, "run_verification", return_value=(SUCCESS, None)
    )
    previous = verifier.verify(download=False)
    initial_run.assert_called_once()
    assert previous.is_success()

    if change in {"command", "compile", "problem"}:
        verification[change] += "-changed"
    elif change == "added":
        verification_list.append({**verification, "name": "additional verification"})
    elif change == "legacy_hash":
        previous.files[source].content_hash = content_hash([source])

    verifier = create_verifier(
        VerifyCommandResult.model_validate_json(previous.model_dump_json()),
        default_tle=1.0 if change == "default_tle" else None,
        default_mle=64.0 if change == "default_mle" else None,
    )
    subsequent_run = mocker.patch.object(
        verifier, "run_verification", return_value=(SUCCESS, None)
    )
    result = verifier.verify(download=False)
    assert result.is_success()
    assert result.files[source].newest is (change != "unchanged")
    assert subsequent_run.call_count == (
        0 if change == "unchanged" else len(verification_list)
    )


@pytest.mark.allow_mkdir
@pytest.mark.parametrize("download", [False, True])
@pytest.mark.parametrize(
    "cache_change",
    [
        "input",
        "output",
        "missing_input",
        "missing_output",
        "checker_source",
        "common_header",
        "judging_config",
        "checker_binary",
    ],
)
def test_verify_regenerates_stale_library_checker_cases_after_no_download(
    testtemp: pathlib.Path,
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    download: bool,
    cache_change: str,
):
    monkeypatch.setenv(COMPETITIVE_VERIFY_CONFIG_PATH, str(testtemp / "config"))
    problem = LibraryCheckerProblem(problem_id="aplusb")
    directory = problem.repo_path / "sample" / "aplusb"
    (directory / "in").mkdir(parents=True)
    (directory / "out").mkdir()
    (directory / "info.toml").write_text("")
    for path in [
        directory / "checker.cpp",
        problem.repo_path / "generate.py",
        problem.repo_path / "common/testlib.h",
    ]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("original judging source")
    input_path = directory / "in" / "example_00.in"
    input_path.write_bytes(b"1 2\n")
    output = directory / "out" / "example_00.out"
    output.write_bytes(b"stale output\n")
    manifest = json.dumps(
        {
            "example_00.in": hashlib.sha256(b"1 2\n").hexdigest(),
            "example_00.out": hashlib.sha256(b"3\n").hexdigest(),
        }
    )
    problem.hash_json.write_text(manifest)
    source = pathlib.Path("source.py")
    source.write_text("source")
    verifications = VerificationInput.model_validate(
        {
            "files": {
                source: {
                    "verification": ProblemVerification(
                        command="true", problem=problem.url
                    )
                }
            }
        }
    )

    def create_verifier(previous: VerifyCommandResult | None = None) -> Verifier:
        return Verifier(
            verifications,
            timeout=10,
            default_tle=None,
            default_mle=None,
            prev_result=previous,
            split_state=None,
            use_git_timestamp=False,
            change_detection="hash",
        )

    def generate_cases(*args: object, **kwargs: object) -> None:
        input_path.write_bytes(b"1 2\n")
        output.write_bytes(b"3\n")
        problem.hash_json.write_text(manifest)
        if not problem.checker.exists():
            problem.checker.write_text(f"compiled checker: {problem.testdata_hash()}")

    mocker.patch.object(LibraryCheckerProblem, "update_cloned_repository")
    generate = mocker.patch(
        "competitive_verifier.oj.problem.subprocess.check_call",
        side_effect=generate_cases,
    )
    run = mocker.patch.object(
        Verifier, "run_verification", return_value=(SUCCESS, None)
    )
    previous = create_verifier().verify(download=False)
    assert previous.is_success()
    assert previous.files[source].testdata_hash is None
    assert output.read_bytes() == b"stale output\n"
    generate.assert_not_called()
    run.assert_called_once()

    current = create_verifier(previous).verify()
    assert current.is_success()
    assert current.files[source].newest
    assert current.files[source].testdata_hash is not None
    assert output.read_bytes() == b"3\n"
    generate.assert_called_once()
    assert run.call_count == 2

    reused = create_verifier(current).verify()
    assert not reused.files[source].newest
    generate.assert_called_once()
    assert run.call_count == 2

    if cache_change == "input":
        input_path.write_bytes(b"modified input\n")
    elif cache_change == "output":
        output.write_bytes(b"modified output\n")
    elif cache_change == "missing_input":
        input_path.unlink()
    elif cache_change == "missing_output":
        output.unlink()
    else:
        changed_path = {
            "checker_source": directory / "checker.cpp",
            "common_header": problem.repo_path / "common/testlib.h",
            "judging_config": directory / "info.toml",
            "checker_binary": problem.checker,
        }[cache_change]
        changed_path.write_bytes(b"changed judging source or binary")
    reverified = create_verifier(reused).verify(download=download)
    assert reverified.files[source].newest
    if download:
        assert reverified.is_success()
        assert generate.call_count == 2
    else:
        assert reverified.files[source].testdata_hash is None
        assert reverified.is_success() is (
            cache_change not in {"missing_input", "missing_output"}
        )
        generate.assert_called_once()
        reverified = create_verifier(reverified).verify()
        assert reverified.is_success()
        assert generate.call_count == 2
    assert reverified.files[
        source
    ].testdata_hash == create_verifier().file_testdata_hash(source)
    assert (
        reverified.files[source].testdata_hash != current.files[source].testdata_hash
    ) is (cache_change in {"checker_source", "common_header", "judging_config"})
    reused = create_verifier(reverified).verify()
    assert not reused.files[source].newest
    assert generate.call_count == 2


test_verify_timeout_params: list[
    tuple[
        MockVerifier,
        list[float],
        dict[str, Any],
    ]
] = [
    (
        MockVerifier(
            {
                "files": {
                    "lib/hoge1.py": {},
                    "test/foo.py": {
                        "dependencies": ["lib/hoge1.py"],
                        "verification": [
                            NotSkippableConstVerification(status=ResultStatus.SUCCESS)
                        ],
                    },
                }
            },
            verification_time=datetime.datetime(2007, 1, 2, 15, 4, 5),
        ),
        [0.0, 11.0, 12.0, 13.0, 14.0],
        {
            "total_seconds": 14.0,
            "files": {
                "test/foo.py": FileResult(
                    newest=True,
                    verifications=[
                        VerificationResult(
                            status=ResultStatus.SKIPPED,
                            elapsed=1.0,
                            last_execution_time=datetime.datetime(2007, 1, 2, 15, 4, 5),
                        ),
                    ],
                ),
            },
        },
    ),
    (
        MockVerifier(
            {
                "files": {
                    "lib/hoge1.py": {},
                    "test/foo.py": {
                        "dependencies": ["lib/hoge1.py"],
                        "verification": [
                            NotSkippableConstVerification(status=ResultStatus.SUCCESS)
                        ],
                    },
                }
            },
            verification_time=datetime.datetime(2007, 1, 2, 15, 4, 5),
        ),
        [0.0, 5.0, 11.0, 12.0, 13.0],
        {
            "total_seconds": 13.0,
            "files": {
                "test/foo.py": FileResult(
                    newest=True,
                    verifications=[
                        VerificationResult(
                            status=ResultStatus.SKIPPED,
                            elapsed=1.0,
                            last_execution_time=datetime.datetime(2007, 1, 2, 15, 4, 5),
                        ),
                    ],
                ),
            },
        },
    ),
    (
        MockVerifier(
            {
                "files": {
                    "lib/hoge1.py": {},
                    "test/foo.py": {
                        "dependencies": ["lib/hoge1.py"],
                        "verification": [
                            NotSkippableConstVerification(status=ResultStatus.SUCCESS)
                        ],
                    },
                }
            },
            verification_time=datetime.datetime(2007, 1, 2, 15, 4, 5),
        ),
        [0.0, 5.0, 6.0, 11.0, 12.0, 13.0],
        {
            "total_seconds": 13.0,
            "files": {
                "test/foo.py": FileResult(
                    newest=True,
                    verifications=[
                        VerificationResult(
                            status=ResultStatus.SKIPPED,
                            elapsed=6.0,
                            last_execution_time=datetime.datetime(2007, 1, 2, 15, 4, 5),
                        ),
                    ],
                ),
            },
        },
    ),
    (
        MockVerifier(
            {
                "files": {
                    "lib/hoge1.py": {},
                    "test/foo1.py": {
                        "dependencies": ["lib/hoge1.py"],
                        "verification": [
                            NotSkippableConstVerification(status=ResultStatus.SUCCESS)
                        ],
                    },
                    "test/foo2.py": {
                        "dependencies": ["lib/hoge1.py"],
                        "verification": [
                            NotSkippableConstVerification(status=ResultStatus.SUCCESS)
                        ],
                    },
                }
            },
            verification_time=datetime.datetime(2007, 1, 2, 15, 4, 5),
        ),
        [0.0, 5.0, 6.0, 7.0, 8.0, 11.0, 12.0, 13.0, 14.0],
        {
            "total_seconds": 14.0,
            "files": {
                "test/foo1.py": FileResult(
                    newest=True,
                    verifications=[
                        VerificationResult(
                            status=ResultStatus.SUCCESS,
                            elapsed=2.0,
                            last_execution_time=datetime.datetime(2007, 1, 2, 15, 4, 5),
                        ),
                    ],
                ),
                "test/foo2.py": FileResult(
                    newest=True,
                    verifications=[
                        VerificationResult(
                            status=ResultStatus.SKIPPED,
                            elapsed=1.0,
                            last_execution_time=datetime.datetime(2007, 1, 2, 15, 4, 5),
                        ),
                    ],
                ),
            },
        },
    ),
    (
        MockVerifier(
            {
                "files": {
                    "lib/hoge1.py": {},
                    "test/foo.py": {
                        "dependencies": ["lib/hoge1.py"],
                        "verification": [
                            NotSkippableConstVerification(status=ResultStatus.SUCCESS),
                            NotSkippableConstVerification(status=ResultStatus.SUCCESS),
                        ],
                    },
                }
            },
            verification_time=datetime.datetime(2007, 1, 2, 15, 4, 5),
        ),
        [0.0, 5.0, 6.0, 7.0, 8.0, 11.0, 12.0, 13.0],
        {
            "total_seconds": 13.0,
            "files": {
                "test/foo.py": FileResult(
                    newest=True,
                    verifications=[
                        VerificationResult(
                            status=ResultStatus.SUCCESS,
                            elapsed=2.0,
                            last_execution_time=datetime.datetime(2007, 1, 2, 15, 4, 5),
                        ),
                        VerificationResult(
                            status=ResultStatus.SKIPPED,
                            elapsed=1.0,
                            last_execution_time=datetime.datetime(2007, 1, 2, 15, 4, 5),
                        ),
                    ],
                ),
            },
        },
    ),
]


@pytest.mark.usefixtures("mock_perf_counter")
@pytest.mark.parametrize(
    ("verifier", "mock_perf_counter", "expected"),
    test_verify_timeout_params,
    indirect=["mock_perf_counter"],
)
def test_verify_timeout(
    mocker: MockerFixture,
    verifier: MockVerifier,
    expected: dict[str, Any],
):
    """Test timeout exception scenarios in enumerate_verifications."""
    mocker.patch.object(pathlib.Path, "exists", return_value=True)
    download = mocker.patch(
        "competitive_verifier.verify.verifier.run_download", return_value=True
    )

    result = verifier.verify(download=False)
    assert result == VerifyCommandResult.model_validate(expected)
    download.assert_not_called()


@pytest.mark.usefixtures("mock_perf_counter")
def test_verify_download_error(
    mocker: MockerFixture,
    caplog: pytest.LogCaptureFixture,
):
    mocker.patch("competitive_verifier.oj.download", return_value=False)
    verification = [
        ProblemVerification(
            name="foo",
            command="false",
            problem="https://judge.yosupo.jp/problem/aplusb",
        ),
        ProblemVerification(
            name="bar",
            command="false",
            problem="https://judge.yosupo.jp/problem/aplusb",
        ),
    ]
    verifier = MockVerifier(
        {
            "files": {
                "lib/hoge1.py": {},
                "test/foo.py": {
                    "dependencies": ["lib/hoge1.py"],
                    "verification": verification,
                },
            }
        },
        verification_time=datetime.datetime(2007, 1, 2, 15, 4, 5),
    )
    result = verifier.verify(download=True)
    assert result.model_dump(exclude_none=True) == {
        "total_seconds": 4.0,
        "files": {
            pathlib.Path("test/foo.py"): {
                "newest": True,
                "verifications": [
                    {
                        "elapsed": 1.0,
                        "last_execution_time": datetime.datetime(2007, 1, 2, 15, 4, 5),
                        "status": ResultStatus.FAILURE,
                    },
                ],
            }
        },
    }
    assert caplog.records == [
        LogComparer(
            f"Failed to download: {verification}",
            logging.ERROR,
            github=GitHubMessageParams(),
        ),
    ]


@pytest.mark.usefixtures("mock_perf_counter")
def test_verify_not_downloaded(
    mocker: MockerFixture,
    caplog: pytest.LogCaptureFixture,
):
    mocker.patch(
        "competitive_verifier.models.ProblemVerification.is_testdata_cached",
        return_value=False,
    )
    verification = [
        ProblemVerification(
            name="foo",
            command="false",
            problem="https://judge.yosupo.jp/problem/aplusb",
        ),
    ]
    verifier = MockVerifier(
        {
            "files": {
                "lib/hoge1.py": {},
                "test/foo.py": {
                    "dependencies": ["lib/hoge1.py"],
                    "verification": verification,
                },
            }
        },
        verification_time=datetime.datetime(2007, 1, 2, 15, 4, 5),
    )
    result = verifier.verify(download=False)
    assert result.model_dump(exclude_none=True) == {
        "total_seconds": 4.0,
        "files": {
            pathlib.Path("test/foo.py"): {
                "newest": True,
                "verifications": [
                    {
                        "elapsed": 1.0,
                        "last_execution_time": datetime.datetime(2007, 1, 2, 15, 4, 5),
                        "status": ResultStatus.FAILURE,
                    },
                ],
            }
        },
    }
    assert caplog.records == [
        LogComparer(
            f"Failed to download: {verification}",
            logging.ERROR,
            github=GitHubMessageParams(),
        ),
    ]


@pytest.mark.allow_mkdir
@pytest.mark.parametrize("extension", ["in", "out"])
def test_verify_rejects_incomplete_testdata_cache(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
    extension: str,
):
    monkeypatch.setenv(COMPETITIVE_VERIFY_CONFIG_PATH, tmp_path.as_posix())
    problem = YukicoderProblem(problem_no=1088)
    problem.test_directory.mkdir(parents=True)
    (problem.test_directory / f"sample_00.{extension}").write_text("1 2\n")
    verifier = MockVerifier(
        {
            "files": {
                "test/foo.py": {
                    "verification": ProblemVerification(
                        command="false", problem=problem.url
                    ),
                },
            },
        },
        verification_time=datetime.datetime(2007, 1, 2, 15, 4, 5),
    )
    download = mocker.patch("competitive_verifier.verify.verifier.run_download")
    run = mocker.patch.object(
        verifier, "run_verification", return_value=(ResultStatus.SUCCESS, None)
    )

    result = verifier.verify(download=False)

    assert [
        v.status for v in result.files[pathlib.Path("test/foo.py")].verifications
    ] == [ResultStatus.FAILURE]
    download.assert_not_called()
    run.assert_not_called()


@pytest.mark.usefixtures("mock_perf_counter")
@pytest.mark.parametrize("is_github_actions", [False, True])
def test_verify_compile_error(
    is_github_actions: bool,
    mocker: MockerFixture,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
):
    mocker.patch.dict(os.environ, {"GITHUB_ACTIONS": str(is_github_actions)})

    mocker.patch.object(
        pathlib.Path, "resolve", return_value=pathlib.Path("/any/dir/test/mock.py")
    )
    mocker.patch(
        "competitive_verifier.models.ProblemVerification.run_compile_command",
        return_value=False,
    )
    mocker.patch(
        "competitive_verifier.models.ProblemVerification.is_testdata_cached",
        return_value=True,
    )
    verifier = MockVerifier(
        {
            "files": {
                "lib/hoge1.py": {},
                "test/foo.py": {
                    "dependencies": ["lib/hoge1.py"],
                    "verification": [
                        ProblemVerification(
                            name="foo",
                            command="false",
                            problem="https://judge.yosupo.jp/problem/aplusb",
                        ),
                        ProblemVerification(
                            name="bar",
                            command="false",
                            problem="https://judge.yosupo.jp/problem/aplusb",
                        ),
                    ],
                },
            }
        },
        verification_time=datetime.datetime(2007, 1, 2, 15, 4, 5),
    )
    result = verifier.verify(download=False)
    assert result.model_dump(exclude_none=True) == {
        "total_seconds": 6.0,
        "files": {
            pathlib.Path("test/foo.py"): {
                "newest": True,
                "verifications": [
                    {
                        "verification_name": "foo",
                        "elapsed": 1.0,
                        "last_execution_time": datetime.datetime(2007, 1, 2, 15, 4, 5),
                        "status": ResultStatus.FAILURE,
                    },
                    {
                        "verification_name": "bar",
                        "elapsed": 1.0,
                        "last_execution_time": datetime.datetime(2007, 1, 2, 15, 4, 5),
                        "status": ResultStatus.FAILURE,
                    },
                ],
            }
        },
    }
    assert caplog.records == [
        LogComparer(
            f"Failed to compile: {pathlib.Path('test/foo.py')}, "
            'verification={"name":"foo","command":"false","problem":"https://judge.yosupo.jp/problem/aplusb"}',
            logging.ERROR,
            github=GitHubMessageParams(file=pathlib.Path("test/foo.py")),
        ),
        LogComparer(
            f"Failed to compile: {pathlib.Path('test/foo.py')}, verification="
            '{"name":"bar","command":"false","problem":"https://judge.yosupo.jp/problem/aplusb"}',
            logging.ERROR,
            github=GitHubMessageParams(file=pathlib.Path("test/foo.py")),
        ),
    ]

    out, err = capsys.readouterr()

    assert out == ""
    if is_github_actions:
        assert err == (
            "::group::current_verification_files\n::endgroup::\n"
            "::group::Verify: test/foo.py\n::endgroup::\n"
        )
    else:
        assert err == (
            "<------------- \x1b[36m Start group:\x1b[33mcurrent_verification_files\x1b[0m ------------->\n"
            "<------------- \x1b[36mFinish group:\x1b[33mcurrent_verification_files\x1b[0m ------------->\n"
            "<------------- \x1b[36m Start group:\x1b[33mVerify: test/foo.py\x1b[0m ------------->\n"
            "<------------- \x1b[36mFinish group:\x1b[33mVerify: test/foo.py\x1b[0m ------------->\n"
        )


@pytest.mark.usefixtures("mock_perf_counter")
def test_verify_error(
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
):
    class ErrorVerification(ConstVerification):
        @property
        def is_lightweight(self) -> bool:
            return False

        def run(self, *args: Any, **kwargs: Any):
            raise RuntimeError("ErrorVerification")

    verifier = MockVerifier(
        {
            "files": {
                "lib/hoge1.py": {},
                "test/foo.py": {
                    "dependencies": ["lib/hoge1.py"],
                    "verification": [
                        ErrorVerification(
                            name="foo",
                            status=ResultStatus.FAILURE,
                        ),
                    ],
                },
            }
        },
        verification_time=datetime.datetime(2007, 1, 2, 15, 4, 5),
    )
    result = verifier.verify(download=False)
    assert result.model_dump(exclude_none=True) == {
        "total_seconds": 5.0,
        "files": {
            pathlib.Path("test/foo.py"): {
                "newest": True,
                "verifications": [
                    {
                        "verification_name": "foo",
                        "elapsed": 2.0,
                        "last_execution_time": datetime.datetime(2007, 1, 2, 15, 4, 5),
                        "status": ResultStatus.FAILURE,
                    },
                ],
            }
        },
    }
    assert caplog.records == [
        LogComparer(
            f"Failed to verify: {pathlib.Path('test/foo.py')}, "
            "ErrorVerification(name='foo', type='const', status=<ResultStatus.FAILURE: 'failure'>)",
            logging.ERROR,
            github=GitHubMessageParams(),
        ),
    ]

    out, err = capsys.readouterr()

    assert out == ""
    assert err == (
        "<------------- \x1b[36m Start group:\x1b[33mcurrent_verification_files\x1b[0m ------------->\n"
        "<------------- \x1b[36mFinish group:\x1b[33mcurrent_verification_files\x1b[0m ------------->\n"
        "<------------- \x1b[36m Start group:\x1b[33mVerify: test/foo.py\x1b[0m ------------->\n"
        "<------------- \x1b[36mFinish group:\x1b[33mVerify: test/foo.py\x1b[0m ------------->\n"
    )


@pytest.mark.usefixtures("mock_perf_counter")
@pytest.mark.parametrize("is_github_actions", [False, True])
def test_verify_failure(
    is_github_actions: bool,
    mocker: MockerFixture,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
):
    mocker.patch.dict(os.environ, {"GITHUB_ACTIONS": str(is_github_actions)})
    mocker.patch.object(
        pathlib.Path, "resolve", return_value=pathlib.Path("/any/dir/test/mock.py")
    )
    verifier = MockVerifier(
        {
            "files": {
                "lib/hoge1.py": {},
                "test/foo.py": {
                    "dependencies": ["lib/hoge1.py"],
                    "verification": [
                        ConstVerification(
                            name="foo",
                            status=ResultStatus.FAILURE,
                        ),
                    ],
                },
            }
        },
        verification_time=datetime.datetime(2007, 1, 2, 15, 4, 5),
    )
    result = verifier.verify(download=False)
    assert result.model_dump(exclude_none=True) == {
        "total_seconds": 4.0,
        "files": {
            pathlib.Path("test/foo.py"): {
                "newest": True,
                "verifications": [
                    {
                        "verification_name": "foo",
                        "elapsed": 2.0,
                        "last_execution_time": datetime.datetime(2007, 1, 2, 15, 4, 5),
                        "status": ResultStatus.FAILURE,
                    },
                ],
            }
        },
    }
    assert not caplog.records

    out, err = capsys.readouterr()

    if is_github_actions:
        assert out == ""
        assert err == "::group::current_verification_files\n::endgroup::\n"
    else:
        assert out == ""
        assert err == (
            "<------------- \x1b[36m Start group:\x1b[33mcurrent_verification_files\x1b[0m ------------->\n"
            "<------------- \x1b[36mFinish group:\x1b[33mcurrent_verification_files\x1b[0m ------------->\n"
        )


@pytest.mark.usefixtures("mock_perf_counter")
def test_failure_result():
    class ResultVerification(ProblemVerification):
        status: ResultStatus

        @property
        def is_lightweight(self) -> bool:
            return True

        def run(self, *args: Any, **kwargs: Any) -> VerificationResult:
            return VerificationResult(
                verification_name="mockresult",
                status=self.status,
                elapsed=1.2,
                last_execution_time=datetime.datetime(2007, 1, 2, 10, 4, 5),
            )

    verifier = MockVerifier(
        {
            "files": {
                "lib/hoge1.py": {},
                "test/foo.py": {
                    "dependencies": ["lib/hoge1.py"],
                    "verification": [
                        ResultVerification(
                            name="foo",
                            problem="https://example.com/problem",
                            command="unused",
                            status=ResultStatus.FAILURE,
                        ),
                    ],
                },
            }
        },
        verification_time=datetime.datetime(2007, 1, 2, 15, 4, 5),
    )
    result = verifier.verify(download=False)
    assert result.model_dump(exclude_none=True) == {
        "total_seconds": 3.0,
        "files": {
            pathlib.Path("test/foo.py"): {
                "newest": True,
                "verifications": [
                    {
                        "verification_name": "mockresult",
                        "elapsed": 1.2,
                        "last_execution_time": datetime.datetime(2007, 1, 2, 10, 4, 5),
                        "status": ResultStatus.FAILURE,
                    },
                ],
            }
        },
    }


@pytest.mark.usefixtures("mock_perf_counter")
@pytest.mark.parametrize(
    ("download", "change_detection", "synced"),
    [
        (True, "hash", True),
        (False, "hash", False),
        (True, "timestamp", False),
    ],
)
def test_verify_syncs_testdata_before_skip_selection(
    mocker: MockerFixture,
    download: bool,
    change_detection: ChangeDetection,
    synced: bool,
):
    mocker.patch.object(pathlib.Path, "exists", return_value=True)
    update = mocker.patch.object(LibraryCheckerProblem, "update_cloned_repository")
    run_download = mocker.patch(
        "competitive_verifier.verify.verifier.run_download", return_value=True
    )
    synced_before_hash: list[int] = []

    def file_testdata_hash(path: pathlib.Path, *, cached: bool = False) -> str:
        synced_before_hash.append(update.call_count)
        return "testdata-foo"

    mocker.patch.object(
        MockVerifier, "file_testdata_hash", side_effect=file_testdata_hash
    )

    verifier = MockVerifier(
        {
            "files": {
                "test/foo.py": {
                    "verification": ProblemVerification(
                        command="false",
                        problem="https://judge.yosupo.jp/problem/aplusb",
                    ),
                },
            }
        },
        verification_time=datetime.datetime(2007, 1, 2, 15, 4, 5),
        prev_result=VerifyCommandResult(
            total_seconds=1.0,
            files={
                pathlib.Path("test/foo.py"): FileResult(
                    content_hash="hash-foo",
                    testdata_hash="testdata-foo",
                    verifications=[
                        VerificationResult(
                            status=SUCCESS,
                            elapsed=1.0,
                            last_execution_time=datetime.datetime(2006, 1, 2),
                        )
                    ],
                )
            },
        ),
        file_hashes={"test/foo.py": "hash-foo"},
        change_detection=change_detection,
    )
    result = verifier.verify(download=download)

    assert result.files[pathlib.Path("test/foo.py")].verifications[0].status == SUCCESS
    assert update.call_count == (1 if synced else 0)
    if synced:
        assert synced_before_hash == [1, 1]
    run_download.assert_not_called()
