import pytest

from competitive_verifier.oj.problem import (
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
