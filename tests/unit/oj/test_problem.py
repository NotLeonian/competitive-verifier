import hashlib
import json
import pathlib

import pytest
from pytest_mock import MockerFixture

from competitive_verifier.config import COMPETITIVE_VERIFY_CONFIG_PATH
from competitive_verifier.oj.problem import (
    LibraryCheckerProblem,
    LocalProblem,
    NotLoggedInError,
    YukicoderProblem,
    normalize_url_path,
    problem_from_url,
)

test_normalize_url_path_params: list[tuple[str, str]] = [
    ("hoge/foo/bar", "hoge/foo/bar"),
    ("/foo/bar", "/foo/bar"),
    ("//foo/bar", "/foo/bar"),
]


@pytest.mark.parametrize(
    ("path", "expected"),
    test_normalize_url_path_params,
    ids=[t[0] for t in test_normalize_url_path_params],
)
def test_normalize_url_path(path: str, expected: str):
    assert normalize_url_path(path) == expected


test_problem_repr_params = [
    (
        "https://onlinejudge.u-aizu.ac.jp/courses/lesson/2/ITP1/1/ITP1_1_A",
        "AOJProblem.from_url('http://judge.u-aizu.ac.jp/onlinejudge/description.jsp?id=ITP1_1_A')",
    ),
    (
        "https://onlinejudge.u-aizu.ac.jp/problems/ITP1_1_A",
        "AOJProblem.from_url('http://judge.u-aizu.ac.jp/onlinejudge/description.jsp?id=ITP1_1_A')",
    ),
    (
        "https://judge.u-aizu.ac.jp/onlinejudge/description.jsp?id=ITP1_1_A&lang=jp",
        "AOJProblem.from_url('http://judge.u-aizu.ac.jp/onlinejudge/description.jsp?id=ITP1_1_A')",
    ),
    (
        "https://onlinejudge.u-aizu.ac.jp/services/room.html#RitsCamp19Day2/problems/A",
        "AOJArenaProblem.from_url('https://onlinejudge.u-aizu.ac.jp/services/room.html#RitsCamp19Day2/problems/A')",
    ),
    (
        "https://old.yosupo.jp/problem/aplusb",
        "LibraryCheckerProblem.from_url('https://judge.yosupo.jp/problem/aplusb')",
    ),
    (
        "https://judge.yosupo.jp/problem/aplusb",
        "LibraryCheckerProblem.from_url('https://judge.yosupo.jp/problem/aplusb')",
    ),
    (
        "http://old.yosupo.jp/problem/aplusb",
        "LibraryCheckerProblem.from_url('https://judge.yosupo.jp/problem/aplusb')",
    ),
    (
        "http://judge.yosupo.jp/problem/aplusb",
        "LibraryCheckerProblem.from_url('https://judge.yosupo.jp/problem/aplusb')",
    ),
    (
        "https://yukicoder.me/problems/4573",
        "YukicoderProblem.from_url('https://yukicoder.me/problems/4573')",
    ),
    (
        "https://yukicoder.me/problems/no/1088",
        "YukicoderProblem.from_url('https://yukicoder.me/problems/no/1088')",
    ),
    (
        "http://yukicoder.me/problems/4573",
        "YukicoderProblem.from_url('https://yukicoder.me/problems/4573')",
    ),
    (
        "http://yukicoder.me/problems/no/1088",
        "YukicoderProblem.from_url('https://yukicoder.me/problems/no/1088')",
    ),
    (
        "http://yukicoder.me/4573",
        "None",
    ),
]


@pytest.mark.parametrize(
    ("url", "expected"),
    test_problem_repr_params,
    ids=[t[0] for t in test_problem_repr_params],
)
def test_problem_repr(url: str, expected: str):
    assert repr(problem_from_url(url)) == expected


