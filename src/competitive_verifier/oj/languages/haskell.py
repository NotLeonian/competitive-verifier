from typing import Literal

from pydantic import Field

from competitive_verifier.models import ShellCommand, ShellCommandLike

from .base import OjVerifyUserDefinedConfig
from .user_defined import UserDefinedLanguage


class OjVerifyHaskellConfig(OjVerifyUserDefinedConfig):
    execute: ShellCommandLike = Field(
        default_factory=lambda: ShellCommand(
            command=["runghc", "{basedir}/{path}"],
        ),
    )


class HaskellLanguage(UserDefinedLanguage[Literal["hs"], OjVerifyHaskellConfig]):
    extension: Literal["hs"] = "hs"
    config: OjVerifyHaskellConfig = Field(default_factory=OjVerifyHaskellConfig)
