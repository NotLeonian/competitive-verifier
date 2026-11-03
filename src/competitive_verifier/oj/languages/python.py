# Python Version: 3.x
import functools
import os
import pathlib
import platform
import subprocess
import sys
from collections.abc import Sequence
from logging import getLogger

from pydantic import TypeAdapter

from competitive_verifier.models import ShellCommand

from .base import Language, LanguageEnvironment

logger = getLogger(__name__)


class PythonLanguageEnvironment(LanguageEnvironment):
    @property
    def name(self) -> str:
        return "Python"

    def _python_path(self, *, basedir: pathlib.Path) -> str:
        python_path = os.getenv("PYTHONPATH")
        return (
            basedir.as_posix() + os.pathsep + python_path
            if python_path
            else basedir.as_posix()
        )

    def get_compile_command(
        self, path: pathlib.Path, *, basedir: pathlib.Path, tempdir: pathlib.Path
    ) -> ShellCommand:
        return ShellCommand(
            command=["python", "-m", "py_compile", str(path)],
            env={"PYTHONPATH": self._python_path(basedir=basedir)},
        )

    def get_execute_command(
        self, path: pathlib.Path, *, basedir: pathlib.Path, tempdir: pathlib.Path
    ) -> ShellCommand:
        return ShellCommand(
            command=["python", str(path)],
            env={"PYTHONPATH": self._python_path(basedir=basedir)},
        )


@functools.cache
def _python_list_depending_files(
    path: pathlib.Path, basedir: pathlib.Path
) -> list[pathlib.Path]:
    basedir = basedir.resolve()
    timeout = 5.0 if platform.uname().system == "Windows" else 1.0
    # 1.0 sec causes timeout on CI using Windows
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(pathlib.Path(__file__).with_name("_python_dependencies.py")),
                str(path),
                str(basedir),
            ],
            capture_output=True,
            check=True,
            timeout=timeout,
            # Keep user-site dependencies available without loading project PYTHONPATH.
            env={
                name: value
                for name, value in os.environ.items()
                if name != "PYTHONPATH"
            },
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(
            f"Failed to analyze the dependency graph (timeout): {path}"
        ) from e
    except subprocess.CalledProcessError as e:
        detail = e.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(
            f"Failed to analyze the dependency graph: {path}\n{detail}"
        ) from e

    res_deps = TypeAdapter[list[pathlib.Path]](list[pathlib.Path]).validate_json(
        result.stdout
    )
    logger.debug("the dependencies of %s: %s", path, res_deps)
    return res_deps


class PythonLanguage(Language):
    def list_dependencies(
        self, path: pathlib.Path, *, basedir: pathlib.Path
    ) -> list[pathlib.Path]:
        return _python_list_depending_files(path.resolve(), basedir)

    def list_environments(
        self, path: pathlib.Path, *, basedir: pathlib.Path
    ) -> Sequence[PythonLanguageEnvironment]:
        return [PythonLanguageEnvironment()]
