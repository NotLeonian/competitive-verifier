import pathlib
import subprocess
import sys

import pytest
from pytest_mock import MockerFixture

from competitive_verifier.oj.languages.python import PythonLanguage


def test_list_dependencies(testtemp: pathlib.Path):
    source = testtemp / "main.py"
    dependency = testtemp / "helper.py"
    source.write_text("from helper import value\nprint(value)\n", encoding="utf-8")
    dependency.write_text("value = 42\n", encoding="utf-8")

    assert set(PythonLanguage().list_dependencies(source, basedir=testtemp)) == {
        source,
        dependency,
    }


@pytest.mark.allow_mkdir
@pytest.mark.parametrize(
    ("files", "expected"),
    [
        (
            {"main.py": "import sys\nimport os\nimport math\nimport missing_module\n"},
            {"main.py"},
        ),
        (
            {
                "main.py": "import helper\nimport leaf\n",
                "helper.py": "import leaf\n",
                "leaf.py": "value = 42\n",
                "unused.py": "value = 0\n",
            },
            {"main.py", "helper.py", "leaf.py"},
        ),
        (
            {
                "main.py": "import helper\n",
                "helper.py": "import leaf\n",
                "leaf.py": "import helper\n",
            },
            {"main.py", "helper.py", "leaf.py"},
        ),
        (
            {
                "main.py": "from pkg.nested import helper\n",
                "pkg/__init__.py": "",
                "pkg/nested/__init__.py": "",
                "pkg/nested/helper.py": "from ..shared import value\n",
                "pkg/shared.py": "value = 42\n",
            },
            {
                "main.py",
                "pkg/__init__.py",
                "pkg/nested/__init__.py",
                "pkg/nested/helper.py",
                "pkg/shared.py",
            },
        ),
        (
            {
                "main.py": "from pkg import *\n",
                "pkg/__init__.py": "from .helper import value\n",
                "pkg/helper.py": "value = 42\n",
            },
            {"main.py", "pkg/__init__.py", "pkg/helper.py"},
        ),
        (
            {
                "main.py": "import ns.helper\n",
                "ns/helper.py": "from .leaf import value\n",
                "ns/leaf.py": "value = 42\n",
            },
            {"main.py", "ns/helper.py", "ns/leaf.py"},
        ),
        (
            {
                "main.py": "from helper import value\nraise RuntimeError('executed')\n",
                "helper.py": "value = 42\nraise RuntimeError('executed')\n",
            },
            {"main.py", "helper.py"},
        ),
        (
            {
                "main.py": "from pkg.nested import helper\n",
                "pkg/__init__.py": "raise RuntimeError('executed')\n",
                "pkg/nested/__init__.py": "raise RuntimeError('executed')\n",
                "pkg/nested/helper.py": "value = 42\n",
            },
            {
                "main.py",
                "pkg/__init__.py",
                "pkg/nested/__init__.py",
                "pkg/nested/helper.py",
            },
        ),
        (
            {
                "main.py": "from ns.nested import helper\n",
                "ns/nested/helper.py": "from ..leaf import value\n",
                "ns/leaf.py": "value = 42\n",
            },
            {"main.py", "ns/nested/helper.py", "ns/leaf.py"},
        ),
        (
            {
                "main.py": "import json\n",
                "json.py": "from helper import value\n",
                "helper.py": "value = 42\n",
            },
            {"main.py", "json.py", "helper.py"},
        ),
    ],
    ids=[
        "stdlib-and-missing-imports",
        "transitive-and-duplicate-imports",
        "circular-imports",
        "packages-and-relative-imports",
        "star-imports",
        "namespace-packages",
        "does-not-execute-source",
        "does-not-execute-package-initializers",
        "nested-namespace-packages",
        "local-module-shadows-stdlib",
    ],
)
def test_dependency_graph(
    testtemp: pathlib.Path, files: dict[str, str], expected: set[str]
):
    for name, contents in files.items():
        path = testtemp / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")
    original_packages = {name: sys.modules.get(name) for name in ("pkg", "ns")}

    assert set(
        PythonLanguage().list_dependencies(testtemp / "main.py", basedir=testtemp)
    ) == {testtemp / name for name in expected}
    assert all(
        sys.modules.get(name) is module for name, module in original_packages.items()
    )


@pytest.mark.allow_mkdir
@pytest.mark.parametrize(
    ("source_name", "regular_package"),
    [
        ("pkg/nested/main.py", True),
        ("pkg/nested/__init__.py", True),
        ("ns/nested/main.py", False),
    ],
)
def test_list_dependencies_package_entrypoint(
    testtemp: pathlib.Path, source_name: str, *, regular_package: bool
):
    source = testtemp / source_name
    source.parent.mkdir(parents=True)
    helper = source.parent.parent / "helper.py"
    helper.write_text("value = 42\n", encoding="utf-8")
    expected = {source, helper}
    if regular_package:
        for directory in (source.parent, source.parent.parent):
            initializer = directory / "__init__.py"
            initializer.write_text("", encoding="utf-8")
            expected.add(initializer)
    source.write_text("from ..helper import value\n", encoding="utf-8")

    assert set(PythonLanguage().list_dependencies(source, basedir=testtemp)) == expected


@pytest.mark.allow_mkdir
def test_list_dependencies_limits_search_path(
    testtemp: pathlib.Path, monkeypatch: pytest.MonkeyPatch
):
    basedir = testtemp / "project"
    basedir.mkdir()
    source = basedir / "main.py"
    dependency = basedir / "helper.py"
    source.write_text("import helper\nimport external_module\n", encoding="utf-8")
    dependency.write_text("value = 42\n", encoding="utf-8")
    (testtemp / "external_module.py").write_text(
        "invalid python syntax!\n", encoding="utf-8"
    )
    monkeypatch.setattr(sys, "path", [str(testtemp), *sys.path])
    original_path = sys.path.copy()

    assert set(
        PythonLanguage().list_dependencies(
            pathlib.Path("project/main.py"), basedir=pathlib.Path("project")
        )
    ) == {source, dependency}
    assert sys.path == original_path


def test_list_dependencies_invalid_source(testtemp: pathlib.Path):
    source = testtemp / "main.py"
    source.write_text("invalid python syntax!\n", encoding="utf-8")

    with pytest.raises(
        RuntimeError, match="Failed to analyze the dependency graph"
    ) as e:
        PythonLanguage().list_dependencies(source, basedir=testtemp)

    assert isinstance(e.value.__cause__, subprocess.CalledProcessError)
    assert "SyntaxError" in str(e.value)


def test_list_dependencies_timeout(testtemp: pathlib.Path, mocker: MockerFixture):
    source = testtemp / "main.py"
    source.write_text("value = 42\n", encoding="utf-8")
    mocker.patch(
        "competitive_verifier.oj.languages.python.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="python", timeout=1.0),
    )

    with pytest.raises(RuntimeError, match=r"Failed to analyze.*\(timeout\)"):
        PythonLanguage().list_dependencies(source, basedir=testtemp)
