import enum
import pathlib
from typing import TYPE_CHECKING, TypeAlias, cast

from natsort import natsort_keygen, ns

if TYPE_CHECKING:
    from collections.abc import Callable


class PathSortOrder(str, enum.Enum):
    lexicographic = "lexicographic"
    natural = "natural"


_NaturalPrimaryKey: TypeAlias = tuple[object, ...]
_NaturalSortKey: TypeAlias = tuple[_NaturalPrimaryKey, str]
_LexicographicSortKey: TypeAlias = tuple[str]
_PathSortKey: TypeAlias = _NaturalSortKey | _LexicographicSortKey

_NATURAL_SORT_KEY = cast(
    "Callable[[str], _NaturalPrimaryKey]",
    natsort_keygen(alg=ns.INT | ns.IGNORECASE),
)


def normalize_path_sort_order(order: PathSortOrder | None) -> PathSortOrder:
    return order or PathSortOrder.lexicographic


def is_natural_path_sort(order: PathSortOrder | None) -> bool:
    return normalize_path_sort_order(order) == PathSortOrder.natural


def path_sort_key_text(value: str, order: PathSortOrder | None) -> _PathSortKey:
    if not is_natural_path_sort(order):
        return (value,)

    return (_NATURAL_SORT_KEY(value), value)


def path_sort_key_path(
    path: pathlib.PurePath,
    order: PathSortOrder | None,
) -> _PathSortKey:
    return path_sort_key_text(path.as_posix(), order)
