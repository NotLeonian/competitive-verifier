import pytest

from competitive_verifier.documents.builder import (
    remote_theme_slug,
    uses_minimal_theme,
)
from competitive_verifier.documents.config import ConfigYaml


@pytest.mark.parametrize(
    ("remote_theme", "expected"),
    [
        ("pages-themes/minimal", "pages-themes/minimal"),
        ("pages-themes/minimal@v0.2.0", "pages-themes/minimal"),
        ("pages-themes/minimal@latest", "pages-themes/minimal"),
        ("https://github.com/pages-themes/minimal", "pages-themes/minimal"),
        ("https://github.com/pages-themes/minimal.git", "pages-themes/minimal"),
        ("https://github.com/pages-themes/minimal@v0.2.0", "pages-themes/minimal"),
        ("pages-themes/modernist@v0.2.0", "pages-themes/modernist"),
    ],
)
def test_remote_theme_slug(remote_theme: str, expected: str) -> None:
    assert remote_theme_slug(remote_theme) == expected


@pytest.mark.parametrize(
    "remote_theme",
    [
        "pages-themes/minimal",
        "pages-themes/minimal@v0.2.0",
        "pages-themes/minimal@latest",
        "https://github.com/pages-themes/minimal",
        "https://github.com/pages-themes/minimal.git",
    ],
)
def test_uses_minimal_theme_for_minimal_remote_theme(remote_theme: str) -> None:
    assert uses_minimal_theme(
        ConfigYaml(
            theme="jekyll-theme-modernist",
            remote_theme=remote_theme,
        ),
    )


@pytest.mark.parametrize(
    "remote_theme",
    [
        "pages-themes/modernist",
        "pages-themes/modernist@v0.2.0",
        "pages-themes/cayman",
        "benbalter/retlab",
        "../my-local-theme",
    ],
)
def test_does_not_use_minimal_override_for_non_minimal_remote_theme(
    remote_theme: str,
) -> None:
    # ConfigYaml.theme defaults to jekyll-theme-minimal, but a non-minimal
    # remote_theme should still win.
    assert not uses_minimal_theme(ConfigYaml(remote_theme=remote_theme))


def test_uses_minimal_theme_for_default_gem_theme() -> None:
    assert uses_minimal_theme(ConfigYaml())


def test_does_not_use_minimal_theme_for_other_gem_theme() -> None:
    assert not uses_minimal_theme(ConfigYaml(theme="jekyll-theme-modernist"))
