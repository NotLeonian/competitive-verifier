import pathlib

import yaml

from competitive_verifier.documents.config import ConfigYaml
from competitive_verifier.documents.path_sort import (
    PathSortOrder,
    path_sort_key_path,
)


def _sorted_path_values(
    values: list[str] | set[str],
    order: PathSortOrder | None,
) -> list[str]:
    paths = [pathlib.PurePosixPath(value) for value in values]
    return [
        path.as_posix()
        for path in sorted(paths, key=lambda path: path_sort_key_path(path, order))
    ]


def test_path_sort_is_not_serialized_by_default():
    dumped = yaml.safe_load(ConfigYaml().model_dump_yml())
    assert "path-sort" not in dumped


def test_path_sort_accepts_yaml_alias():
    config = ConfigYaml.model_validate({"path-sort": "natural"})
    assert config.path_sort == PathSortOrder.natural


def test_path_sort_accepts_python_field_name():
    config = ConfigYaml.model_validate({"path_sort": "natural"})
    assert config.path_sort == PathSortOrder.natural


def test_path_sort_serializes_with_yaml_alias_when_set():
    config = ConfigYaml(path_sort=PathSortOrder.natural)
    dumped = yaml.safe_load(config.model_dump_yml())
    assert dumped["path-sort"] == "natural"


def test_natural_path_sort_order():
    paths = [
        pathlib.PurePosixPath("verify/yukicoder-1907.test.cpp"),
        pathlib.PurePosixPath("verify/yukicoder-2362.test.cpp"),
        pathlib.PurePosixPath("verify/yukicoder-2603.test.cpp"),
        pathlib.PurePosixPath("verify/yukicoder-275.test.cpp"),
        pathlib.PurePosixPath("verify/yukicoder-3148.test.cpp"),
    ]

    assert [
        p.as_posix()
        for p in sorted(
            paths,
            key=lambda p: path_sort_key_path(p, PathSortOrder.natural),
        )
    ] == [
        "verify/yukicoder-275.test.cpp",
        "verify/yukicoder-1907.test.cpp",
        "verify/yukicoder-2362.test.cpp",
        "verify/yukicoder-2603.test.cpp",
        "verify/yukicoder-3148.test.cpp",
    ]


def test_default_path_sort_order_is_lexicographic():
    paths = [
        pathlib.PurePosixPath("verify/yukicoder-1907.test.cpp"),
        pathlib.PurePosixPath("verify/yukicoder-2362.test.cpp"),
        pathlib.PurePosixPath("verify/yukicoder-2603.test.cpp"),
        pathlib.PurePosixPath("verify/yukicoder-275.test.cpp"),
        pathlib.PurePosixPath("verify/yukicoder-3148.test.cpp"),
    ]

    assert [
        p.as_posix() for p in sorted(paths, key=lambda p: path_sort_key_path(p, None))
    ] == [
        "verify/yukicoder-1907.test.cpp",
        "verify/yukicoder-2362.test.cpp",
        "verify/yukicoder-2603.test.cpp",
        "verify/yukicoder-275.test.cpp",
        "verify/yukicoder-3148.test.cpp",
    ]


def test_lexicographic_path_sort_is_case_distinct():
    values = {"dsu.hpp", "DSU.hpp"}

    assert _sorted_path_values(values, None) == [
        "DSU.hpp",
        "dsu.hpp",
    ]


def test_lexicographic_path_sort_is_deterministic_for_case_only_difference():
    paths = {
        pathlib.PurePosixPath("data_structure/dsu.hpp"),
        pathlib.PurePosixPath("data_structure/DSU.hpp"),
    }

    assert [
        p.as_posix() for p in sorted(paths, key=lambda p: path_sort_key_path(p, None))
    ] == [
        "data_structure/DSU.hpp",
        "data_structure/dsu.hpp",
    ]


def test_natural_path_sort_uses_original_value_as_tie_breaker():
    values = [
        "lib/a2.hpp",
        "lib/a02.hpp",
    ]

    assert _sorted_path_values(values, PathSortOrder.natural) == [
        "lib/a02.hpp",
        "lib/a2.hpp",
    ]


def test_natural_path_sort_is_case_distinct_when_casefolded_keys_match():
    values = {"dsu2.hpp", "DSU2.hpp"}

    assert _sorted_path_values(values, PathSortOrder.natural) == [
        "DSU2.hpp",
        "dsu2.hpp",
    ]


def test_natural_path_sort_keeps_prefix_before_numbered_continuation():
    values = [
        "lib/foo1",
        "lib/foo",
    ]

    assert _sorted_path_values(values, PathSortOrder.natural) == [
        "lib/foo",
        "lib/foo1",
    ]


def test_natural_path_sort_preserves_digit_prefixed_names():
    values = [
        "2.hpp",
        "a.hpp",
        "10.hpp",
    ]

    assert _sorted_path_values(values, PathSortOrder.natural) == [
        "2.hpp",
        "10.hpp",
        "a.hpp",
    ]


def test_natural_path_sort_compares_path_segments():
    values = [
        "lib/a2.hpp",
        "lib/a/10.hpp",
        "lib/a10.hpp",
        "lib/a/2.hpp",
    ]

    assert _sorted_path_values(values, PathSortOrder.natural) == [
        "lib/a/2.hpp",
        "lib/a/10.hpp",
        "lib/a2.hpp",
        "lib/a10.hpp",
    ]


def test_default_path_sort_preserves_case_sensitive_index_order():
    values = ["a.hpp", "B.hpp"]

    assert _sorted_path_values(values, None) == [
        "B.hpp",
        "a.hpp",
    ]
