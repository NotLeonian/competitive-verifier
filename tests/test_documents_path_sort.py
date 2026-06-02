import pathlib

import yaml

from competitive_verifier.documents.config import ConfigYaml
from competitive_verifier.documents.path_sort import (
    PathSortOrder,
    path_sort_key_path,
    path_sort_key_text,
)


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
        pathlib.Path("verify/yukicoder-1907.test.cpp"),
        pathlib.Path("verify/yukicoder-2362.test.cpp"),
        pathlib.Path("verify/yukicoder-2603.test.cpp"),
        pathlib.Path("verify/yukicoder-275.test.cpp"),
        pathlib.Path("verify/yukicoder-3148.test.cpp"),
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
        pathlib.Path("verify/yukicoder-1907.test.cpp"),
        pathlib.Path("verify/yukicoder-2362.test.cpp"),
        pathlib.Path("verify/yukicoder-2603.test.cpp"),
        pathlib.Path("verify/yukicoder-275.test.cpp"),
        pathlib.Path("verify/yukicoder-3148.test.cpp"),
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

    assert sorted(values, key=lambda s: path_sort_key_text(s, None)) == [
        "DSU.hpp",
        "dsu.hpp",
    ]


def test_lexicographic_path_sort_is_deterministic_for_case_only_difference():
    paths = {
        pathlib.Path("data_structure/dsu.hpp"),
        pathlib.Path("data_structure/DSU.hpp"),
    }

    assert [
        p.as_posix() for p in sorted(paths, key=lambda p: path_sort_key_path(p, None))
    ] == [
        "data_structure/DSU.hpp",
        "data_structure/dsu.hpp",
    ]


def test_natural_path_sort_uses_original_value_as_tie_breaker():
    values = {"a2.hpp", "a02.hpp"}

    assert sorted(
        values,
        key=lambda s: path_sort_key_text(s, PathSortOrder.natural),
    ) == [
        "a02.hpp",
        "a2.hpp",
    ]


def test_natural_path_sort_is_case_distinct_when_casefolded_keys_match():
    values = {"dsu2.hpp", "DSU2.hpp"}

    assert sorted(
        values,
        key=lambda s: path_sort_key_text(s, PathSortOrder.natural),
    ) == [
        "DSU2.hpp",
        "dsu2.hpp",
    ]
