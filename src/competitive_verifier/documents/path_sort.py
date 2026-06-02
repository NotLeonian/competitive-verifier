import pathlib
import re
from typing import Literal, TypeAlias

PathSortOrder: TypeAlias = Literal["lexicographic", "natural"]

_TOKEN_RE = re.compile(r"\d+|\D+")
_SortToken: TypeAlias = tuple[int, str | int]
_SortKey: TypeAlias = tuple[tuple[_SortToken, ...], str]


def sort_key_text(value: str, order: PathSortOrder) -> _SortKey:
    folded = value.casefold()

    if order == "lexicographic":
        # equivalent to `str.casefold(...)`
        return (((0, folded),), "")

    if order == "natural":
        tokens: list[_SortToken] = []
        for token in _TOKEN_RE.findall(value):
            if token.isdecimal():
                tokens.append((1, int(token)))
            else:
                tokens.append((0, token.casefold()))

        # tie-break
        return (tuple(tokens), folded)

    raise ValueError(f"unknown path sort order: {order}")


def sort_key_path(path: pathlib.Path, order: PathSortOrder) -> _SortKey:
    return sort_key_text(path.as_posix(), order)
