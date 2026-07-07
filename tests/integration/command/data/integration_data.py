import pathlib
import shutil
from typing import Any

import pytest

from ..types import ConfigDirSetter, FilePaths


class IntegrationData:
    required_commands: tuple[str, ...] = ()
    config_dir_path: pathlib.Path
    targets_path: pathlib.Path
    file_paths: FilePaths

    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        set_config_dir: ConfigDirSetter,
        file_paths: FilePaths,
    ) -> None:
        self.config_dir_path = set_config_dir(self.config_dir_name())
        self.file_paths = file_paths
        self.targets_path = file_paths.root / self.input_name()
        monkeypatch.chdir(self.targets_path)

    @classmethod
    def input_name(cls) -> str:
        return cls.__name__

    @classmethod
    def config_dir_name(cls) -> str:
        return cls.__name__

    @property
    def config_path(self) -> str | None:
        return None

    @property
    def include_path(self) -> list[str] | None:
        return None

    @property
    def exclude_path(self) -> list[str] | None:
        return None

    def assert_oj_resolve(self): ...

    @classmethod
    def missing_commands(cls) -> tuple[str, ...]:
        return tuple(
            command
            for command in cls.required_commands
            if shutil.which(command) is None
        )

    @classmethod
    def environment_skip_reason(cls) -> str | None:
        if missing_commands := cls.missing_commands():
            return f"{cls.__name__} requires commands: {', '.join(missing_commands)}"
        return None

    def skip_if_environment_unavailable(self) -> None:
        if reason := type(self).environment_skip_reason():
            pytest.skip(reason)

    def check_environment(self) -> bool:
        return type(self).environment_skip_reason() is None

    def expected_verify_json(self) -> dict[str, Any]:
        raise NotImplementedError

    def expected_verify_result(self) -> dict[str, Any]:
        raise NotImplementedError
