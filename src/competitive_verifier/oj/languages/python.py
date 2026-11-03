# Python Version: 3.x
import atexit
import concurrent.futures
import functools
import json
import os
import pathlib
import platform
import subprocess
import sys
import tempfile
import threading
from collections.abc import Sequence
from contextlib import ExitStack, suppress
from logging import getLogger
from typing import BinaryIO

from pydantic import BaseModel, Field

from competitive_verifier.models import ShellCommand

from .base import Language, LanguageEnvironment

logger = getLogger(__name__)


class _DependencyResponse(BaseModel):
    dependencies: list[pathlib.Path] = Field(default_factory=list[pathlib.Path])
    error: str | None = None


class PythonDependencyWorker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._process: subprocess.Popen[str] | None = None
        self._executor: concurrent.futures.ThreadPoolExecutor | None = None
        self._stderr: BinaryIO | None = None
        self._resources = ExitStack()
        self._executable: str | None = None
        self._environment: dict[str, str] | None = None

    def _start(self, executable: str, environment: dict[str, str]) -> None:
        with ExitStack() as resources:
            stderr = resources.enter_context(tempfile.TemporaryFile())
            process = subprocess.Popen(
                [
                    executable,
                    str(pathlib.Path(__file__).with_name("_python_dependencies.py")),
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=stderr,
                text=True,
                encoding="utf-8",
                env=environment,
            )
            self._process = process
            self._stderr = stderr
            self._resources = resources.pop_all()
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self._executable = executable
        self._environment = environment

    def _stop(self) -> str:
        if self._process is not None:
            if self._process.poll() is None:
                self._process.kill()
            self._process.wait()
        if self._executor is not None:
            self._executor.shutdown(wait=True, cancel_futures=True)
            self._executor = None
        if self._process is not None:
            for stream in (self._process.stdin, self._process.stdout):
                if stream is not None:
                    with suppress(OSError):
                        stream.close()
            self._process = None
        detail = ""
        if self._stderr is not None:
            self._stderr.seek(0)
            detail = self._stderr.read().decode("utf-8", errors="replace").strip()
            self._stderr = None
        self._resources.close()
        return detail

    def close(self) -> None:
        with self._lock:
            self._stop()

    @staticmethod
    def _exchange(
        process: subprocess.Popen[str], path: pathlib.Path, basedir: pathlib.Path
    ) -> str:
        assert process.stdin is not None
        assert process.stdout is not None
        process.stdin.write(json.dumps([str(path), str(basedir)]) + "\n")
        process.stdin.flush()
        response = process.stdout.readline()
        if not response:
            raise EOFError("The Python dependency worker exited without a response")
        return response

    def list_dependencies(
        self, path: pathlib.Path, basedir: pathlib.Path, *, timeout: float
    ) -> list[pathlib.Path]:
        # Keep user-site dependencies available without loading project PYTHONPATH.
        environment = {
            name: value for name, value in os.environ.items() if name != "PYTHONPATH"
        }
        with self._lock:
            if (
                self._process is None
                or self._process.poll() is not None
                or self._executable != sys.executable
                or self._environment != environment
            ):
                self._stop()
                self._start(sys.executable, environment)
            assert self._process is not None
            assert self._executor is not None
            future = self._executor.submit(self._exchange, self._process, path, basedir)
            try:
                response = future.result(timeout=timeout)
            except concurrent.futures.TimeoutError as e:
                self._stop()
                raise RuntimeError(
                    f"Failed to analyze the dependency graph (timeout): {path}"
                ) from e
            except (OSError, EOFError) as e:
                detail = self._stop()
                raise RuntimeError(
                    f"Failed to analyze the dependency graph: {path}\n{detail}"
                ) from e
            result = _DependencyResponse.model_validate_json(response)
            if result.error is not None:
                raise RuntimeError(
                    f"Failed to analyze the dependency graph: {path}\n{result.error}"
                )
            return result.dependencies


@functools.cache
def _python_dependency_worker() -> PythonDependencyWorker:
    worker = PythonDependencyWorker()
    atexit.register(worker.close)
    return worker


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
    res_deps = _python_dependency_worker().list_dependencies(
        path, basedir, timeout=timeout
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
