from __future__ import annotations

import importlib.resources
from typing import TYPE_CHECKING, Protocol, cast

if TYPE_CHECKING:
    import pathlib
    from collections.abc import Iterable, Iterator

_DOC_USAGE_PATH = "doc_usage.txt"


class TraversableResource(Protocol):
    @property
    def name(self) -> str: ...

    def iterdir(self) -> Iterable[TraversableResource]: ...

    def is_dir(self) -> bool: ...

    def is_file(self) -> bool: ...

    def read_bytes(self) -> bytes: ...

    def read_text(self, encoding: str | None = None) -> str: ...

    def __truediv__(self, child: str) -> TraversableResource: ...


_ROOT = cast("TraversableResource", importlib.resources.files(cast("str", __package__)))


def doc_usage(
    *,
    markdown_dir_path: pathlib.Path,
    repo_name: str,
    sample_repo_name: str,
) -> str:
    template = _ROOT / _DOC_USAGE_PATH
    return (
        template.read_text(encoding="utf-8")
        .replace("{{{{{markdown_dir_path}}}}}", markdown_dir_path.as_posix())
        .replace("{{{{{repository}}}}}", repo_name)
        .replace("{{{{{sample_repository}}}}}", sample_repo_name)
    )


def _walk_files(
    root: TraversableResource,
    prefix: str = "",
) -> Iterator[tuple[str, TraversableResource]]:
    for child in root.iterdir():
        rel = f"{prefix}{child.name}"
        if child.is_file():
            yield rel, child
        elif child.is_dir():
            yield from _walk_files(child, f"{rel}/")


def jekyll_files() -> dict[str, bytes]:
    root = _ROOT / "jekyll"
    return {path: resource.read_bytes() for path, resource in _walk_files(root)}


def jekyll_theme_override_files(theme_name: str) -> dict[str, bytes]:
    root = _ROOT / "jekyll_theme_overrides" / theme_name

    if not root.is_dir():
        return {}

    return {path: resource.read_bytes() for path, resource in _walk_files(root)}
