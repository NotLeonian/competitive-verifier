import glob
import json
import os
import pathlib
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import zipfile
from abc import abstractmethod
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from logging import getLogger
from typing import ClassVar, Optional, TypeVar

import requests

from competitive_verifier import config
from competitive_verifier.log import GitHubMessageParams
from competitive_verifier.models import (
    Problem,
    TestCaseData,
    TestCaseFile,
    TestCaseProvider,
)

logger = getLogger(__name__)

_ASCII_SPACE = 0x20
_ASCII_DELETE = 0x7F


class NotLoggedInError(RuntimeError):
    pass


class _BaseProblem(Problem):
    def iter_system_cases(self) -> Iterator[TestCaseFile]:
        return iter_testcases(directory=self.test_directory)

    def download_system_cases(self) -> Iterable[TestCaseData] | bool:
        test_directory = self.test_directory

        if test_directory.exists() and any(test_directory.iterdir()):
            logger.info("download:already exists: %s", self.url)
            return True

        self.problem_directory.mkdir(parents=True, exist_ok=True)

        samples = list(self._download_cases())

        # Check samples
        if not samples:
            logger.error(
                "Sample not found",
                extra={"github": GitHubMessageParams()},
            )
            return False

        # write samples to files
        save_testcases(samples, directory=test_directory)
        return samples

    @abstractmethod
    def _download_cases(self) -> Iterable[TestCaseData]: ...


class LibraryCheckerProblem(Problem):
    checker_exe_name: ClassVar[str] = (
        "checker.exe" if sys.platform == "win32" else "checker"
    )

    def __init__(self, *, problem_id: str):
        self.problem_id = problem_id
        self._source_directory = None

    def __hash__(self) -> int:
        return hash((self.problem_id, self.repo_path))

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, LibraryCheckerProblem):
            return False
        return self.problem_id == value.problem_id and self.repo_path == value.repo_path

    @property
    def repo_path(self):
        return config.get_cache_dir() / "library-checker-problems"

    def iter_system_cases(self) -> Iterator[TestCaseFile]:
        inputs: dict[str, pathlib.Path] = {}
        outputs: dict[str, pathlib.Path] = {}
        for path in self.source_directory.glob("in/*.in"):
            inputs[path.stem] = path
        for path in self.source_directory.glob("out/*.out"):
            outputs[path.stem] = path
        return merge_testcase_files(inputs, outputs)

    def download_system_cases(self) -> bool:
        self.problem_directory.mkdir(parents=True, exist_ok=True)
        self.generate_test_cases()
        return True

    @property
    def checker(self) -> pathlib.Path | None:
        return self.source_directory / self.checker_exe_name

    def generate_test_cases(self) -> None:
        self.update_cloned_repository()
        path = self.repo_path

        spec = str(self.source_directory / "info.toml")
        command = [sys.executable, str(path / "generate.py"), spec]
        logger.info("$ %s", " ".join(command))
        try:
            subprocess.check_call(command, stdout=sys.stderr, stderr=sys.stderr)
        except subprocess.CalledProcessError:
            logger.exception(
                "the generate.py failed: check https://github.com/yosupo06/library-checker-problems/issues",
                extra={"github": GitHubMessageParams()},
            )
            raise

    @property
    def source_directory(self):
        if self._source_directory is None:
            problem_id = self.problem_id
            info_tomls = list(
                self.repo_path.glob(f"**/{glob.escape(problem_id)}/info.toml")
            )
            if len(info_tomls) != 1:
                raise RuntimeError(f"the problem {problem_id!r} not found or broken")
            self._source_directory = info_tomls[0].parent
        return self._source_directory

    @property
    def url(self) -> str:
        return f"https://judge.yosupo.jp/problem/{self.problem_id}"

    @classmethod
    def from_url(cls, url: str) -> Optional["LibraryCheckerProblem"]:
        # example: https://judge.yosupo.jp/problem/unionfind
        result = urllib.parse.urlparse(url)
        if result.scheme in ("", "http", "https") and result.netloc in (
            "judge.yosupo.jp",
            "old.yosupo.jp",
        ):
            m = re.match(r"/problem/(\w+)/?", result.path)
            if m:
                return cls(problem_id=m.group(1))
        return None

    _is_repository_updated: ClassVar[set[pathlib.Path]] = set()

    def update_cloned_repository(self) -> None:
        if self.repo_path in self._is_repository_updated:
            return

        try:
            subprocess.check_call(
                ["git", "--version"],  # noqa: S607
                stdout=sys.stderr,
                stderr=sys.stderr,
            )
        except FileNotFoundError:
            logger.exception(
                "git command not found",
                exc_info=False,
                extra={"github": GitHubMessageParams()},
            )
            raise

        path = self.repo_path
        if not path.exists():
            # init the problem repository
            url = "https://github.com/yosupo06/library-checker-problems"
            logger.info("$ git clone %s %s", url, path)
            subprocess.check_call(
                ["git", "clone", url, str(path)],  # noqa: S607
                stdout=sys.stderr,
                stderr=sys.stderr,
            )
        else:
            # sync the problem repository
            logger.info("$ git -C %s pull", path)
            subprocess.check_call(
                ["git", "-C", str(path), "pull"],  # noqa: S607
                stdout=sys.stderr,
                stderr=sys.stderr,
            )

        LibraryCheckerProblem._is_repository_updated.add(self.repo_path)


