import datetime
import pathlib
from typing import Any

import pytest
from pytest_mock import MockerFixture

from competitive_verifier.models import ProblemVerification, VerificationInput
from competitive_verifier.verify.verifier import InputContainer, content_hash

pytestmark = pytest.mark.allow_mkdir


@pytest.fixture(autouse=True)
def chdir_tmp(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    pathlib.Path("foo.py").write_bytes(b"print(1)")
    pathlib.Path("bar.py").write_bytes(b"print(2)")


def test_content_hash_changes_with_content():
    before = content_hash([pathlib.Path("foo.py"), pathlib.Path("bar.py")])
    assert before is not None
    pathlib.Path("bar.py").write_bytes(b"print(3)")
    assert content_hash([pathlib.Path("foo.py"), pathlib.Path("bar.py")]) != before


def test_content_hash_preserves_file_boundaries_with_nul_bytes():
    files = [pathlib.Path("a"), pathlib.Path("b")]
    files[0].write_bytes(b"x")
    files[1].write_bytes(b"\0b\0y")
    before = content_hash(files)
    assert before is not None

    files[0].write_bytes(b"x\0b\0")
    files[1].write_bytes(b"y")
    after = content_hash(files)
    assert after is not None
    assert after != before


def test_content_hash_changes_with_path():
    before = content_hash([pathlib.Path("foo.py")])
    pathlib.Path("foo.py").rename("baz.py")
    assert content_hash([pathlib.Path("baz.py")]) != before


def test_content_hash_ignores_order():
    assert content_hash([pathlib.Path("foo.py"), pathlib.Path("bar.py")]) == (
        content_hash([pathlib.Path("bar.py"), pathlib.Path("foo.py")])
    )


def test_content_hash_none_when_file_missing():
    assert content_hash([pathlib.Path("foo.py"), pathlib.Path("missing.py")]) is None


class HashInputContainer(InputContainer):
    def __init__(self, verifications: VerificationInput) -> None:
        super().__init__(
            verifications=verifications,
            verification_time=datetime.datetime.now(),
            prev_result=None,
            split_state=None,
        )

    def get_file_timestamp(self, path: pathlib.Path) -> datetime.datetime:
        raise NotImplementedError


def _file_content_hash(obj: dict[str, Any], path: str = "foo.py") -> str | None:
    return HashInputContainer(VerificationInput.model_validate(obj)).file_content_hash(
        pathlib.Path(path)
    )


def _file_testdata_hash(obj: dict[str, Any], path: str = "foo.py") -> str | None:
    return HashInputContainer(VerificationInput.model_validate(obj)).file_testdata_hash(
        pathlib.Path(path)
    )


def _problem() -> dict[str, Any]:
    return {
        "files": {
            "foo.py": {
                "verification": {
                    "type": "problem",
                    "problem": "https://judge.yosupo.jp/problem/aplusb",
                    "command": "true",
                },
            },
        },
    }


def _input() -> dict[str, Any]:
    return {
        "files": {
            "foo.py": {
                "dependencies": ["bar.py"],
                "verification": {
                    "type": "local",
                    "input": "cases",
                    "command": "true",
                },
            },
            "bar.py": {},
        },
    }


def test_file_content_hash_covers_transitive_dependencies():
    obj = _input()
    obj["files"]["bar.py"]["dependencies"] = ["baz.py"]
    obj["files"]["baz.py"] = {}
    pathlib.Path("baz.py").write_bytes(b"print(3)")
    before = _file_content_hash(obj)
    assert before is not None
    pathlib.Path("baz.py").write_bytes(b"print(4)")
    assert _file_content_hash(obj) != before


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("command", "false"),
        ("command", {"command": "true", "env": {"MODE": "strict"}}),
        ("command", {"command": "true", "cwd": "other"}),
        ("compile", "compile foo.py"),
        ("input", "other-cases"),
        ("name", "other-verification"),
        ("tle", 1.0),
        ("mle", 64.0),
        ("error", 1e-6),
        ("tempdir", "other-tempdir"),
    ],
)
def test_file_content_hash_changes_with_verification_settings(field: str, value: Any):
    obj = _input()
    before = _file_content_hash(obj)
    assert before is not None
    obj["files"]["foo.py"]["verification"][field] = value
    assert _file_content_hash(obj) != before


