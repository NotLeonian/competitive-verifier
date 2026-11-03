import pathlib
import shutil
import subprocess
import sys
import venv
from collections.abc import Generator
from importlib.metadata import distribution

import pytest
from pytest_mock import MockerFixture

from competitive_verifier.oj.languages.python import (
    PythonDependencyWorker,
    PythonLanguage,
)


@pytest.fixture(autouse=True)
def python_dependency_worker(
    testtemp: pathlib.Path, mocker: MockerFixture
) -> Generator[PythonDependencyWorker, None, None]:
    worker = PythonDependencyWorker()
    mocker.patch(
        "competitive_verifier.oj.languages.python._python_dependency_worker",
        return_value=worker,
    )
    try:
        yield worker
    finally:
        # Stop temporary interpreters before testtemp removes their executable files.
        worker.close()


def test_list_dependencies(testtemp: pathlib.Path):
    source = testtemp / "main.py"
    dependency = testtemp / "helper.py"
    source.write_text("from helper import value\nprint(value)\n", encoding="utf-8")
    dependency.write_text("value = 42\n", encoding="utf-8")

    assert set(PythonLanguage().list_dependencies(source, basedir=testtemp)) == {
        source,
        dependency,
    }


def test_list_dependencies_reuses_worker(testtemp: pathlib.Path, mocker: MockerFixture):
    processes = mocker.spy(subprocess, "Popen")
    helper = testtemp / "helper.py"
    helper.write_text("value = 42\n", encoding="utf-8")
    first = testtemp / "first.py"
    second = testtemp / "second.py"
    first.write_text("from helper import value\n", encoding="utf-8")
    second.write_text("value = 0\n", encoding="utf-8")

    language = PythonLanguage()
    assert set(language.list_dependencies(first, basedir=testtemp)) == {first, helper}
    assert language.list_dependencies(second, basedir=testtemp) == [second]
    assert processes.call_count == 1


@pytest.mark.allow_mkdir
def test_list_dependencies_isolates_worker_requests(
    testtemp: pathlib.Path, mocker: MockerFixture
):
    processes = mocker.spy(subprocess, "Popen")
    for name in ("first", "second"):
        basedir = testtemp / name
        package = basedir / "pkg"
        package.mkdir(parents=True)
        source = basedir / "main.py"
        initializer = package / "__init__.py"
        helper = package / "helper.py"
        source.write_text("from pkg.helper import value\n", encoding="utf-8")
        initializer.write_text("raise RuntimeError('executed')\n", encoding="utf-8")
        helper.write_text("value = 42\n", encoding="utf-8")

        assert set(PythonLanguage().list_dependencies(source, basedir=basedir)) == {
            source,
            initializer,
            helper,
        }
    assert processes.call_count == 1


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


@pytest.mark.allow_mkdir
def test_list_dependencies_with_user_site(
    testtemp: pathlib.Path, monkeypatch: pytest.MonkeyPatch
):
    environment = testtemp / "venv"
    venv.EnvBuilder(system_site_packages=True).create(environment)
    interpreter = environment / (
        "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
    )
    monkeypatch.setenv("PYTHONUSERBASE", str(testtemp / "user-base"))
    monkeypatch.delenv("PYTHONNOUSERSITE", raising=False)
    monkeypatch.delenv("PYTHONPATH", raising=False)
    user_site = pathlib.Path(
        subprocess.run(
            [str(interpreter), "-c", "import site; print(site.getusersitepackages())"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    user_site.mkdir(parents=True)
    for package in ("modulegraph2", "objectgraph"):
        shutil.copytree(
            str(distribution(package).locate_file(package)), user_site / package
        )
    shutil.copyfile(
        str(distribution("typing_extensions").locate_file("typing_extensions.py")),
        user_site / "typing_extensions.py",
    )
    marker = testtemp / "user-site-imported"
    initializer = user_site / "modulegraph2/__init__.py"
    with initializer.open("a", encoding="utf-8") as stream:
        stream.write(
            f"\nwith open({str(marker)!r}, 'w', encoding='utf-8') as marker:\n"
            "    marker.write('imported')\n"
        )

    source = testtemp / "main.py"
    helper = testtemp / "helper.py"
    source.write_text("from helper import value\n", encoding="utf-8")
    helper.write_text("value = 42\n", encoding="utf-8")
    (testtemp / "json.py").write_text(
        "raise RuntimeError('PYTHONPATH code was executed')\n", encoding="utf-8"
    )
    monkeypatch.setenv("PYTHONPATH", str(testtemp))
    monkeypatch.setattr(sys, "executable", str(interpreter))

    assert set(PythonLanguage().list_dependencies(source, basedir=testtemp)) == {
        source,
        helper,
    }
    assert marker.read_text(encoding="utf-8") == "imported"


def test_list_dependencies_invalid_source(
    testtemp: pathlib.Path, mocker: MockerFixture
):
    processes = mocker.spy(subprocess, "Popen")
    source = testtemp / "main.py"
    source.write_text("invalid python syntax!\n", encoding="utf-8")

    with pytest.raises(
        RuntimeError, match="Failed to analyze the dependency graph"
    ) as e:
        PythonLanguage().list_dependencies(source, basedir=testtemp)

    assert "SyntaxError" in str(e.value)
    source.write_text("value = 42\n", encoding="utf-8")
    assert PythonLanguage().list_dependencies(source, basedir=testtemp) == [source]
    assert processes.call_count == 1


def test_list_dependencies_timeout(
    testtemp: pathlib.Path,
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    python_dependency_worker: PythonDependencyWorker,
):
    source = testtemp / "main.py"
    source.write_text("value = 42\n", encoding="utf-8")
    processes = mocker.spy(subprocess, "Popen")
    (testtemp / "_python_dependencies.py").write_text(
        "import sys\nfor request in sys.stdin:\n    pass\n", encoding="utf-8"
    )
    with monkeypatch.context() as context:
        context.setattr(
            "competitive_verifier.oj.languages.python.__file__",
            str(testtemp / "python.py"),
        )
        with pytest.raises(RuntimeError, match=r"Failed to analyze.*\(timeout\)"):
            python_dependency_worker.list_dependencies(source, testtemp, timeout=0.1)

    assert processes.spy_return.poll() is not None
    assert PythonLanguage().list_dependencies(source, basedir=testtemp) == [source]
    assert processes.call_count == 2


def test_list_dependencies_recovers_from_worker_error(
    testtemp: pathlib.Path, mocker: MockerFixture
):
    source = testtemp / "main.py"
    source.write_text("value = 42\n", encoding="utf-8")
    processes = mocker.spy(subprocess, "Popen")
    malformed_request = mocker.patch(
        "competitive_verifier.oj.languages.python.json.dumps", return_value="null"
    )

    with pytest.raises(RuntimeError, match="TypeError"):
        PythonLanguage().list_dependencies(source, basedir=testtemp)

    assert processes.spy_return.poll() is not None
    mocker.stop(malformed_request)
    assert PythonLanguage().list_dependencies(source, basedir=testtemp) == [source]
    assert processes.call_count == 2