class _YukicoderProblemNo(int):
    def __new__(cls, value: int):
        return super().__new__(cls, value)

    def __str__(self) -> str:
        return "no/" + super().__str__()


class _YukicoderProblemId(int):
    def __new__(cls, value: int):
        return super().__new__(cls, value)


class YukicoderProblem(_BaseProblem):
    problem: _YukicoderProblemNo | _YukicoderProblemId

    def __init__(self, *, problem_no: int | None = None, problem_id: int | None = None):
        if problem_no is not None:
            self.problem = _YukicoderProblemNo(problem_no)
        elif problem_id is not None:
            self.problem = _YukicoderProblemId(problem_id)
        else:
            raise ValueError("Needs problem_no or problem_id")

    @staticmethod
    def _env_float(name: str, default: float) -> float:
        value = os.environ.get(name)
        if value is None or value == "":
            return default
        try:
            return float(value)
        except ValueError as e:
            raise ValueError(f"{name} must be a float: {value!r}") from e

    @staticmethod
    def _env_int(name: str, default: int) -> int:
        value = os.environ.get(name)
        if value is None or value == "":
            return default
        try:
            return int(value)
        except ValueError as e:
            raise ValueError(f"{name} must be an integer: {value!r}") from e

    @staticmethod
    def _validate_yukicoder_token(token: str) -> str:
        if not token:
            raise NotLoggedInError("Required: $YUKICODER_TOKEN environment variable")

        if token.startswith("YUKICODER_TOKEN="):
            raise NotLoggedInError(
                "YUKICODER_TOKEN must contain only the token value, "
                "not a 'YUKICODER_TOKEN=...' assignment."
            )

        if token.lower().startswith("bearer "):
            raise NotLoggedInError(
                "YUKICODER_TOKEN must contain only the token value, "
                "not a 'Bearer ...' authorization header value."
            )

        if token != token.strip():
            raise NotLoggedInError(
                "YUKICODER_TOKEN contains leading or trailing whitespace."
            )

        bad_control_chars: list[str] = []
        for index, ch in enumerate(token):
            code = ord(ch)
            if code < _ASCII_SPACE or code == _ASCII_DELETE:
                name = {
                    0x09: "TAB",
                    0x0A: "LF",
                    0x0D: "CR",
                    0x1B: "ESC",
                    _ASCII_DELETE: "DEL",
                }.get(code, "control")
                bad_control_chars.append(f"offset {index}: 0x{code:02X} ({name})")

        if bad_control_chars:
            extra = ""
            if "\x1b[" in token:
                extra = (
                    " It looks like an ANSI escape sequence was included, "
                    "possibly by pressing an arrow key while entering the token."
                )

            raise NotLoggedInError(
                "YUKICODER_TOKEN contains control characters: "
                + ", ".join(bad_control_chars)
                + "."
                + extra
            )

        non_visible_ascii: list[str] = []
        for index, ch in enumerate(token):
            code = ord(ch)
            if code <= _ASCII_SPACE or code >= _ASCII_DELETE:
                non_visible_ascii.append(f"offset {index}: U+{code:04X}")

        if non_visible_ascii:
            raise NotLoggedInError(
                "YUKICODER_TOKEN contains characters that are not visible ASCII: "
                + ", ".join(non_visible_ascii)
            )

        return token

    @classmethod
    def _yukicoder_headers(cls) -> dict[str, str]:
        token = cls._validate_yukicoder_token(os.environ.get("YUKICODER_TOKEN", ""))
        return {"Authorization": f"Bearer {token}"}

    def download_system_cases(self) -> Iterable[TestCaseData] | bool:
        test_directory = self.test_directory
        if test_directory.exists() and any(test_directory.iterdir()):
            logger.info("download:already exists: %s", self.url)
            return True

        headers = self._yukicoder_headers()
        if not self._is_logged_in(headers=headers):
            raise NotLoggedInError("Required: $YUKICODER_TOKEN environment variable")

        self.problem_directory.parent.mkdir(parents=True, exist_ok=True)

        tmp_root = pathlib.Path(
            tempfile.mkdtemp(
                prefix=f"{self.hash_id}.",
                dir=self.problem_directory.parent,
            )
        )
        zip_path = tmp_root / "testcase.zip"
        staging_directory = tmp_root / "test"

        try:
            self._download_testcase_zip(zip_path, headers=headers)
            case_count = self._extract_testcase_zip(zip_path, staging_directory)

            if case_count == 0:
                logger.error(
                    "Sample not found",
                    extra={"github": GitHubMessageParams()},
                )
                return False

            self.problem_directory.mkdir(parents=True, exist_ok=True)

            if test_directory.exists():
                shutil.rmtree(test_directory)

            staging_directory.rename(test_directory)
            logger.info("download:saved: %s cases: %s", case_count, self.url)
            return True
        finally:
            shutil.rmtree(tmp_root, ignore_errors=True)

    def _download_cases(self) -> list[TestCaseData]:
        headers = self._yukicoder_headers()
        if not self._is_logged_in(headers=headers):
            raise NotLoggedInError("Required: $YUKICODER_TOKEN environment variable")

        self.problem_directory.parent.mkdir(parents=True, exist_ok=True)

        tmp_root = pathlib.Path(
            tempfile.mkdtemp(
                prefix=f"{self.hash_id}.",
                dir=self.problem_directory.parent,
            )
        )
        zip_path = tmp_root / "testcase.zip"

        try:
            self._download_testcase_zip(zip_path, headers=headers)
            with zipfile.ZipFile(zip_path) as fh:
                inputs: dict[str, bytes] = {}
                outputs: dict[str, bytes] = {}

                for info in fh.infolist():
                    filename = info.filename
                    if filename.endswith("/"):
                        continue

                    path = pathlib.PurePosixPath(filename)
                    self._validate_zip_member_path(path)

                    if filename.startswith("test_in/"):
                        inputs[path.stem] = fh.read(info)
                    elif filename.startswith("test_out/"):
                        outputs[path.stem] = fh.read(info)

                return [
                    TestCaseData(name=name, input_data=i, output_data=o)
                    for name, i, o in enumerate_input_outputs(inputs, outputs)
                ]
        finally:
            shutil.rmtree(tmp_root, ignore_errors=True)

    def _download_testcase_zip(
        self,
        destination: pathlib.Path,
        *,
        headers: dict[str, str] | None,
    ) -> None:
        url = f"{self.url}/testcase.zip"

        connect_timeout = self._env_float(
            "COMPETITIVE_VERIFIER_YUKICODER_CONNECT_TIMEOUT",
            10.0,
        )
        read_timeout = self._env_float(
            "COMPETITIVE_VERIFIER_YUKICODER_READ_TIMEOUT",
            30.0,
        )
        download_timeout = self._env_float(
            "COMPETITIVE_VERIFIER_YUKICODER_DOWNLOAD_TIMEOUT",
            0.0,
        )
        report_interval = self._env_float(
            "COMPETITIVE_VERIFIER_YUKICODER_REPORT_INTERVAL",
            5.0,
        )
        chunk_size = self._env_int(
            "COMPETITIVE_VERIFIER_YUKICODER_CHUNK_SIZE",
            1024 * 1024,
        )

        logger.info("download:yukicoder testcase.zip: %s", url)

        started_at = time.perf_counter()
        last_reported_at = started_at
        total = 0

        with requests.get(
            url,
            headers=headers,
            allow_redirects=True,
            stream=True,
            timeout=(connect_timeout, read_timeout),
        ) as resp:
            resp.raise_for_status()

            content_length_text = resp.headers.get("content-length")
            content_length = (
                int(content_length_text)
                if content_length_text is not None and content_length_text.isdigit()
                else None
            )

            logger.info(
                "download:yukicoder response: status=%s, content-type=%s, content-length=%s",
                resp.status_code,
                resp.headers.get("content-type"),
                content_length_text,
            )

            with destination.open("wb") as out:
                for chunk in resp.iter_content(chunk_size=chunk_size):
                    if not chunk:
                        continue

                    out.write(chunk)
                    total += len(chunk)

                    now = time.perf_counter()
                    elapsed = now - started_at

                    if download_timeout > 0 and elapsed > download_timeout:
                        raise TimeoutError(
                            f"download timeout: {url}: "
                            f"{total} bytes in {download_timeout:.0f} sec"
                        )

                    if (
                        report_interval > 0
                        and now - last_reported_at >= report_interval
                    ):
                        mib = total / 1024 / 1024
                        speed = mib / elapsed if elapsed > 0 else 0.0

                        if content_length:
                            percent = total * 100.0 / content_length
                            logger.info(
                                "download:yukicoder progress: %.1f / %.1f MiB, %.1f%%, %.2f MiB/s",
                                mib,
                                content_length / 1024 / 1024,
                                percent,
                                speed,
                            )
                        else:
                            logger.info(
                                "download:yukicoder progress: %.1f MiB, %.2f MiB/s",
                                mib,
                                speed,
                            )

                        last_reported_at = now

        elapsed = time.perf_counter() - started_at
        mib = total / 1024 / 1024
        speed = mib / elapsed if elapsed > 0 else 0.0
        logger.info(
            "download:yukicoder done: %.1f MiB, %.2f MiB/s, %.1f sec",
            mib,
            speed,
            elapsed,
        )

    def _extract_testcase_zip(
        self,
        zip_path: pathlib.Path,
        destination: pathlib.Path,
    ) -> int:
        inputs: dict[str, zipfile.ZipInfo] = {}
        outputs: dict[str, zipfile.ZipInfo] = {}

        with zipfile.ZipFile(zip_path) as fh:
            for info in fh.infolist():
                filename = info.filename
                if filename.endswith("/"):
                    continue

                path = pathlib.PurePosixPath(filename)
                self._validate_zip_member_path(path)

                if filename.startswith("test_in/"):
                    inputs[path.stem] = info
                elif filename.startswith("test_out/"):
                    outputs[path.stem] = info

            common_names = sorted(inputs.keys() & outputs.keys())

            if len(inputs) != len(common_names) or len(outputs) != len(common_names):
                logger.warning("dangling output case")

            if not common_names:
                logger.warning("no cases found")
                return 0

            destination.mkdir(parents=True, exist_ok=False)

            for name in common_names:
                input_path = destination / _name_to_filename(name, "in")
                output_path = destination / _name_to_filename(name, "out")

                with fh.open(inputs[name]) as src, input_path.open("wb") as out:
                    shutil.copyfileobj(src, out)

                with fh.open(outputs[name]) as src, output_path.open("wb") as out:
                    shutil.copyfileobj(src, out)

        return len(common_names)

    @staticmethod
    def _validate_zip_member_path(path: pathlib.PurePosixPath) -> None:
        if path.is_absolute() or ".." in path.parts:
            raise RuntimeError(f"unsafe path in testcase.zip: {path}")

    @property
    def url(self) -> str:
        return f"https://yukicoder.me/problems/{self.problem}"

    @classmethod
    def from_url(cls, url: str) -> Optional["YukicoderProblem"]:
        # example: https://yukicoder.me/problems/no/499
        # example: http://yukicoder.me/problems/1476
        result = urllib.parse.urlparse(url)
        dirname, basename = posixpath.split(_normpath(result.path))
        if result.scheme in ("", "http", "https") and result.netloc == "yukicoder.me":
            try:
                n = int(basename)
            except ValueError:
                pass
            else:
                if dirname == "/problems/no":
                    return cls(problem_no=n)
                if dirname == "/problems":
                    return cls(problem_id=n)
        return None

    def _is_logged_in(self, *, headers: dict[str, str] | None = None) -> bool:
        url = "https://yukicoder.me"
        resp = requests.get(url, headers=headers, allow_redirects=True, timeout=10)
        resp.raise_for_status()
        return "login-btn" not in str(resp.content)


