from typing import Literal

from pydantic import Field

from competitive_verifier.models import ShellCommand, ShellCommandLike

from .base import OjVerifyUserDefinedConfig
from .user_defined import UserDefinedLanguage


class OjVerifyRubyConfig(OjVerifyUserDefinedConfig):
    execute: ShellCommandLike = Field(
        default_factory=lambda: ShellCommand(command=["ruby", "{basedir}/{path}"]),
    )


class RubyLanguage(UserDefinedLanguage[Literal["rb"], OjVerifyRubyConfig]):
    extension: Literal["rb"] = "rb"
    config: OjVerifyRubyConfig = Field(default_factory=OjVerifyRubyConfig)
