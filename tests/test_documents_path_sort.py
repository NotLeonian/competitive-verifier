import datetime
import pathlib

import yaml

from competitive_verifier.documents.config import ConfigYaml
from competitive_verifier.documents.front_matter import Markdown
from competitive_verifier.documents.path_sort import (
    PathSortOrder,
    path_sort_key_path,
)
from competitive_verifier.documents.render import PageRenderJob, SourceCodeStat
from competitive_verifier.documents.render_data import StatusIcon
from competitive_verifier.models import (
    VerificationFile,
    VerificationInput,
    VerifyCommandResult,
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


def _make_page_render_job(
    *,
    source_path: pathlib.Path,
    group_dir: pathlib.Path,
    page_jobs: dict[pathlib.Path, PageRenderJob],
    verifications: VerificationInput,
    depends_on: set[pathlib.Path] | None = None,
    path_sort: PathSortOrder | None = None,
) -> PageRenderJob:
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("", encoding="utf-8")
    return PageRenderJob(
        source_path=source_path,
        group_dir=group_dir,
        markdown=Markdown.make_default(source_path),
        stat=SourceCodeStat(
            path=source_path,
            is_verification=False,
            verification_status=StatusIcon.LIBRARY_NO_TESTS,
            file_input=VerificationFile(),
            timestamp=datetime.datetime(2026, 1, 1),
            depends_on=depends_on or set(),
            required_by=set(),
            verified_with=set(),
        ),
        verifications=verifications,
        result=VerifyCommandResult(total_seconds=0),
        page_jobs=page_jobs,
        path_sort=path_sort,
    )


def _dependency_link_path_values(
    tmp_path: pathlib.Path,
    values: list[str],
    order: PathSortOrder | None,
) -> list[str]:
    dependency_paths = {tmp_path / value for value in values}
    subject_path = tmp_path / "subject.hpp"
    verifications = VerificationInput(
        files={path: VerificationFile() for path in dependency_paths | {subject_path}}
    )
    page_jobs: dict[pathlib.Path, PageRenderJob] = {}

    for path in dependency_paths:
        page_jobs[path] = _make_page_render_job(
            source_path=path,
            group_dir=tmp_path,
            page_jobs=page_jobs,
            verifications=verifications,
            path_sort=order,
        )

    subject_job = _make_page_render_job(
        source_path=subject_path,
        group_dir=tmp_path,
        page_jobs=page_jobs,
        verifications=verifications,
        depends_on=dependency_paths,
        path_sort=order,
    )

    return [link.filename for link in subject_job.get_page_data().dependencies[0].files]


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


def test_lexicographic_path_sort_matches_legacy_casefold_order():
    values = ["a.hpp", "B.hpp"]

    assert _sorted_path_values(values, None) == [
        "a.hpp",
        "B.hpp",
    ]


def test_lexicographic_path_sort_keeps_legacy_casefold_ties():
    lower_path = pathlib.PurePosixPath("data_structure/dsu.hpp")
    upper_path = pathlib.PurePosixPath("data_structure/DSU.hpp")

    for order in (None, PathSortOrder.lexicographic):
        assert path_sort_key_path(lower_path, order) == path_sort_key_path(
            upper_path, order
        )


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


def test_natural_path_sort_uses_original_path_as_case_tie_breaker():
    paths = [
        pathlib.PurePosixPath("data_structure/dsu.hpp"),
        pathlib.PurePosixPath("data_structure/DSU.hpp"),
    ]

    assert [
        path.as_posix()
        for path in sorted(
            paths, key=lambda path: path_sort_key_path(path, PathSortOrder.natural)
        )
    ] == [
        "data_structure/DSU.hpp",
        "data_structure/dsu.hpp",
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


def test_dependency_links_default_sort_matches_legacy_casefold_order(
    tmp_path: pathlib.Path,
):
    values = ["a.hpp", "B.hpp"]

    assert _dependency_link_path_values(tmp_path, values, None) == [
        "a.hpp",
        "B.hpp",
    ]


def test_dependency_links_explicit_lexicographic_sort_matches_default_order(
    tmp_path: pathlib.Path,
):
    values = ["a.hpp", "B.hpp"]

    assert _dependency_link_path_values(
        tmp_path, values, PathSortOrder.lexicographic
    ) == [
        "a.hpp",
        "B.hpp",
    ]


def test_dependency_links_natural_sort_compares_path_segments(
    tmp_path: pathlib.Path,
):
    values = [
        "lib/a2.hpp",
        "lib/a/10.hpp",
        "lib/a10.hpp",
        "lib/a/2.hpp",
    ]

    assert _dependency_link_path_values(tmp_path, values, PathSortOrder.natural) == [
        "lib/a/2.hpp",
        "lib/a/10.hpp",
        "lib/a2.hpp",
        "lib/a10.hpp",
    ]