class AOJProblem(_BaseProblem):
    def __init__(self, *, problem_id: str):
        self.problem_id = problem_id

    def _download_cases(self) -> Iterable[TestCaseData]:
        return AOJProblem.download_cases(self.problem_id)

    @staticmethod
    def download_cases(problem_id: str) -> Iterable[TestCaseData]:
        # get header
        # reference: http://developers.u-aizu.ac.jp/api?key=judgedat%2Ftestcases%2F%7BproblemId%7D%2Fheader_GET
        url = f"https://judgedat.u-aizu.ac.jp/testcases/{problem_id}/header"
        resp = requests.get(url, allow_redirects=True, timeout=10)
        resp.raise_for_status()
        header_res = json.loads(resp.text)

        # get testcases via the official API
        for header in header_res["headers"]:
            # NOTE: the endpoints are not same to http://developers.u-aizu.ac.jp/api?key=judgedat%2Ftestcases%2F%7BproblemId%7D%2F%7Bserial%7D_GET since the json API often says "..... (terminated because of the limitation)"
            # NOTE: even when using https://judgedat.u-aizu.ac.jp/testcases/PROBLEM_ID/SERIAL, there is the 1G limit (see https://twitter.com/beet_aizu/status/1194947611100188672)
            serial = header["serial"]
            url = f"https://judgedat.u-aizu.ac.jp/testcases/{problem_id}/{serial}"

            resp_in = requests.get(url + "/in", allow_redirects=True, timeout=10)
            resp_in.raise_for_status()
            resp_out = requests.get(url + "/out", allow_redirects=True, timeout=10)
            resp_out.raise_for_status()

            yield TestCaseData(
                header["name"],
                resp_in.content,
                resp_out.content,
            )

    @property
    def url(self) -> str:
        return f"http://judge.u-aizu.ac.jp/onlinejudge/description.jsp?id={self.problem_id}"

    @classmethod
    def from_url(cls, url: str) -> Optional["AOJProblem"]:
        result = urllib.parse.urlparse(url)

        # example: http://judge.u-aizu.ac.jp/onlinejudge/description.jsp?id=1169
        # example: http://judge.u-aizu.ac.jp/onlinejudge/description.jsp?id=DSL_1_A&lang=jp
        querystring = urllib.parse.parse_qs(result.query)
        if (
            result.scheme in ("", "http", "https")
            and result.netloc == "judge.u-aizu.ac.jp"
            and _normpath(result.path) == "/onlinejudge/description.jsp"
            and querystring.get("id")
            and len(querystring["id"]) == 1
        ):
            (n,) = querystring["id"]
            return cls(problem_id=n)

        # example: https://onlinejudge.u-aizu.ac.jp/challenges/sources/JAG/Prelim/2881
        # example: https://onlinejudge.u-aizu.ac.jp/courses/library/4/CGL/3/CGL_3_B
        m = re.match(
            r"^/(challenges|courses)/(sources|library/\d+|lesson/\d+)/(\w+)/(\w+)/(\w+)$",
            _normpath(result.path),
        )
        if (
            result.scheme in ("", "http", "https")
            and result.netloc == "onlinejudge.u-aizu.ac.jp"
            and m
        ):
            n = m.group(5)
            return cls(problem_id=n)

        # example: https://onlinejudge.u-aizu.ac.jp/problems/0423
        # example: https://onlinejudge.u-aizu.ac.jp/problems/CGL_3_B
        m = re.match(r"^/problems/(\w+)$", _normpath(result.path))
        if (
            result.scheme in ("", "http", "https")
            and result.netloc == "onlinejudge.u-aizu.ac.jp"
            and m
        ):
            n = m.group(1)
            return cls(problem_id=n)

        return None


