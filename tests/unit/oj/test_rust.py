import pathlib

import pytest
from pytest_mock import MockerFixture

from competitive_verifier.oj.languages import OjVerifyRustConfig, RustLanguage, rust


@pytest.mark.allow_mkdir
@pytest.mark.parametrize("source_name", ["main.rs", "main with spaces.rs"])
def test_list_dependencies_with_escaped_spaces(
    testtemp: pathlib.Path, mocker: MockerFixture, source_name: str
):
    source = testtemp / source_name
    dependency = testtemp / "module with spaces.rs"
    source.touch()
    dependency.touch()
    dep_info = testtemp / "target/debug/deps/example-123.d"
    dep_info.parent.mkdir(parents=True)
    escaped_source = source_name.replace(" ", r"\ ")
    dep_info.write_text(
        f"target/debug/deps/example-123.d: {escaped_source} module\\ with\\ spaces.rs\n",
        encoding="utf-8",
    )
    mocker.patch.object(rust, "_cargo_checked_workspaces", {testtemp})
    mocker.patch.object(rust, "_related_source_files_by_workspace", {})

    mocker.patch.object(
        rust,
        "_cargo_metadata",
        return_value={
            "workspace_root": str(testtemp),
            "target_directory": str(testtemp / "target"),
            "workspace_members": ["example"],
            "resolve": {"nodes": [{"id": "example", "deps": []}]},
            "packages": [
                {
                    "id": "example",
                    "targets": [
                        {"name": "example", "kind": ["bin"], "src_path": str(source)}
                    ],
                }
            ],
        },
    )

    language = RustLanguage(config=OjVerifyRustConfig())
    assert language.list_dependencies(source, basedir=testtemp) == sorted(
        [source, dependency]
    )
