import enum
import pathlib
import re
from typing import Literal, TypeAlias

_NATURAL_SORT_RE = re.compile(r"\d+|\D+")


class PathSortOrder(str, enum.Enum):
    lexicographic = "lexicographic"
    natural = "natural"


_SortToken: TypeAlias = tuple[Literal[0], str] | tuple[Literal[1], int]
_PrimarySortKey: TypeAlias = tuple[_SortToken, ...]
_SortKey: TypeAlias = tuple[_PrimarySortKey, str]


def normalize_path_sort_order(order: PathSortOrder | None) -> PathSortOrder:
    return order or PathSortOrder.lexicographic


def path_sort_key_text(value: str, order: PathSortOrder | None) -> _SortKey:
    order = normalize_path_sort_order(order)

    if order == PathSortOrder.lexicographic:
        return (((0, value.casefold()),), value)  # (casefold, raw)

    tokens: list[_SortToken] = []
    for token in _NATURAL_SORT_RE.findall(value):
        if token.isdecimal():
            tokens.append((1, int(token)))
        else:
            tokens.append((0, token.casefold()))

    # tie-break
    return (tuple(tokens), value)


def path_sort_key_path(path: pathlib.Path, order: PathSortOrder | None) -> _SortKey:
    return path_sort_key_text(path.as_posix(), order)