class AOJArenaProblem(_BaseProblem):
    def __init__(self, *, arena_id: str, alphabet: str):
        if len(alphabet) != 1 or not alphabet.isupper():
            raise ValueError(arena_id, alphabet)
        self.arena_id = arena_id
        self.alphabet = alphabet

        self._problem_id: str | None = None

    def get_problem_id(self) -> str:
        if self._problem_id is None:
            url = f"https://judgeapi.u-aizu.ac.jp/arenas/{self.arena_id}/problems"
            resp = requests.get(url, allow_redirects=True, timeout=10)
            resp.raise_for_status()
            problems = json.loads(resp.text)
            for problem in problems:
                if problem["id"] == self.alphabet:
                    p = problem["problemId"]
                    logger.debug("problem: %s", p)
                    self._problem_id = p
                    return p
            raise ValueError("Problem is not found.")
        return self._problem_id

    def _download_cases(self) -> Iterable[TestCaseData]:
        return AOJProblem.download_cases(self.get_problem_id())

    @property
    def url(self) -> str:
        return f"https://onlinejudge.u-aizu.ac.jp/services/room.html#{self.arena_id}/problems/{self.alphabet}"

    @classmethod
    def from_url(cls, url: str) -> Optional["AOJArenaProblem"]:
        # example: https://onlinejudge.u-aizu.ac.jp/services/room.html#RitsCamp19Day2/problems/A
        result = urllib.parse.urlparse(url)
        if (
            result.scheme in ("", "http", "https")
            and result.netloc == "onlinejudge.u-aizu.ac.jp"
            and _normpath(result.path) == "/services/room.html"
        ):
            fragment = result.fragment.split("/")
            if len(fragment) == 3 and fragment[1] == "problems":  # noqa: PLR2004
                return cls(arena_id=fragment[0], alphabet=fragment[2].upper())
        return None


