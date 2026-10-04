import os
import pathlib
import sys
from typing import Any

import pytest
from pytest_mock import MockerFixture

from competitive_verifier.config import COMPETITIVE_VERIFY_CONFIG_PATH
from competitive_verifier.models import (
    CommandVerification,
    ResultStatus,
    VerificationInput,
)
from competitive_verifier.oj.languages import VerificationConfig
from competitive_verifier.oj.languages.python import PythonLanguageEnvironment
from competitive_verifier.oj.languages.rust import RustLanguageEnvironment
from competitive_verifier.oj.resolver import OjResolver

pytestmark = pytest.mark.allow_mkdir


@pytest.mark.parametrize("extension", ["cpp", "java", "go", "py", "rs", "custom"])
def test_resolved_commands_survive_checkout_relocation(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
    extension: str,
):
    producer = tmp_path / "producer"
    consumer = tmp_path / "consumer"
    (producer / "checks").mkdir(parents=True)
    monkeypatch.chdir(producer)
    monkeypatch.setenv(COMPETITIVE_VERIFY_CONFIG_PATH, ".competitive-verifier")
    monkeypatch.delenv("PYTHONPATH", raising=False)
    monkeypatch.setenv(
        "PATH",
        str(pathlib.Path(sys.executable).parent),
        prepend=os.pathsep,
    )
    source = pathlib.Path("checks") / f"check.{extension}"
    source.write_text("from support import value\nassert value == 42\n")
    pathlib.Path("support.py").write_text("value = 42\n")
    config = VerificationConfig.model_validate(
        {
            "languages": {
                "cpp": {"environments": [{"CXX": "g++", "CXXFLAGS": []}]},
                "custom": {
                    "execute": {
                        "command": ["python", "{basedir}/{path}"],
                        "env": {"PYTHONPATH": "{basedir}"},
                    }
                },
            }
        }
    )
    language = config.get_dict()[f".{extension}"]
    dependencies = mocker.patch.object(
        type(language), "list_dependencies", return_value=[source]
    )
    mocker.patch.object(
        type(language), "list_attributes", return_value={"STANDALONE": ""}
    )
    mocker.patch("competitive_verifier.oj.resolver.git.ls_files", return_value=[source])

    def cargo_metadata(cwd: pathlib.Path) -> dict[str, Any]:
        assert cwd == (producer / source).parent
        return {
            "packages": [
                {
                    "targets": [
                        {
                            "src_path": str(producer / source),
                            "name": "check",
                            "kind": ["bin"],
                        }
                    ]
                }
            ],
            "target_directory": str(producer / "target"),
        }

    mocker.patch(
        "competitive_verifier.oj.languages.rust._cargo_metadata",
        side_effect=cargo_metadata,
    )
    resolved = OjResolver(include=["."], exclude=[], config=config).resolve(
        bundle=False
    )
    dependencies.assert_called_once_with(source, basedir=producer)
    artifact = resolved.model_dump_json()
    assert "producer" not in artifact
    pathlib.Path("verify_files.json").write_text(artifact)
    monkeypatch.chdir(tmp_path)
    producer.rename(consumer)
    monkeypatch.chdir(consumer)
    relocated = VerificationInput.parse_file_relative("verify_files.json")
    verification = relocated.files[source].verification_list[0]
    assert isinstance(verification, CommandVerification)
    if extension in {"py", "custom"}:
        assert verification.run_compile_command()
        assert verification.run() == ResultStatus.SUCCESS


def test_python_commands_preserve_configured_pythonpath(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("PYTHONPATH", "external-packages")
    environment = PythonLanguageEnvironment()
    for command in [environment.get_compile_command, environment.get_execute_command]:
        result = command(
            pathlib.Path("check.py"),
            basedir=pathlib.Path(),
            tempdir=pathlib.Path("temp"),
        )
        assert result.env == {"PYTHONPATH": "." + os.pathsep + "external-packages"}


def test_rust_commands_preserve_external_target_directory(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
):
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    monkeypatch.chdir(checkout)
    source = pathlib.Path("src/main.rs")
    target_directory = tmp_path / "external-target"
    mocker.patch(
        "competitive_verifier.oj.languages.rust._cargo_metadata",
        return_value={
            "packages": [
                {
                    "targets": [
                        {
                            "src_path": str(checkout / source),
                            "name": "check",
                            "kind": ["bin"],
                        }
                    ]
                }
            ],
            "target_directory": str(target_directory),
        },
    )
    command = RustLanguageEnvironment().get_execute_command(
        source, basedir=pathlib.Path(), tempdir=pathlib.Path("temp")
    )
    assert pathlib.Path(command) == target_directory / "release" / "check"