def test_yukicoder_token_rejects_ansi_escape(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("YUKICODER_TOKEN", "dummy-token\x1b[C")

    with pytest.raises(NotLoggedInError, match="control characters"):
        YukicoderProblem.yukicoder_headers()


def test_yukicoder_token_rejects_surrounding_whitespace(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("YUKICODER_TOKEN", "dummy-token ")

    with pytest.raises(NotLoggedInError, match="whitespace"):
        YukicoderProblem.yukicoder_headers()


def test_yukicoder_token_rejects_assignment_text(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("YUKICODER_TOKEN", "YUKICODER_TOKEN=dummy-token")

    with pytest.raises(NotLoggedInError, match="assignment"):
        YukicoderProblem.yukicoder_headers()


def test_yukicoder_token_accepts_visible_ascii(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("YUKICODER_TOKEN", "abcDEF0123._-+/=")

    assert YukicoderProblem.yukicoder_headers() == {
        "Authorization": "Bearer abcDEF0123._-+/="
    }


@pytest.mark.allow_mkdir
@pytest.mark.parametrize(
    "url",
    [
        "https://onlinejudge.u-aizu.ac.jp/problems/ITP1_1_A",
        "https://yukicoder.me/problems/no/1088",
    ],
)
@pytest.mark.parametrize("extension", ["in", "out"])
def test_base_problem_is_testdata_cached(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    url: str,
    extension: str,
):
    monkeypatch.setenv(COMPETITIVE_VERIFY_CONFIG_PATH, tmp_path.as_posix())
    p = problem_from_url(url)
    assert p is not None
    assert p.is_testdata_cached() is False

    p.test_directory.mkdir(parents=True)
    assert p.is_testdata_cached() is False

    (p.test_directory / "README.txt").write_text("Test data cache")
    (p.test_directory / "subdir").mkdir()
    assert p.is_testdata_cached() is False

    (p.test_directory / f"sample_00.{extension}").write_text("1 2\n")
    assert p.is_testdata_cached() is False

    other_extension = "out" if extension == "in" else "in"
    (p.test_directory / f"sample_01.{other_extension}").write_text("3\n")
    assert p.is_testdata_cached() is False

    (p.test_directory / "sample_00.in").write_text("1 2\n")
    (p.test_directory / "sample_00.out").write_text("3\n")
    assert p.is_testdata_cached() is True


@pytest.mark.allow_mkdir
def test_library_checker_is_testdata_cached(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv(COMPETITIVE_VERIFY_CONFIG_PATH, tmp_path.as_posix())
    p = LibraryCheckerProblem(problem_id="aplusb")
    assert p.is_testdata_cached() is False

    source = p.repo_path / "sample" / "aplusb"
    source.mkdir(parents=True)
    (source / "info.toml").write_text("")
    assert p.is_testdata_cached() is False

    (source / "in").mkdir()
    (source / "out").mkdir()
    (source / "in" / "example_00.in").write_text("1 2\n")
    assert p.is_testdata_cached() is False

    (source / "out" / "example_00.out").write_text("3\n")
    assert p.is_testdata_cached() is True


@pytest.mark.allow_mkdir
def test_local_problem_is_testdata_cached(tmp_path: pathlib.Path):
    assert LocalProblem(tmp_path / "missing").is_testdata_cached() is True


@pytest.mark.allow_mkdir
@pytest.mark.parametrize("extension", ["in", "out"])
@pytest.mark.parametrize("error_type", [PermissionError, FileNotFoundError])
def test_local_problem_testdata_hash_unreadable_case(
    tmp_path: pathlib.Path,
    mocker: MockerFixture,
    extension: str,
    error_type: type[OSError],
):
    (tmp_path / "a.in").write_bytes(b"1 2\n")
    (tmp_path / "a.out").write_bytes(b"3\n")
    problem = LocalProblem(tmp_path)
    assert problem.testdata_hash() is not None
    original_read_bytes = pathlib.Path.read_bytes

    def read_bytes(path: pathlib.Path) -> bytes:
        if path == tmp_path / f"a.{extension}":
            raise error_type("Cannot read local case")
        return original_read_bytes(path)

    mocker.patch.object(
        pathlib.Path, "read_bytes", autospec=True, side_effect=read_bytes
    )
    assert problem.testdata_hash() is None


@pytest.mark.allow_mkdir
@pytest.mark.parametrize("operation", ["is_dir", "glob"])
def test_local_problem_testdata_hash_directory_error(
    tmp_path: pathlib.Path, mocker: MockerFixture, operation: str
):
    mocker.patch.object(
        pathlib.Path, operation, side_effect=PermissionError("Cannot access cases")
    )
    assert LocalProblem(tmp_path).testdata_hash() is None


@pytest.fixture
def library_checker_repo(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> pathlib.Path:
    monkeypatch.setenv("COMPETITIVE_VERIFY_CONFIG_PATH", str(tmp_path))
    repo_path = tmp_path / "cache" / "library-checker-problems"
    (repo_path / "sample" / "aplusb").mkdir(parents=True)
    (repo_path / "sample" / "aplusb" / "info.toml").write_text("")
    return repo_path


@pytest.mark.allow_mkdir
def test_library_checker_testdata_hash(
    library_checker_repo: pathlib.Path,
    mocker: MockerFixture,
):
    update = mocker.patch.object(LibraryCheckerProblem, "update_cloned_repository")
    problem = LibraryCheckerProblem(problem_id="aplusb")
    hash_json = library_checker_repo / "sample" / "aplusb" / "hash.json"
    assert problem.hash_json == hash_json

    assert problem.testdata_hash() is None

    hash_json.write_bytes(b'{"example_00.in": "0" * 64}')
    assert problem.testdata_hash() == hashlib.sha256(hash_json.read_bytes()).hexdigest()
    assert problem.testdata_hash() == problem.testdata_hash()

    hash_json.write_bytes(b'{"example_00.in": "1" * 64}')
    assert problem.testdata_hash() == hashlib.sha256(hash_json.read_bytes()).hexdigest()

    update.assert_not_called()


@pytest.mark.allow_mkdir
@pytest.mark.usefixtures("library_checker_repo")
def test_library_checker_testdata_hash_unknown_problem():
    problem = LibraryCheckerProblem(problem_id="no_such_problem")
    assert problem.testdata_hash() is None
    assert problem.cached_testdata_hash() is None


@pytest.mark.allow_mkdir
@pytest.mark.parametrize(
    "change", ["input", "output", "missing", "extra", "manifest", "invalid_manifest"]
)
def test_library_checker_cached_testdata_hash(
    library_checker_repo: pathlib.Path,
    mocker: MockerFixture,
    change: str,
):
    update = mocker.patch.object(LibraryCheckerProblem, "update_cloned_repository")
    problem = LibraryCheckerProblem(problem_id="aplusb")
    directory = problem.source_directory
    (directory / "in").mkdir()
    (directory / "out").mkdir()
    input_path = directory / "in" / "example_00.in"
    output_path = directory / "out" / "example_00.out"
    manifest = json.dumps(
        {
            "example_00.in": hashlib.sha256(b"1 2\n").hexdigest(),
            "example_00.out": hashlib.sha256(b"3\n").hexdigest(),
        }
    )
    problem.hash_json.write_text(manifest)
    assert problem.cached_testdata_hash() is None
    input_path.write_bytes(b"1 2\n")
    output_path.write_bytes(b"3\n")
    expected = problem.testdata_hash()
    assert expected is not None
    assert problem.cached_testdata_hash() == expected

    if change == "input":
        input_path.write_bytes(b"1 3\n")
    elif change == "output":
        output_path.write_bytes(b"4\n")
    elif change == "missing":
        output_path.unlink()
    elif change == "extra":
        (directory / "in" / "extra.in").write_bytes(b"1 2\n")
        (directory / "out" / "extra.out").write_bytes(b"3\n")
    elif change == "manifest":
        problem.hash_json.write_text(manifest.replace("example_00", "example_01"))
    else:
        problem.hash_json.write_text("invalid json")

    assert problem.cached_testdata_hash() is None
    update.assert_not_called()


def test_library_checker_sync_testdata(mocker: MockerFixture):
    update = mocker.patch.object(LibraryCheckerProblem, "update_cloned_repository")
    LibraryCheckerProblem(problem_id="aplusb").sync_testdata()
    update.assert_called_once_with()


def test_base_problem_sync_testdata(mocker: MockerFixture):
    download = mocker.patch.object(YukicoderProblem, "download_system_cases")
    YukicoderProblem(problem_no=1088).sync_testdata()
    download.assert_not_called()