@dataclass
class LocalProblem(TestCaseProvider):
    path: pathlib.Path

    def download_system_cases(self) -> Iterable[TestCaseData] | bool:
        return bool(any(self.iter_system_cases()))

    def iter_system_cases(self) -> Iterable[TestCaseFile]:
        return iter_testcases(directory=self.path, recursive=True)


def _normpath(path: str) -> str:
    """A wrapper of posixpath.normpath.

    posixpath.normpath doesn't collapse a leading duplicated slashes.
    """
    path = posixpath.normpath(path)
    if path.startswith("//"):
        path = "/" + path.lstrip("/")
    return path


def _subclasses_recursive(cls: type[object]) -> Iterable[type[Problem]]:
    for ch in cls.__subclasses__():
        if issubclass(ch, Problem):
            yield ch
            yield from _subclasses_recursive(ch)


def problem_from_url(url: str) -> Problem | None:
    for ch in set(_subclasses_recursive(Problem)):
        if (problem := ch.from_url(url)) is not None:
            return problem
    return None


_InputOutput = TypeVar("_InputOutput")


def enumerate_input_outputs(
    inputs: dict[str, _InputOutput],
    outputs: dict[str, _InputOutput],
) -> Iterator[tuple[str, _InputOutput, _InputOutput]]:
    common_keys = inputs.keys() & outputs.keys()
    if len(inputs) != len(common_keys) or len(outputs) != len(common_keys):
        logger.warning("dangling output case")

    if len(common_keys) == 0:
        logger.warning("no cases found")

    for key in sorted(common_keys):
        yield (key, inputs[key], outputs[key])