def test_file_content_hash_changes_with_problem_url():
    obj = _input()
    obj["files"]["foo.py"]["verification"] = {
        "type": "problem",
        "command": "true",
        "problem": "https://judge.yosupo.jp/problem/aplusb",
    }
    before = _file_content_hash(obj)
    assert before is not None
    obj["files"]["foo.py"]["verification"]["problem"] = (
        "https://judge.yosupo.jp/problem/many_aplusb"
    )
    assert _file_content_hash(obj) != before


def test_file_content_hash_normalizes_verification_list_and_key_order():
    obj = _input()
    verification = obj["files"]["foo.py"]["verification"]
    verification["command"] = {"command": "true", "env": {"A": "1", "B": "2"}}
    before = _file_content_hash(obj)
    assert before is not None
    verification["command"]["env"] = {"B": "2", "A": "1"}
    obj["files"]["foo.py"]["verification"] = [verification]
    assert _file_content_hash(obj) == before


def test_file_content_hash_ignores_documentation_and_other_verifications():
    obj = _input()
    before = _file_content_hash(obj)
    assert before is not None
    obj["files"]["foo.py"]["document_attributes"] = {"TITLE": "New title"}
    obj["files"]["bar.py"]["verification"] = {"type": "command", "command": "false"}
    assert _file_content_hash(obj) == before


def test_file_content_hash_none_for_unknown_file():
    assert _file_content_hash(_input(), "unknown.py") is None


def test_file_content_hash_none_for_missing_dependency():
    pathlib.Path("bar.py").unlink()
    assert _file_content_hash(_input()) is None


def test_file_content_hash_ignores_testdata(mocker: MockerFixture):
    cases = pathlib.Path("cases")
    cases.mkdir()
    (cases / "a.in").write_bytes(b"1 2\n")
    (cases / "a.out").write_bytes(b"3\n")
    before = _file_content_hash(_input())
    (cases / "a.out").write_bytes(b"4\n")
    assert _file_content_hash(_input()) == before

    problem = _file_content_hash(_problem())
    mocker.patch.object(ProblemVerification, "testdata_hash", return_value="v1")
    assert _file_content_hash(_problem()) == problem


def test_file_testdata_hash_changes_with_local_cases():
    cases = pathlib.Path("cases")
    cases.mkdir()
    (cases / "a.in").write_bytes(b"1 2\n")
    (cases / "a.out").write_bytes(b"3\n")
    with_a = _file_testdata_hash(_input())
    assert with_a is not None
    assert with_a == _file_testdata_hash(_input())

    (cases / "a.out").write_bytes(b"4\n")
    with_a_changed = _file_testdata_hash(_input())
    assert with_a_changed != with_a

    (cases / "b.in").write_bytes(b"5 6\n")
    (cases / "b.out").write_bytes(b"11\n")
    with_a_b = _file_testdata_hash(_input())
    assert len({with_a, with_a_changed, with_a_b}) == 3

    (cases / "b.in").unlink()
    (cases / "b.out").unlink()
    assert _file_testdata_hash(_input()) == with_a_changed


def test_file_testdata_hash_none_when_local_cases_missing():
    assert _file_testdata_hash(_input()) is None
    cases = pathlib.Path("cases")
    cases.mkdir()
    empty = _file_testdata_hash(_input())
    assert empty is not None
    (cases / "a.in").write_bytes(b"1 2\n")
    (cases / "a.out").write_bytes(b"3\n")
    assert _file_testdata_hash(_input()) not in {None, empty}


def test_file_testdata_hash_combines_verifications(mocker: MockerFixture):
    hashes: list[str | None] = []
    for testdata_hash in ["version1", "version2"]:
        mocker.patch.object(
            ProblemVerification, "testdata_hash", return_value=testdata_hash
        )
        hashes.append(_file_testdata_hash(_problem()))
        assert _file_testdata_hash(_problem()) == hashes[-1]
    assert None not in hashes
    assert len(set(hashes)) == len(hashes)

    mocker.patch.object(ProblemVerification, "testdata_hash", return_value=None)
    assert _file_testdata_hash(_problem()) is None

    obj: dict[str, Any] = {
        "files": {"foo.py": {"verification": {"type": "command", "command": "true"}}}
    }
    assert _file_testdata_hash(obj) is None