def merge_testcase_files(
    inputs: dict[str, pathlib.Path],
    outputs: dict[str, pathlib.Path],
) -> Iterator[TestCaseFile]:
    for name, i, o in enumerate_input_outputs(inputs, outputs):
        yield TestCaseFile(name=name, input_path=i, output_path=o)


def _casename(path: pathlib.Path, *, directory: pathlib.Path) -> str:
    return path.relative_to(directory).with_suffix("").as_posix()


def iter_testcases(
    *, directory: pathlib.Path, recursive: bool = False
) -> Iterator[TestCaseFile]:
    inputs: dict[str, pathlib.Path] = {}
    outputs: dict[str, pathlib.Path] = {}
    pre = "**/" if recursive else ""

    for path in directory.glob(pre + "*.in"):
        if path.is_file():
            inputs[_casename(path, directory=directory)] = path
    for path in directory.glob(pre + "*.out"):
        if path.is_file():
            outputs[_casename(path, directory=directory)] = path

    return merge_testcase_files(inputs, outputs)


def _name_to_filename(name: str, ext: str):
    return pathlib.Path(name).with_suffix(f".{ext}").name


def save_testcases(samples: Iterable[TestCaseData], *, directory: pathlib.Path):
    for sample in samples:
        for data, ext in [(sample.input_data, "in"), (sample.output_data, "out")]:
            path = directory / _name_to_filename(sample.name, ext)

            if path.exists():
                logger.error("Failed to download since file already exists: %s", path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            logger.debug("saved to: %s", path)
